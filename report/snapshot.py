"""
Snapshot emitter.

Architectural note, and the main thing worth taking from the reference site:
separate DATA from PRESENTATION. Python writes a small JSON file; a static
HTML/JS page reads it and renders.

Why this beats generating complete HTML in Python:

  1. The daily commit is a small JSON diff instead of a 100KB HTML blob, so git
     history stays readable and the repo stays small.
  2. Git history of the JSON becomes a free, immutable time series of every
     signal you ever published. That IS the ledger, versioned by someone else's
     infrastructure.
  3. The page can be edited and reviewed once, independently of the pipeline.
  4. Anything static can be hosted free on GitHub Pages.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from engine.ranking import (
    score_sectors, classify_zone, sector_drivers, top_picks, sector_picks,
    oscillator_slope,
)

SITE = Path(__file__).resolve().parent.parent / "docs"
(SITE / "data").mkdir(parents=True, exist_ok=True)


def _clean(o):
    """
    JSON cannot hold NaN, numpy scalars, or Timestamps. Convert or drop.

    Order matters: bool must be tested before int, because bool subclasses int
    in Python and would otherwise serialise as 0/1.
    """
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if o is None or isinstance(o, str):
        return o
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if (np.isnan(o) or np.isinf(o)) else round(float(o), 6)
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.strftime("%Y-%m-%d")
    if isinstance(o, np.ndarray):
        return [_clean(v) for v in o.tolist()]
    try:
        if pd.isna(o):
            return None
    except (TypeError, ValueError):
        pass
    return str(o)


def emit_snapshot(
    market: str,
    payload: dict,
    name_states: dict[str, pd.DataFrame],
    group_states: dict[str, dict],
    config: dict,
    data_through: pd.Timestamp,
    coverage_warnings: list[str] | None = None,
    technical: pd.DataFrame | None = None,
    quality: pd.DataFrame | None = None,
    quality_mode: str = "trend + fundamentals + forward estimates",
) -> Path:
    """
    payload        {theme: {"result", "basket", "gate"}} from the cycle engine
    name_states    {theme: DataFrame from signals.name_state}
    group_states   {theme: dict from signals.group_state}
    """
    now = datetime.now(timezone.utc)

    themes_out = {}
    for theme, blob in payload.items():
        res = blob["result"]
        osc = res["oscillator"].dropna()
        cycles = res["cycles"]
        closed = [c for c in cycles if c["exit_reason"] != "open"]
        basket = blob.get("basket")
        gate = blob.get("gate")
        ns = name_states.get(theme)

        # Oscillator history, weekly sampled -- daily would bloat the JSON for
        # no visual gain at chart resolution.
        hist = osc.resample("W-FRI").last().dropna()
        series = [{"d": d.strftime("%Y-%m-%d"), "v": round(float(v), 1)}
                  for d, v in hist.items()]

        members = []
        if ns is not None:
            for tk, r in ns.iterrows():
                rec = {"ticker": tk, **{k: r.get(k) for k in (
                    "close", "ret_1d", "ret_1w", "ret_1m", "ret_3m", "ret_6m", "rs_1m",
                    "dist_20d", "dist_50d", "dist_200d",
                    "rising_20d", "rising_50d", "rising_200d",
                    "atr_extension", "rel_volume", "setup")}}
                if gate is not None and tk in gate.index:
                    g = gate.loc[tk]
                    rec["gate_passed"] = bool(g["passed"])
                    rec["gate_reasons"] = str(g["reasons"])
                    rec["revenue_growth"] = g.get("revenue_growth")
                    rec["roce"] = g.get("roce")
                if basket is not None and tk in basket.index:
                    rec["in_basket"] = True
                    rec["basket_rank"] = int(basket.loc[tk, "basket_rank"])
                    rec["tier"] = basket.loc[tk, "tier"]
                    rec["weight"] = float(basket.loc[tk, "weight"])
                members.append(rec)
            members.sort(key=lambda r: (-(r.get("rs_1m") or -9)))

        themes_out[theme] = {
            "oscillator_now": round(float(osc.iloc[-1]), 1) if len(osc) else None,
            "in_cycle": basket is not None and not basket.empty,
            "entry_date": (cycles[-1]["entry_date"].strftime("%Y-%m-%d")
                           if cycles and cycles[-1]["exit_reason"] == "open" else None),
            "oscillator_series": series,
            "signals": [{"date": r["date"].strftime("%Y-%m-%d"),
                         "signal": r["signal"],
                         "oscillator": round(float(r["oscillator"]), 1)}
                        for _, r in res["signals"].iterrows()],
            "group": group_states.get(theme, {}),
            "cycles": [{
                "entry": c["entry_date"].strftime("%Y-%m-%d"),
                "exit": c["exit_date"].strftime("%Y-%m-%d"),
                "reason": c["exit_reason"],
                "days": c["held_days"],
                "ret": round(c["basket_return"], 4),
                "dd": round(c["max_drawdown"], 4),
            } for c in closed],
            "members": members,
        }

    # ---- enriched member frames, used by both the per-sector and the
    # cross-sector pick lists so the two rank identically
    members_enriched = {}
    for name, ns in name_states.items():
        if ns is None or ns.empty:
            continue
        e = ns.copy()
        gate = payload[name].get("gate")
        basket = payload[name].get("basket")
        if gate is not None:
            e["gate_passed"] = [bool(gate.loc[i, "passed"]) if i in gate.index else None
                                for i in e.index]
            e["gate_reasons"] = [str(gate.loc[i, "reasons"]) if i in gate.index else ""
                                 for i in e.index]
            for c in ("revenue_growth", "roce"):
                e[c] = [gate.loc[i, c] if i in gate.index and c in gate.columns else None
                        for i in e.index]
        if basket is not None and not basket.empty:
            e["in_basket"] = [i in basket.index for i in e.index]
        # Quality screen results. Names outside the screened pool get no
        # quality_passed value, which makes them ineligible below.
        if quality is not None and not quality.empty:
            for col in quality.columns:
                e[col] = [quality.loc[i, col] if i in quality.index else None
                          for i in e.index]
        members_enriched[name] = e
    any_gate = any(payload[n].get("gate") is not None for n in payload)
    use_quality = quality is not None and not quality.empty

    # ---- sector league table and zones
    rank_input = {
        name: {
            "oscillator": payload[name]["result"]["oscillator"],
            "group": group_states.get(name, {}),
            "in_cycle": themes_out[name]["in_cycle"],
        }
        for name in themes_out
    }
    ss = score_sectors(rank_input)

    sectors_out = []
    if not ss.empty:
        zs = ss.apply(classify_zone, axis=1)
        ss["zone"] = [z[0] for z in zs]
        ss["reason"] = [z[1] for z in zs]
        for name, r in ss.iterrows():
            themes_out[name]["score"] = r["score"]
            themes_out[name]["rank"] = int(r["rank"])
            themes_out[name]["zone"] = r["zone"]
            themes_out[name]["reason"] = r["reason"]
            themes_out[name]["osc_slope"] = (None if pd.isna(r["osc_slope"])
                                             else round(float(r["osc_slope"]), 1))
            sp = sector_picks(name, members_enriched.get(name), r,
                               n=5, require_gate=any_gate,
                               require_quality=use_quality)
            sp_list = ([{"ticker": tk, **{k: v for k, v in row.items()}}
                        for tk, row in sp.iterrows()] if not sp.empty else [])
            themes_out[name]["picks"] = sp_list
            themes_out[name]["pick_pool"] = (
                {"candidates": int(sp["candidates"].iloc[0]),
                 "excluded": int(sp["excluded"].iloc[0])} if not sp.empty else None)

            sectors_out.append({
                "picks": sp_list,
                "pick_pool": themes_out[name]["pick_pool"],
                "theme": name, "rank": int(r["rank"]), "score": r["score"],
                "zone": r["zone"], "reason": r["reason"],
                "in_cycle": bool(r["in_cycle"]),
                "oscillator": r.get("oscillator"),
                "osc_slope": r.get("osc_slope"),
                "breadth_50d": r.get("breadth_50d"),
                "members": r.get("members"),
                "rs_1m": r.get("rs_1m"), "rs_3m": r.get("rs_3m"),
                "ret_1m": r.get("ret_1m"), "ret_3m": r.get("ret_3m"),
                "dist_50d": r.get("dist_50d"), "rising_50d": r.get("rising_50d"),
                "dist_200d": r.get("dist_200d"), "rising_200d": r.get("rising_200d"),
            })

    # ---- top 20 drivers per theme
    for name, ns in name_states.items():
        if name not in themes_out or ns is None or ns.empty:
            continue
        enriched = ns.copy()
        gate = payload[name].get("gate")
        basket = payload[name].get("basket")
        if gate is not None:
            enriched["gate_passed"] = [
                bool(gate.loc[i, "passed"]) if i in gate.index else None
                for i in enriched.index]
        if basket is not None and not basket.empty:
            enriched["in_basket"] = [i in basket.index for i in enriched.index]
        dr = sector_drivers(enriched, n=20)
        themes_out[name]["drivers"] = [
            {"driver_rank": int(r["driver_rank"]), "ticker": tk,
             **{k: r.get(k) for k in (
                 "close", "ret_1w", "ret_1m", "ret_3m", "ret_6m", "rs_1m",
                 "dist_50d", "rising_50d", "atr_extension", "rel_volume",
                 "setup", "contribution_1m", "driver_score")}}
            for tk, r in dr.iterrows()]

    # ---- top picks across every theme
    tp = top_picks(ss, members_enriched, n=5, require_gate=any_gate,
                   require_quality=use_quality) if not ss.empty \
        else pd.DataFrame()
    picks_out = ([{"ticker": tk, **{k: r.get(k) for k in tp.columns}}
                  for tk, r in tp.iterrows()] if not tp.empty else [])

    # ---- technical buy setups
    tech_out = []
    if technical is not None and not technical.empty:
        for tk, r in technical.iterrows():
            tech_out.append({"ticker": tk, **{k: r.get(k) for k in technical.columns}})
    tech_by_ticker = {t_["ticker"]: t_ for t_ in tech_out}
    # Tag picks that also have a technical entry -- the two layers agreeing is
    # worth surfacing, though neither is conditional on the other.
    for lst in [picks_out] + [s["picks"] for s in sectors_out]:
        for pk in lst:
            sig = tech_by_ticker.get(pk["ticker"])
            if not sig:
                continue
            pk["tech_signal"] = sig["signal"]
            pk["tech_quality"] = sig["quality"]
            pk["tech_entry"] = sig["entry"]
            pk["tech_stop"] = sig["stop"]
            pk["tech_target"] = sig["target"]
            pk["tech_rr"] = sig["reward_risk"]
            pk["tech_risk_pct"] = sig["risk_pct"]
    # ---- setup scans, pooled across themes
    pull, rally = [], []
    for theme, t in themes_out.items():
        for m in t["members"]:
            row = {"theme": theme, **{k: m.get(k) for k in (
                "ticker", "close", "ret_1d", "ret_1w", "rs_1m",
                "dist_20d", "dist_50d", "rel_volume", "atr_extension")}}
            if m.get("setup") == "pullback":
                pull.append(row)
            elif m.get("setup") == "rally_weak":
                rally.append(row)
    pull.sort(key=lambda r: -(r.get("rs_1m") or -9))
    rally.sort(key=lambda r: (r.get("rs_1m") or 9))

    live = [t for t, v in themes_out.items() if v["in_cycle"]]
    all_closed = [c for v in themes_out.values() for c in v["cycles"]]
    wins = sum(1 for c in all_closed if c["ret"] > 0)
    by_zone = {z: [s["theme"] for s in sectors_out if s["zone"] == z]
               for z in ("leading", "building", "neutral", "avoid")}

    doc = {
        "market": market,
        "generated_utc": now.strftime("%Y-%m-%d %H:%M UTC"),
        # ISO form so the page can render it in the viewer's own timezone and
        # compute how long ago the run happened.
        "generated_iso": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_through": pd.Timestamp(data_through).strftime("%Y-%m-%d"),
        "config": config,
        "warnings": coverage_warnings or [],
        "gate_applied": any_gate,
        "summary": {
            "themes": len(themes_out),
            "themes_in_cycle": len(live),
            "live_themes": live,
            "cycles_closed": len(all_closed),
            "hit_rate": round(wins / len(all_closed), 3) if all_closed else None,
            "avg_cycle_return": (round(sum(c["ret"] for c in all_closed) / len(all_closed), 4)
                                 if all_closed else None),
            "worst_drawdown": round(min((c["dd"] for c in all_closed), default=0.0), 4),
            "zones": {k: len(v) for k, v in by_zone.items()},
            "technical_signals": len(tech_out),
            "screened": int(len(quality)) if quality is not None else 0,
            "quality_passed": (int(quality["quality_passed"].sum())
                               if quality is not None and len(quality) else 0),
        },
        "quality_mode": quality_mode,
        "sectors": sectors_out,
        "technical": tech_out,
        "zones": by_zone,
        "picks": picks_out,
        "scans": {"pullback": pull[:40], "rally_weak": rally[:40]},
        "themes": themes_out,
    }

    path = SITE / "data" / f"{market}.json"
    path.write_text(json.dumps(_clean(doc), indent=1))
    print(f"  {path}  ({path.stat().st_size // 1024} KB)")
    return path

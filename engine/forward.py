"""
Forward expectations.

Everything else in this system describes the past. This module adds what the
market expects next, from free consensus data (Yahoo Finance via yfinance).

WHAT IS WEIGHTED, AND WHY IN THIS ORDER

  Estimate revisions (heaviest)  How the consensus EPS estimate has CHANGED over
      the last 30 and 90 days. The level of an estimate is already known to the
      market and largely priced in; the change is new information. Upward
      revisions tend to persist for a while, because analysts adjust gradually
      after new information arrives. This is the most useful forward signal
      available for free.

  Revision breadth   How many analysts raised versus cut in the last 30 days.
      A +3% average revision driven by one analyst is weaker than one driven by
      eight.

  Forward growth     Next year's estimated EPS against this year's.

  Valuation sanity   Forward P/E against trailing P/E. A forward P/E well below
      trailing means earnings are expected to grow into the price.

  Target upside (lightest, capped)   Analyst price targets have a poor track
      record and are biased upward. Included at a low weight, capped at +30%,
      and ignored with fewer than 3 analysts.

  Buy/sell ratings are displayed but never scored. Sell-side ratings skew so
      heavily toward "buy" that they carry little information.

THE HARD REJECT -- "something might be wrong"
  A name is rejected outright, however strong its chart, when:
    - this year's or next year's EPS estimate has been cut more than 5% in 90 days
    - analysts cutting outnumber those raising by 3+ in 30 days, with a net cut
    - next year's EPS is expected to be negative
    - forward EPS growth is below -15%
  Falling estimates are one of the clearest early signs that a business is
  deteriorating, and often show up before the price does.

MISSING DATA
  Many Indian mid-caps have little or no analyst coverage on Yahoo. Missing
  data is reported as missing -- it neither penalises nor rewards a name.
  `coverage` states how much the forward score can be trusted.

Data is cached for 7 days (estimates move more often than annual financials).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parent.parent / "data" / "forward"
CACHE.mkdir(parents=True, exist_ok=True)

REJECT = {
    "max_cut_90d": -0.05,        # estimate cut beyond 5% in 90 days
    "net_down_revisions": 3,     # cutters outnumber raisers by this many
    "min_fwd_growth": -0.15,
}


# ---------------------------------------------------------------- parsing

def _lower_frame(df) -> pd.DataFrame | None:
    """yfinance has changed these tables' orientation and casing across
    versions. Normalise to: index = period ('0y', '+1y'...), lowercase columns."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    d = df.copy()
    d.index = [str(i).strip().lower() for i in d.index]
    d.columns = [str(c).strip().lower() for c in d.columns]
    periods = {"0q", "+1q", "0y", "+1y"}
    if not (set(d.index) & periods) and (set(d.columns) & periods):
        d = d.T
    return d


def _cell(df, row, *cols):
    if df is None or row not in df.index:
        return None
    for c in cols:
        c = c.lower()
        if c in df.columns:
            v = df.loc[row, c]
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            if np.isfinite(v):
                return v
    return None


def _pct_change(now, before):
    if now is None or before is None or before == 0:
        return None
    return (now - before) / abs(before)


def parse_forward(info: dict, eps_trend, eps_revisions, price: float | None) -> dict:
    """Turn raw yfinance objects into the handful of numbers this system uses."""
    info = info or {}
    et = _lower_frame(eps_trend)
    er = _lower_frame(eps_revisions)

    cy_now = _cell(et, "0y", "current")
    ny_now = _cell(et, "+1y", "current")

    out = {
        "eps_cy": cy_now,
        "eps_ny": ny_now,
        "rev_30d_cy": _pct_change(cy_now, _cell(et, "0y", "30daysago")),
        "rev_90d_cy": _pct_change(cy_now, _cell(et, "0y", "90daysago")),
        "rev_30d_ny": _pct_change(ny_now, _cell(et, "+1y", "30daysago")),
        "rev_90d_ny": _pct_change(ny_now, _cell(et, "+1y", "90daysago")),
        "up_30d": _cell(er, "0y", "uplast30days"),
        "down_30d": _cell(er, "0y", "downlast30days"),
    }

    fwd_g = None
    if cy_now is not None and ny_now is not None and cy_now > 0:
        fwd_g = ny_now / cy_now - 1.0
    if fwd_g is None:
        fe, te = info.get("forwardEps"), info.get("trailingEps")
        try:
            if fe is not None and te not in (None, 0) and float(te) > 0:
                fwd_g = float(fe) / float(te) - 1.0
        except (TypeError, ValueError):
            pass
    out["fwd_growth"] = fwd_g

    def num(k):
        try:
            v = float(info.get(k))
            return v if np.isfinite(v) else None
        except (TypeError, ValueError):
            return None

    out["fwd_pe"] = num("forwardPE")
    out["trailing_pe"] = num("trailingPE")
    out["forward_eps"] = num("forwardEps")
    out["n_analysts"] = num("numberOfAnalystOpinions")
    out["rec_mean"] = num("recommendationMean")          # displayed, never scored
    tgt = num("targetMeanPrice")
    px = price if price else num("currentPrice")
    out["target_mean"] = tgt
    out["target_upside"] = (tgt / px - 1.0) if (tgt and px) else None
    return out


# ---------------------------------------------------------------- fetch

def fetch_forward(ticker: str, price: float | None = None, refresh_days: int = 7) -> dict:
    path = CACHE / f"{ticker.replace('.', '_').replace('^', '_')}.json"
    if path.exists() and (time.time() - path.stat().st_mtime) / 86400 < refresh_days:
        try:
            return json.loads(path.read_text())
        except Exception:
            pass

    rec = {"ticker": ticker, "fetched": time.strftime("%Y-%m-%d"), "ok": False}
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)

        def safe(attr):
            try:
                return getattr(t, attr)
            except Exception:
                return None

        info = safe("info") or {}
        parsed = parse_forward(info, safe("eps_trend"), safe("eps_revisions"), price)
        rec.update(parsed)
        rec["ok"] = any(parsed.get(k) is not None
                        for k in ("rev_30d_cy", "fwd_growth", "fwd_pe", "n_analysts"))
    except Exception as e:
        rec["error"] = str(e)[:200]

    path.write_text(json.dumps(rec, indent=1, default=lambda o: None))
    return rec


# ---------------------------------------------------------------- scoring

def _lin(v, lo, mid, hi):
    """Map v onto 0..100: lo -> 0, mid -> 50, hi -> 100, clipped."""
    if v is None or not np.isfinite(v):
        return None
    if v <= mid:
        return float(np.clip((v - lo) / (mid - lo) * 50, 0, 50))
    return float(np.clip(50 + (v - mid) / (hi - mid) * 50, 50, 100))


def coverage_level(n) -> str:
    if n is None or n <= 0:
        return "none"
    if n >= 5:
        return "high"
    if n >= 2:
        return "medium"
    return "low"


def forward_score(f: dict) -> dict:
    """
    0-100 composite, re-weighted over whatever components are available.
    Returns the score, which components contributed, and any hard-reject reason.
    """
    comps = {}

    revs = [x for x in (f.get("rev_30d_cy"), f.get("rev_90d_cy"),
                        f.get("rev_30d_ny"), f.get("rev_90d_ny")) if x is not None]
    if revs:
        comps["revisions"] = (_lin(float(np.mean(revs)), -0.10, 0.0, 0.10), 0.45)

    up, dn = f.get("up_30d"), f.get("down_30d")
    if up is not None and dn is not None and (up + dn) > 0:
        comps["breadth"] = ((up - dn) / (up + dn) * 50 + 50, 0.15)

    g = f.get("fwd_growth")
    if g is not None:
        comps["growth"] = (_lin(g, -0.10, 0.05, 0.25), 0.20)

    fpe, tpe = f.get("fwd_pe"), f.get("trailing_pe")
    if fpe and tpe and fpe > 0 and tpe > 0:
        val = _lin(tpe / fpe - 1.0, -0.20, 0.0, 0.30)     # fwd below trailing = growth
        if fpe > 80:
            val = min(val, 25.0)                             # priced for perfection
        comps["valuation"] = (val, 0.10)

    n = f.get("n_analysts") or 0
    tu = f.get("target_upside")
    if tu is not None and n >= 3:
        comps["target"] = (_lin(min(tu, 0.30), -0.10, 0.05, 0.30), 0.10)

    comps = {k: v for k, v in comps.items() if v[0] is not None}
    score = None
    if comps:
        w = sum(v[1] for v in comps.values())
        score = round(sum(v[0] * v[1] for v in comps.values()) / w, 1)

    # ---- hard rejects
    reject = None
    cuts = [x for x in (f.get("rev_90d_cy"), f.get("rev_90d_ny")) if x is not None]
    if cuts and min(cuts) <= REJECT["max_cut_90d"]:
        reject = f"EPS estimates cut {abs(min(cuts)):.0%} in 90 days"
    elif (up is not None and dn is not None and dn - up >= REJECT["net_down_revisions"]
          and (f.get("rev_30d_cy") or 0) < 0):
        reject = f"{int(dn)} analysts cut estimates vs {int(up)} raised in 30 days"
    elif f.get("eps_ny") is not None and f["eps_ny"] < 0:
        reject = "a loss is expected next year"
    elif g is not None and g <= REJECT["min_fwd_growth"]:
        reject = f"earnings expected to fall {g:.0%} next year"

    return {
        "fwd_score": score,
        "fwd_components": sorted(comps.keys()),
        "fwd_reject": reject,
        "coverage": coverage_level(f.get("n_analysts")),
    }


def describe(f: dict) -> str:
    """One short human line for the dashboard."""
    parts = []
    r = f.get("rev_30d_cy") if f.get("rev_30d_cy") is not None else f.get("rev_90d_cy")
    if r is not None:
        parts.append(f"EPS estimate {'up' if r >= 0 else 'down'} {abs(r):.1%}"
                     f" ({'30' if f.get('rev_30d_cy') is not None else '90'}d)")
    if f.get("fwd_growth") is not None:
        parts.append(f"next-year EPS {f['fwd_growth']:+.0%}")
    if f.get("fwd_pe"):
        parts.append(f"fwd P/E {f['fwd_pe']:.0f}")
    n = f.get("n_analysts")
    if n:
        parts.append(f"{int(n)} analyst{'s' if n != 1 else ''}")
    return " · ".join(parts) if parts else "no analyst coverage"

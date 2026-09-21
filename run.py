#!/usr/bin/env python3
"""
One command. Run this and nothing else.

    python run.py

It decides whether prices need refreshing, processes both markets, writes both
pages, starts a local server and opens your browser.

    python run.py --fresh        force a re-download even if the cache looks current
    python run.py --offline      never download; fail if there is no cache
    python run.py --market india just one market
    python run.py --no-serve     produce files only, do not open a browser
    python run.py --no-gate      skip the fundamental screen (faster)

The refresh decision: prices are re-downloaded when there is no cache at all,
or when the newest cached date is more than one weekend behind today. Otherwise
the cache is reused, which makes re-runs instant.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from engine.cycle import run_theme, rank_members, build_basket
from engine.gate import apply_gate
from engine.signals import name_state, group_state
from engine.technical import scan as technical_scan
from engine.quality import evaluate as quality_evaluate, trend_health
from engine.forward import fetch_forward
from engine.ranking import _name_strength
from fetch.prices import update_cache, load_ohlcv, coverage_report, DATA
from report.dashboard import build_dashboard
from report.snapshot import emit_snapshot
from themes import INDIA_THEMES, US_THEMES, all_tickers

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "ledger"
LEDGER.mkdir(exist_ok=True)

BENCHMARK = {"india": "^NSEI", "us": "SPY"}

CONFIG = {
    "entry_zone": 25.0,
    "exit_zone": 75.0,
    "confirm_days": 3,
    "ma_window": 200,
    "smooth": 10,
    "percentile_window": 750,
    "n_tier1": 4,
    "n_tier2": 4,
    "tier1_weight": 0.70,
    "stop_loss": 0.20,
    "max_hold_days": 252,
    "gate_pool": 20,
    "quality_pool_per_sector": 12,     # candidates screened per sector
    "require_forward_coverage": False, # True = only names with analyst coverage
    "stale_after_days": 4,
    # How often the published site is expected to refresh. The page uses this
    # to decide when data is stale, so a weekly site isn't flagged red every
    # weekend. Keep it in step with the cron line in .github/workflows/update.yml.
    "refresh_every_days": 7,
}


# ---------------------------------------------------------------- refresh logic

def needs_refresh(market: str, stale_days: int) -> tuple[bool, str]:
    """Decide whether to download, and say why. Never silently re-fetch."""
    path = DATA / f"{market}_close.parquet"
    if not path.exists():
        return True, "no cache yet"
    try:
        last = pd.read_parquet(path, columns=None).index[-1]
    except Exception as e:
        return True, f"cache unreadable ({e})"
    age = (datetime.now() - last.to_pydatetime()).days
    if age > stale_days:
        return True, f"cache ends {last.date()} ({age} days old)"
    return False, f"cache current through {last.date()}"


# ---------------------------------------------------------------- one market

def process_market(market: str, args) -> dict | None:
    themes = INDIA_THEMES if market == "india" else US_THEMES
    tickers = all_tickers(themes)
    bench = BENCHMARK[market]

    print(f"\n{'=' * 62}\n{market.upper()}  |  {len(themes)} themes, {len(tickers)} tickers\n{'=' * 62}")

    # ---- 1. prices
    refresh, why = needs_refresh(market, CONFIG["stale_after_days"])
    if args.fresh:
        refresh, why = True, "--fresh requested"
    if args.offline:
        if refresh and "no cache" in why:
            print(f"  [1/8] offline mode and {why} -- cannot continue for {market}")
            return None
        refresh, why = False, why + " (offline mode)"

    if refresh:
        print(f"  [1/8] Downloading prices: {why}")
        print("        first run takes 3-5 minutes; later runs are incremental")
        try:
            ohlcv = update_cache(market, tickers + [bench], start=args.start)
        except Exception as e:
            print(f"        download failed: {e}")
            try:
                ohlcv = load_ohlcv(market)
                print("        falling back to the existing cache")
            except FileNotFoundError:
                print(f"        no cache to fall back on -- skipping {market}")
                return None
    else:
        print(f"  [1/8] Using cache: {why}")
        try:
            ohlcv = load_ohlcv(market)
        except FileNotFoundError:
            print(f"        no cache found -- skipping {market}")
            return None

    prices = ohlcv["Close"]
    benchmark = prices[bench].dropna() if bench in prices.columns else None
    if benchmark is None:
        print(f"        WARNING: benchmark {bench} missing; relative strength unavailable")

    warnings_out = []
    cov = coverage_report(prices)
    bad = cov[~cov["usable"]]
    if len(bad):
        msg = f"{len(bad)} tickers lack history: " + ", ".join(bad['ticker'].tolist()[:8])
        print(f"        {msg}")
        warnings_out.append(msg)
    stale = cov[(cov["stale_days"].fillna(0) > 10) & cov["usable"]]
    if len(stale):
        msg = f"{len(stale)} tickers stale >10d: " + ", ".join(stale['ticker'].tolist()[:8])
        print(f"        {msg}")
        warnings_out.append(msg)

    # ---- 2. cycle engine
    print("  [2/8] Cycle engine")
    results = {}
    for name, members in themes.items():
        cols = [t for t in members if t in prices.columns]
        px = prices[cols].dropna(how="all")
        px = px.loc[:, px.notna().sum() >= 500]
        if px.shape[1] < 8:
            print(f"        {name:24s} skipped ({px.shape[1]} usable names)")
            continue
        res = run_theme(
            px, name,
            osc_kwargs={k: CONFIG[k] for k in ("ma_window", "smooth", "percentile_window")},
            signal_kwargs={k: CONFIG[k] for k in ("entry_zone", "exit_zone", "confirm_days")},
            basket_kwargs={k: CONFIG[k] for k in ("n_tier1", "n_tier2", "tier1_weight")},
            stop_loss=CONFIG["stop_loss"], max_hold_days=CONFIG["max_hold_days"],
        )
        o = res["oscillator"].dropna()
        live = bool(res["cycles"]) and res["cycles"][-1]["exit_reason"] == "open"
        print(f"        {name:24s} osc={o.iloc[-1]:5.1f}  {px.shape[1]:3d} names  "
              f"{'IN CYCLE' if live else ''}")
        results[name] = {"res": res, "px": px, "live": live}

    if not results:
        print("        no usable themes -- check your ticker list")
        return None

    # ---- 3. rank + gate
    print("  [3/8] Ranking and screening")
    payload = {}
    for name, blob in results.items():
        res, px = blob["res"], blob["px"]
        basket, gate_df = None, None
        if blob["live"]:
            entry = res["cycles"][-1]["entry_date"]
            ranked = rank_members(px, entry)
            if args.no_gate:
                basket = build_basket(ranked, n_tier1=CONFIG["n_tier1"],
                                      n_tier2=CONFIG["n_tier2"],
                                      tier1_weight=CONFIG["tier1_weight"])
            else:
                pool = ranked.head(CONFIG["gate_pool"]).index.tolist()
                th = {"min_roce": 0.10, "min_market_cap": 2e9} if market == "us" else {}
                gate_df = apply_gate(pool, thresholds=th, verbose=False)
                n_ok = int(gate_df["passed"].sum())
                print(f"        {name:24s} gate {n_ok}/{len(pool)} passed")
                basket = build_basket(ranked, eligible=set(gate_df[gate_df["passed"]].index),
                                      n_tier1=CONFIG["n_tier1"], n_tier2=CONFIG["n_tier2"],
                                      tier1_weight=CONFIG["tier1_weight"])
        payload[name] = {"result": res, "basket": basket, "gate": gate_df}

    # ---- 4. technical state
    print("  [4/8] Technical state")
    nstates, gstates = {}, {}
    for name, blob in results.items():
        cols = list(blob["px"].columns)
        sub = lambda f: (ohlcv[f].reindex(columns=cols) if f in ohlcv else None)
        try:
            nstates[name] = name_state(blob["px"], high=sub("High"), low=sub("Low"),
                                       volume=sub("Volume"), benchmark=benchmark)
        except ValueError as e:
            print(f"        {name}: {e}")
            continue
        gstates[name] = group_state(blob["px"], cols, benchmark=benchmark)

    # ---- 4b. technical setups across every ticker in every theme
    print("  [5/8] Technical setups")
    theme_map, rs_map = {}, {}
    for name, ns in nstates.items():
        for tk in ns.index:
            theme_map.setdefault(tk, name)
            v = ns.loc[tk].get("rs_1m")
            if v is not None and not pd.isna(v):
                rs_map[tk] = float(v)
    tech = technical_scan(
        prices, sorted(theme_map.keys()),
        high=ohlcv.get("High"), low=ohlcv.get("Low"), volume=ohlcv.get("Volume"),
        rs_map=rs_map, theme_map=theme_map,
    )
    if len(tech):
        counts = tech["signal"].value_counts().to_dict()
        print(f"        {len(tech)} setups from {len(theme_map)} names: {counts}")
    else:
        print(f"        no setups met the quality floor today")

    # ---- 5b. quality screen: every name that could be recommended is checked
    # for trend health, fundamentals and forward expectations. Anything not
    # screened is ineligible -- "not checked" is never treated as a pass.
    print("  [6/8] Quality screen")
    pool: set[str] = set()
    n_trend_ok = 0
    for name, ns in nstates.items():
        ok = [tk for tk in ns.index
              if tk in prices.columns and trend_health(prices[tk])["ok"]]
        n_trend_ok += len(ok)
        if not ok:
            continue
        strength = _name_strength(ns.loc[ok])
        if strength is None:
            continue
        pool.update(strength.sort_values(ascending=False)
                    .head(CONFIG["quality_pool_per_sector"]).index)
    if len(tech):
        pool.update(tech.index)
    pool = sorted(pool)
    print(f"        {n_trend_ok} of {len(theme_map)} names are not falling; "
          f"screening {len(pool)} candidates")

    fund_df = forward_map = None
    if not args.no_gate:
        th = {"min_roce": 0.10, "min_market_cap": 2e9} if market == "us" else {}
        fund_df = apply_gate(pool, thresholds=th, verbose=False)
        forward_map = {}
        for i, tk in enumerate(pool, 1):
            px = float(prices[tk].dropna().iloc[-1]) if tk in prices.columns else None
            forward_map[tk] = fetch_forward(tk, price=px)
            if i % 25 == 0:
                print(f"        forward estimates {i}/{len(pool)}")
        covered = sum(1 for f in forward_map.values() if f.get("n_analysts"))
        print(f"        fundamentals: {int(fund_df['passed'].sum())}/{len(fund_df)} pass; "
              f"analyst coverage on {covered}/{len(pool)}")
    else:
        print("        --no-gate: screening on price structure only "
              "(no fundamentals, no forward estimates)")

    quality = quality_evaluate(
        pool, prices, fundamentals=fund_df, forward=forward_map,
        require_forward_coverage=CONFIG["require_forward_coverage"])
    n_pass = int(quality["quality_passed"].sum()) if len(quality) else 0
    print(f"        {n_pass}/{len(pool)} pass every quality check")

    if len(tech) and len(quality):
        before = len(tech)
        keep = [tk for tk in tech.index
                if tk in quality.index and bool(quality.loc[tk, "quality_passed"])]
        tech = tech.loc[keep]
        for col in ("fwd_score", "fwd_summary", "coverage", "drawdown_from_high"):
            if col in quality.columns:
                tech[col] = [quality.loc[tk, col] for tk in tech.index]
        print(f"        technical setups: {len(tech)} of {before} survive the quality gate")

    # ---- 5. ledger
    print("  [7/8] Ledger")
    stamp = datetime.now().strftime("%Y-%m-%d")
    rec = {"date": stamp, "market": market, "config": CONFIG, "themes": {}}
    for name, blob in payload.items():
        b = blob["basket"]
        rec["themes"][name] = {
            "oscillator": float(blob["result"]["oscillator"].dropna().iloc[-1]),
            "in_cycle": b is not None and not b.empty,
            "basket": ([{"ticker": t, "rank": int(r["basket_rank"]), "tier": r["tier"],
                         "weight": round(float(r["weight"]), 4)}
                        for t, r in b.iterrows()] if b is not None and not b.empty else []),
        }
    rec["technical"] = ([{"ticker": tk, "signal": r["signal"], "quality": r["quality"],
                          "entry": r["entry"], "stop": r["stop"], "target": r["target"],
                          "reward_risk": r["reward_risk"]}
                         for tk, r in tech.iterrows()] if len(tech) else [])
    (LEDGER / f"{stamp}-{market}.json").write_text(json.dumps(rec, indent=1, default=str))

    # ---- 6. outputs
    print("  [8/8] Writing pages")
    build_dashboard(payload, filename=f"dashboard-{market}-{stamp}.html",
                    entry_zone=CONFIG["entry_zone"], exit_zone=CONFIG["exit_zone"])
    emit_snapshot(market, payload, nstates, gstates, CONFIG,
                  data_through=prices.index[-1], coverage_warnings=warnings_out,
                  technical=tech, quality=quality,
                  quality_mode="price structure only" if args.no_gate
                  else "trend + fundamentals + forward estimates")
    return {"market": market, "themes": len(payload)}


# ---------------------------------------------------------------- summary

def print_headline(markets: list[str]) -> None:
    """Show the answer in the terminal too, so you see it before the browser opens."""
    for m in markets:
        f = ROOT / "docs" / "data" / f"{m}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        print(f"\n  {m.upper()}  (data through {d['data_through']})")

        for zone, label in (("leading", "LEADING"), ("building", "BUILDING"), ("avoid", "AVOID")):
            names = d.get("zones", {}).get(zone, [])
            if names:
                print(f"    {label:9s} {', '.join(names)}")

        picks = d.get("picks", [])
        if picks:
            print("    TOP PICKS")
            for p in picks:
                tech = f"  [{p['tech_signal']} {p['tech_rr']:.1f}R]" if p.get("tech_signal") else ""
                print(f"      {p['pick_rank']}. {p['ticker']:16s} {p['theme'][:20]:20s} "
                      f"score {p['pick_score']:5.1f}  {p.get('setup', '')}{tech}")

        tech = d.get("technical", [])
        if tech:
            print(f"    TECHNICAL SETUPS ({len(tech)} total, best 5)")
            for s in tech[:5]:
                print(f"      {s['ticker']:16s} {s['signal']:9s} q{s['quality']:5.1f}  "
                      f"entry {s['entry']:9.2f}  stop {s['stop']:9.2f}  "
                      f"target {s['target']:9.2f}  risk {s['risk_pct'] * 100:4.1f}%  "
                      f"{s['reward_risk']:.1f}R")


def serve(port: int, open_browser: bool) -> None:
    import http.server
    import socketserver
    from functools import partial

    docs = ROOT / "docs"

    class H(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Cache-Control", "no-store, max-age=0")
            super().end_headers()

        def log_message(self, *a):
            pass

    for p in range(port, port + 10):
        try:
            with socketserver.TCPServer(("127.0.0.1", p), partial(H, directory=str(docs))) as s:
                url = f"http://localhost:{p}"
                print(f"\n  Dashboard: {url}")
                print("  Ctrl+C to stop.\n")
                if open_browser:
                    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
                s.serve_forever()
            return
        except OSError:
            continue
        except KeyboardInterrupt:
            print("\nStopped.")
            return
    print(f"  No free port between {port} and {port + 9}.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the whole pipeline and open the dashboard.")
    ap.add_argument("--market", choices=["india", "us", "both"], default="both")
    ap.add_argument("--fresh", action="store_true", help="force re-download")
    ap.add_argument("--offline", action="store_true", help="never download")
    ap.add_argument("--no-gate", action="store_true", help="skip the fundamental screen")
    ap.add_argument("--no-serve", action="store_true", help="write files only")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--max-age", type=int, default=None, metavar="DAYS",
                    help="refresh when the cache is older than this many days "
                         "(default 4; the scheduled job passes 1 for a daily site)")
    args = ap.parse_args()

    if args.max_age is not None:
        CONFIG["stale_after_days"] = args.max_age

    markets = ["india", "us"] if args.market == "both" else [args.market]
    t0 = time.time()
    done = []
    for m in markets:
        try:
            if process_market(m, args):
                done.append(m)
        except Exception as e:
            print(f"\n  {m.upper()} failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc(limit=3)

    if not done:
        print("\nNothing was produced. Check the messages above.")
        sys.exit(1)

    print(f"\n{'=' * 62}\nDone in {time.time() - t0:.0f}s — {', '.join(m.upper() for m in done)}")
    print_headline(done)
    print("\n  This is a screen for your own research, not advice.")

    if not args.no_serve:
        serve(args.port, open_browser=True)
    else:
        print(f"\n  Files written. View with: python run.py --offline\n")


if __name__ == "__main__":
    main()

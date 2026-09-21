"""
Quality gate.

One gate every recommendation must pass -- Top 5, per-sector picks, and
technical setups alike. Three independent tests, all required:

  1. Trend health  -- the stock is not falling
  2. Fundamentals  -- the business is growing, profitable, not over-levered
  3. Forward       -- analysts are not cutting their estimates

A name that has never been screened is NOT eligible. Earlier versions treated
"not checked" as "passed", which meant most recommendations had never had their
financials looked at. That default is reversed here.

ON "NOT FALLING"
A stock that has been falling usually falls for a reason the chart shows before
the news does. Buying it is a bet that you know better than everyone selling.
This gate refuses that bet.

It distinguishes two things that look alike on a one-week chart:
  - a PULLBACK: a short dip inside an intact long-term uptrend. Allowed.
  - a DECLINE: the long-term trend itself has rolled over. Refused.
The 200-day average and the distance from the 52-week high are what separate
them; a one-week return cannot.

The cost of this rule, stated plainly: it will miss genuine turnarounds. Every
recovery starts from a falling stock, and this gate only lets a name in once the
recovery is well established. That is a deliberate trade -- fewer, later,
safer entries.

On share price: a low *nominal* price (a Rs 40 share versus a Rs 4,000 share)
says nothing about quality. Share count is arbitrary. What matters is market
capitalisation, which the fundamental gate already floors.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TREND = {
    "max_drawdown_from_high": 0.25,   # within 25% of the 52-week high
    "min_ret_6m": 0.0,                # positive over six months
    "min_ret_3m": -0.08,              # allow consolidation, not a breakdown
    "no_new_low_sessions": 126,       # no fresh 52-week low in six months
}


def trend_health(close: pd.Series, as_of: pd.Timestamp | None = None,
                 cfg: dict | None = None) -> dict:
    """Is this stock falling? Returns ok, the individual checks, and plain reasons."""
    c = {**TREND, **(cfg or {})}
    s = (close.loc[:as_of] if as_of is not None else close).dropna()
    if len(s) < 260:
        return {"ok": False, "checks": {}, "reasons": ["under a year of price history"]}

    px = float(s.iloc[-1])
    ma50 = s.rolling(50).mean()
    ma200 = s.rolling(200).mean()
    m50, m50_prev = float(ma50.iloc[-1]), float(ma50.iloc[-13])
    m200, m200_prev = float(ma200.iloc[-1]), float(ma200.iloc[-22])

    yr = s.iloc[-252:]
    hi52, lo52 = float(yr.max()), float(yr.min())
    days_since_low = len(yr) - 1 - int(np.argmin(yr.values))
    dd = px / hi52 - 1.0
    r3 = px / float(s.iloc[-64]) - 1.0
    r6 = px / float(s.iloc[-127]) - 1.0

    checks = {
        "above_rising_200d": px > m200 and m200 > m200_prev,
        "near_52w_high": dd >= -c["max_drawdown_from_high"],
        "positive_6m": r6 > c["min_ret_6m"],
        "no_breakdown_3m": r3 > c["min_ret_3m"],
        "no_recent_52w_low": days_since_low > c["no_new_low_sessions"],
        # A pullback may dip slightly under the 50-day, but only if the 50-day
        # itself is still rising. Under a falling 50-day is a decline.
        "holding_50d": px >= m50 or (px >= m50 * 0.96 and m50 > m50_prev),
    }

    words = {
        "above_rising_200d": ("below its 200-day average" if px <= m200
                              else "200-day average is falling"),
        "near_52w_high": f"{abs(dd):.0%} below its 52-week high",
        "positive_6m": f"down {abs(r6):.0%} over six months",
        "no_breakdown_3m": f"down {abs(r3):.0%} over three months",
        "no_recent_52w_low": f"made a 52-week low {days_since_low} sessions ago",
        "holding_50d": "lost its 50-day average",
    }
    reasons = [words[k] for k, ok in checks.items() if not ok]
    return {
        "ok": not reasons,
        "checks": checks,
        "reasons": reasons,
        "drawdown_from_high": round(dd, 4),
        "ret_6m": round(r6, 4),
        "days_since_52w_low": days_since_low,
    }


def evaluate(
    tickers: list[str],
    close: pd.DataFrame,
    fundamentals: pd.DataFrame | None = None,
    forward: dict[str, dict] | None = None,
    require_forward_coverage: bool = False,
) -> pd.DataFrame:
    """
    One row per ticker: passed / reasons, plus the fields the dashboard shows.

    fundamentals  output of gate.apply_gate (index=ticker), or None to skip
    forward       {ticker: parsed forward dict}, or None to skip
    """
    from engine.forward import forward_score, describe

    rows = []
    for tk in tickers:
        if tk not in close.columns:
            continue
        th = trend_health(close[tk])
        reasons = list(th["reasons"])
        row = {
            "ticker": tk,
            "trend_ok": th["ok"],
            "drawdown_from_high": th.get("drawdown_from_high"),
            "days_since_52w_low": th.get("days_since_52w_low"),
        }

        # ---- fundamentals
        if fundamentals is not None:
            if tk in fundamentals.index:
                g = fundamentals.loc[tk]
                row["fund_ok"] = bool(g["passed"])
                row["revenue_growth"] = g.get("revenue_growth")
                row["profit_growth"] = g.get("profit_growth")
                row["roce"] = g.get("roce")
                if not g["passed"]:
                    why = str(g.get("reasons") or "")
                    reasons.append("fundamentals: " + (
                        "financial data unavailable" if why == "no_data" else why))
            else:
                row["fund_ok"] = False
                reasons.append("fundamentals not screened")

        # ---- forward
        if forward is not None:
            f = forward.get(tk) or {}
            fs = forward_score(f) if f.get("ok") else {
                "fwd_score": None, "fwd_reject": None, "coverage": "none",
                "fwd_components": []}
            row.update({
                "fwd_score": fs["fwd_score"],
                "coverage": fs["coverage"],
                "fwd_summary": describe(f) if f else "no analyst coverage",
                "rev_30d_cy": f.get("rev_30d_cy"),
                "rev_90d_cy": f.get("rev_90d_cy"),
                "fwd_growth": f.get("fwd_growth"),
                "fwd_pe": f.get("fwd_pe"),
                "n_analysts": f.get("n_analysts"),
                "target_upside": f.get("target_upside"),
            })
            if fs["fwd_reject"]:
                reasons.append("forward: " + fs["fwd_reject"])
            if require_forward_coverage and fs["coverage"] == "none":
                reasons.append("forward: no analyst coverage")

        row["quality_passed"] = not reasons
        row["quality_reasons"] = "; ".join(reasons)
        rows.append(row)

    return pd.DataFrame(rows).set_index("ticker") if rows else pd.DataFrame()

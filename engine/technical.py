"""
Technical setup detection.

The `setup` label in signals.py describes a *state* ("this name is in a
pullback"). This module produces a *signal*: a named setup with an entry
reference, a stop, a target, and the resulting risk/reward. Without a stop, a
"buy signal" is just an opinion.

Four setups, each requiring independent conditions to agree. Confluence is the
whole point -- any single indicator is close to noise, and the value comes from
demanding that trend, structure, volatility and volume all say the same thing.

    breakout   Clears a genuine base on expanding volume
    pullback   Uptrend pulls back to a rising average and holds
    squeeze    Volatility contracted near the highs; expansion pending
    reclaim    Reclaims the 50-day after being below it (turnaround, weakest)

WHAT THIS IS NOT
These are entry mechanics, not predictions. Technical setups have modest hit
rates even when executed well -- a good breakout system might win 40-50% of the
time and make money only because the winners run further than the losers. That
arithmetic only works if you take the stop every time. A setup without a stop
taken is not this system.

Everything here uses data up to `as_of` only. No value at date t touches a row
after date t.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.signals import atr


# ---------------------------------------------------------------- trend filter

def trend_template(close: pd.Series, as_of: pd.Timestamp | None = None) -> dict:
    """
    An eight-point structural check, in the spirit of the widely used
    Minervini trend template. It is a *filter*, not a signal: it says the
    structure is sound enough to consider a long, nothing about timing.

    Each check is a plain, verifiable statement about moving averages and the
    52-week range. Nothing is fitted.
    """
    s = close.loc[:as_of] if as_of is not None else close
    s = s.dropna()
    if len(s) < 252:
        return {"checks": {}, "passed": 0, "total": 0, "ok": False,
                "reason": "needs 252 sessions of history"}

    px = float(s.iloc[-1])
    ma50 = float(s.rolling(50).mean().iloc[-1])
    ma150 = float(s.rolling(150).mean().iloc[-1])
    ma200 = float(s.rolling(200).mean().iloc[-1])
    ma200_1m_ago = float(s.rolling(200).mean().iloc[-22])

    hi52 = float(s.iloc[-252:].max())
    lo52 = float(s.iloc[-252:].min())

    checks = {
        "above_150_200": px > ma150 and px > ma200,
        "ma150_above_ma200": ma150 > ma200,
        "ma200_rising": ma200 > ma200_1m_ago,
        "ma50_above_others": ma50 > ma150 and ma50 > ma200,
        "above_ma50": px > ma50,
        "above_52w_low_30pct": px >= lo52 * 1.30,
        "within_25pct_of_high": px >= hi52 * 0.75,
        "not_at_52w_low": px > lo52 * 1.10,
    }
    passed = sum(checks.values())
    return {
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "ok": passed >= 7,          # allow one miss; demanding 8/8 is brittle
        "pct_from_52w_high": round(px / hi52 - 1.0, 4),
        "pct_above_52w_low": round(px / lo52 - 1.0, 4),
    }


# ---------------------------------------------------------------- base & squeeze

def find_base(
    close: pd.Series,
    high: pd.Series | None,
    low: pd.Series | None,
    as_of: pd.Timestamp | None = None,
    min_days: int = 15,
    max_days: int = 90,
) -> dict:
    """
    Find the most recent consolidation: a stretch where price stopped making
    progress and the range narrowed.

    Walks backwards from today looking for the longest window whose depth
    (high-to-low as a share of the high) stays under a ceiling. A tight, long
    base is a better setup than a deep, short one -- depth is the proxy for how
    much supply is overhead.
    """
    s = close.loc[:as_of].dropna() if as_of is not None else close.dropna()
    if len(s) < max_days + 5:
        return {"found": False}

    h = (high.loc[:as_of].dropna() if high is not None else s)
    l = (low.loc[:as_of].dropna() if low is not None else s)

    best = None
    for n in range(max_days, min_days - 1, -5):
        win_h = float(h.iloc[-n:].max())
        win_l = float(l.iloc[-n:].min())
        if win_h <= 0:
            continue
        depth = (win_h - win_l) / win_h
        # A base deeper than 35% is a downtrend, not a consolidation.
        if depth > 0.35:
            continue
        px = float(s.iloc[-1])
        pos = (px - win_l) / (win_h - win_l) if win_h > win_l else 0.5
        cand = {
            "found": True, "days": n,
            "high": round(win_h, 4), "low": round(win_l, 4),
            "depth": round(depth, 4),
            "position_in_base": round(pos, 3),   # 1.0 = at the top of the range
        }
        if best is None or (n > best["days"] and depth <= best["depth"] * 1.35):
            best = cand
    return best or {"found": False}


def squeeze_score(
    close: pd.Series,
    high: pd.Series | None,
    low: pd.Series | None,
    as_of: pd.Timestamp | None = None,
    window: int = 20,
    lookback: int = 120,
) -> float:
    """
    How contracted is volatility right now, as a percentile of its own recent
    history? 0 = tightest in `lookback` sessions, 100 = widest.

    Volatility clusters and mean-reverts: quiet periods are followed by active
    ones. A tight range near the highs is therefore a *pre*-move condition. It
    says nothing about direction -- which is why it is only ever combined with
    a trend filter here, never used alone.
    """
    s = close.loc[:as_of].dropna() if as_of is not None else close.dropna()
    if len(s) < lookback + window:
        return np.nan

    if high is not None and low is not None:
        h = high.loc[:as_of].reindex(s.index)
        l = low.loc[:as_of].reindex(s.index)
        rng = (h.rolling(window).max() - l.rolling(window).min()) / s
    else:
        rng = (s.rolling(window).max() - s.rolling(window).min()) / s

    r = rng.dropna()
    if len(r) < lookback:
        return np.nan
    win = r.iloc[-lookback:]
    return round(float((win <= win.iloc[-1]).mean() * 100), 1)


# ---------------------------------------------------------------- the detector

def detect_signal(
    ticker: str,
    close: pd.Series,
    high: pd.Series | None = None,
    low: pd.Series | None = None,
    volume: pd.Series | None = None,
    as_of: pd.Timestamp | None = None,
    rs_1m: float | None = None,
    min_rr: float = 2.0,
    max_risk_pct: float = 0.12,
    min_quality: float = 60.0,
    allow_reclaim: bool = False,
) -> dict | None:
    """
    Return a signal dict, or None if nothing qualifies.

    Every signal carries entry, stop, target and risk/reward. A setup whose stop
    would sit more than `max_risk_pct` away, or whose reward/risk is below
    `min_rr`, is rejected -- a good-looking chart at a bad price is not a trade.
    """
    s = close.loc[:as_of].dropna() if as_of is not None else close.dropna()
    if len(s) < 260:
        return None
    px = float(s.iloc[-1])
    if px <= 0:
        return None

    tt = trend_template(close, as_of)
    if not tt.get("checks"):
        return None

    # ATR for stop placement.
    if high is not None and low is not None:
        h = high.loc[:as_of].reindex(s.index)
        l = low.loc[:as_of].reindex(s.index)
        a = atr(h.to_frame("x"), l.to_frame("x"), s.to_frame("x")).iloc[-1, 0]
    else:
        a = float(s.diff().abs().rolling(14).mean().iloc[-1])
    if not np.isfinite(a) or a <= 0:
        return None

    ma20 = float(s.rolling(20).mean().iloc[-1])
    ma50 = float(s.rolling(50).mean().iloc[-1])
    ma50_prev = float(s.rolling(50).mean().iloc[-13])
    ma200 = float(s.rolling(200).mean().iloc[-1])
    ma20_prev = float(s.rolling(20).mean().iloc[-6])
    rising50, rising20 = ma50 > ma50_prev, ma20 > ma20_prev

    ret_1w = float(px / s.iloc[-6] - 1.0) if len(s) > 6 else np.nan
    ext = (px - ma20) / a

    # Volume: today's, and the pullback's, against a 50-day average.
    rvol = pullback_rvol = np.nan
    if volume is not None:
        v = volume.loc[:as_of].reindex(s.index).dropna()
        if len(v) > 50 and v.iloc[-50:].mean() > 0:
            avg = float(v.iloc[-50:].mean())
            rvol = float(v.iloc[-1] / avg)
            pullback_rvol = float(v.iloc[-5:].mean() / avg)

    base = find_base(close, high, low, as_of)
    sq = squeeze_score(close, high, low, as_of)

    prior_high = float(s.iloc[-61:-1].max())
    swing_low = float((low.loc[:as_of].iloc[-21:].min()) if low is not None
                      else s.iloc[-21:].min())

    kind = None
    reasons: list[str] = []

    # ---- 1. Breakout: clears a real base, volume expanding.
    if (tt["passed"] >= 6 and base.get("found")
            and px >= prior_high * 0.995
            and base["depth"] <= 0.30
            and (np.isnan(rvol) or rvol >= 1.3)
            and ext < 3.5):
        kind = "breakout"
        reasons.append(f"clears a {base['days']}-day base ({base['depth']:.0%} deep)")
        if not np.isnan(rvol):
            reasons.append(f"volume {rvol:.1f}x average")

    # ---- 2. Squeeze: tight near the highs, expansion pending.
    # Checked before pullback deliberately: when volatility sits at an extreme
    # low, that is the more informative description of the chart even if the
    # week happens to be slightly down.
    elif (tt["passed"] >= 6 and not np.isnan(sq) and sq <= 15
            and base.get("found") and base.get("position_in_base", 0) >= 0.55
            and rising50 and ext < 2.0):
        kind = "squeeze"
        reasons.append(f"tightest 20-day range in 120 sessions (percentile {sq:.0f})")
        reasons.append(f"holding the top of a {base['days']}-day base")

    # ---- 3. Pullback: uptrend comes back toward a rising average and holds.
    # A normal pullback runs 2-3 ATR below the 20-day and often undercuts the
    # 50-day intraday, so the gates allow that. What it may not do is lose the
    # 200-day or break the 50-day by a meaningful margin -- that is a failed
    # trend, not a pullback.
    elif (tt["passed"] >= 6 and rising50
            and not np.isnan(ret_1w) and ret_1w < 0
            and px > ma200
            and px >= ma50 * 0.96
            and -3.5 <= ext <= 1.0):
        kind = "pullback"
        near = "20-day" if abs(px - ma20) < abs(px - ma50) else "50-day"
        reasons.append(f"pulled back to a rising {near} in an intact uptrend")
        if not np.isnan(pullback_rvol) and pullback_rvol < 0.9:
            reasons.append(f"volume drying up on the dip ({pullback_rvol:.1f}x average)")

    # ---- 4. Reclaim: back above the 50-day from below. Weakest, flagged so.
    # Off by default: a reclaim is by definition a stock that was falling, which
    # the quality gate exists to exclude. Kept for anyone who wants turnarounds.
    elif (allow_reclaim and tt["passed"] >= 4 and px > ma50 and float(s.iloc[-11]) < ma50_prev
            and rising20 and (np.isnan(rvol) or rvol >= 1.2)):
        kind = "reclaim"
        reasons.append("reclaimed the 50-day from below")
        reasons.append("earlier in a turn than the others, and less reliable")

    if kind is None:
        return None

    # ---- stop, target, risk/reward
    atr_stop = px - 2.0 * a
    if kind == "breakout" and base.get("found"):
        struct_stop = max(base["low"], px - 2.5 * a)
    elif kind == "pullback":
        struct_stop = min(swing_low, ma50 * 0.97)
    elif kind == "squeeze" and base.get("found"):
        struct_stop = base["low"]
    else:
        struct_stop = swing_low
    stop = float(min(max(struct_stop, px * (1 - max_risk_pct)), atr_stop))
    stop = min(stop, px * 0.995)

    risk = px - stop
    if risk <= 0:
        return None
    risk_pct = risk / px
    if risk_pct > max_risk_pct:
        return None

    # Target: the measured move of the base where there is one, else 3R.
    if base.get("found") and kind in ("breakout", "squeeze"):
        measured = base["high"] + (base["high"] - base["low"])
        target = float(max(measured, px + 3 * risk))
    else:
        target = float(px + 3 * risk)
    rr = (target - px) / risk
    if rr < min_rr:
        return None

    # ---- quality score: confluence, not any single factor
    q = 0.0
    q += (tt["passed"] / tt["total"]) * 30                       # structure
    q += min(rr / 4.0, 1.0) * 20                                 # reward vs risk
    q += (1 - min(risk_pct / max_risk_pct, 1.0)) * 15            # tightness of stop
    if not np.isnan(sq):
        q += (1 - sq / 100) * 10                                 # volatility coiled
    if not np.isnan(rvol):
        q += min(max(rvol - 1.0, 0) / 1.5, 1.0) * 10             # volume confirming
    if rs_1m is not None and not (isinstance(rs_1m, float) and np.isnan(rs_1m)):
        q += min(max(rs_1m, 0) / 0.10, 1.0) * 10                 # leading its market
    q += {"breakout": 5, "pullback": 5, "squeeze": 3, "reclaim": 0}[kind]

    # Quality floor. Measured on 200 synthetic series per population, this
    # threshold fires on ~32% of uptrend-then-base charts, ~20% of plain
    # uptrends, ~6% of pure random walks and ~1% of downtrends. Patterns do
    # appear in noise -- the floor limits how often, it cannot abolish it.
    if q < min_quality:
        return None

    return {
        "ticker": ticker,
        "signal": kind,
        "quality": round(q, 1),
        "entry": round(px, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_pct": round(risk_pct, 4),
        "reward_risk": round(rr, 2),
        "atr": round(float(a), 2),
        "atr_extension": round(float(ext), 2),
        "trend_checks": f"{tt['passed']}/{tt['total']}",
        "trend_passed": tt["passed"],
        "pct_from_52w_high": tt.get("pct_from_52w_high"),
        "squeeze_pctile": None if np.isnan(sq) else sq,
        "rel_volume": None if np.isnan(rvol) else round(rvol, 2),
        "base_days": base.get("days"),
        "base_depth": base.get("depth"),
        "reasons": "; ".join(reasons),
    }


def scan(
    close: pd.DataFrame,
    tickers: list[str],
    high: pd.DataFrame | None = None,
    low: pd.DataFrame | None = None,
    volume: pd.DataFrame | None = None,
    as_of: pd.Timestamp | None = None,
    rs_map: dict[str, float] | None = None,
    theme_map: dict[str, str] | None = None,
    **kw,
) -> pd.DataFrame:
    """Run the detector across a list of tickers and return the hits, best first."""
    out = []
    for tk in tickers:
        if tk not in close.columns:
            continue
        try:
            sig = detect_signal(
                tk, close[tk],
                high[tk] if high is not None and tk in high.columns else None,
                low[tk] if low is not None and tk in low.columns else None,
                volume[tk] if volume is not None and tk in volume.columns else None,
                as_of=as_of,
                rs_1m=(rs_map or {}).get(tk),
                **kw,
            )
        except Exception:
            continue
        if sig:
            sig["theme"] = (theme_map or {}).get(tk, "")
            sig["rs_1m"] = (rs_map or {}).get(tk)
            out.append(sig)

    if not out:
        return pd.DataFrame()
    df = pd.DataFrame(out).sort_values("quality", ascending=False)
    return df.set_index("ticker")

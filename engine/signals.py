"""
Per-name technical state.

Our cycle engine answers "is this group turning?" and "which members lead?".
It says nothing about whether a name is a sensible *entry today*, which is a
separate question and the gap this module fills.

Four measurements, each answering a distinct question:

  ma_distance + ma_slope   Where is price relative to its averages, and are
                           those averages rising or falling? "3% above a rising
                           50-day" and "3% above a falling 50-day" are opposite
                           situations that a simple above/below flag conflates.

  atr_extension            How many ATRs is price above its 20-day? This is the
                           single most useful entry-timing number we were
                           missing. Buying a name 4 ATRs extended means buying
                           after the move, and the first pullback hurts.

  rel_volume               Today's volume against its own 50-day average. Moves
                           on thin volume are less likely to persist.

  setup                    A named classification combining the above, so the
                           dashboard can answer "which of my basket names are
                           buyable right now" rather than only "what should I own".
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def true_range(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    """Standard true range: the widest of today's span, or either gap from
    yesterday's close. Gaps matter -- a name that opens 5% up and closes flat
    has moved 5%, which a high-minus-low measure would miss."""
    prev = close.shift(1)
    return pd.concat([
        (high - low).stack(future_stack=True),
        (high - prev).abs().stack(future_stack=True),
        (low - prev).abs().stack(future_stack=True),
    ], axis=1).max(axis=1).unstack()


def atr(high, low, close, window: int = 14) -> pd.DataFrame:
    return true_range(high, low, close).rolling(window, min_periods=window).mean()


def name_state(
    close: pd.DataFrame,
    high: pd.DataFrame | None = None,
    low: pd.DataFrame | None = None,
    volume: pd.DataFrame | None = None,
    as_of: pd.Timestamp | None = None,
    benchmark: pd.Series | None = None,
) -> pd.DataFrame:
    """
    One row per ticker describing its technical state on `as_of`.

    high/low/volume are optional. Without high/low, ATR falls back to a
    close-to-close proxy, which understates true range on gappy names --
    acceptable, but noted in the output as atr_is_proxy.
    """
    as_of = as_of or close.index[-1]
    c = close.loc[:as_of]
    if len(c) < 210:
        raise ValueError("Need at least 210 rows of close data.")

    last = c.iloc[-1]
    out = pd.DataFrame(index=c.columns)
    out["close"] = last

    # --- distance from each moving average, and whether that average is rising
    for w in (20, 50, 200):
        ma = c.rolling(w).mean()
        out[f"dist_{w}d"] = (last / ma.iloc[-1] - 1.0)
        # Slope measured over w/4 sessions: long enough to ignore daily wiggle,
        # short enough to catch a turn while it still matters.
        lag = max(3, w // 4)
        out[f"slope_{w}d"] = (ma.iloc[-1] / ma.iloc[-1 - lag] - 1.0)
        out[f"rising_{w}d"] = out[f"slope_{w}d"] > 0

    # --- returns
    for label, n in (("1d", 1), ("1w", 5), ("1m", 21), ("3m", 63), ("6m", 126)):
        if len(c) > n:
            out[f"ret_{label}"] = last / c.iloc[-1 - n] - 1.0

    # --- relative strength vs benchmark over 1 month
    if benchmark is not None:
        b = benchmark.loc[:as_of]
        if len(b) > 21:
            bench_1m = b.iloc[-1] / b.iloc[-22] - 1.0
            out["rs_1m"] = out.get("ret_1m", np.nan) - bench_1m

    # --- ATR extension from the 20-day
    if high is not None and low is not None:
        a = atr(high.loc[:as_of], low.loc[:as_of], c)
        out["atr"] = a.iloc[-1]
        out["atr_is_proxy"] = False
    else:
        # Close-to-close proxy: mean absolute daily change over 14 sessions.
        out["atr"] = c.diff().abs().rolling(14).mean().iloc[-1]
        out["atr_is_proxy"] = True

    ma20 = c.rolling(20).mean().iloc[-1]
    out["atr_extension"] = (last - ma20) / out["atr"].replace(0, np.nan)

    # --- relative volume
    if volume is not None:
        v = volume.loc[:as_of]
        avg = v.rolling(50, min_periods=20).mean().iloc[-1]
        out["rel_volume"] = v.iloc[-1] / avg.replace(0, np.nan)

    out["setup"] = [classify_setup(r) for _, r in out.iterrows()]
    return out


def classify_setup(r: pd.Series) -> str:
    """
    Name the situation. Order matters -- the first match wins, and the
    dangerous states are checked before the attractive ones.

    extended    price is 3+ ATRs above the 20-day. Chasing. Wait.
    pullback    above a rising 50-day, down on the week, near a rising average.
                The best entry state: trend intact, price came back to you.
    trend       above a rising 50-day but not near it. Own it, don't add.
    rally_weak  below a falling 50-day but up on the week. A bounce inside a
                downtrend. The most common trap in a momentum screen.
    broken      below a falling 50-day. Avoid.
    neutral     none of the above cleanly.
    """
    ext = r.get("atr_extension", np.nan)
    d50, rise50 = r.get("dist_50d", np.nan), bool(r.get("rising_50d", False))
    d20, rise20 = r.get("dist_20d", np.nan), bool(r.get("rising_20d", False))
    w = r.get("ret_1w", np.nan)

    if pd.notna(ext) and ext >= 3.0:
        return "extended"

    near = (pd.notna(ext) and abs(ext) <= 1.0)

    if d50 > 0 and rise50:
        if pd.notna(w) and w < 0 and near and (rise20 or rise50):
            return "pullback"
        return "trend"

    if d50 < 0 and not rise50:
        if pd.notna(w) and w > 0 and near:
            return "rally_weak"
        return "broken"

    return "neutral"


def group_state(
    close: pd.DataFrame,
    members: list[str],
    as_of: pd.Timestamp | None = None,
    benchmark: pd.Series | None = None,
) -> dict:
    """
    Theme-level summary. Equal-weight the members rather than
    capitalisation-weight: we want the health of the group, not of its two
    largest names.
    """
    as_of = as_of or close.index[-1]
    cols = [m for m in members if m in close.columns]
    c = close.loc[:as_of, cols].dropna(how="all")
    if c.shape[1] < 3:
        return {}

    norm = c / c.iloc[0]
    idx = norm.mean(axis=1)          # equal-weight group index

    ma50 = c.rolling(50).mean()
    ma200 = c.rolling(200).mean()
    above50 = float((c.iloc[-1] > ma50.iloc[-1]).mean() * 100)
    above200 = float((c.iloc[-1] > ma200.iloc[-1]).mean() * 100)

    res = {
        "members": c.shape[1],
        "pct_above_50d": round(above50, 1),
        "pct_above_200d": round(above200, 1),
    }
    for label, n in (("1w", 5), ("1m", 21), ("3m", 63), ("6m", 126)):
        if len(idx) > n:
            res[f"ret_{label}"] = round(float(idx.iloc[-1] / idx.iloc[-1 - n] - 1.0), 4)

    if benchmark is not None:
        b = benchmark.loc[:as_of]
        # Store the benchmark's own returns too: relative strength over more
        # than one horizon needs them, and recomputing per theme would be waste.
        for label, n in (("1m", 21), ("3m", 63)):
            if len(b) > n:
                res[f"bench_{label}"] = round(float(b.iloc[-1] / b.iloc[-1 - n] - 1.0), 4)
        if "bench_1m" in res and "ret_1m" in res:
            res["rs_1m"] = round(res["ret_1m"] - res["bench_1m"], 4)
        if "bench_3m" in res and "ret_3m" in res:
            res["rs_3m"] = round(res["ret_3m"] - res["bench_3m"], 4)

    for w in (20, 50, 200):
        if len(idx) > w + 10:
            ma = idx.rolling(w).mean()
            res[f"dist_{w}d"] = round(float(idx.iloc[-1] / ma.iloc[-1] - 1.0), 4)
            lag = max(3, w // 4)
            res[f"rising_{w}d"] = bool(ma.iloc[-1] > ma.iloc[-1 - lag])

    return res

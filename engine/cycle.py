"""
Cycle engine.

Reverse-engineered from a working macro-momentum basket system, then made
reproducible: every number here comes from a published formula over price data.

Core idea:
  1. For a themed sub-universe, measure internal breadth (% of members above
     their long moving average).
  2. Percentile-rank that breadth over a trailing window -> 0-100 oscillator.
  3. Oscillator troughs (turns up out of the low zone) = NEW CYCLE, buy a basket.
  4. Oscillator peaks (turns down out of the high zone) = TAKE PROFITS, exit
     the whole basket together.

No look-ahead: every value at date t uses only data up to and including t.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------------
# 1. The oscillator
# ----------------------------------------------------------------------------

def breadth_oscillator(
    prices: pd.DataFrame,
    ma_window: int = 200,
    smooth: int = 10,
    percentile_window: int = 750,
    min_members: int = 10,
) -> pd.Series:
    """
    prices : DataFrame, index=DatetimeIndex, columns=tickers, values=close.
    Returns a 0-100 Series. 0 = breadth at its lowest in the trailing window.

    percentile_window of 750 trading days is roughly 3 years. Longer windows
    make the oscillator slower and the extremes rarer.
    """
    ma = prices.rolling(ma_window, min_periods=ma_window).mean()

    valid = prices.notna() & ma.notna()
    above = (prices > ma) & valid

    member_count = valid.sum(axis=1)
    raw = above.sum(axis=1) / member_count.replace(0, np.nan) * 100.0
    raw = raw.where(member_count >= min_members)

    smoothed = raw.rolling(smooth, min_periods=smooth).mean()

    # Percentile rank of the latest value within the trailing window.
    osc = smoothed.rolling(percentile_window, min_periods=250).apply(
        lambda w: (w <= w[-1]).mean() * 100.0, raw=True
    )
    return osc.rename("oscillator")


# ----------------------------------------------------------------------------
# 2. Cycle detection
# ----------------------------------------------------------------------------

def cycle_signals(
    osc: pd.Series,
    entry_zone: float = 25.0,
    exit_zone: float = 75.0,
    confirm_days: int = 3,
) -> pd.DataFrame:
    """
    ENTRY fires when the oscillator has been in the low zone and then closes
    above it for `confirm_days` consecutive days -- i.e. the trough has turned.
    EXIT fires symmetrically out of the high zone.

    Waiting for the turn rather than buying the first touch of the low zone is
    deliberate: a falling oscillator can sit under 25 for months.
    """
    osc = osc.dropna()
    if osc.empty:
        return pd.DataFrame(columns=["date", "signal", "oscillator"])

    rows = []
    state = "flat"          # flat | armed | long | primed
    run = 0

    for date, v in osc.items():
        if state == "flat":
            if v <= entry_zone:
                state, run = "armed", 0
        elif state == "armed":
            run = run + 1 if v > entry_zone else 0
            if run >= confirm_days:
                rows.append({"date": date, "signal": "ENTRY", "oscillator": v})
                state, run = "long", 0
        elif state == "long":
            if v >= exit_zone:
                state, run = "primed", 0
        elif state == "primed":
            run = run + 1 if v < exit_zone else 0
            if run >= confirm_days:
                rows.append({"date": date, "signal": "EXIT", "oscillator": v})
                state, run = "flat", 0

    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# 3. Ranking members at a cycle start
# ----------------------------------------------------------------------------

def rank_members(
    prices: pd.DataFrame,
    as_of: pd.Timestamp,
    lookbacks: tuple[int, ...] = (63, 126, 252),
    weights: tuple[float, ...] = (0.4, 0.4, 0.2),
    vol_window: int = 63,
    trend_filter: int = 200,
) -> pd.DataFrame:
    """
    Composite momentum score, cross-sectionally ranked.

    Score = weighted average of percentile-ranked returns over each lookback,
    divided by realised volatility so a 60% move in a quiet name outranks a
    60% move in a name that swings 60% every quarter.

    Names below their 200DMA on the entry date are dropped: the cycle trigger
    says the group has turned, this says the individual name has too.
    """
    hist = prices.loc[:as_of]
    if len(hist) < max(max(lookbacks), trend_filter) + 5:
        raise ValueError(f"Not enough history before {as_of.date()} to rank.")

    last = hist.iloc[-1]
    out = pd.DataFrame(index=prices.columns)

    score = pd.Series(0.0, index=prices.columns)
    total_w = 0.0
    for lb, w in zip(lookbacks, weights):
        past = hist.iloc[-(lb + 1)]
        ret = last / past - 1.0
        out[f"ret_{lb}d"] = ret
        score = score.add(ret.rank(pct=True) * w, fill_value=0.0)
        total_w += w
    score = score / total_w

    daily = hist.pct_change()
    vol = daily.iloc[-vol_window:].std() * np.sqrt(252)
    out["ann_vol"] = vol

    # Volatility haircut, bounded so a very quiet name cannot dominate.
    haircut = (vol / vol.median()).clip(0.5, 2.0)
    out["score"] = score / haircut

    ma = hist.iloc[-trend_filter:].mean()
    out["above_200dma"] = last > ma

    out["price"] = last
    out = out[out["above_200dma"] & out["score"].notna()]
    out = out.sort_values("score", ascending=False)
    out.insert(0, "rank", range(1, len(out) + 1))
    return out


# ----------------------------------------------------------------------------
# 4. Basket construction
# ----------------------------------------------------------------------------

def build_basket(
    ranked: pd.DataFrame,
    n_tier1: int = 4,
    n_tier2: int = 4,
    tier1_weight: float = 0.70,
    eligible: set[str] | None = None,
) -> pd.DataFrame:
    """
    Tiered basket: top `n_tier1` names share `tier1_weight` of capital, the
    next `n_tier2` share the remainder. Equal weight within each tier.

    `eligible` is the fundamental gate. Names failing it are skipped and the
    next-ranked eligible name is promoted -- the gate never leaves a slot empty,
    it just pushes further down the ranking.
    """
    pool = ranked if eligible is None else ranked[ranked.index.isin(eligible)]
    pool = pool.copy()

    take = pool.head(n_tier1 + n_tier2).copy()
    if take.empty:
        return take

    take["tier"] = ["T1"] * min(n_tier1, len(take)) + \
                   ["T2"] * max(0, len(take) - n_tier1)

    t1 = (take["tier"] == "T1").sum()
    t2 = (take["tier"] == "T2").sum()

    if t2 == 0:
        take["weight"] = 1.0 / t1
    else:
        take.loc[take["tier"] == "T1", "weight"] = tier1_weight / t1
        take.loc[take["tier"] == "T2", "weight"] = (1 - tier1_weight) / t2

    take["basket_rank"] = range(1, len(take) + 1)
    return take


# ----------------------------------------------------------------------------
# 5. Walk-forward evaluation of one theme
# ----------------------------------------------------------------------------

def run_theme(
    prices: pd.DataFrame,
    theme_name: str,
    osc_kwargs: dict | None = None,
    signal_kwargs: dict | None = None,
    basket_kwargs: dict | None = None,
    stop_loss: float | None = 0.20,
    max_hold_days: int | None = 189,
) -> dict:
    """
    Walk the oscillator forward, build a basket at each ENTRY, close it at the
    next EXIT (or stop / time stop, whichever comes first), and record results.

    stop_loss is a basket-level drawdown stop, measured from the basket's own
    peak after entry. The source system has no stop at all; single names in its
    published results lost 50-60% inside a cycle. This is the fix.
    """
    osc = breadth_oscillator(prices, **(osc_kwargs or {}))
    sigs = cycle_signals(osc, **(signal_kwargs or {}))

    cycles, open_entry = [], None
    for _, row in sigs.iterrows():
        if row["signal"] == "ENTRY" and open_entry is None:
            open_entry = row["date"]
        elif row["signal"] == "EXIT" and open_entry is not None:
            cycles.append((open_entry, row["date"]))
            open_entry = None
    if open_entry is not None:
        cycles.append((open_entry, None))

    results = []
    for entry_date, exit_date in cycles:
        try:
            ranked = rank_members(prices, entry_date)
        except ValueError:
            continue
        basket = build_basket(ranked, **(basket_kwargs or {}))
        if basket.empty:
            continue

        held = basket.index.tolist()
        w = basket["weight"].values

        window = prices.loc[entry_date:, held]
        if max_hold_days:
            window = window.iloc[: max_hold_days + 1]
        if exit_date is not None:
            window = window.loc[:exit_date]
        if len(window) < 2:
            continue

        norm = window / window.iloc[0]
        curve = (norm * w).sum(axis=1)

        reason = "signal" if exit_date is not None else "open"
        if stop_loss is not None:
            dd = curve / curve.cummax() - 1.0
            hit = dd[dd <= -stop_loss]
            if not hit.empty:
                curve = curve.loc[: hit.index[0]]
                reason = "stop"
        # A still-unsignalled cycle that has already run past the time stop is
        # closed, not open -- otherwise the dashboard would show a live basket
        # you should have exited months ago.
        if reason in ("signal", "open") and max_hold_days and len(curve) > max_hold_days:
            curve = curve.iloc[: max_hold_days + 1]
            reason = "time_stop"

        closed = curve.index[-1]
        per_name = (prices.loc[closed, held] / prices.loc[entry_date, held] - 1.0)

        results.append({
            "theme": theme_name,
            "entry_date": entry_date,
            "exit_date": closed,
            "exit_reason": reason,
            "held_days": (closed - entry_date).days,
            "basket_return": float(curve.iloc[-1] - 1.0),
            "max_drawdown": float((curve / curve.cummax() - 1.0).min()),
            "names": held,
            "weights": w.tolist(),
            "per_name_return": per_name.to_dict(),
        })

    return {"theme": theme_name, "oscillator": osc, "signals": sigs, "cycles": results}

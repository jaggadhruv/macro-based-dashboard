"""
Ranking and classification.

Three outputs the raw cycle engine doesn't produce:

  sector_scores   One comparable 0-100 number per theme, so themes can be put
                  in a league table instead of read one tab at a time.

  zones           Each theme sorted into leading / building / avoid. The point
                  of "building" is that it names the thing a cycle system is
                  otherwise blind to: a theme that has not signalled yet but is
                  improving. That is where the next entry comes from.

  top_picks       The strongest individual names across every theme, so there
                  is one answer to "what looks best right now" rather than
                  eight separate lists.

Everything here is derived from values computed elsewhere. Nothing new is
measured; this layer only ranks and labels.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Sector score weights. Cross-sectional percentile ranks within one market,
# so a score of 80 means "stronger than 80% of this market's themes today",
# not an absolute claim.
SECTOR_WEIGHTS = {
    "rs_1m": 0.22,        # leading right now
    "rs_3m": 0.15,        # leading over the quarter, less noisy
    "breadth_50d": 0.20,  # is the move broad or carried by two names
    "trend_200d": 0.13,   # above a rising long-term average
    "osc_slope": 0.18,    # is the cycle improving -- the forward-looking part
    "osc_level": 0.12,    # where in its own range it sits
}


def oscillator_slope(osc: pd.Series, lookback: int = 20) -> float:
    """
    Change in the oscillator over the last `lookback` sessions.

    This is the single most important input for spotting a theme that is
    building. Level alone cannot distinguish a theme at 40 on the way up from
    one at 40 on the way down, and those are opposite situations.
    """
    s = osc.dropna()
    if len(s) < lookback + 1:
        return np.nan
    return float(s.iloc[-1] - s.iloc[-1 - lookback])


def score_sectors(themes: dict) -> pd.DataFrame:
    """
    themes: {name: {"oscillator": Series, "group": dict, "in_cycle": bool}}

    Returns a DataFrame indexed by theme, with the component percentiles, the
    composite score, and a rank.
    """
    rows = []
    for name, t in themes.items():
        g = t.get("group") or {}
        osc = t.get("oscillator")
        osc_now = float(osc.dropna().iloc[-1]) if osc is not None and len(osc.dropna()) else np.nan
        rows.append({
            "theme": name,
            "rs_1m": g.get("rs_1m"),
            "rs_3m": g.get("rs_3m"),
            "breadth_50d": g.get("pct_above_50d"),
            "trend_200d": (g.get("dist_200d") or 0) * (1.5 if g.get("rising_200d") else 0.5)
                          if g.get("dist_200d") is not None else np.nan,
            "osc_slope": oscillator_slope(osc) if osc is not None else np.nan,
            "osc_level": osc_now,
            "oscillator": osc_now,
            "in_cycle": bool(t.get("in_cycle")),
            "members": g.get("members"),
            "ret_1m": g.get("ret_1m"),
            "ret_3m": g.get("ret_3m"),
            "dist_50d": g.get("dist_50d"),
            "rising_50d": g.get("rising_50d"),
            "dist_200d": g.get("dist_200d"),
            "rising_200d": g.get("rising_200d"),
        })

    df = pd.DataFrame(rows).set_index("theme")
    if df.empty:
        return df

    score = pd.Series(0.0, index=df.index)
    used = 0.0
    for col, w in SECTOR_WEIGHTS.items():
        v = df[col]
        if v.notna().sum() < 2:
            continue
        # pct=True gives 0..1; fill missing at the median so one absent
        # component does not push a theme to the bottom.
        score += v.rank(pct=True).fillna(0.5) * w
        used += w
    df["score"] = (score / used * 100).round(1) if used else np.nan
    df = df.sort_values("score", ascending=False)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


def classify_zone(row: pd.Series) -> tuple[str, str]:
    """
    Sort a theme into a zone and give the one-line reason.

    The governing rule: **'building' must mean improving.** Every path into that
    zone requires a rising oscillator. A high rank with a collapsing oscillator
    is a sector that has already had its run, not one about to have it, and
    painting it amber would invite exactly the wrong trade.

    'leading' likewise needs confirmation from breadth and trend, not just a
    good month. Rank alone is relative -- in a weak market something ranks
    first regardless.

    Returns (zone, reason).
    """
    score = row.get("score", np.nan)
    slope = row.get("osc_slope", np.nan)
    breadth = row.get("breadth_50d", np.nan)
    rising50 = bool(row.get("rising_50d", False))
    rising200 = bool(row.get("rising_200d", False))
    d200 = row.get("dist_200d", np.nan)
    in_cycle = bool(row.get("in_cycle", False))

    has_slope = pd.notna(slope)
    rising_osc = has_slope and slope > 0
    # A strong surge is the signature of a cycle trough, and at a trough breadth
    # is low by definition. So a surge lifts the low-breadth veto below --
    # otherwise the 'avoid' rules would hide exactly the entries this system
    # exists to find. The reason text still flags the thin breadth.
    surging = has_slope and slope >= 8

    # ---- Leading: acted on, or top-ranked with breadth and trend agreeing.
    if in_cycle:
        return "leading", "Cycle entry triggered; basket held"
    if pd.notna(score) and score >= 68 and rising50 and pd.notna(breadth) and breadth >= 50:
        return "leading", (f"Top-ranked, {breadth:.0f}% of members above their 50-day, "
                           f"trend rising")

    # ---- Avoid: weak and still deteriorating. Checked before 'building' so a
    # broken sector cannot be rescued by a small bounce in its oscillator.
    if pd.notna(score) and score <= 30 and (not has_slope or slope <= 0):
        return "avoid", "Bottom-ranked and the cycle is still falling"
    if pd.notna(breadth) and breadth <= 25 and not rising200 and not surging:
        return "avoid", (f"Only {breadth:.0f}% of members above their 50-day, "
                         f"long-term trend falling")
    if pd.notna(d200) and d200 < -0.10 and not rising200 and not rising_osc:
        return "avoid", "Well below a falling 200-day, no sign of a turn"

    # ---- Building: the oscillator must be climbing. No exceptions.
    if rising_osc:
        if slope >= 8 and pd.notna(breadth) and breadth >= 35:
            return "building", (f"Oscillator up {slope:.0f} points in a month, "
                                f"breadth recovering to {breadth:.0f}%")
        if slope >= 8:
            return "building", (f"Oscillator up {slope:.0f} points in a month, "
                                f"but breadth still thin")
        if pd.notna(score) and score >= 50 and rising50:
            return "building", (f"Mid-ranked with the cycle turning up "
                                f"(+{slope:.0f} in a month)")

    # ---- Everything else, with a reason that says which piece is missing.
    if pd.notna(score) and score >= 68:
        if has_slope and slope <= 0:
            return "neutral", (f"Ranks high but the cycle is rolling over "
                               f"({slope:+.0f} in a month) -- late, not early")
        return "neutral", "Ranks high but breadth or trend has not confirmed"
    if pd.notna(score) and score <= 35:
        return "neutral", "Weak, though not deteriorating fast enough to write off"
    return "neutral", "Neither improving nor deteriorating enough to act on"


def sector_drivers(
    members: pd.DataFrame,
    n: int = 20,
    horizon: str = "ret_1m",
) -> pd.DataFrame:
    """
    The names actually moving a theme.

    Because the group index is equal-weight, each member contributes its own
    return divided by the member count. So 'driving' is simply the size of a
    member's move -- but we rank on a blend of 1M and 3M so a single spiking
    week does not crown a name that has gone nowhere over the quarter.

    Returns the top `n` with their contribution to the group's move.
    """
    if members is None or members.empty:
        return pd.DataFrame()

    df = members.copy()
    k = max(len(df), 1)

    r1 = df.get("ret_1m", pd.Series(dtype=float))
    r3 = df.get("ret_3m", pd.Series(dtype=float))
    df["contribution_1m"] = r1 / k
    df["contribution_3m"] = r3 / k if len(r3) else np.nan

    blend = pd.Series(0.0, index=df.index)
    used = 0.0
    for col, w in (("ret_1m", 0.6), ("ret_3m", 0.4)):
        if col in df and df[col].notna().sum() >= 2:
            blend += df[col].rank(pct=True).fillna(0.5) * w
            used += w
    df["driver_score"] = (blend / used * 100).round(1) if used else np.nan

    df = df.sort_values(horizon if horizon in df else "driver_score", ascending=False)
    df.insert(0, "driver_rank", range(1, len(df) + 1))
    return df.head(n)


# Shared by the cross-sector and per-sector pick lists, so both rank identically
# and a name cannot appear high in one and low in the other.
SETUP_ADJ = {"pullback": 6.0, "trend": 3.0, "neutral": 0.0,
             "extended": -6.0, "rally_weak": -10.0, "broken": -15.0}


def _name_strength(mem: pd.DataFrame) -> pd.Series | None:
    """Percentile-blended strength of each member *within its own theme*."""
    blend = pd.Series(0.0, index=mem.index)
    used = 0.0
    for col, w in (("rs_1m", 0.45), ("ret_3m", 0.35), ("ret_6m", 0.20)):
        if col in mem and mem[col].notna().sum() >= 2:
            blend += mem[col].rank(pct=True).fillna(0.5) * w
            used += w
    return None if used == 0 else blend / used * 100


def _is_eligible(r: pd.Series, max_extension: float, require_gate: bool,
                 require_quality: bool = False) -> str | None:
    """
    Return None if the name is buyable, else the reason it is not.

    With require_quality, a name must have been positively screened. "Not
    checked" is treated as "not eligible" -- never as a pass.
    """
    if require_quality:
        # Truthiness, not identity: pandas hands back numpy.bool_, and
        # `numpy.True_ is True` is False. An identity check here silently
        # rejected every screened name.
        qp = r.get("quality_passed")
        passed = qp is not None and not (isinstance(qp, float) and np.isnan(qp)) and bool(qp)
        if not passed:
            why = r.get("quality_reasons")
            return why if isinstance(why, str) and why else "not quality-screened"
    d50 = r.get("dist_50d")
    if d50 is not None and not pd.isna(d50) and d50 < 0 and not bool(r.get("rising_50d", False)):
        return "below a falling 50-day"
    ext = r.get("atr_extension")
    if ext is not None and not pd.isna(ext) and ext >= max_extension:
        return f"stretched {ext:.1f} ATR above the 20-day"
    gp = r.get("gate_passed")
    if require_gate and gp is not None and not (isinstance(gp, float) and np.isnan(gp)) \
            and not bool(gp):
        return "failed the fundamental screen"
    return None


def _pick_row(tk, r, theme, s_row, s_score) -> dict:
    """
    Sector strength + the name's own strength + forward expectations:
    35% sector, 32% name, 18% forward.

    A name with NO analyst coverage is scored with a neutral forward score of 50
    -- "no information" is treated as "average expectations".

    An earlier version instead re-weighted the missing component away, and that
    created a perverse incentive: an uncovered name kept its full sector and
    momentum score, while a covered name with merely average estimates had part
    of its score replaced by a middling 50. Being unexamined beat being examined
    and found ordinary, and uncovered names crowded the top of the list.
    Imputing the neutral value removes that. Rising estimates now beat both;
    falling ones are rejected outright by the quality gate.
    """
    setup = r.get("setup", "neutral")
    fwd = r.get("fwd_score")
    has_fwd = fwd is not None and not (isinstance(fwd, float) and np.isnan(fwd))
    fwd_eff = float(fwd) if has_fwd else 50.0
    base = 0.35 * s_score + 0.32 * float(r["name_score"]) + 0.18 * fwd_eff
    combined = base + SETUP_ADJ.get(setup, 0.0)
    if bool(s_row.get("in_cycle")):
        combined += 5.0          # the theme has actually triggered
    return {
        "ticker": tk,
        "theme": theme,
        "pick_score": round(combined, 1),
        "sector_score": s_score,
        "sector_rank": int(s_row.get("rank", 0)),
        "name_score": round(float(r["name_score"]), 1),
        "setup": setup,
        "in_cycle_theme": bool(s_row.get("in_cycle")),
        "close": r.get("close"),
        "ret_1m": r.get("ret_1m"),
        "ret_3m": r.get("ret_3m"),
        "ret_6m": r.get("ret_6m"),
        "rs_1m": r.get("rs_1m"),
        "dist_50d": r.get("dist_50d"),
        "rising_50d": bool(r.get("rising_50d", False)),
        "atr_extension": r.get("atr_extension"),
        "rel_volume": r.get("rel_volume"),
        "gate_passed": r.get("gate_passed"),
        "gate_reasons": r.get("gate_reasons"),
        "revenue_growth": r.get("revenue_growth"),
        "roce": r.get("roce"),
        "in_basket": bool(r.get("in_basket", False)),
        "fwd_score": float(fwd) if has_fwd else None,
        "fwd_summary": r.get("fwd_summary"),
        "coverage": r.get("coverage"),
        "rev_30d_cy": r.get("rev_30d_cy"),
        "fwd_growth": r.get("fwd_growth"),
        "fwd_pe": r.get("fwd_pe"),
        "n_analysts": r.get("n_analysts"),
        "drawdown_from_high": r.get("drawdown_from_high"),
        "quality_passed": r.get("quality_passed"),
    }


def sector_picks(
    theme: str,
    mem: pd.DataFrame,
    sector_row: pd.Series,
    n: int = 5,
    require_gate: bool = True,
    max_extension: float = 3.0,
    require_quality: bool = False,
) -> pd.DataFrame:
    """
    The best `n` buyable names *inside one sector*.

    Same scoring and the same hard exclusions as the cross-sector list, with the
    two-per-theme cap removed -- here the whole point is to see the sector's own
    leaders side by side.

    It may return fewer than `n`, and that is information rather than a defect:
    a sector whose members are mostly stretched or below falling averages is one
    where the move has already happened. The excluded count is reported so the
    difference is visible.
    """
    if mem is None or mem.empty:
        return pd.DataFrame()
    s_score = float(sector_row.get("score", np.nan))
    if np.isnan(s_score):
        return pd.DataFrame()

    df = mem.copy()
    ns = _name_strength(df)
    if ns is None:
        return pd.DataFrame()
    df["name_score"] = ns

    rows, excluded = [], 0
    for tk, r in df.iterrows():
        why = _is_eligible(r, max_extension, require_gate, require_quality)
        if why:
            excluded += 1
            continue
        rows.append(_pick_row(tk, r, theme, sector_row, s_score))

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).sort_values("pick_score", ascending=False).head(n)
    out = out.set_index("ticker")
    out.insert(0, "sector_pick_rank", range(1, len(out) + 1))
    out["candidates"] = len(df)
    out["excluded"] = excluded
    return out


def top_picks(
    sector_scores: pd.DataFrame,
    members_by_theme: dict[str, pd.DataFrame],
    n: int = 5,
    require_gate: bool = True,
    max_extension: float = 3.0,
    max_per_theme: int = 2,
    require_quality: bool = False,
) -> pd.DataFrame:
    """
    The strongest individual names across every theme.

    A name's score blends the strength of the theme it sits in with its own
    strength inside that theme, then adjusts for how buyable it is today.

    Hard exclusions, applied before scoring:
      - below a falling 50-day (the trend disagrees)
      - stretched beyond `max_extension` ATRs (entering here is chasing)
      - failed the fundamental gate, when the gate has run

    `max_per_theme` stops all picks coming from whichever sector happens to be
    hottest -- five names from one theme is one bet, not five. That cap is the
    difference between this list and `sector_picks`, which deliberately has none.
    """
    rows = []
    for theme, mem in members_by_theme.items():
        if mem is None or mem.empty or theme not in sector_scores.index:
            continue
        s_row = sector_scores.loc[theme]
        s_score = float(s_row.get("score", np.nan))
        if np.isnan(s_score):
            continue

        df = mem.copy()
        ns = _name_strength(df)
        if ns is None:
            continue
        df["name_score"] = ns

        for tk, r in df.iterrows():
            if _is_eligible(r, max_extension, require_gate, require_quality):
                continue
            rows.append(_pick_row(tk, r, theme, s_row, s_score))

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows).sort_values("pick_score", ascending=False)

    capped, counts = [], {}
    for _, r in out.iterrows():
        c = counts.get(r["theme"], 0)
        if c >= max_per_theme:
            continue
        counts[r["theme"]] = c + 1
        capped.append(r)
        if len(capped) >= n:
            break

    res = pd.DataFrame(capped).set_index("ticker")
    res.insert(0, "pick_rank", range(1, len(res) + 1))
    return res

"""
Price fetching with an immutable local cache.

Stores full OHLCV, not just close. High/low are needed for a true ATR (gaps
matter), volume for relative volume. One parquet per field keeps each file
simple and lets you load only what a given job needs.

Never delete data/prices/. Replaying last month's data through this month's
code is the only honest way to test whether a change improved anything.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "prices"
DATA.mkdir(parents=True, exist_ok=True)

FIELDS = ("Close", "High", "Low", "Volume")


def fetch_ohlcv(
    tickers: list[str],
    start: str = "2015-01-01",
    end: str | None = None,
    batch: int = 40,
    pause: float = 1.0,
) -> dict[str, pd.DataFrame]:
    """
    Returns {field: DataFrame(index=date, columns=ticker)}.

    Indian tickers need the .NS suffix (RELIANCE.NS). US tickers are bare (AAPL).
    """
    import yfinance as yf

    collected = {f: [] for f in FIELDS}

    for i in range(0, len(tickers), batch):
        chunk = tickers[i : i + batch]
        print(f"  fetching {i + 1}-{i + len(chunk)} of {len(tickers)}...")
        df = yf.download(
            chunk, start=start, end=end,
            auto_adjust=True, progress=False, threads=True, group_by="column",
        )
        if df.empty:
            continue
        for f in FIELDS:
            if isinstance(df.columns, pd.MultiIndex):
                if f in df.columns.get_level_values(0):
                    collected[f].append(df[f])
            elif f in df.columns:
                sub = df[[f]].copy()
                sub.columns = chunk[:1]
                collected[f].append(sub)
        time.sleep(pause)

    out = {}
    for f, frames in collected.items():
        if frames:
            m = pd.concat(frames, axis=1).sort_index()
            out[f] = m.loc[:, ~m.columns.duplicated()]
    if "Close" not in out:
        raise RuntimeError("No close data returned. Check tickers and connectivity.")
    return out


def update_cache(
    market: str,
    tickers: list[str],
    start: str = "2015-01-01",
    incremental: bool = True,
    overlap_days: int = 10,
) -> dict:
    """
    Fetch, merge into the cache, save, return the full history per field.

    Incremental by default: when a cache already exists, only the window since
    its last date (minus `overlap_days`) is downloaded. A daily refresh then
    pulls a couple of weeks rather than ten years, which is roughly a hundred
    times less traffic and far less likely to be rate-limited -- the difference
    between a scheduled job that survives and one that gets blocked.

    The overlap matters: the last few cached rows may have been provisional, and
    splits or dividend adjustments restate history. Re-fetching a short tail and
    letting new data win on overlap picks those corrections up.

    Any ticker absent from the cache is fetched in full regardless, since a
    newly added name has no history to be incremental about.
    """
    path_close = DATA / f"{market}_close.parquet"
    fetch_start, known = start, set()

    if incremental and path_close.exists():
        try:
            cached = pd.read_parquet(path_close)
            known = set(cached.columns)
            last = cached.index[-1]
            fetch_start = (last - pd.Timedelta(days=overlap_days)).strftime("%Y-%m-%d")
        except Exception as e:
            print(f"  cache unreadable ({e}); downloading in full")
            fetch_start, known = start, set()

    new_tickers = [t for t in tickers if t not in known]
    known_tickers = [t for t in tickers if t in known]

    collected: dict[str, list[pd.DataFrame]] = {}

    if known_tickers and fetch_start != start:
        print(f"  incremental: {len(known_tickers)} tickers from {fetch_start}")
        part = fetch_ohlcv(known_tickers, start=fetch_start)
        for f, df in part.items():
            collected.setdefault(f, []).append(df)

    if new_tickers:
        print(f"  full history: {len(new_tickers)} new tickers from {start}")
        part = fetch_ohlcv(new_tickers, start=start)
        for f, df in part.items():
            collected.setdefault(f, []).append(df)

    if not collected:
        print(f"  nothing to fetch; loading cache")
        return load_ohlcv(market)

    merged = {}
    for f, frames in collected.items():
        new = pd.concat(frames, axis=1).sort_index()
        new = new.loc[:, ~new.columns.duplicated()]

        path = DATA / f"{market}_{f.lower()}.parquet"
        if path.exists():
            old = pd.read_parquet(path)
            # New data wins on overlapping dates, so restatements are picked up.
            m = new.combine_first(old)
            m = m.reindex(columns=sorted(set(old.columns) | set(new.columns)))
        else:
            m = new
        m = m.sort_index()
        m.to_parquet(path)
        merged[f] = m

    for f in FIELDS:
        if f not in merged:
            fp = DATA / f"{market}_{f.lower()}.parquet"
            if fp.exists():
                merged[f] = pd.read_parquet(fp).sort_index()

    c = merged["Close"]
    print(f"  cached {c.shape[1]} tickers x {c.shape[0]} days, "
          f"through {c.index[-1].date()}")
    return merged


def load_ohlcv(market: str) -> dict[str, pd.DataFrame]:
    out = {}
    for f in FIELDS:
        path = DATA / f"{market}_{f.lower()}.parquet"
        if path.exists():
            out[f] = pd.read_parquet(path).sort_index()
    if "Close" not in out:
        raise FileNotFoundError(
            f"No close cache for '{market}' in {DATA}. Run with --refresh first."
        )
    return out


def load_cache(market: str) -> pd.DataFrame:
    """Close prices only. Kept for code that does not need OHLCV."""
    return load_ohlcv(market)["Close"]


def coverage_report(prices: pd.DataFrame, min_days: int = 500) -> pd.DataFrame:
    """
    Which tickers have enough history, and which have gone stale.
    Run this every time -- silent gaps are the main failure mode of free data.
    """
    last = prices.index[-1]
    rows = []
    for col in prices.columns:
        s = prices[col].dropna()
        rows.append({
            "ticker": col,
            "days": len(s),
            "first": s.index[0].date() if len(s) else None,
            "last": s.index[-1].date() if len(s) else None,
            "stale_days": (last - s.index[-1]).days if len(s) else None,
            "usable": len(s) >= min_days,
        })
    return pd.DataFrame(rows).sort_values("days")

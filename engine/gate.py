"""
Fundamental quality gate.

This is the piece the source system does not have. Its published results include
names that fell 50-60% inside a single cycle. Momentum ranking alone will happily
hand you a leveraged company whose revenue is shrinking.

The gate is BINARY and runs BEFORE basket selection. It does not re-rank; it
removes. Failures are pushed down the list and the next eligible name is promoted.

Phase 1 uses yfinance financials because they are free and immediate. They are
also less reliable than XBRL. Phase 2 replaces this module with deterministic
XBRL parsing (SEC companyfacts for US, BSE Reg-33 filings for India) with no
change to the interface below.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parent.parent / "data" / "fundamentals"
CACHE.mkdir(parents=True, exist_ok=True)

THRESHOLDS = {
    "min_revenue_growth": 0.0,     # TTM revenue YoY must be positive
    "min_profit_growth": 0.0,      # TTM net income YoY must be positive
    "max_net_debt_ebitda": 3.0,
    "min_interest_cover": 3.0,
    "min_roce": 0.12,              # 0.10 for US
    "max_share_growth": 0.05,
    "min_market_cap": 2000e7,      # Rs 2,000 cr; override per market
}


def _safe(d, *keys):
    for k in keys:
        try:
            v = d.get(k)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                return float(v)
        except Exception:
            continue
    return None


def fetch_fundamentals(ticker: str, refresh_days: int = 80) -> dict:
    """
    Pull and cache one company's fundamentals. Cached for refresh_days so a
    monthly run does not re-hit the source; results only change quarterly.
    """
    path = CACHE / f"{ticker.replace('.', '_')}.json"
    if path.exists():
        age = (time.time() - path.stat().st_mtime) / 86400
        if age < refresh_days:
            return json.loads(path.read_text())

    import yfinance as yf

    rec = {"ticker": ticker, "fetched": time.strftime("%Y-%m-%d"), "ok": False}
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        fin = t.financials
        bs = t.balance_sheet

        rec["market_cap"] = _safe(info, "marketCap")
        rec["sector"] = info.get("sector")

        def row(df, *names):
            if df is None or df.empty:
                return None
            for n in names:
                if n in df.index:
                    s = df.loc[n].dropna()
                    if len(s):
                        return s
            return None

        rev = row(fin, "Total Revenue", "TotalRevenue")
        ni = row(fin, "Net Income", "NetIncome", "Net Income Common Stockholders")
        ebit = row(fin, "EBIT", "Operating Income", "OperatingIncome")
        interest = row(fin, "Interest Expense", "InterestExpense")

        if rev is not None and len(rev) >= 2:
            rec["revenue_growth"] = float(rev.iloc[0] / rev.iloc[1] - 1) if rev.iloc[1] else None
            rec["revenue"] = float(rev.iloc[0])
        if ni is not None and len(ni) >= 2 and ni.iloc[1]:
            rec["profit_growth"] = float(ni.iloc[0] / abs(ni.iloc[1]) - 1)
            rec["net_income"] = float(ni.iloc[0])
        if ebit is not None:
            rec["ebit"] = float(ebit.iloc[0])
            if interest is not None and abs(interest.iloc[0]) > 0:
                rec["interest_cover"] = float(ebit.iloc[0] / abs(interest.iloc[0]))

        debt = row(bs, "Total Debt", "TotalDebt")
        cash = row(bs, "Cash And Cash Equivalents", "CashAndCashEquivalents")
        equity = row(bs, "Stockholders Equity", "StockholdersEquity", "Total Stockholder Equity")

        if debt is not None:
            nd = float(debt.iloc[0]) - (float(cash.iloc[0]) if cash is not None else 0.0)
            rec["net_debt"] = nd
            if rec.get("ebit"):
                rec["net_debt_ebit"] = nd / rec["ebit"] if rec["ebit"] > 0 else 99.0
        if equity is not None and rec.get("ebit"):
            cap = float(equity.iloc[0]) + max(rec.get("net_debt", 0.0), 0.0)
            if cap > 0:
                rec["roce"] = rec["ebit"] / cap

        rec["ok"] = rec.get("revenue_growth") is not None
    except Exception as e:
        rec["error"] = str(e)[:200]

    path.write_text(json.dumps(rec, indent=1))
    return rec


def apply_gate(
    tickers: list[str],
    thresholds: dict | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Returns a DataFrame with one row per ticker, a boolean `passed`, and a
    `reasons` string listing every failed check.

    Tickers whose data could not be parsed get passed=False and reason
    'no_data' -- they go to a review queue, never silently into the basket.
    """
    th = {**THRESHOLDS, **(thresholds or {})}
    rows = []

    for i, tk in enumerate(tickers, 1):
        if verbose and i % 25 == 0:
            print(f"  gate {i}/{len(tickers)}")
        f = fetch_fundamentals(tk)
        reasons = []

        if not f.get("ok"):
            rows.append({"ticker": tk, "passed": False, "reasons": "no_data", **f})
            continue

        rg = f.get("revenue_growth")
        if rg is None or rg <= th["min_revenue_growth"]:
            reasons.append(f"revenue_growth={rg}")

        pg = f.get("profit_growth")
        if pg is None or pg <= th["min_profit_growth"]:
            reasons.append(f"profit_growth={pg}")

        nd = f.get("net_debt_ebit")
        if nd is not None and nd > th["max_net_debt_ebitda"]:
            reasons.append(f"net_debt/ebit={nd:.1f}")

        ic = f.get("interest_cover")
        if ic is not None and ic < th["min_interest_cover"]:
            reasons.append(f"interest_cover={ic:.1f}")

        rc = f.get("roce")
        if rc is not None and rc < th["min_roce"]:
            reasons.append(f"roce={rc:.2%}")

        mc = f.get("market_cap")
        if mc is not None and mc < th["min_market_cap"]:
            reasons.append(f"market_cap_too_small")

        rows.append({
            "ticker": tk,
            "passed": len(reasons) == 0,
            "reasons": "; ".join(reasons) if reasons else "",
            "revenue_growth": rg,
            "profit_growth": pg,
            "roce": rc,
            "net_debt_ebit": nd,
            "interest_cover": ic,
            "market_cap": mc,
            "sector": f.get("sector"),
        })

    df = pd.DataFrame(rows).set_index("ticker")
    if verbose:
        n_pass = int(df["passed"].sum())
        n_nodata = int((df["reasons"] == "no_data").sum())
        print(f"  gate: {n_pass}/{len(df)} passed, {n_nodata} missing data (review queue)")
    return df

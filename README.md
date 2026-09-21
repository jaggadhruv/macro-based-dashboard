# Macro cycle baskets

Free-data sector rotation and stock screening for Indian and US equities.

Measures where each themed group sits in its own cycle, buys a fundamentally
screened basket when the group turns up, exits the basket when it rolls over.

**Not investment advice.** Screening output for your own research.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py
python run.py
```

`run.py` opens the dashboard at `http://localhost:8000`. Don't double-click
`docs/index.html` — browsers block it from reading local data files.

## Documentation

| File | What it covers |
|---|---|
| `HOW_TO_USE.md` | **Start here.** The monthly routine, position sizing, a worked example |
| `GUIDE.md` | Setup, validating before risking money |
| `CONCEPTS.md` | Every concept used and the reasoning behind it |
| `PUBLISH.md` | Hosting it free on GitHub Pages, auto-refreshed daily |

## Layout

```
themes.py           your universe, grouped into themes      ← edit this
run.py              the only entrypoint; CONFIG holds the knobs ← and this
engine/cycle.py     oscillator, signals, ranking, baskets
engine/signals.py   MA distance + slope, ATR extension, RVol, setups
engine/ranking.py   sector scores, zones, drivers, top picks
engine/technical.py trend template, base/squeeze detection, entry+stop+target
engine/forward.py   analyst estimate revisions, forward growth, hard rejects on cuts
engine/quality.py   the gate every recommendation passes: not falling + fundamentals + forward
engine/gate.py      fundamental screen
fetch/prices.py     OHLCV fetch and cache
report/snapshot.py  JSON emitter for the static site
report/dashboard.py standalone local HTML (opens without a server)
docs/               the published site
ledger/             immutable signal record — never delete
ledger/private/     anything with real amounts; gitignored
```

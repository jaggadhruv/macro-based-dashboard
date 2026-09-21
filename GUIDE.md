# Cycle Basket System — build and run guide

Everything here is free to run. Python, a text editor, and a browser.

---

## Part 1 — What your friend's system actually is

Read from the screenshots, not from what he says about it.

| Element | Evidence in the posts | Reading |
|---|---|---|
| **Universe** | "my own list of 350 stocks", "Nifty 750" | A curated mid/small-heavy list, not an index |
| **Trigger** | An oscillator chart with `NEW CYCLE` at the troughs, `TAKE PROFITS` at the peaks | A mean-reversion breadth or momentum oscillator, not a discretionary call |
| **Selection** | `Rank 1` … `Rank 8` per basket, 16 stocks across two baskets | Rank the universe on the signal date, take the top N |
| **Weighting** | `T1 [70%] R1–R4`, `T2 [30%] R5–R8`, and elsewhere "give equal weightage" | Tiered by rank, or flat — he runs both |
| **Exit** | "System triggers ENTRY & EXITS as a basket rather than individual stocks" | Whole basket in, whole basket out. No per-name management |
| **Parallel themes** | `SECTOR MOMENTUM [THEMES]` and `[THEMES 2]` have **different cycle dates** (17 Dec 2025 / 20 Feb 2026 vs 13 Jan 2026 / 27 Feb 2026) | Each theme has its own oscillator computed over its own members. This is the smartest part of the design |
| **Cadence** | "It triggers monthly once on an average" | Across all themes combined. An individual basket is held far longer |
| **Hold length** | 30 May 2022 → 13 Mar 2023 ≈ 9.5 months. 17 Mar 2025 → 09 Mar 2026 ≈ 12 months | **9–12 months per cycle**, not 3–6 |

His own words confirm the theme logic: *"Top is 1 basket where macro is different, bottom is another basket with another macro basket… one outperforms the other based on which macro plays well."* That is a portfolio of independent regime bets, and it's genuinely well conceived.

### What is missing from it

1. **No fundamental screen.** Pure momentum ranking. His published baskets contain `BLUEJET (-60.48%)` and `FIVESTAR (-51.40%)` — closed at those levels.
2. **No stop loss.** Positions are held from trough to peak regardless of what happens between. That is where the -60% names come from.
3. **No position-level risk control**, only basket-level entry and exit.

---

## Part 2 — Read the returns honestly

This matters more than the code, because it determines how much money you put behind it.

**The headline numbers are backtests, and they carry at least three biases.**

- **Universe selection is the big one.** A list of 350 stocks assembled today contains the names that survived and did well. `CGPOWER (2039%)`, `GVT&D (1238%)`, `NEULANDLAB (591%)` are exactly the names anyone building a list in 2026 would include, and would not have obviously included in 2021. This single effect can inflate a backtest by several multiples.
- **Parameter instability.** The same theme appears twice with different totals and different cycle dates — `[THEMES 2]` reads 1049.80% in one screenshot and 1489.16% in another, with cycle dates 13 Jan 2026 / 27 Feb 2026 in one and 13 Mar 2023 / 03 Feb 2025 / 09 Mar 2026 in the other. Re-fit parameters produce re-fit history.
- **No costs shown.** Nothing visible for brokerage, impact, or short-term capital gains tax. At 9–12 month holds in India you are just inside the short-term window, which is the worst possible place to sit.

**Now the numbers that are probably real**, because they are forward-looking and modest:

- *"last 8 months, it has picked 4 swing trades, clocked 41% booked and 19% current one running"*
- The live theme in the most recent screenshot: total 242%, with recent cycles at 4.22%, 12.43%, 6.41%

**41% booked over 8 months is a genuinely good result.** It is also roughly one-thirtieth of what the 1031% and 1489% figures imply. Build to the forward numbers, not the backtest ones. If the system delivers 20–30% a year net of costs it is excellent; expecting 300% will make you size positions in a way that ruins you on the first bad cycle.

None of this makes him wrong or dishonest — backtests on curated universes flatter *everyone*, and he is publishing his live results too, which most people don't. It just means you should build your own version and validate it forward before it carries real size.

---

## Part 3 — How this merges with your existing design

Your seven-layer design and his cycle system are complementary, not competing.

| Your layer | What happens now |
|---|---|
| L1 Regime gate | **Absorbed.** The per-theme oscillator *is* the regime gate, and it's better than one market-wide reading because it fires per theme |
| L2 Macro state | **Kept, demoted to context.** Displayed on the dashboard, not in the trigger. His system proves price-based breadth carries the macro signal already |
| L3 Policy extraction | **Kept as a tiebreaker.** When two themes signal in the same month and you can only fund one, policy decides |
| L4 Sector scorecard | **Replaced by the oscillator.** Simpler, fully reproducible, and it produces a date rather than a ranking. This is a real simplification of your design |
| L5 Universe filter | **Kept.** Becomes the theme lists |
| L6 Quality gate | **Kept — this is your main upgrade over his system.** Runs on ~20 candidates per signalling theme |
| L7 Sizing, exits, ledger | **Kept, and this is the second upgrade.** His system has no stop; yours has a 20% basket stop and a time stop |

**Net effect: your design gets simpler and his gets safer.**

### One decision you need to make

Your locked design says **3–6 months tactical**. His cycles run **9–12 months**. His large winners come from the long holds — `NEULANDLAB 591%` and `CGPOWER 2039%` are not three-month moves.

Three options:

- **Follow the cycle** (`max_hold_days = 252`). Highest expected return, but you carry full drawdowns and every exit is short-term for tax.
- **Cap at 6 months** (`max_hold_days = 126`). Matches your stated horizon, truncates winners, more tax events.
- **Follow the cycle but trail a stop after 6 months.** Keeps the upside, caps the giveback.

The code ships with `max_hold_days = 252`. Change it in `run.py` → `CONFIG` once you've decided.

---

## Part 4 — Setup (about 30 minutes, once)

### Step 1 — Install Python

You need Python 3.10 or newer. Check:

```bash
python3 --version
```

If that fails, install from python.org (Windows/macOS) or `sudo apt install python3 python3-pip` (Linux).

### Step 2 — Put the project somewhere permanent

Unzip `macro_rotation` into a folder you won't accidentally delete. Then:

```bash
cd macro_rotation
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

The `.venv` keeps these libraries separate from the rest of your system. You need to run the `activate` line every time you open a new terminal.

### Step 3 — Run it

One command does everything: decides whether prices need downloading, processes both
markets, writes both pages, starts a local server and opens your browser.

```bash
python run.py
```

The first run downloads about ten years of prices for ~470 tickers and takes 5-8
minutes. Later runs reuse the cache and finish in seconds, re-downloading only when the
cache is more than a few days stale.

**From PyCharm or another IDE:** the green Run button works with no arguments. Just make
sure the run configuration points at `run.py`.

Useful variations:

| Command | What it does |
|---|---|
| `python run.py` | Everything. This is the one you want |
| `python run.py --fresh` | Force a re-download even if the cache looks current |
| `python run.py --offline` | Never download; use the cache only |
| `python run.py --market india` | One market instead of both |
| `python run.py --no-gate` | Skip the fundamental screen (faster) |
| `python run.py --no-serve` | Write files without opening a browser |

Watch the output for ticker warnings:

```
WARNING: N tickers lack history: ...
```

**Fix those in `themes.py` before trusting anything.** A theme quietly running on 9
members instead of 30 gives a noisy oscillator and nothing will tell you.

### Step 4 — Read the dashboard

The browser opens on the **Overview** page:

- **Top 5 picks** across every sector, capped at two per sector
- **Leading** (green) — cycle triggered, or top-ranked with breadth confirming
- **Building** (amber) — no signal yet, but the oscillator is climbing. Your watchlist
- **Avoid** (red) — weak and still deteriorating
- **Ranked table** of every sector, sortable

- **Technical buy setups** — names whose chart, base, volatility and volume agree, each
  with an entry, stop, target and reward-to-risk. Filter by setup type

**Theme detail** has the oscillator chart, cycle history, held basket and **top 20
drivers** for each sector.

On the technical setups: they are entry mechanics, not predictions. Every one carries a
stop, and the arithmetic only works if you take it. At the default quality floor the
filter fires on roughly 6% of pure random walks, so treat it as the last filter after the
sector zone and the quality gate — never as a standalone reason to buy.

The terminal also prints the zones and picks before the browser opens, so you can read
the answer without leaving your editor.

A self-contained copy you can double-click, email or archive is written to
`data/reports/dashboard-<market>-<date>.html` on every run.

### Step 5 — Turn the gate on

```bash
python run.py --market india
```

(No `--refresh` reuses cached prices, so this is fast. No `--no-gate` means fundamentals now run.)

The first gated run pulls financials for ~20 names per live theme and caches each for 80 days. Expect a few minutes. Names that fail print their reasons; names whose data won't parse are marked `no_data` and excluded rather than assumed good.

### Step 6 — Do the same for the US

```bash
python run.py --market us
```

Same flow, and no manual queue at all — US data is clean.

---

## Part 5 — Validate before risking money

**Do not trade this yet.** Three checks first.

### Check 1 — Does the oscillator find sensible cycles?

Open the dashboard and look at each oscillator chart. Entries should sit near visible troughs and exits near peaks. If a theme shows 15 signals in 8 years it's too twitchy — widen the zones (`entry_zone: 20`, `exit_zone: 80`). If it shows one, it's too slow — narrow them (`30` / `70`).

Tune this by *looking at the shape*, not by maximising returns. Optimising the zones against past returns is exactly how you build something that only works on history.

### Check 2 — What is the worst case?

In each theme's closed-cycles table, find the largest `Max DD`. That is roughly what you should expect to live through, and the next one can be worse. If a theme shows -25% drawdowns and you'd sell in a panic at -15%, either size it smaller or skip it.

### Check 3 — Paper trade two cycles

Write down each basket when it signals. Do not put money in. Score it at the exit. You need to see the system be wrong at least once before you trust it, because everyone can hold a winner.

**This is what your ledger folder is for.** Every run writes `ledger/YYYY-MM-DD-market.json` with the config, the oscillator reading, and the exact basket. It is immutable and timestamped — this is the accountability mechanism the reference website never had.

---

## Part 6 — The monthly routine (about 20 minutes)

Pick a fixed day. First trading day of the month is fine. The system is designed to be checked monthly, not daily — that's a feature.

```bash
cd macro_rotation
source .venv/bin/activate
python run.py
python run.py --market us
```

Then open both dashboards and read them in this order:

1. **Any theme newly showing `IN CYCLE`?** That's a new basket. Check the gate results — if 3 of the top 8 failed, ask why before funding it.
2. **Any theme that flipped to `FLAT`?** That's an exit. Sell the whole basket, don't keep favourites.
3. **Any open basket near its stop?** The engine flags stops on the next run, but if a basket is down 15%+ decide in advance what you'll do at 20%.
4. **Nothing changed?** That's the normal case. Close the laptop. Most months should be boring.

### Sizing across themes

If three themes are live at once, that is three baskets of eight names — 24 positions. Split capital equally per theme, not per name, so each theme is one unit of risk. Keep total deployment at or below what your worst historical drawdown says you can carry.

---

## Part 7 — Files and what to change

```
macro_rotation/
├── themes.py            ← EDIT THIS: your universe, grouped into themes
├── run.py       ← EDIT CONFIG: zones, stop loss, hold length
├── engine/
│   ├── cycle.py         oscillator, signals, ranking, basket, walk-forward
│   └── gate.py          fundamental screen + thresholds
├── fetch/prices.py      yfinance + parquet cache
├── report/dashboard.py  HTML generator
├── data/                cached prices, fundamentals, generated dashboards
└── ledger/              immutable record of every run — never delete
```

**The two knobs that matter:**

`themes.py` — the universe. Adding names to a theme changes both its oscillator and its candidate pool. Do this deliberately and note the date, because it breaks comparability with earlier cycles.

`run.py → CONFIG` — `entry_zone` / `exit_zone` control how often you trade; `stop_loss` controls how much you can lose in one cycle; `max_hold_days` is the horizon decision from Part 3.

---

## Part 8 — Next upgrades, in order of value

1. **Replace the yfinance gate with XBRL** (SEC `companyfacts` for US, BSE Reg-33 filings for India). Same interface, much more reliable. This is the biggest quality win.
2. **Add NSDL FPI fortnightly sector holdings** as a confirmation input — it tells you whether foreign money is actually moving into a theme that just signalled.
3. **Add DGTR / PIB policy rows** as the tiebreaker when several themes signal at once.
4. **Widen the India universe to Nifty 500** once two results seasons have run cleanly — this is your Phase 2 gate, and it's where the mid-cap edge lives.

---

## A note on what this is

This produces a screened shortlist from public price and financial data. It is not advice, and it isn't a prediction. The system will have losing cycles — the ribbon on the dashboard will show red segments, and that is the design working, not failing. Size positions so that the worst historical drawdown is something you can sit through without selling at the bottom.

# How to actually use this

One command, twenty minutes a month, in a fixed reading order. Everything below
assumes you have run `python run.py` at least once.

---

## Part 1 — The monthly session

Pick a day and keep it. First trading day of the month works. Then:

```bash
cd macro_rotation
.venv\Scripts\activate          # Windows;  source .venv/bin/activate  on Mac/Linux
python run.py
```

It refreshes prices if they're stale, processes both markets, prints a summary, and opens
the dashboard. Two to eight minutes depending on whether it needs to download.

**Read in this order. The order is the method — it stops you starting from a ticker you
already like and reasoning backwards.**

| Step | Where | The question you're answering |
|---|---|---|
| 1 | Zone blocks | Is anything **green**? Where is money rotating? |
| 2 | Zone blocks | What's **amber**? What should I be watching for next month? |
| 3 | Zone blocks | What's **red**? What do I refuse to buy this month, whatever it looks like? |
| 4 | **Inside each green sector** | Which 5 names in *that* sector? Shown right under it |
| 5 | Top 5 picks | The cross-sector view, capped at two per sector |
| 6 | Technical setups | Is today a sensible entry price? |
| 7 | Theme detail | Only if something looked odd and I want to know why |

**If nothing is green, you are done. Buy nothing.** Most months should end here. A
rotation system that finds something to do every month isn't a rotation system.

---

## Part 1b — What every recommendation has already passed

The bar at the top of the overview reads:

```
EVERY RECOMMENDATION PASSED  ✓ not falling  ✓ fundamentals  ✓ estimates not being cut
```

**Not falling** — above a rising 200-day, within 25% of its 52-week high, up over six
months, no fresh 52-week low. A short pullback inside an uptrend is allowed; a decline is
not. Low *share price* is irrelevant — only falling matters.

**Fundamentals** — revenue and profit growing, returns above the cost of capital, debt
under control.

**Estimates not being cut** — analysts haven't cut EPS estimates more than 5% in 90 days,
aren't net cutting, and don't expect a loss or a sharp earnings fall.

Each pick card also shows a **Forward** score (0–100) with a coverage badge. `high` means
five or more analysts follow the name; `none` means no coverage, scored as average. A pick
with rising estimates *and* high coverage is the strongest case the tool produces.

If the bar shows fundamentals and estimates **struck through**, that run used `--no-gate`
and checked price structure only. Run without it before acting.

---

## Part 2 — The position sizing formula

This is the most important arithmetic in the whole tool, and it takes ten seconds.

```
Shares = (Capital × Risk%) / (Entry − Stop)
```

Risk% is how much of your **total capital** you accept losing if the stop is hit. Use
**1%**. Not 1% of the position — 1% of everything.

Worked: capital ₹5,00,000, risk 1% = ₹5,000. A setup with entry ₹237 and stop ₹226 risks
₹11 per share. `5000 / 11 = 454 shares`, a position of about ₹1,07,600.

That position is 21% of your capital, which *sounds* enormous — but if the stop is hit you
lose ₹5,000, or 1%. **The stop, not the position size, is what determines your risk.** A
tight stop earns a bigger position; a loose one forces a smaller one, automatically.

Two caps on top: no single position above 20% of capital, no single sector above 35%.

---

## Part 3 — A worked example, three months

Illustrative numbers, showing the shape of a real sequence. Capital ₹5,00,000, 1% risk per
position.

### Month 1 — the first run

Terminal prints:

```
INDIA  (data through 2026-04-03)
  LEADING   Capital goods
  BUILDING  Power & utilities, Metals & materials
  AVOID     IT & digital
  TOP PICKS
    1. CARBORUNIV.NS   Capital goods    score 82.3  pullback  [pullback 3.2R]
    2. CUMMINSIND.NS   Capital goods    score 78.7  trend
    3. TATAPOWER.NS    Power & utilities score 77.3 trend
    ...
  TECHNICAL SETUPS (23 total, best 5)
    SRF.NS        breakout  q 83.3  entry 236.96  stop 225.63  target 304.22  risk 4.8%  5.9R
    ...
```

**Step 1.** Capital goods is green — "cycle entry triggered, basket held". One sector, not
five. Good; that's normal.

**Step 2.** Power & Utilities and Metals are amber. Write them down. Don't buy them.

**Step 3.** IT is red. It will keep appearing in momentum lists all month. Ignore it.

**Step 4.** Expand the green sector. Its own top 5 sit right underneath:

```
Capital goods                                    score 82   ▾
  #  Ticker          Score  Close   RS 1M    3M   Ext  State      Entry / stop / target
  1  CARBORUNIV.NS      82  1,842  +6.2%  +19%   0.7  pullback   pullback 1,842 / 1,749 / 2,121  3.2R
  2  CUMMINSIND.NS      79  3,410  +4.8%  +14%   1.3  trend      no technical entry yet
  3  THERMAX.NS         74  4,102  +3.1%  +11%   2.1  trend      no technical entry yet
  4  KEI.NS             71  3,240  +2.4%   +9%   0.4  pullback   pullback 3,240 / 3,088 / 3,696  3.0R
  5  ABB.NS             68  6,880  +1.9%   +7%   2.8  extended   no technical entry yet
  Top 5 of 30 members; 14 excluded as not buyable today.
```

Two things to read here. **Rank 1 and rank 4 have technical entries** — those rows are
shaded, and they're the only two that come with a stop. **14 of 30 members were excluded**
as not buyable: below a falling 50-day, stretched past 3 ATR, or failed the screen. That
count is itself information — when 25 of 30 are excluded, the sector's move has already
happened.

**Step 5.** The cross-sector Top 5 confirms CARBORUNIV at #1.

**Step 6.** Open the technical card for the full detail:

```
CARBORUNIV.NS   pullback   q 71   entry 1,842   stop 1,749   target 2,121   risk 5.0%   3.2R
                pulled back to a rising 50-day in an intact uptrend; volume drying up (0.6x)
```

Sizing: risk per share = 1842 − 1749 = ₹93. `5000 / 93 = 53 shares` ≈ ₹97,600.

Write down, before buying: **entry 1,842 · stop 1,749 · target 2,121 · 53 shares · max
loss ₹5,000.**

Pick 2 (CUMMINSIND) has no technical setup — the sector is right but there's no defined
entry. Skip it. It'll still be there next month.

### Month 2 — one works, one doesn't

CARBORUNIV is at ₹1,988. Up 8%. Do nothing: it hasn't hit the target, the sector is still
green, the stop stays at 1,749.

New this month: Power & Utilities has gone **amber → green**. TATAPOWER shows a breakout,
entry ₹412, stop ₹389, 3.8R. Risk per share ₹23 → `5000/23 = 217 shares` ≈ ₹89,400.

Now two positions, ₹1,87,000 deployed of ₹5,00,000. Total risk if both stops hit: ₹10,000,
or 2%.

### Month 3 — a stop gets hit, which is the point

CARBORUNIV ran to ₹2,130, above target. You sold half at target and trailed the rest — or
you sold it all. Either is fine, as long as you decided *before* you were in it.

TATAPOWER dropped to ₹385. **Below the ₹389 stop.**

Sell it. Today. At a loss of ₹5,859.

This is the part that decides whether the system works. At 45% wins and 3:1 reward, the
expectancy is `0.45 × 3 − 0.55 × 1 = +0.80R` per trade. Let losers run to −3R instead of
−1R and that goes **negative** — same hit rate, same signals, same tool. The edge is
entirely in taking the stop.

Also this month: Capital goods dropped out of green. That closes the basket thesis, so any
remaining Capital goods position is exited regardless of profit.

---

## Part 4 — Situations, and what each one means

| What you see | What to do |
|---|---|
| Nothing green | Buy nothing. Hold cash. This is normal and correct |
| Green sector, #1 pick has a technical setup **and** rising estimates | The strongest case the tool produces. Size it and take it |
| Pick has a forward score but coverage is `low` | One analyst. Treat the forward score as a hint, not evidence |
| Green sector, most members excluded from its top 5 | The move already happened. Be sceptical of what's left |
| Green sector, pick has **no** technical setup | The *what* is right, the *when* isn't. Add to watchlist |
| Technical setup in an **amber** sector | Half a signal. Smaller size, or wait for the sector to turn green |
| Technical setup in a **red** sector | Skip. This is the trap the red zone exists to mark |
| Five greens at once | Broad rally. Cap total deployment; don't take all five at full size |
| A held sector turns from green to neutral for two months | Thesis gone. Exit the basket |
| Position down 20% from its peak | The basket stop. Exit, whatever the dashboard says |
| A sector jumps amber → green | That's the tool working. Amber existed to warn you |

---

## Part 5 — What not to do

**Don't skip the zone reading and jump to Top 5 Picks.** The picks are *derived* from the
zones. Reading them alone discards the reasoning and leaves you with a momentum list.

**Don't buy a name because it's extended and rising.** The `Ext` column is ATRs above the
20-day. At 3+, you're chasing — the tool excludes those from picks for a reason.

**Don't take a setup without writing the stop down first.** If you didn't record it, you
won't honour it.

**Don't run this daily and act daily.** Refresh as often as you like; act monthly. The
temptation to trade what changed since yesterday is what the monthly cadence exists to
suppress.

**Don't tune the parameters because last month disappointed.** Eight knobs, and searching
them against past returns will always find a combination that looks excellent and won't
repeat. Freeze them until the ledger has years, not months, of data.

**Don't treat 5 picks as a portfolio.** It's a shortlist to research. Five concentrated
positions carry real single-name risk, and the score says nothing about correlation
between them.

---

## Part 6 — First three months: do it on paper

Before any money:

1. **Month 1** — run it, write down the picks and every stop. Buy nothing.
2. **Month 2** — check what happened. Were the green sectors actually stronger?
3. **Month 3** — check again. Did a stop get hit? Would you have taken it?

You need to watch the system be wrong once before you trust it. Everyone can hold a
winner.

The `ledger/` folder does this automatically — every run writes a timestamped record of
the zones, the picks, and the technical setups with their stops, *before* you act. That's
what makes the review honest three months later. Never delete it.

---

## Part 7 — The one-page version

```
MONTHLY
  python run.py
  1. Green sectors?        → none, stop here
  2. Amber?                → watchlist only
  3. Red?                  → refuse all month
  4. Expand each green sector → its own top 5, with stops
  5. Cross-sector Top 5 as a cross-check
  6. Technical setup on that name? → entry, stop, target
  7. Shares = (Capital × 1%) / (Entry − Stop)
  8. Write down the stop. Then buy.

HOLDING
  Stop hit             → sell today
  Target hit           → sell, or sell half and trail
  Sector leaves green  → exit the basket
  Down 20% from peak   → exit the basket
  Nothing changed      → do nothing

CAPS
  1% capital risk per position
  20% capital max per position
  35% capital max per sector
```

Not investment advice. Every number here is a screen for your own research, and the
example figures are illustrative, not predictions.

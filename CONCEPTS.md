# Concepts and reasoning

Why every piece of this system exists, what it assumes, and how each one fails.

Read this before you change any parameter. Most of the ways to break a system like
this look like improvements at the time.

---

## The one-paragraph version

Groups of related stocks move together in cycles. When most members of a group are
below their long moving average and then start climbing back above it, the group has
probably turned. That turn is measurable, it's dateable, and it doesn't require you to
predict anything. So: **measure the turn (breadth), wait for confirmation, buy the
strongest members that also pass a quality check, hold as one basket, exit when the
group rolls over or the loss gets too large.** Every layer below is a defensible answer
to one sub-problem inside that sentence.

---

# Part A — Measuring where a group is in its cycle

## A1. Breadth, not price

**The concept.** Breadth is the percentage of members of a group that are above their
own 200-day moving average. It's a count, not an average.

**Why not just use the sector index?** An index is capitalisation-weighted, so a
sector index can rise while most of its members fall — two large names carry it. That
tells you the wrong thing about whether the *group* is healthy. Breadth counts every
member once, so it answers "is this a broad move or a narrow one?" and narrowness is
the standard warning sign before a group rolls over.

There's also a mechanical reason. You're going to buy 8 names from a list of 20. You
need to know the state of the 20, not the state of the 3 that dominate the index
weight.

**Why 200 days?** It's roughly ten months of trading. The choice sets what counts as
"the trend" — a 50-day average makes the measure react to every swing, a 200-day
average only registers something that has persisted for months. Since you're trying to
catch cycles that run 9–12 months, the reference line needs to be roughly on that
timescale.

**How it fails.** A group where every member is a leveraged play on the same commodity
gives you breadth that's really just one signal counted twenty times. Breadth's value
comes from members being *somewhat* independent. If you build a theme of 15 tickers
that all move on the crude price, breadth tells you about crude, not about the theme's
internal health.

```python
ma = prices.rolling(200).mean()
raw = (prices > ma).sum(axis=1) / valid.sum(axis=1) * 100
```

## A2. Smoothing

**The concept.** A 10-day moving average over the raw breadth reading.

**Why.** Raw breadth is jumpy. On a single volatile day, a dozen names can cross their
moving average and cross back the next day. Without smoothing you'd get signals from
noise.

**The trade-off is unavoidable and worth naming.** Every unit of smoothing you add
removes a whipsaw and adds lag. There is no setting that gives you both. Ten days is a
deliberate compromise: enough to kill single-day noise, short enough that you're not
finding the turn a month after it happened. If you widen it to 30, expect fewer false
signals and later entries.

## A3. Percentile ranking — turning breadth into a 0–100 oscillator

This is the least obvious step and the most important one.

**The problem it solves.** Raw breadth is not comparable across time. In a strong bull
market, 60% of names above their 200DMA might be a *weak* reading. In a bear market,
60% would be extraordinary. A fixed threshold like "buy below 30%" means completely
different things in different eras.

**The fix.** Instead of the raw number, ask: *where does today's reading sit within the
last three years of readings for this same group?* An oscillator value of 15 means
"breadth is in the bottom 15% of everything we've seen recently." That's a statement
that means the same thing in 2021 and 2026.

```python
osc = smoothed.rolling(750).apply(lambda w: (w <= w[-1]).mean() * 100)
```

**Why 750 days (~3 years).** Long enough to contain several full cycles, so the
percentile has something to rank against. Short enough that a structural change in the
sector eventually washes out of the window. Widen it and extremes become rarer and
more meaningful; narrow it and you'll signal more often on less information.

**The critical implementation detail:** `w[-1]` is today, and `w` is the trailing
window ending today. Nothing from the future enters. If you ever rewrite this using a
whole-history percentile, you've introduced look-ahead bias and every backtest after
that point is fiction.

**How it fails.** A sector in genuine secular decline will keep producing "low
percentile, must be a bottom" readings all the way down, because the window keeps
re-baselining to the new lower normal. Percentile ranking assumes mean reversion within
the window. Structural decline breaks that assumption, and no oscillator setting fixes
it — only the fundamental gate does.

## A4. One oscillator per theme

**The concept.** Each theme's breadth is computed over its own members only.

**Why this is the best idea in the source system.** A single market-wide gate says
"risk-on" or "risk-off" for everything at once. But pharma and capital goods don't
bottom on the same date. Computing breadth per theme lets each group signal on its own
schedule — which is exactly what the screenshots show: `[THEMES]` and `[THEMES 2]` with
different cycle dates in the same period.

**The second-order effect** is what makes it valuable as a portfolio. If eight themes
signal independently, you naturally stagger entries across the year rather than
deploying everything at one moment. That's diversification across *time*, which is
harder to get than diversification across names and does more for you.

**The requirement:** a theme needs enough members for the percentage to be stable. The
code drops any theme under 8 usable names. Below that, one stock crossing its moving
average moves breadth by 12+ points and the oscillator is mostly noise. Aim for 12–20.

---

# Part B — Turning the measurement into a date

## B1. What the trigger actually assumes

Be clear about this: the entry rule is a **mean-reversion bet on the group**, and the
selection rule is a **trend-following bet on the individual names**. Buy the group when
it's beaten down; within it, buy the names already recovering.

That combination isn't arbitrary. It's the observation that groups oscillate but
individual leadership persists. Both halves have to hold for the system to work, and
they can fail separately — which is why the dashboard's attribution matters.

## B2. Waiting for the turn, not the touch

**The concept.** Entry does not fire when the oscillator drops below 25. It fires when
the oscillator has *been* below 25 and then closes above it for three consecutive days.

**Why.** "Low" and "bottoming" are different states. An oscillator falling through 25
can keep falling to 5 and sit there for four months. If you buy the first touch, you
have bought early and you will hold through the remainder of the decline with no
information about when it ends.

Requiring the cross back up means you're buying evidence of a turn rather than evidence
of cheapness. You give up the exact low — you'll enter maybe 3–8% above it — in
exchange for not catching a falling knife. That's a good trade.

Look at the source system's chart: `NEW CYCLE` markers sit at the V-bottoms, slightly
after them, not on the way down. Same logic.

**Why three days of confirmation.** One day of crossing back above is easy noise. Three
consecutive closes is a meaningfully harder bar. Raise it to 5 for fewer false starts
and later entries.

## B3. The four-state machine

```
flat ──(osc ≤ 25)──> armed ──(3 closes > 25)──> long ──(osc ≥ 75)──> primed ──(3 closes < 75)──> flat
```

**Why states rather than a simple threshold test.** Without memory, an oscillator
oscillating around 25 would fire an entry every time it wiggled across. The `armed`
state records "we have been in the low zone" so that the entry can only fire *once* per
visit. `primed` does the same for exits. This is the difference between a system that
trades 4 times in 8 years and one that trades 40 times.

## B4. Why entry and exit zones aren't symmetric in effect

Entry at 25 and exit at 75 look symmetric, but they don't behave symmetrically, because
breadth spends more time high than low in a rising market. Expect exits to fire more
readily than entries. If you find the system rarely entering, the entry zone is doing
the constraining — widen it to 30 before touching anything else.

**Do not tune these against past returns.** Tune them by looking at the oscillator
chart and asking whether the markers sit near visible turns. The moment you start
picking zones because they produced better backtest numbers, you're fitting to history
and your forward results will disappoint in exactly the amount you gained.

---

# Part C — Choosing which names to buy

## C1. Cross-sectional momentum

**The concept.** Rank every member of the theme by recent return relative to *each
other*, and buy the top of the ranking.

**Why momentum at all.** The tendency for relative winners over 3–12 months to keep
outperforming over the following months is one of the most widely documented patterns
in equity markets, going back to Jegadeesh and Titman's work in the early 1990s and
replicated across markets and decades since. It is not a guarantee and the effect has
weakened as it became well known, but it's a far more solid empirical footing than most
things a retail system could be built on.

**Why "cross-sectional" matters.** You're not asking "has this stock gone up?" — you're
asking "has it gone up more than its peers?" That comparison automatically strips out
the common factor. If the whole theme rose 30%, a name that rose 30% ranks in the
middle, not near the top. You're isolating relative strength, which is the part that
persists.

## C2. Three lookback windows

```python
lookbacks = (63, 126, 252)     # ~3, 6, 12 months
weights   = (0.4, 0.4, 0.2)
```

**Why three instead of one.** Any single window is fragile — a name that spiked 40% in
one week eleven months ago dominates a 252-day ranking long after the move is over.
Blending three windows means a name has to be strong on multiple timescales to rank
highly, which filters out one-off jumps.

**Why 3 and 6 months are weighted heaviest.** You're buying at a cycle turn. The
12-month window still contains the decline you're buying the recovery from, so it's
partly measuring the wrong thing. The shorter windows capture "who is leading the
turn," which is what you actually want. The 12-month window stays at 20% as a check
that the name isn't a dead-cat bounce.

## C3. Ranking the returns before combining them

```python
score += ret.rank(pct=True) * w
```

**The subtlety.** The code converts each window's returns to percentile ranks *before*
blending, rather than averaging the raw returns.

**Why.** Raw returns have wildly different scales across windows and across market
conditions. A 12-month window in a recovery might have returns from -20% to +180%; a
3-month window might span -5% to +25%. Averaging those directly lets whichever window
happens to have the widest spread dominate the blend — and which one that is changes
month to month.

Converting to ranks (0 to 1) puts every window on the same scale, so the weights you
set are the weights you actually get.

## C4. Volatility adjustment

```python
haircut = (vol / vol.median()).clip(0.5, 2.0)
score = score / haircut
```

**The concept.** Divide the momentum score by how volatile the name is, relative to the
theme's median volatility.

**Why.** A 60% gain in a name that typically swings 25% a year is a much stronger signal
than a 60% gain in one that swings 80% a year. The second is closer to noise. Without
this adjustment, the highest-volatility names win the ranking almost every time — you'd
systematically buy the most speculative member of every theme, which is precisely how
you end up with a `-60%` name in your basket.

This is the same intuition behind risk parity: equal *risk* contribution beats equal
capital when the underlying assets differ wildly in volatility.

**Why the `clip(0.5, 2.0)`.** Without bounds, an unusually quiet name gets an enormous
score boost and can top the ranking on stability alone, with barely any momentum. The
clip caps the adjustment at 2× in either direction, so volatility can reorder the
ranking but cannot single-handedly determine it.

**How it fails.** Volatility is measured over the trailing 63 days — a name that was
quiet during the decline and is about to become violent looks safe. Trailing volatility
is always a lagging estimate of future volatility.

## C5. The individual 200DMA filter

```python
out = out[out["above_200dma"]]
```

**The concept.** Drop any name trading below its own 200-day average, even if it ranks
well.

**Why, when the theme has already signalled.** The theme trigger says "the group has
turned." This says "and this specific name has turned too." A name still below its
200DMA when its peers have recovered is telling you something specific about that
company — usually that the market knows something the momentum score doesn't.

This is a cheap filter that catches the case where a name ranks highly only because it
fell less than everything else during the decline. Falling least is not the same as
rising.

---

# Part D — The quality gate

## D1. Why fundamentals are a gate, not a ranker

**The reasoning.** Over a 9–12 month hold, quality metrics do not predict which name
performs best — momentum and flows do. But quality does predict which name *blows up*.
Those are different jobs.

So the gate is binary and runs before selection. It doesn't nudge the ranking; it
removes names entirely. A company can have exceptional ROCE and still rank 15th on
momentum, and it stays 15th — quality earns it eligibility, not a promotion.

**The promotion mechanic.** When a top-ranked name fails the gate, the slot isn't left
empty; the next eligible name moves up. This matters: a gate that shrank your basket
from 8 to 5 in bad quarters would silently concentrate your risk exactly when
conditions are worst.

## D2. What each check is actually for

| Check | Threshold | What it catches |
|---|---|---|
| Revenue growth (TTM YoY) | > 0 | The business is not shrinking. Momentum can carry a declining business for a quarter or two; it cannot for a year |
| Profit growth (TTM YoY) | > 0 | Growth that isn't reaching the bottom line — usually competitive pressure or cost inflation the market hasn't priced yet |
| ROCE | > 12% India, > 10% US | **Whether growth creates or destroys value.** A company earning 8% on capital that costs it 12% gets *less* valuable as it grows. This is the check that separates growth from expansion |
| Net debt / EBIT | < 3× | Survives a demand or rate shock. Highly levered names are the ones that gap down 40% on one bad quarter |
| Interest coverage | > 3× | The same risk from the income side. Coverage below 3 means most of operating profit services debt |
| Share count growth | < 5% | Per-share growth is what you own. A company growing revenue 20% while issuing 15% more shares grew your stake by very little |
| Market cap floor | ₹2,000cr / $2B | Your explicit "ignore very small" requirement — and separately, small caps have wide spreads that eat the edge |

## D3. Why ROCE and not ROE

ROE can be manufactured with leverage. Borrow money, buy back shares, shrink the
denominator, and ROE goes up while the business gets riskier. ROCE uses total capital
employed — debt plus equity — so leverage doesn't flatter it. For a screen that's
partly trying to avoid over-levered companies, ROE would be actively misleading.

## D4. Cash conversion — the one to add first

The current gate uses yfinance data, which doesn't reliably expose cash flow for Indian
tickers. **When you move to XBRL, add CFO/EBITDA > 0.6 (3-year average) as your first
new check.**

**Why it's the single most valuable filter.** Revenue and profit are accounting
judgments — revenue recognition timing, inventory valuation, receivables policy all
give management legitimate discretion. Cash in the bank is not a judgment. A company
reporting rising profits while cash flow stays flat is usually recognising revenue it
hasn't collected, and that gap closes eventually, always downward.

Almost every accounting blow-up shows up in the profit-to-cash gap a year or more before
it shows up in the price.

## D5. Why the gate runs on ~20 names, not the whole universe

Pure engineering economics. Fetching fundamentals is the slowest, most fragile, most
rate-limited part of the pipeline. Running it on 350 names monthly would take hours and
get you throttled. Running it on the top 20 of a theme that just signalled takes under a
minute.

The ordering — cheap price filters first, expensive fundamental checks last, on the
smallest possible set — is what makes a free-data pipeline viable at all. It's the same
principle as putting the selective `WHERE` clause before the expensive join.

## D6. `no_data` is a failure, not a pass

If fundamentals can't be parsed, the name is excluded and flagged for review. This is
deliberate and it's the opposite of what's convenient.

Free data fails **silently**. A parser that returns nothing looks identical to a
parser that returns nothing because the company is fine. If missing data defaulted to
"pass," your gate would quietly stop working the moment the data source changed its
format, and you'd find out from your P&L.

---

# Part E — Portfolio construction

## E1. Basket in, basket out

**The concept.** The whole basket is bought on the signal date and sold on the exit
date. No trimming winners, no adding to losers, no per-name calls.

**Why this is more than laziness.** The signal is about the *group*, so the position
should be about the group. The moment you start managing individual names you've
replaced a rule-based system with your own judgment, and you'll do it asymmetrically —
selling winners early and holding losers, which is the single most reliably documented
behavioural error in retail trading.

There's also a measurement argument. If you intervene, you can no longer tell whether
the system works. The dashboard's cycle history becomes a record of your decisions
rather than the system's, and you've lost the ability to learn from it.

## E2. Tiered weighting: 70% across ranks 1–4, 30% across ranks 5–8

**What it assumes.** That the momentum ranking carries real information — rank 2 is
genuinely more likely to outperform than rank 7 — but not enough information to bet
everything on rank 1.

**Why not just equal-weight all 8?** That throws away the ranking entirely. If you
believe the score means nothing, you shouldn't be ranking.

**Why not weight proportionally to score?** That over-trusts small score differences.
The gap between rank 3 and rank 4 is usually within the noise of the estimate; treating
it as meaningful is false precision.

The two-tier structure is the honest middle: **the ranking is informative enough to
separate a top half from a bottom half, and not informative enough for anything
finer.** Equal weight within each tier reflects exactly that.

The source system uses the identical structure — `T1 [70%] R1–R4`, `T2 [30%] R5–R8` —
and elsewhere runs flat equal weight. Both are defensible. Flat weight is more robust if
you doubt the ranking; tiered has higher expected return if you trust it.

## E3. Why eight names

Below about 5, single-name risk dominates and one bad pick determines the basket.
Above about 12, you're increasingly buying the theme average and paying commissions for
the privilege — the marginal name is adding diversification you already had.

Eight sits where most of the diversification benefit has been captured while the
ranking still has real influence on the outcome.

## E4. Sizing across themes, not across names

If three themes are live, split capital by theme first, then within the theme by the
tier weights. **Each theme is one unit of risk**, regardless of how many names it holds.
Sizing per name instead would give a live 3-theme portfolio triple the exposure of a
1-theme portfolio, entirely by accident.

---

# Part F — Risk control

## F1. The basket stop, measured from the peak

```python
dd = curve / curve.cummax() - 1.0      # drawdown from the basket's own high
```

**Why from the peak and not from entry.** Suppose a basket rises 40%, then falls 25%.
Measured from entry it's still up 5% — no stop. Measured from its peak it's down 25%,
which is a serious deterioration and probably the cycle rolling over. The peak-based
measure treats the same deterioration identically whether it happens early or late.

This is the fix for the biggest gap in the source system. Holding trough-to-peak with
no stop is how you get `BLUEJET (-60.48%)` and `FIVESTAR (-51.40%)` closed at those
levels.

**Why 20%.** It needs to be wide enough to survive normal volatility in a basket of
mid-cap equities — a 10% stop would trigger constantly and turn a cycle system into a
churn machine. It needs to be narrow enough that recovery is plausible: recovering from
-20% requires +25%, from -50% requires +100%. The asymmetry gets punishing fast.

**Check your own history before accepting 20%.** The dashboard's `Max DD` column shows
what each theme actually did. If a theme routinely breathes -18%, a 20% stop will fire
on noise.

## F2. The time stop

**The concept.** Close a basket after a fixed number of trading days regardless of the
oscillator.

**Why.** The oscillator can fail to reach the exit zone for years if a theme grinds
sideways. Without a time stop you can hold dead capital indefinitely, and at this
turnover, opportunity cost is a real expense. It also bounds your maximum exposure to
any single thesis being quietly wrong.

## F3. Drawdown is the number that matters, not return

The dashboard shows both. Read the drawdown column first, every time.

**Why.** Returns tell you what happened to the money. Drawdown tells you whether you'd
have still been in the position when it did. A system with a 30% average return and a
45% drawdown is unusable by most people, because almost nobody holds through -45% —
they capitulate near the bottom and realise the loss without the recovery.

**Size to the drawdown you can actually sit through**, not the return you'd like.

---

# Part G — Epistemics: how a system like this lies to you

This section is the difference between a tool and a story.

## G1. Look-ahead bias

**What it is.** Using information at time *t* that wasn't available at time *t*.

**How it sneaks in.** Percentile-ranking over the full history instead of a trailing
window. Ranking on returns computed to today's date rather than the entry date. Using
restated financials for a decision made before the restatement.

**How the code guards against it.** Every window is trailing (`rolling`), and
`rank_members` slices `prices.loc[:as_of]` before doing anything. If you modify the
engine, this is the invariant to preserve: *nothing at date t may touch a row after
date t.*

## G2. Survivorship bias — the one that inflates the source system

**What it is.** Testing on a universe assembled today, which by construction contains
the companies that survived and did well.

**Why it's the dominant bias here.** A hand-curated list of 350 stocks built in 2026
includes CGPOWER and GVT&D *because* they already returned 2039% and 1238%. Backtest
that list to 2022 and those returns appear as if the system found them. It didn't — the
list did. This single effect can inflate a backtest by several multiples, and it's
invisible in the output.

**What to do.** You can't fully fix this without point-in-time index membership, which
isn't free. So: treat any backtest of your own theme lists as an upper bound, note the
date you last edited `themes.py`, and weight the forward ledger far more heavily than
any historical figure.

## G3. Overfitting

**What it is.** Choosing parameters because they worked on history.

**Why it's seductive here.** There are at least eight knobs — two zones, confirm days,
MA window, smoothing, percentile window, lookbacks, weights, stop, hold length. Search
that space against past returns and you will *always* find a combination that looks
excellent. It will not repeat.

**The tell.** The source system's `[THEMES 2]` appears with 1049.80% in one screenshot
and 1489.16% in another, with different cycle dates. That's what re-fitting looks like
from the outside.

**The discipline.** Set parameters from reasoning about what they *mean* — 200 days
because the cycle is ~10 months, 20% stop because recovery from deeper is implausible —
then freeze them. Change a parameter only when you can state the mechanical reason,
before you look at what it does to returns.

## G4. Sample size

Four cycles is not evidence. Neither is eight.

With outcomes this variable, distinguishing a system with genuine edge from a lucky one
takes dozens of independent observations. A cycle system that trades ~1–2 times per
theme per year, across 8 themes, produces maybe 10–15 observations a year — and they're
not fully independent, since themes share macro exposure.

**Practical consequence: you will not know whether this works for two or three years.**
That isn't a reason not to run it. It's a reason to size positions as though you don't
know, because you don't.

## G5. Why the ledger is the actual product

Every run writes an immutable, timestamped record: config, oscillator reading, exact
basket, weights, prices. Written *before* you act.

**Why this matters more than any single feature.** It's the only mechanism that lets
you distinguish these cases when a cycle loses money:

- The theme signalled correctly, the stock selection was poor → fix the ranking
- The theme signalled wrongly → fix the oscillator or the theme composition
- Both were fine, the timing was unlucky → change nothing

Without the record, every loss becomes a story, and the story is always that you were
right in spirit. That's exactly the failure mode of the reference website: confident
narrative, unauditable numbers, no scoreboard.

**Never delete the `ledger/` folder.** It is the only thing in this project that gets
more valuable over time.

---

## Summary: what has to be true

| The system works if | It fails if |
|---|---|
| Themed groups oscillate in measurable multi-month cycles | Groups drift without cycling, or cycle faster than the oscillator can see |
| Breadth turning up marks the turn better than chance | Breadth lags too much, or the theme is in secular decline |
| Relative strength within a group persists a few months | Momentum reverses at short horizons in your universe |
| Fundamental quality predicts blow-ups | Blow-ups come from things financials don't show |
| You can hold through the drawdowns | You capitulate near the bottom |

The last row is the one most systems die on, and it's not a technical problem.

---

# Part H — Technical state: where a name is *today*

The cycle engine answers "is this group turning?" and "which members lead?". Neither
question tells you whether a name is a sensible entry *today*. These four measurements
close that gap. They were the most useful thing to take from a second reference system.

## H1. Distance from a moving average, plus its slope

**The concept.** For each of the 20-, 50- and 200-day averages, record how far price sits
from it *and* whether that average is rising or falling.

**Why both.** "Above the 50-day" is a single bit of information and it conflates two
opposite situations. A name 3% above a **rising** 50-day is in an intact uptrend that has
pulled back to support. A name 3% above a **falling** 50-day is a dead-cat bounce into
resistance. Same boolean, opposite meaning.

Our original engine only used the boolean. The slope is what disambiguates it.

**How slope is measured.** Compare the average to itself `w/4` sessions ago — 5 sessions
for the 20-day, ~12 for the 50-day, 50 for the 200-day. Scaling the lookback to the
window's own length keeps the sensitivity consistent: a fixed 5-day lag would make the
200-day average look flat almost always.

## H2. ATR extension — the entry-timing number we were missing

**The concept.** How many Average True Ranges is price above its 20-day average?

**Why it matters.** Momentum ranking is deliberately blind to this. A name that just ran
30% in three weeks ranks at the top — and is also the worst possible entry, because the
first normal pullback takes back a chunk of it.

Expressing the distance in **ATRs rather than percent** is what makes the number
comparable across names. A 10% extension means nothing on its own: for a quiet large cap
it's an enormous move, for a volatile mid cap it's a Tuesday. Dividing by that name's own
typical daily range normalises it. Roughly:

- **0–1 ATR** — near the average. Normal entry zone
- **1–3 ATRs** — moving, still reasonable
- **3+ ATRs** — stretched. Buying here is chasing

**Why true range and not high-minus-low.** True range takes the widest of today's span,
today's high vs yesterday's close, and today's low vs yesterday's close. A name that gaps
5% overnight and then trades flat has moved 5%, and a high-minus-low measure would score
it as calm. Gaps are exactly where risk lives.

**The proxy caveat.** Without high/low data the code falls back to mean absolute daily
*close-to-close* change, which systematically understates true range — so extensions look
larger than they are. The output flags this as `atr_is_proxy`. Fetching OHLCV rather than
close-only is why the price cache stores four fields.

## H3. Relative volume

**The concept.** Today's volume against its own 50-day average.

**Why.** A move on half-normal volume has few participants behind it and reverses easily.
A breakout on 2× volume has real repositioning behind it. It's a confirmation input, never
a trigger on its own — high volume accompanies capitulation just as readily as accumulation,
so it tells you a move is *real*, not which direction it resolves.

## H4. Named setups

Combining the above into one label — `pullback`, `trend`, `extended`, `rally_weak`,
`broken`, `neutral` — so the dashboard can answer a question the cycle engine can't:
*given that I should own this basket, which names are buyable right now?*

**Order of evaluation matters.** `extended` is checked first, before the attractive
states, so a stretched name can never be labelled a good entry.

**`pullback` is the one to act on.** Above a rising 50-day (trend intact), down on the
week (price came back to you), within one ATR of a rising average (not falling through
it). This is the entry the momentum ranking alone will never find, because by
construction it prefers whatever just went up most.

**`rally_weak` is the one to recognise.** Below a falling 50-day but up on the week. It
looks like strength in a one-week return column and it is the most common trap a momentum
screen walks into. It's displayed so you learn to see it, not to buy it.

## H5. Where these fit

Deliberately **advisory, not automatic**. The basket is still bought as a basket on the
signal date — introducing "wait for a pullback on each name" would fragment entries,
reintroduce discretion, and destroy the measurability that makes basket trading work.

What they're for: when several themes signal in the same month and you can only fund
some, the one whose members are mostly `pullback` and `trend` is a better entry than the
one whose members are mostly `extended`. That's a tie-break, not an override.

## H6. Why the group breadth number is displayed raw

The theme tracker shows `>50d` — the raw percentage of a theme's members above their
50-day — alongside the percentile-ranked oscillator.

**Why show both.** The oscillator is *relative* to the theme's own history: a reading of
80 means "high for this group." The raw percentage is *absolute*: 45% of members above
their 50-day is objectively middling regardless of history. A theme can read 90 on the
oscillator with only 50% of members participating, which tells you the group has been
weak for years and this is merely its best state recently. Relative and absolute
disagreeing is information.

---

# Part I — Ranking, zones and picks

The cycle engine answers one theme at a time. This layer compares themes to each other
and produces the three things a per-theme view cannot: a league table, a traffic-light
classification, and a single list of best names. Nothing new is measured here — it only
ranks and labels what earlier layers computed.

## I1. Why the sector score is a percentile, not an absolute

Each component is percentile-ranked **against the other sectors in the same market** on
the same day, then blended. A score of 80 means "stronger than 80% of these sectors right
now."

**Why relative.** There is no stable absolute scale for "how good is a sector." A 4%
monthly gain is excellent in one regime and mediocre in another. Ranking sidesteps the
question: you are choosing between sectors, so the comparison that matters is between
them.

**The cost, which is important.** *Something always ranks first, including in a market
where everything is falling.* A score of 95 means "least bad" just as easily as "strong."
This is why the zone classification exists and why the dashboard shows raw breadth
alongside the score — the absolute numbers are what stop you buying the best house on a
burning street.

## I2. Weights, and why oscillator slope carries so much

| Component | Weight | What it answers |
|---|---|---|
| RS 1M | 22% | Is money moving here now |
| RS 3M | 15% | Is it a trend or a week |
| Breadth (% above 50d) | 20% | Broad move, or two names carrying it |
| Trend vs 200d | 13% | Is the long-term structure intact |
| **Oscillator slope** | **18%** | **Is the cycle improving** |
| Oscillator level | 12% | Where in its own range it sits |

**Slope is the only forward-looking component**, and it is the one that makes the
"building" zone possible. Everything else describes what has already happened.

**Level alone is useless without slope.** A theme reading 40 on the way up and a theme
reading 40 on the way down are opposite situations with identical levels. That
distinction is measured as the change over the last 20 sessions.

## I3. The three zones

The classification is a decision tree, and the order of the checks is deliberate.

**Leading (green)** — a cycle entry has actually triggered, *or* the sector scores ≥68
with a rising 50-day and at least half its members above their own 50-day. Rank alone is
never enough, because rank is relative.

**Avoid (red)** — checked *before* building, so a broken sector cannot be rescued by a
small bounce. Bottom-ranked with a falling oscillator, or breadth collapsed below 25%
with the long-term trend down.

**Building (amber)** — every path in requires a **rising oscillator**. No exceptions.
This is enforced by an invariant test: no negative slope may ever produce "building".

That rule matters more than it looks. Without it, a high-scoring sector whose oscillator
is collapsing would be painted amber — and that is precisely the sector that has already
had its run. Labelling it "building momentum" would invite the exact wrong trade at the
exact wrong moment. A high score with a falling oscillator is reported as *"ranks high but
the cycle is rolling over — late, not early."*

**One deliberate exception inside 'avoid'.** A sector with thin breadth but a *strongly*
surging oscillator (+8 or more in a month) is classified building, not avoid. At a genuine
cycle trough, breadth is low by definition — that is what a trough is. Vetoing on low
breadth alone would hide exactly the entries this system exists to find. The reason text
still flags the thin breadth so you know what you are looking at.

**Why 'building' is the most valuable zone.** The cycle engine is binary: signalled or
not. That leaves you blind between signals. Building names the sectors that have not
triggered but are repairing, which is where the next entries come from. It is a
watchlist, never a buy.

## I4. Drivers — who is actually moving a sector

Because the group index is equal-weight, each member contributes its own return divided by
the member count. So `contribution_1m = ret_1m / n_members`, and the top 20 by contribution
are literally the names responsible for the sector's move.

**Why rank on a 1M/3M blend rather than 1M alone.** A single spiking week would otherwise
crown a name that has gone nowhere over the quarter.

**What the driver list is for.** It answers a question the basket cannot: *why* is this
sector moving, and is it broad or concentrated? If the top 3 drivers account for most of a
sector's gain and the other 27 are flat, the sector's strength is an illusion that breadth
alone might not catch at a 30-name resolution.

## I5. Top picks — and its honest limitations

Each candidate's score is `0.40 × sector score + 0.45 × its own strength within the
sector + setup adjustment`, with a +5 bonus if the sector has actually triggered a cycle.

**Hard exclusions before scoring**, because these are disqualifying rather than
penalising: below a falling 50-day, stretched past 3 ATRs, or failed the fundamental gate.

**The two-per-sector cap is the most important line in that function.** Without it, the
strongest sector supplies all five names and you own one bet wearing five tickers. The cap
forces at least three sectors into the list.

**Two lists, one scoring function.** The cross-sector Top 5 and the per-sector top 5
shown inside each zone block run through the identical scoring and the identical hard
exclusions — verified by a test asserting every cross-sector pick carries the same score in
its own sector's list. The only difference is the two-per-sector cap, which the per-sector
list deliberately has none of, because there the point is to see one sector's leaders side
by side.

**The excluded count is part of the output.** A sector showing "top 5 of 30 members, 25
excluded" is telling you its move has largely happened: almost everything is stretched or
below a falling average. A sector showing 5 of 30 with 10 excluded has room left. That
ratio is often more informative than the picks themselves.

**Avoid sectors get no buy list at all.** Not a filtered one, not a collapsed one — none.
Ranking the least-bad names in a deteriorating sector would contradict the label, and those
names are precisely the trap the red zone exists to mark.

**What this output is not.** Five names is a *ranking*, not a portfolio. Concentration
into five positions carries real single-name risk, and the score says nothing about
position sizing, correlation between the picks, or what to do when one is wrong. Treat it
as the shortlist to research, not the trade to place.

**And the scoring weights are priors, not findings.** They were set by reasoning about what
each component means, not fitted to past returns — deliberately, since fitting them to
history is how you build something that only works on history. They should not be tuned
until the forward ledger has enough observations to say anything, which will take years,
not months.

---

# Part J — Technical setups

Parts A–I answer "which sector, which names". This part answers a different question:
**at what price, with what stop, risking how much.** A name can be the right pick and
still be the wrong buy today.

## J1. Signal versus state

The `setup` label in Part H describes a *state* — "this name is in a pullback". A signal
is a state plus three numbers: entry, stop, and target.

**Why the stop is the part that matters.** Without it, a "buy signal" is an opinion. With
it, the trade has a defined maximum loss, a measurable reward-to-risk ratio, and a
condition under which you were wrong. Everything in this module exists to produce those
three numbers honestly — the pattern recognition is the easy half.

## J2. The trend template

An eight-point structural filter, in the spirit of the widely used Minervini template:
price above the 150- and 200-day, 150 above 200, the 200-day rising, the 50-day above
both, price above the 50-day, at least 30% off the 52-week low, within 25% of the
52-week high, and not sitting at the low.

**It is a filter, not a signal.** It says the structure is sound enough to consider a
long. It says nothing about timing, and a name can satisfy all eight points and still be
a terrible entry because it is stretched.

**Seven of eight, not eight of eight.** Demanding a perfect score is brittle — during a
normal pullback, "price above the 50-day" fails by construction, and that is exactly when
you want to be buying. Individual setups require six.

## J3. The four setups

| Setup | What has to be true | Where the stop goes |
|---|---|---|
| **Breakout** | Clears a base's high, base under 30% deep, volume ≥1.3× average, not stretched past 3.5 ATR | Base low, or 2.5 ATR |
| **Pullback** | Rising 50-day, down on the week, price still above the 200-day and within 4% of the 50-day, 1–3.5 ATR below the 20-day | Recent swing low, or just under the 50-day |
| **Squeeze** | 20-day range in the bottom 15th percentile of 120 sessions, holding the top of a base | Base low |
| **Reclaim** | Back above the 50-day from below, rising 20-day, volume confirming | Recent swing low |

**Ordering is deliberate.** Breakout is checked first, then squeeze, then pullback, then
reclaim. Squeeze sits ahead of pullback because when volatility is at an extreme low, that
is the more informative description of the chart even if the week happens to be slightly
down.

**Reclaim is flagged as the weakest and scores a zero setup bonus.** It is the earliest in
a turn and the most likely to be a bounce inside a downtrend. It is included because
catching a genuine reversal early is valuable; it is labelled because most of them are not
genuine.

**Pullback gates allow real depth.** An early version required price strictly above the
50-day and capped the pullback at 1.5 ATR. Both were wrong: normal pullbacks run 2–3 ATR
below the 20-day and routinely undercut the 50-day intraday. Gates that tight would only
ever have fired on pullbacks so shallow they weren't worth taking.

## J4. Volatility contraction, and why it predicts nothing directional

The squeeze score is the current 20-day range as a percentile of its own last 120
sessions. Volatility **clusters and mean-reverts**: quiet periods are followed by active
ones. So a tight range is a *pre-move* condition.

**It says nothing about direction.** A coil can resolve either way, which is why it is
never used alone here — only combined with the trend filter and a requirement that price
sits in the upper half of its base. Even then, a squeeze is a watch, not a buy.

## J5. Stops, targets and the rejection rules

The stop is the *tightest* of: the structural level (base low or swing low), 2 ATR below
entry, and a hard 12% cap. Targets are the base's measured move where one exists,
otherwise three times the risk.

Two rejections happen after the setup is identified, and both matter:

- **Risk above 12% of entry** — rejected. A wide stop turns a 2% position into a real
  loss, and a stop that far away usually means the structure isn't tight yet.
- **Reward-to-risk under 2:1** — rejected. A good-looking chart at a bad price is not a
  trade. This single rule removes more setups than the pattern rules do.

## J6. The quality score is confluence, not any one factor

Structure 30, reward-to-risk 20, stop tightness 15, volatility contraction 10, volume
confirmation 10, relative strength 10, setup-type bonus 5.

**Why confluence.** Any single technical indicator is close to noise. The value comes from
demanding that trend, structure, volatility and volume independently agree — each one is
weak, and the conjunction is much less common than any of them alone.

## J7. Base rates — the number the reference site never published

Measured on 200 synthetic series per population, at the default quality floor of 60:

| Population | Signal fires |
|---|---|
| Uptrend into a base | ~32% |
| Steady uptrend | ~21% |
| **Pure random walk** | **~6%** |
| Downtrend | ~1% |

Read that table honestly. **Technical patterns appear in random data.** About one in
sixteen pure random walks produces a setup that clears every filter. The trend template is
doing real work — downtrends almost never fire — but no filter abolishes the problem.

This is precisely the base-rate disclosure missing from the reference material in Part 3:
listing the times a signal preceded a move, without the times it fired and nothing
happened, is an anecdote in table form.

**The practical consequence.** The technical layer is the *last* filter, not the first.
Its job is to time an entry into a name the sector and quality layers already selected.
Trading these signals on their own, ignoring the zone and the gate, means trading the 6%
noise rate as often as the real thing.

## J8. What the win rate has to be

A setup like this might resolve favourably 40–50% of the time. At 3:1 reward to risk that
is comfortably profitable — but **only if the stop is taken every time**.

The arithmetic is unforgiving. At 45% wins and 3:1, expectancy is `0.45 × 3 − 0.55 × 1 =
+0.80R` per trade. Let a few losers run to −3R instead of −1R and expectancy goes
negative, at the same hit rate, with the same signals. The edge here lives entirely in the
discipline of the exit, not in the cleverness of the entry.

---

# Part K — Forward expectations and the quality gate

## K1. What was missing

Until this layer, every input described the past: breadth, momentum, moving averages,
even the fundamental gate (last year's reported revenue and profit). The only
forward-leaning piece was the oscillator's slope, and that is still built from past
prices.

**A correction to something stated earlier in this project.** Part 6.2 said free data
gives reported results but not analyst revisions. That was too strong. Yahoo publishes the
consensus EPS estimate as it stood 7, 30, 60 and 90 days ago, which is exactly what a
revision signal needs. Coverage for Indian mid-caps is thin and the data is only as good
as Yahoo's feed — but it is buildable for free.

## K2. Why revisions, not estimates

The **level** of an estimate is already public and largely in the price. The **change**
is new information. When analysts raise estimates they tend to do so gradually, over
several weeks, after new information arrives — so the direction of recent revisions
carries some information about the next few. This is among the better-documented
forward-looking signals in equity research, and it is the heaviest component here.

| Component | Weight | Why this weight |
|---|---|---|
| Estimate revisions (30d, 90d; this year and next) | 45% | New information, not yet fully priced |
| Revision breadth (analysts raising vs cutting) | 15% | One analyst's +3% is weaker than eight analysts' |
| Forward EPS growth | 20% | What the business is expected to do |
| Forward vs trailing P/E | 10% | Growth expected to grow into the price; capped when forward P/E > 80 |
| Price-target upside | 10% | **Lightest, capped at +30%, ignored below 3 analysts** |
| Buy/sell ratings | 0% | Shown, never scored |

**Why targets and ratings get so little.** Sell-side price targets have a poor track
record and a well-known upward bias. Ratings skew so heavily toward "buy" that they barely
discriminate. They are displayed for context and excluded from the score.

**Weight in the overall pick score: 18%.** A name with strongly rising estimates scores
about 6 points above an otherwise identical name with flat ones. Meaningful, not dominant —
deliberately, because consensus estimates are noisy and herd together.

## K3. The hard reject — "something might be wrong"

Regardless of how strong the chart is, a name is removed when:

- this year's or next year's EPS estimate has been cut **more than 5% in 90 days**
- analysts cutting outnumber those raising by **3 or more** in 30 days, with a net cut
- a **loss** is expected next year
- earnings are expected to **fall more than 15%**

Falling estimates are one of the clearest early signs that a business is deteriorating,
and they frequently show up before the price does. This is the forward-looking version of
the "don't buy something that's breaking" instinct.

## K4. The missing-coverage trap, and how it was fixed

Many Indian mid-caps have no analyst coverage on Yahoo at all.

The first version handled this by re-weighting: without forward data, a name was scored on
sector and momentum alone. Testing exposed the problem. A strong uncovered name kept its
full score, while a covered name with *merely average* estimates had part of its score
replaced by a middling 50. **Being unexamined beat being examined and found ordinary**, and
three of the Top 5 turned out to be uncovered names.

The fix: missing coverage is scored as a neutral 50 — "no information" is treated as
"average expectations". Rising estimates now beat both; falling estimates are rejected
outright. Uncovered names can still rank highly, but on the strength of their sector and
trend rather than because nobody looked.

If you want only names that analysts actually follow, set
`"require_forward_coverage": True` in `run.py`. In India that effectively restricts
recommendations to larger, well-followed companies.

## K5. "Not falling" — the trend health gate

Six checks, all required:

| Check | Why |
|---|---|
| Above a **rising** 200-day average | The long-term trend itself is up |
| Within 25% of the 52-week high | Not a stock that has already broken down |
| Positive over 6 months | Not a decline, however it looks this week |
| Not down more than 8% over 3 months | Consolidation allowed, breakdown not |
| No new 52-week low in the last 6 months | Not a stock still making fresh lows |
| Holding the 50-day (or just under a *rising* one) | A dip, not a failure |

**The distinction it draws.** A *pullback* is a short dip inside an intact long-term
uptrend — allowed. A *decline* is when the long-term trend itself has rolled over —
refused. On a one-week chart they look identical. The 200-day average and the distance
from the 52-week high separate them.

Measured on 40 random paths per shape: a steady uptrend passes ~88% of the time, a normal
6-day pullback ~78%, a stock bouncing after a 35% fall **0%**, one rolling over from a top
**0%**. A sharp 12% drop inside an uptrend passes only ~12% — the gate reads a fast fall of
that size as a likely breakdown.

**The cost, stated plainly.** This gate will miss genuine turnarounds. Every recovery starts
from a falling stock, and this only admits a name once the recovery is well established.
That is a deliberate trade: fewer, later, safer entries. The `reclaim` technical setup is
switched off for the same reason — a reclaim is by definition a stock that was falling.

**On low share prices.** A low *nominal* price — a ₹40 share versus a ₹4,000 share — says
nothing about quality. Share count is arbitrary; a company can split its stock tenfold
without changing anything about the business. What matters is market capitalisation, which
the fundamental gate already floors. "Falling" is the thing worth avoiding, and that is
what this gate measures.

## K6. Unscreened is ineligible

The single most important change in this layer is not a new signal. Before it, the
fundamental gate only ran on live cycle baskets, and eligibility checked whether a name had
*failed* — so a name that was **never checked** counted as eligible. Most per-sector picks
and Top 5 names had never had their financials looked at.

Now every candidate is screened — the strongest 12 per sector that aren't falling, plus
every technical setup — and anything not positively screened cannot be recommended.

**A bug worth knowing about.** The first version of that check read
`quality_passed is not True`. Pandas returns `numpy.bool_`, and `numpy.True_ is True` is
**False** in Python — so every screened name was silently rejected and the pick lists came
back empty. Identity comparisons against booleans are unsafe anywhere pandas is involved;
the code now uses truthiness throughout.

## K7. Verification

With a stubbed mix of data — rising estimates, flat, sharp cuts, failing fundamentals, and
roughly a third with no coverage — every recommendation across the Top 5, all eight
per-sector lists and the technical setups was audited:

- names with estimates being cut: **0**
- names failing fundamentals: **0**
- names never screened: **0**
- technical setups failing either: **0**

Of 228 Indian names, about 87 passed the "not falling" gate on the test data — roughly 60%
of the universe is refused before anything else is checked. Expect the recommendation lists
to be noticeably shorter than before. That is the gate working.

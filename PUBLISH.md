# Publish it as a website

Free, automatic, and readable from any phone or laptop with the link.

```
GitHub Actions (every Saturday)  →  runs the pipeline
        ↓  commits docs/data/*.json back to the repo
GitHub Pages  →  https://<you>.github.io/<repo>/
```

Every page shows when it was last updated, in **your** timezone, with a coloured dot. On
the weekly schedule it stays **green all week**, turns **amber** once a Saturday run has
been missed, and **red** after two. If prices fall more than eleven days behind, a banner
says so outright. A hosted page that looks current but isn't is worse than no page.

---

## Before you start: what becomes public

Free GitHub Pages needs a **public repository**.

**Published:** sector zones and scores, ticker lists, weight *percentages*, entry/stop/
target levels, oscillator readings, cycle history.
**Never published:** rupee or dollar amounts, how much capital you deploy, broker details.

The project ships a gitignored `ledger/private/` for anything with real amounts. The
default `ledger/` files hold percentages only. You don't have to share the link with
anyone — the discipline works with an audience of one.

---

## Step 1 — Create the repo (10 min)

```bash
git --version          # install from git-scm.com if missing
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

On github.com: **New repository** → name it `macro-cycles` → **Public** → do **not** add a
README.

From inside the project folder:

```bash
git init
git add .
git commit -m "Cycle engine, technical scanner, static site"
git branch -M main
git remote add origin https://github.com/<your-username>/macro-cycles.git
git push -u origin main
```

GitHub asks for a password but wants a **personal access token**: Settings → Developer
settings → Personal access tokens → Tokens (classic) → tick `repo`. Save it in your
password manager.

**Then check nothing sensitive went up:**

```bash
git ls-files | grep -E "prices|private|fundamentals"
```

Should print nothing. If it prints anything, fix `.gitignore` before continuing —
scrubbing git history afterwards is painful.

---

## Step 2 — Turn on Pages (2 min)

**Settings → Pages → Build and deployment → Source: GitHub Actions.**

Not "Deploy from a branch". The workflow publishes the site itself; the branch option
relies on GitHub noticing a commit made by the workflow, which doesn't reliably happen.

---

## Step 3 — First snapshot

Run locally first so you can fix ticker problems before automation runs unattended.

```bash
python run.py
```

Fix any ticker warnings in `themes.py`, re-run until clean, then:

```bash
git add docs ledger
git commit -m "First snapshot"
git push
```

Refresh the Pages URL. Data should appear, with a green dot and "Updated just now".

---

## Step 4 — Turn on the schedule

**Settings → Actions → General → Workflow permissions** → **Read and write permissions**
→ Save.

Without this the job runs but can't push its results, and every run fails at the commit.

Test it by hand — don't wait for Saturday: **Actions** tab → **Update and publish** →
**Run workflow** → `both`.

You'll see two jobs. **update** takes 8–15 minutes the first time (ten years of prices,
plus fundamentals and analyst data for every candidate). **deploy** then takes about a
minute, and its box shows your site's URL when it finishes.

**If the whole run finishes in under 3 minutes, something failed early.** A real refresh
can't be that fast. Click into the run and find the red step.

### The schedule — weekly

```yaml
- cron: "30 2 * * 6"    # Saturday 02:30 UTC = 08:00 IST
```

One run a week, after **both** markets have closed on Friday (NSE at 15:30 IST, the US at
16:00 ET), so both carry the full week's closes. You'll see fresh data from Saturday
morning.

Cron in Actions is **always UTC** and never adjusts for daylight saving. Scheduled runs are
queued, so starting 5–30 minutes late is normal.

**Why weekly suits this system.** Decisions are made monthly; a weekly refresh is frequent
enough to see a position nearing its stop, and infrequent enough that you won't be tempted
to trade every wiggle.

### The two things weekly changes

**Staleness is judged against the weekly cadence.** `run.py` declares
`"refresh_every_days": 7`, and the page uses it. Without that, a weekly site would flag
itself stale every weekend — a false alarm that teaches you to ignore the real one.

**The cache usually expires between runs.** GitHub evicts cached files unused for 7 days,
which is exactly the weekly gap, so many runs re-download ten years of prices plus
fundamentals and analyst data. That takes several minutes instead of one, and slightly
raises the chance of Yahoo rate-limiting. Nothing breaks — it's just slower. The workflow
retries each market three times, 90 seconds apart.

**Cost: nothing.** Public repos get unlimited Actions minutes.

### Changing the frequency

Change **both** of these together:

| You want | Cron in `.github/workflows/update.yml` | `refresh_every_days` in `run.py` |
|---|---|---|
| Weekly, Saturday (**current**) | `"30 2 * * 6"` | `7` |
| Daily, weekdays | `"30 22 * * 1-5"` | `1` |
| Twice a week (Wed + Sat) | `"30 2 * * 3,6"` | `4` |

The 60-day rule: **scheduled workflows are disabled after 60 days of repository
inactivity.** A weekly commit keeps it alive — but if runs fail silently for two months,
the schedule stops for good. The amber/red dot is your warning; the Actions tab shows why.

---

## Step 5 — Put it on your phone

Open the Pages URL on your phone.

- **iPhone (Safari):** Share → Add to Home Screen
- **Android (Chrome):** ⋮ → Add to Home screen

It installs as a standalone app with its own icon, no browser chrome. The layout collapses
to one column on narrow screens, tables scroll sideways, and it follows your phone's
light/dark setting.

---

## When it breaks

Open **Actions**, click the run, click the job with the red ✕, and expand the red step.
The last 20 lines say why.

| What you see | Cause | Fix |
|---|---|---|
| Run finished in 1–3 minutes, site not updated | Failed during setup | Find the red step; see the rows below |
| **Check repository layout** is red: "Not found at the repository root" | The project is inside a subfolder of the repo (unzipping often creates `macro_rotation/macro_rotation/`) | Move the files so `run.py` sits at the top level, commit, push |
| Only a job called **pages build and deployment** ran | Pages is set to "Deploy from a branch" | Step 2: set Source to **GitHub Actions** |
| **deploy** is red: "Branch not allowed to deploy" | Your branch isn't called `main` | `git branch -M main` then `git push -u origin main` |
| **deploy** is red: "Get Pages site failed" | Pages isn't enabled | Step 2 |
| **Commit snapshot** red: "Permission denied" | Workflow can't push | Settings → Actions → General → Workflow permissions → Read and write |
| **Sanity-check output** red: "No snapshot files" | Every market failed to download | Open **Refresh snapshots**; usually Yahoo blocking GitHub's servers — re-run later, or run locally and push |
| Site loads but says "No snapshot yet" | Deploy ran, refresh didn't | Run the workflow manually |
| Amber dot on Sunday/Monday | Saturday's run failed | Check the Actions tab |
| Site shows old data after a run | Browser cache | Hard-refresh: Ctrl-Shift-R |

**Yahoo blocking GitHub** is the most likely long-term failure. GitHub's runners are
datacenter IPs, which Yahoo rate-limits. The workflow retries each market three times,
90 seconds apart. If it keeps failing, run `python run.py --no-serve` locally, then
`git add docs ledger`, commit and push — the deploy job publishes it within a minute.

---

## Running locally instead

```bash
python run.py
```

Serves at `http://localhost:8000` and opens your browser. **Don't double-click
`docs/index.html`** — browsers block a `file://` page from reading local data, so every
field comes up empty. A self-contained copy you *can* double-click is written to
`data/reports/dashboard-<market>-<date>.html` on every run.

---

## Why hosting it is worth the setup

1. **A URL.** Check your own system from your phone, anywhere.
2. **It runs whether or not your laptop is on.**
3. **An immutable, timestamped audit trail** kept by infrastructure you can't quietly edit
   after the fact. `git log docs/data/india.json` becomes a complete record of every signal
   you ever published. A ledger you *can* revise is not really a ledger.
4. **Working in the open keeps you honest.** A dashboard showing its losing cycles in red,
   in public, is much harder to tell yourself stories about.

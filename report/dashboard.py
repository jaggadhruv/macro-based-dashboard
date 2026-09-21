"""
Dashboard generator.

Produces one self-contained HTML file. No CDN, no build step, no server --
the chart is inline SVG rendered here in Python, interactivity is vanilla JS.
Open the file directly in a browser, or email it to yourself.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data" / "reports"
OUT.mkdir(parents=True, exist_ok=True)

CSS = """
:root{
  --paper:#EFF1EC; --card:#F8F9F6; --ink:#18211D; --ink-2:#5A665F;
  --rule:#CDD3CB; --long:#1F6F5C; --short:#A63D2F; --band:#D4A843;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
     font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:32px 24px 80px}
header{border-bottom:2px solid var(--ink);padding-bottom:16px;margin-bottom:28px}
h1{font-size:26px;font-weight:700;letter-spacing:-.02em;margin:0 0 4px}
.sub{font-family:var(--mono);font-size:12px;color:var(--ink-2);letter-spacing:.04em;text-transform:uppercase}
.tabs{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:24px}
.tab{font-family:var(--mono);font-size:12.5px;letter-spacing:.03em;padding:9px 15px;
     border:1px solid var(--rule);background:transparent;color:var(--ink-2);
     border-radius:3px;cursor:pointer;transition:.12s}
.tab:hover{border-color:var(--ink-2);color:var(--ink)}
.tab[aria-selected=true]{background:var(--ink);border-color:var(--ink);color:var(--paper)}
.tab:focus-visible{outline:2px solid var(--band);outline-offset:2px}
.panel[hidden]{display:none}
.card{background:var(--card);border:1px solid var(--rule);border-radius:4px;
      padding:20px 22px;margin-bottom:18px}
.card h2{font-size:12px;font-family:var(--mono);letter-spacing:.09em;text-transform:uppercase;
         color:var(--ink-2);margin:0 0 16px;font-weight:600}
.stats{display:flex;flex-wrap:wrap;gap:0;border:1px solid var(--rule);border-radius:4px;
       background:var(--card);margin-bottom:18px;overflow:hidden}
.stat{flex:1 1 150px;padding:16px 18px;border-right:1px solid var(--rule)}
.stat:last-child{border-right:none}
.stat .k{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;
         text-transform:uppercase;color:var(--ink-2);margin-bottom:5px}
.stat .v{font-family:var(--mono);font-size:22px;font-weight:600;letter-spacing:-.01em}
.state-open{color:var(--long)} .state-flat{color:var(--ink-2)}
table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:13px}
th{text-align:left;font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;
   color:var(--ink-2);font-weight:600;padding:0 10px 8px 0;border-bottom:1px solid var(--rule)}
td{padding:8px 10px 8px 0;border-bottom:1px solid var(--rule)}
tr:last-child td{border-bottom:none}
.num{text-align:right;font-variant-numeric:tabular-nums}
.pos{color:var(--long)} .neg{color:var(--short)}
.tag{display:inline-block;font-size:10px;letter-spacing:.06em;padding:2px 7px;
     border-radius:2px;border:1px solid currentColor}
.t1{color:var(--long)} .t2{color:var(--ink-2)}
.ribbon{display:flex;gap:3px;margin-top:6px}
.seg{flex:1;min-width:0;height:38px;border-radius:2px;position:relative;cursor:default;
     display:flex;align-items:center;justify-content:center;font-family:var(--mono);
     font-size:11px;color:#fff;font-weight:600}
.seg small{position:absolute;bottom:-17px;left:0;font-size:9.5px;color:var(--ink-2);
           letter-spacing:.02em;font-weight:400}
.ribwrap{padding-bottom:22px}
.note{font-size:13px;color:var(--ink-2);margin-top:12px;line-height:1.55}
.warn{border-left:3px solid var(--band);padding:12px 16px;background:#F6F1E2;
      border-radius:0 3px 3px 0;font-size:13.5px;margin-bottom:22px}
svg{display:block;width:100%;height:auto}
.legend{display:flex;gap:18px;font-family:var(--mono);font-size:11px;
        color:var(--ink-2);margin-top:10px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;
     vertical-align:middle}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--rule);
       font-size:12px;color:var(--ink-2)}
@media (max-width:640px){.wrap{padding:20px 14px 60px}.stat{flex:1 1 50%}h1{font-size:21px}}
"""


def _osc_svg(osc: pd.Series, signals: pd.DataFrame,
             entry_zone: float, exit_zone: float,
             w: int = 1100, h: int = 250) -> str:
    """Inline SVG of the oscillator with zone bands and cycle markers."""
    s = osc.dropna()
    if len(s) < 2:
        return '<p class="note">Not enough history to draw the oscillator yet.</p>'

    pad_l, pad_r, pad_t, pad_b = 42, 12, 12, 26
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b
    n = len(s)

    def X(i): return pad_l + (i / (n - 1)) * pw
    def Y(v): return pad_t + (1 - v / 100.0) * ph

    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(s.values))
    pos = {d: i for i, d in enumerate(s.index)}

    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Cycle oscillator">']
    parts.append(f'<rect x="{pad_l}" y="{Y(entry_zone):.1f}" width="{pw}" '
                 f'height="{ph - (Y(entry_zone) - pad_t):.1f}" fill="#1F6F5C" opacity=".07"/>')
    parts.append(f'<rect x="{pad_l}" y="{pad_t}" width="{pw}" '
                 f'height="{Y(exit_zone) - pad_t:.1f}" fill="#A63D2F" opacity=".07"/>')

    for lvl in (0, 25, 50, 75, 100):
        y = Y(lvl)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w - pad_r}" y2="{y:.1f}" '
                     f'stroke="#CDD3CB" stroke-width="1" stroke-dasharray="2 3"/>')
        parts.append(f'<text x="{pad_l - 7}" y="{y + 3.5:.1f}" text-anchor="end" '
                     f'font-family="ui-monospace,monospace" font-size="10" fill="#5A665F">{lvl}</text>')

    parts.append(f'<polyline points="{pts}" fill="none" stroke="#18211D" '
                 f'stroke-width="1.4" stroke-linejoin="round"/>')

    for _, r in signals.iterrows():
        if r["date"] not in pos:
            continue
        x = X(pos[r["date"]])
        col = "#1F6F5C" if r["signal"] == "ENTRY" else "#A63D2F"
        parts.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t + ph}" '
                     f'stroke="{col}" stroke-width="1.2" opacity=".65"/>')
        cy = Y(r["oscillator"])
        parts.append(f'<circle cx="{x:.1f}" cy="{cy:.1f}" r="4" fill="{col}" '
                     f'stroke="#F8F9F6" stroke-width="1.5"><title>'
                     f'{r["signal"]} {pd.Timestamp(r["date"]).date()}</title></circle>')

    step = max(1, n // 7)
    for i in range(0, n, step):
        parts.append(f'<text x="{X(i):.1f}" y="{h - 7}" text-anchor="middle" '
                     f'font-family="ui-monospace,monospace" font-size="10" fill="#5A665F">'
                     f'{s.index[i].strftime("%b %y")}</text>')

    parts.append("</svg>")
    return "".join(parts)


def _ribbon(cycles: list[dict]) -> str:
    """Signature element: cycle history as a strip of outcome-coloured segments."""
    if not cycles:
        return '<p class="note">No completed cycles yet.</p>'
    segs = []
    for c in cycles:
        r = c["basket_return"]
        col = "#1F6F5C" if r >= 0 else "#A63D2F"
        op = min(1.0, 0.42 + abs(r) * 1.6)
        segs.append(
            f'<div class="seg" style="background:{col};opacity:{op:.2f}" '
            f'title="{c["entry_date"].date()} to {c["exit_date"].date()} '
            f'({c["exit_reason"]}), {c["held_days"]} days">{r * 100:+.1f}%'
            f'<small>{c["entry_date"].strftime("%b %y")}</small></div>'
        )
    return f'<div class="ribwrap"><div class="ribbon">{"".join(segs)}</div></div>'


def _basket_table(basket: pd.DataFrame, gate: pd.DataFrame | None) -> str:
    if basket is None or basket.empty:
        return '<p class="note">No basket. The oscillator has not signalled an entry.</p>'
    head = ("<tr><th>#</th><th>Ticker</th><th>Tier</th><th class='num'>Weight</th>"
            "<th class='num'>6M</th><th class='num'>12M</th><th class='num'>Vol</th>"
            "<th class='num'>Rev gr</th><th class='num'>ROCE</th></tr>")
    rows = []
    for tk, r in basket.iterrows():
        g = gate.loc[tk] if gate is not None and tk in gate.index else None
        def fmt(v, pct=True):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return '<td class="num">—</td>'
            cls = "pos" if v >= 0 else "neg"
            return f'<td class="num {cls}">{v * 100:+.1f}%</td>' if pct else f'<td class="num">{v:.2f}</td>'
        tier = r.get("tier", "T1")
        rows.append(
            f"<tr><td>{r['basket_rank']}</td><td><strong>{tk}</strong></td>"
            f"<td><span class='tag {tier.lower()}'>{tier}</span></td>"
            f"<td class='num'>{r['weight'] * 100:.1f}%</td>"
            f"{fmt(r.get('ret_126d'))}{fmt(r.get('ret_252d'))}"
            f"<td class='num'>{r.get('ann_vol', float('nan')):.0%}</td>"
            f"{fmt(g.get('revenue_growth') if g is not None else None)}"
            f"{fmt(g.get('roce') if g is not None else None)}</tr>"
        )
    return f"<table>{head}{''.join(rows)}</table>"


def _cycle_table(cycles: list[dict]) -> str:
    if not cycles:
        return '<p class="note">No cycle history yet.</p>'
    head = ("<tr><th>Entry</th><th>Exit</th><th>Closed by</th><th class='num'>Days</th>"
            "<th class='num'>Return</th><th class='num'>Max DD</th></tr>")
    rows = []
    for c in reversed(cycles):
        r, dd = c["basket_return"], c["max_drawdown"]
        rows.append(
            f"<tr><td>{c['entry_date'].date()}</td><td>{c['exit_date'].date()}</td>"
            f"<td>{c['exit_reason']}</td><td class='num'>{c['held_days']}</td>"
            f"<td class='num {'pos' if r >= 0 else 'neg'}'>{r * 100:+.2f}%</td>"
            f"<td class='num neg'>{dd * 100:.2f}%</td></tr>"
        )
    return f"<table>{head}{''.join(rows)}</table>"


def build_dashboard(
    themes: dict,
    filename: str | None = None,
    entry_zone: float = 25.0,
    exit_zone: float = 75.0,
) -> Path:
    """
    themes: {theme_name: {"result": run_theme output,
                          "basket": DataFrame or None,
                          "gate": DataFrame or None}}
    """
    stamp = datetime.now().strftime("%Y-%m-%d")
    filename = filename or f"dashboard-{stamp}.html"

    tabs, panels = [], []
    for i, (name, blob) in enumerate(themes.items()):
        res = blob["result"]
        cycles = res["cycles"]
        osc = res["oscillator"].dropna()
        latest = float(osc.iloc[-1]) if len(osc) else float("nan")

        closed = [c for c in cycles if c["exit_reason"] != "open"]
        wins = sum(1 for c in closed if c["basket_return"] > 0)
        avg = (sum(c["basket_return"] for c in closed) / len(closed)) if closed else 0.0
        worst = min((c["max_drawdown"] for c in closed), default=0.0)
        open_now = blob.get("basket") is not None and not blob["basket"].empty

        sel = "true" if i == 0 else "false"
        tabs.append(f'<button class="tab" role="tab" aria-selected="{sel}" '
                    f'data-panel="p{i}">{name}</button>')

        panels.append(f"""
<div class="panel" id="p{i}" role="tabpanel" {'' if i == 0 else 'hidden'}>
  <div class="stats">
    <div class="stat"><div class="k">Oscillator now</div><div class="v">{latest:.0f}</div></div>
    <div class="stat"><div class="k">State</div>
      <div class="v {'state-open' if open_now else 'state-flat'}">{'IN CYCLE' if open_now else 'FLAT'}</div></div>
    <div class="stat"><div class="k">Cycles closed</div><div class="v">{len(closed)}</div></div>
    <div class="stat"><div class="k">Hit rate</div>
      <div class="v">{(wins / len(closed) * 100) if closed else 0:.0f}%</div></div>
    <div class="stat"><div class="k">Avg cycle</div>
      <div class="v {'pos' if avg >= 0 else 'neg'}">{avg * 100:+.1f}%</div></div>
    <div class="stat"><div class="k">Worst drawdown</div>
      <div class="v neg">{worst * 100:.1f}%</div></div>
  </div>

  <div class="card"><h2>Cycle oscillator</h2>
    {_osc_svg(res['oscillator'], res['signals'], entry_zone, exit_zone)}
    <div class="legend">
      <span><span class="dot" style="background:#1F6F5C"></span>Entry — breadth turned up out of the low zone</span>
      <span><span class="dot" style="background:#A63D2F"></span>Exit — turned down out of the high zone</span>
    </div>
  </div>

  <div class="card"><h2>Cycle history</h2>{_ribbon(closed)}</div>

  <div class="card"><h2>Current basket</h2>
    {_basket_table(blob.get('basket'), blob.get('gate'))}
    <p class="note">Tier 1 holds 70% of the sleeve across the top four names,
    tier 2 the remaining 30%. Entered and exited as one basket, not name by name.</p>
  </div>

  <div class="card"><h2>Closed cycles</h2>{_cycle_table(closed)}</div>
</div>""")

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cycle baskets — {stamp}</title><style>{CSS}</style></head>
<body><div class="wrap">
<header>
  <h1>Macro cycle baskets</h1>
  <div class="sub">Generated {stamp} · India + US · reproducible from price data</div>
</header>

<div class="warn"><strong>Read the drawdown column, not just the return column.</strong>
Every number here is computed from a published formula over cached price data, so it can be
re-run and checked. It is a screen for your own research, not advice, and past cycle
returns do not predict the next one.</div>

<div class="tabs" role="tablist">{''.join(tabs)}</div>
{''.join(panels)}

<footer>Built from cached daily closes. Re-run monthly. Every call is written to
the ledger before you act on it.</footer>
</div>
<script>
document.querySelectorAll('.tab').forEach(function(t){{
  t.addEventListener('click',function(){{
    document.querySelectorAll('.tab').forEach(function(x){{x.setAttribute('aria-selected','false');}});
    document.querySelectorAll('.panel').forEach(function(p){{p.hidden=true;}});
    t.setAttribute('aria-selected','true');
    document.getElementById(t.dataset.panel).hidden=false;
  }});
}});
</script>
</body></html>"""

    path = OUT / filename
    path.write_text(html, encoding="utf-8")
    return path

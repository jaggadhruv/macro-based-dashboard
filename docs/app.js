// Shared helpers for both pages. No dependencies, no build step.

const MARKETS = ['india', 'us'];
let DATA = {};
let market = new URLSearchParams(location.search).get('m') || 'india';

const pct = (v, d = 1) => v == null ? '—' : (v * 100).toFixed(d) + '%';
const sgn = (v, d = 1) => v == null ? '—' : (v >= 0 ? '+' : '') + (v * 100).toFixed(d) + '%';
const cls = v => v == null ? 'muted' : (v >= 0 ? 'pos' : 'neg');
const num = (v, d = 2) => v == null ? '—' : v.toFixed(d);
const arrow = r => r == null ? '' : (r ? '▲' : '▼');

async function loadMarket(m) {
  if (DATA[m]) return DATA[m];

  // Browsers block fetch() on file:// URLs. Opening this page by
  // double-clicking it will always fail here, whatever the data looks like,
  // so name that cause specifically rather than reporting a generic error.
  if (location.protocol === 'file:') {
    const err = new Error('This page must be served over http, not opened directly from disk.');
    err.kind = 'file-protocol';
    throw err;
  }

  let res;
  try {
    res = await fetch(`data/${m}.json?v=${Date.now()}`);
  } catch (e) {
    const err = new Error(`Could not reach data/${m}.json (${e.message}).`);
    err.kind = 'network';
    throw err;
  }
  if (res.status === 404) {
    const err = new Error(`No snapshot has been generated for ${m.toUpperCase()} yet.`);
    err.kind = 'missing';
    err.market = m;
    throw err;
  }
  if (!res.ok) {
    const err = new Error(`Server returned ${res.status} for data/${m}.json.`);
    err.kind = 'http';
    throw err;
  }
  try {
    DATA[m] = await res.json();
  } catch (e) {
    const err = new Error(`data/${m}.json exists but is not valid JSON (${e.message}).`);
    err.kind = 'parse';
    throw err;
  }
  return DATA[m];
}

// One place that decides what a failure should say, so both pages agree.
function failureHtml(e, m) {
  const cmd = `python run.py`;
  if (e.kind === 'file-protocol') {
    return `<div class="card"><h2>Open this over http, not from disk</h2>
      <p class="hint">Browsers refuse to let a page loaded from
      <code>file://</code> read a local data file, so the dashboard has nothing to show.
      This is a browser security rule, not a problem with your data.</p>
      <p class="hint"><strong>Run this from the project folder:</strong></p>
      <pre class="cmd">python run.py</pre>
      <p class="hint">Then open <code>http://localhost:8000</code>. Leave that window
      running while you use the dashboard.</p></div>`;
  }
  if (e.kind === 'missing') {
    return `<div class="card"><h2>No snapshot yet</h2>
      <p class="hint">${e.message} Generate one:</p>
      <pre class="cmd">${cmd}</pre>
      <p class="hint">The first run downloads about ten years of prices and takes
      3-5 minutes. Then refresh this page.</p></div>`;
  }
  return `<div class="card"><h2>Could not load data</h2>
    <p class="hint">${e.message}</p>
    <pre class="cmd">${cmd}</pre></div>`;
}

function marketChips(onSwitch) {
  const el = document.getElementById('market-chips');
  if (!el) return;
  el.innerHTML = MARKETS.map(m =>
    `<button class="chip" aria-pressed="${m === market}" data-m="${m}">${m.toUpperCase()}</button>`
  ).join('');
  el.querySelectorAll('.chip').forEach(b => b.onclick = () => {
    market = b.dataset.m;
    history.replaceState(null, '', `?m=${market}`);
    el.querySelectorAll('.chip').forEach(x =>
      x.setAttribute('aria-pressed', x.dataset.m === market));
    onSwitch();
  });
}

function relativeAge(iso) {
  if (!iso) return null;
  const then = new Date(iso), mins = (Date.now() - then.getTime()) / 60000;
  if (mins < 0) return { text: 'just now', hours: 0 };
  const hours = mins / 60;
  let text;
  if (mins < 2) text = 'just now';
  else if (mins < 60) text = `${Math.round(mins)} min ago`;
  else if (hours < 24) text = `${Math.round(hours)} hour${Math.round(hours) === 1 ? '' : 's'} ago`;
  else {
    const days = Math.round(hours / 24);
    text = `${days} day${days === 1 ? '' : 's'} ago`;
  }
  return { text, hours, local: then.toLocaleString(undefined, {
    weekday: 'short', day: 'numeric', month: 'short',
    hour: '2-digit', minute: '2-digit' }) };
}

// Freshness is the one thing a hosted page must never lie about: a stale
// snapshot that looks current is worse than no page at all.
// Thresholds scale with how often the site is meant to refresh, so a weekly
// site is green all week and only turns red once a scheduled run is missed.
//   green: within one cycle plus a day and a half of slack for queue delays
//   amber: up to two cycles  (one run missed)
//   red:   beyond that       (the schedule has stopped)
function freshness(hours, everyDays) {
  const cyc = Math.max(1, everyDays || 1) * 24;
  if (hours == null) return { cls: 'stale-unknown', label: 'unknown' };
  if (hours <= cyc + 36) return { cls: 'fresh-ok', label: 'current' };
  if (hours <= cyc * 2 + 36) return { cls: 'fresh-warn', label: 'one refresh missed' };
  return { cls: 'fresh-bad', label: 'stale' };
}

function stamp(d) {
  const every = (d.config && d.config.refresh_every_days) || 1;
  const age = relativeAge(d.generated_iso);
  const f = freshness(age ? age.hours : null, every);
  const el = document.getElementById('stamp');
  if (el) {
    el.innerHTML =
      `<span class="freshdot ${f.cls}" title="Snapshot is ${f.label}"></span>` +
      `Updated <b>${age ? age.text : d.generated_utc}</b>` +
      `<span class="dim"> · data through <b>${d.data_through}</b>` +
      ` · refreshes ${every === 7 ? 'weekly' : every === 1 ? 'daily' : 'every ' + every + ' days'}` +
      ` · ${d.summary.themes} sectors, ${d.summary.themes_in_cycle} in cycle</span>`;
    el.title = age
      ? `Snapshot generated ${age.local} your time (${d.generated_utc}).\n` +
        `Latest closing prices are from ${d.data_through}.`
      : d.generated_utc;
  }

  const w = document.getElementById('warnings');
  if (!w) return;
  let html = '';

  // Prices lag the run: a Monday morning refresh still shows Friday's close.
  // Say so rather than letting the reader assume the data is intraday.
  const dataAgeDays = Math.floor(
    (Date.now() - new Date(d.data_through + 'T00:00:00Z').getTime()) / 86400000);
  // Prices can legitimately be up to one cycle old, plus a weekend and a
  // holiday. Beyond that the refresh has failed, and the reader must know.
  if (dataAgeDays > every + 4) {
    html += `<div class="warn warn-bad"><strong>Prices are ${dataAgeDays} days old.</strong>
      The latest close in this snapshot is ${d.data_through}. Either the scheduled refresh
      has stopped running, or the data source is failing. Check before acting on anything
      below.</div>`;
  } else if (f.cls === 'fresh-bad') {
    html += `<div class="warn"><strong>This snapshot was generated ${age.text}.</strong>
      The automatic refresh may have stopped. Prices shown are from ${d.data_through}.</div>`;
  }

  if (d.warnings && d.warnings.length) {
    html += `<div class="warn"><strong>Data warnings</strong><ul>` +
      d.warnings.map(x => `<li>${x}</li>`).join('') + `</ul></div>`;
  }
  w.innerHTML = html;
}

// Sortable tables. Sort key lives in data-sort on each cell so display
// formatting never affects ordering.
function makeSortable(table) {
  const ths = table.querySelectorAll('thead th');
  ths.forEach((th, i) => {
    if (th.dataset.nosort !== undefined) return;
    th.onclick = () => {
      const asc = !(th.classList.contains('sorted') && !th.classList.contains('asc'));
      ths.forEach(x => x.classList.remove('sorted', 'asc'));
      th.classList.add('sorted');
      if (asc) th.classList.add('asc');
      const tb = table.querySelector('tbody');
      const groups = [];
      let cur = null;
      // Keep detail rows attached to their parent row when sorting.
      tb.querySelectorAll('tr').forEach(tr => {
        if (tr.classList.contains('detail')) { if (cur) cur.push(tr); }
        else { cur = [tr]; groups.push(cur); }
      });
      groups.sort((A, B) => {
        const a = A[0].children[i]?.dataset.sort, b = B[0].children[i]?.dataset.sort;
        const na = parseFloat(a), nb = parseFloat(b);
        const bothNum = !isNaN(na) && !isNaN(nb);
        if (bothNum) return asc ? na - nb : nb - na;
        return asc ? String(a ?? '').localeCompare(String(b ?? ''))
                   : String(b ?? '').localeCompare(String(a ?? ''));
      });
      tb.innerHTML = '';
      groups.forEach(g => g.forEach(tr => tb.appendChild(tr)));
    };
  });
}

// Oscillator line chart as inline SVG, drawn from the weekly series.
function oscChart(series, signals, entryZone, exitZone, h = 170) {
  if (!series || series.length < 2) return '<p class="hint">Not enough history.</p>';
  const w = 1000, pl = 34, pr = 8, pt = 8, pb = 20;
  const pw = w - pl - pr, ph = h - pt - pb;
  const n = series.length;
  const X = i => pl + (i / (n - 1)) * pw;
  const Y = v => pt + (1 - v / 100) * ph;
  const idx = {}; series.forEach((p, i) => idx[p.d] = i);

  let s = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Cycle oscillator">`;
  s += `<rect x="${pl}" y="${Y(entryZone)}" width="${pw}" height="${ph - (Y(entryZone) - pt)}" fill="#1F6F5C" opacity=".08"/>`;
  s += `<rect x="${pl}" y="${pt}" width="${pw}" height="${Y(exitZone) - pt}" fill="#A63D2F" opacity=".08"/>`;
  [0, 25, 50, 75, 100].forEach(l => {
    s += `<line x1="${pl}" y1="${Y(l)}" x2="${w - pr}" y2="${Y(l)}" stroke="currentColor" stroke-opacity=".18" stroke-dasharray="2 3"/>`;
    s += `<text x="${pl - 6}" y="${Y(l) + 3.5}" text-anchor="end" font-family="ui-monospace,monospace" font-size="9.5" fill="currentColor" fill-opacity=".55">${l}</text>`;
  });
  s += `<polyline points="${series.map((p, i) => `${X(i).toFixed(1)},${Y(p.v).toFixed(1)}`).join(' ')}" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>`;

  (signals || []).forEach(g => {
    // Signals are daily, the series is weekly: snap to the nearest week.
    let i = idx[g.date];
    if (i === undefined) {
      i = series.findIndex(p => p.d >= g.date);
      if (i < 0) return;
    }
    const c = g.signal === 'ENTRY' ? '#1F6F5C' : '#A63D2F';
    s += `<line x1="${X(i).toFixed(1)}" y1="${pt}" x2="${X(i).toFixed(1)}" y2="${pt + ph}" stroke="${c}" stroke-width="1.1" opacity=".55"/>`;
    s += `<circle cx="${X(i).toFixed(1)}" cy="${Y(g.oscillator).toFixed(1)}" r="3.6" fill="${c}"><title>${g.signal} ${g.date}</title></circle>`;
  });

  const step = Math.max(1, Math.floor(n / 7));
  for (let i = 0; i < n; i += step) {
    const d = new Date(series[i].d);
    s += `<text x="${X(i).toFixed(1)}" y="${h - 5}" text-anchor="middle" font-family="ui-monospace,monospace" font-size="9.5" fill="currentColor" fill-opacity=".55">${d.toLocaleString('en', { month: 'short' })} ${String(d.getFullYear()).slice(2)}</text>`;
  }
  return s + '</svg>';
}

// Diverging bar: value relative to zero, scaled against the widest in the set.
function rsBar(v, maxAbs) {
  if (v == null || !maxAbs) return '';
  const half = 50, w = Math.min(50, Math.abs(v) / maxAbs * 50);
  const c = v >= 0 ? 'var(--long)' : 'var(--short)';
  const left = v >= 0 ? half : half - w;
  return `<div class="rsbar"><span class="mid" style="left:${half}%"></span>` +
         `<i style="left:${left}%;width:${w}%;background:${c}"></i></div>`;
}

function ribbon(cycles) {
  if (!cycles || !cycles.length) return '<p class="hint">No completed cycles yet.</p>';
  return '<div class="ribbon">' + cycles.map(c => {
    const col = c.ret >= 0 ? '#1F6F5C' : '#A63D2F';
    const op = Math.min(1, 0.42 + Math.abs(c.ret) * 1.6);
    return `<div class="seg" style="background:${col};opacity:${op.toFixed(2)}" ` +
      `title="${c.entry} → ${c.exit} (${c.reason}), ${c.days} days, dd ${pct(c.dd)}">` +
      `${sgn(c.ret)}<small>${c.entry.slice(0, 7)}</small></div>`;
  }).join('') + '</div>';
}

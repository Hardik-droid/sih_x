// Overview (#overview): case health at a glance and fast paths into every workflow.
import { get } from "../api.js";
import { state, notify } from "../state.js";
import { defineActions } from "../actions.js";
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { bytes, date, number, pad2, readable, relative, time, timeTag } from "../format.js";
import { QUALITY_ORDER, STATUS, statusInfo } from "../statusMap.js";
import { activeJobs, qualityOf, recoveredArtifacts, totalCapacity } from "../selectors.js";
import { barChart, lineChart } from "../charts.js";
import { badge, actorChip } from "../components/badge.js";
import { button, textLink } from "../components/button.js";
import { pageHeader, panel } from "../components/card.js";
import { statCard } from "../components/statCard.js";
import { emptyState } from "../components/emptyState.js";
import { skeletonBlock } from "../components/skeleton.js";
import { platter } from "../components/visuals.js";
import { toast } from "../components/toast.js";

const DAY = 24 * 3600 * 1000;
const recent = (items, field = "created_at") => items.filter((x) => Date.now() - new Date(x[field]).getTime() < DAY).length;

function hero(d) {
  let cta;
  if (!state.caseId) cta = button({ label: "Start an investigation", variant: "primary", icon: "arrow", action: "new-case" });
  else if (!d) cta = "";
  else if (!d.sources.length) cta = button({ label: "Import evidence", variant: "primary", icon: "upload", action: "import" });
  else if (d.artifacts.length) cta = button({ label: "Explore recovered evidence", variant: "primary", iconRight: "arrow", href: "#evidence" });
  else cta = button({ label: "Open recovery engine", variant: "primary", iconRight: "arrow", href: "#recovery" });
  return `<section class="hero-banner" aria-labelledby="hero-title">
    <div class="hero-banner__copy">
      <p class="eyebrow eyebrow--amber">Built for evidence. Designed for clarity.</p>
      <h2 class="hero-banner__title" id="hero-title">Every fragment has a story.<br><span>Find the pieces that matter.</span></h2>
      <p class="hero-banner__body">A local workspace for DVR and NVR recovery, from the first disk image to a verifiable evidence report.</p>
      <div class="row">${cta}</div>
    </div>
    <div class="hero-banner__visual" aria-hidden="true">
      ${platter()}
      <span class="float-tag float-tag--top">SOURCE / READ ONLY</span>
      <span class="float-badge">${icon("integrity", { size: 15 })}Original evidence preserved</span>
    </div>
  </section>`;
}

function kpis(d) {
  if (state.caseId && !d) return `<div class="grid-kpi">${Array.from({ length: 4 }, () => skeletonBlock(132)).join("")}</div>`;
  const sources = d?.sources || [];
  const recovered = d ? recoveredArtifacts(d) : [];
  const active = d ? activeJobs(d).length : 0;
  const events = d?.audit?.events || [];
  const trend = (n, label) => (n > 0 ? { direction: "up", text: `${number(n)} ${label}` } : null);
  return `<div class="grid-kpi">
    ${statCard({ label: "Evidence sources", value: pad2(sources.length), icon: "sources", note: `${bytes(totalCapacity(d))} total evidence`, trend: trend(recent(sources), "in 24 h"), href: "#sources" })}
    ${statCard({ label: "Recovered artifacts", value: pad2(recovered.length), icon: "evidence", note: "Validated against surviving bytes", trend: trend(recent(recovered), "in 24 h"), href: "#evidence" })}
    ${statCard({ label: "Active operations", value: pad2(active), icon: "recovery", note: active ? "Recovery engine is working" : "Ready for your next source", href: "#recovery" })}
    ${statCard({ label: "Audit events", value: pad2(events.length), icon: "integrity", note: d?.audit?.valid ? "Hash chain verified" : d ? "Hash chain needs review" : "Traceable from the first step", trend: trend(recent(events, "timestamp"), "in 24 h"), href: "#integrity" })}
  </div>`;
}

// ---------------------------------------------------------------- charts --
function progressSeries(d) {
  if (!d) return [];
  const recovered = d.artifacts
    .filter((a) => (a.kind === "RECOVERED" || a.kind === "RECONSTRUCTED") && a.status !== "UNRECOVERABLE" && a.created_at)
    .map((a) => new Date(a.created_at).getTime())
    .filter((t) => !Number.isNaN(t))
    .sort((a, b) => a - b);
  if (!recovered.length) return [];
  const firstJob = d.jobs.map((j) => new Date(j.created_at).getTime()).filter((t) => !Number.isNaN(t) && t <= recovered[0]).sort((a, b) => a - b)[0];
  const points = [];
  if (firstJob !== undefined) points.push({ x: firstJob, y: 0, label: `${date(firstJob)} · job started` });
  recovered.forEach((t, i) => points.push({ x: t, y: i + 1, label: `${date(t)} · ${time(t)}` }));
  return points;
}

function tickFormatter(points) {
  const span = points.length ? points[points.length - 1].x - points[0].x : 0;
  if (span < 3600 * 1000) return (x) => time(x);
  if (span < 2 * DAY) return (x) => new Date(x).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return (x) => new Date(x).toLocaleDateString([], { month: "short", day: "numeric" });
}

function qualityBars(d) {
  const counts = {};
  let assessed = 0;
  for (const a of d.artifacts) {
    const q = qualityOf(a);
    if (!q || !q.category) continue;
    assessed += 1;
    counts[q.category] = (counts[q.category] || 0) + 1;
  }
  if (!assessed) return null;
  const cats = QUALITY_ORDER.filter((c, i) => i < 4 || counts[c]);
  return { assessed, bars: cats.map((c) => ({ label: statusInfo(c).label, value: counts[c] || 0, tone: statusInfo(c).tone, hint: c })) };
}

function outcomeBars(d) {
  const order = ["EXACT_RECOVERED", "PARTIAL_RECOVERED", "INFERRED", "ENHANCED_COPY", "UNRECOVERABLE"];
  const counts = {};
  for (const a of d.artifacts) counts[a.status] = (counts[a.status] || 0) + 1;
  return order.map((code) => ({ label: STATUS[code].label, value: counts[code] || 0, tone: STATUS[code].tone, hint: code }));
}

function chartPanels(d) {
  if (state.caseId && !d) return `<div class="grid-2">${skeletonBlock(300)}${skeletonBlock(300)}</div>`;
  const points = progressSeries(d);
  const total = d ? recoveredArtifacts(d).length : 0;
  const left = panel({
    title: "Recovery progress",
    description: points.length >= 2 ? `Cumulative recovered artifacts · since ${date(points[0].x)}` : "Cumulative recovered artifacts over the case timeline",
    icon: "activity",
    action: d ? `<div class="panel-figure"><span class="panel-figure__value tabular">${number(total)}</span><span class="panel-figure__label">This case</span></div>` : "",
    body: points.length >= 2
      ? `<div class="chart-slot" data-island data-chart="progress"></div>`
      : emptyState({ icon: "activity", title: "Not enough history yet", body: "The curve appears once the engine has recovered artifacts over at least two recorded moments.", compact: true }),
  });
  let right;
  const quality = d ? qualityBars(d) : null;
  if (quality) {
    right = panel({
      title: "Fragment quality distribution",
      description: `Forensic Quality Index by category · ${number(quality.assessed)} of ${number(d.artifacts.length)} artifacts assessed`,
      icon: "gauge",
      action: button({ label: "Assess all", variant: "pill", size: "sm", icon: "refresh", action: "rank-quality" }),
      body: '<div class="chart-slot" data-island data-chart="quality"></div>',
    });
  } else if (d && d.artifacts.length) {
    right = panel({
      title: "Recovery outcomes",
      description: "Artifacts by recovery status · quality not assessed yet",
      icon: "chart",
      action: button({ label: "Assess quality", variant: "pill", size: "sm", icon: "gauge", action: "rank-quality" }),
      body: '<div class="chart-slot" data-island data-chart="outcomes"></div>',
    });
  } else {
    right = panel({
      title: "Fragment quality distribution",
      description: "Forensic Quality Index by category",
      icon: "gauge",
      body: emptyState({ icon: "gauge", title: "Nothing to score yet", body: "Quality scores appear after recovered artifacts are assessed. Scoring never modifies evidence.", compact: true }),
    });
  }
  return `<div class="grid-2">${left}${right}</div>`;
}

// ---------------------------------------------------------- lists --------
function sourcesPanel(d) {
  const sources = d?.sources || [];
  const body = sources.length
    ? `<ul class="list" role="list">${sources.slice(-4).reverse().map((s) => `<li class="list__row" data-key="${esc(s.id)}">
        <span class="icon-chip">${icon(s.type === "REMOVABLE_USB" ? "usb-drive" : s.type === "MEDIA_EXPORT" ? "film" : "disk", { size: 16 })}</span>
        <div class="list__main"><strong class="truncate">${esc(s.name)}</strong><span class="list__meta">${bytes(s.capacity)} · ${esc(readable(s.type))} · ${timeTag(s.created_at)}</span></div>
        ${badge(s.status)}
      </li>`).join("")}</ul>`
    : emptyState({ icon: "sources", title: "Your evidence, organized.", body: "Add a forensic image or media export to begin read-only acquisition and analysis.", action: button({ label: "Add first source", icon: "plus", action: "import" }), compact: true });
  return panel({
    title: "Evidence sources",
    count: sources.length,
    icon: "sources",
    action: textLink({ label: "View all", href: "#sources" }),
    body,
    footer: sources.length ? `<span>${icon("integrity", { size: 14 })}SHA-256 verification on every acquisition</span>` : "",
  });
}

function activityPanel(d) {
  const events = (d?.audit?.events || []).slice(-5).reverse();
  const body = events.length
    ? `<ol class="activity" role="list">${events.map((e) => `<li class="activity__item" data-key="${esc(e.hash)}">
        <span class="activity__dot activity__dot--${e.actor === "engine" ? "blue" : e.actor === "system" ? "gray" : "amber"}" aria-hidden="true"></span>
        <div class="activity__main"><strong>${esc(readable(e.action))}</strong><span class="list__meta">${actorChip(e.actor)} · <span title="${esc(e.timestamp)}">${esc(relative(e.timestamp))}</span></span></div>
      </li>`).join("")}</ol>`
    : emptyState({ icon: "clock", title: "A record of every step", body: "Acquisition, recovery and export events appear here as your case develops.", compact: true });
  return panel({ title: "Recent activity", icon: "clock", action: textLink({ label: "Chain of custody", href: "#integrity" }), body });
}

function workflow() {
  const steps = [
    ["01", "Acquire", "Import & verify the source", "upload", 'data-action="import"'],
    ["02", "Recover", "Find surviving media", "recovery", 'href="#recovery"'],
    ["03", "Examine", "Review clips & provenance", "evidence", 'href="#evidence"'],
    ["04", "Report", "Export a verifiable record", "reports", 'href="#reports"'],
  ];
  return `<section class="workflow" aria-labelledby="workflow-title">
    <div class="section-head"><div><h2 class="section-head__title" id="workflow-title">From source to certainty</h2><p class="section-head__desc">A deliberate workflow. An unbroken evidence trail.</p></div><span class="eyebrow">The Trace workflow</span></div>
    <div class="workflow__grid">${steps.map(([n, t, p, i, target]) => `<${target.startsWith("href") ? "a" : "button type=\"button\""} class="workflow-card" ${target}><span class="workflow-card__num tabular">${n}</span><span class="workflow-card__text"><strong>${t}</strong><span>${p}</span></span><span class="workflow-card__icon">${icon(i, { size: 18 })}</span></${target.startsWith("href") ? "a" : "button"}>`).join("")}</div>
  </section>`;
}

function integrityStrip() {
  return `<aside class="strip">${icon("integrity", { size: 20, className: "strip__icon" })}<p><strong>Preservation comes first.</strong> Original sources are opened read-only. Recovered evidence and viewing copies stay distinct.</p>${textLink({ label: "View capabilities", href: "#registry" })}</aside>`;
}

export function render() {
  const d = state.detail;
  const actions = button({ label: "New case", icon: "plus", action: "new-case" })
    + button({ label: "Import evidence", variant: "primary", icon: "upload", action: "import" })
    + button({ label: "Forensic USB Ingest", variant: "accent", icon: "zap", action: "usb-ingest" });
  return `${pageHeader({ eyebrow: d ? d.case.name : "Your investigation starts here", title: "A clearer path to the evidence.", description: "Acquire safely. Recover what survives. Keep every step traceable.", actions })}
    ${hero(d)}
    ${kpis(d)}
    ${chartPanels(d)}
    <div class="grid-2">${sourcesPanel(d)}${activityPanel(d)}</div>
    ${workflow()}
    ${integrityStrip()}`;
}

// ------------------------------------------------------------ charts mount --
let charts = {};
let signatures = {};

function drawCharts(root) {
  const d = state.detail;
  const slots = {
    progress: root.querySelector('[data-chart="progress"]'),
    quality: root.querySelector('[data-chart="quality"]'),
    outcomes: root.querySelector('[data-chart="outcomes"]'),
  };
  for (const [key, el] of Object.entries(slots)) {
    if (!el || !d) { charts[key]?.destroy(); delete charts[key]; delete signatures[key]; continue; }
    let config;
    if (key === "progress") {
      const points = progressSeries(d);
      config = { points, label: "Cumulative recovered artifacts over time", valueLabel: (v) => `${number(v)} recovered`, tickLabel: tickFormatter(points) };
    } else if (key === "quality") {
      config = { bars: qualityBars(d)?.bars || [], label: "Artifacts by Forensic Quality Index category", valueLabel: (v) => `${number(v)} artifacts` };
    } else {
      config = { bars: outcomeBars(d), label: "Artifacts by recovery status", valueLabel: (v) => `${number(v)} artifacts` };
    }
    const sig = JSON.stringify(config.points || config.bars);
    if (signatures[key] === sig && el.firstChild && charts[key]?.el === el) continue;
    charts[key]?.destroy();
    const chart = key === "progress" ? lineChart(el, config) : barChart(el, config);
    charts[key] = { ...chart, el };
    signatures[key] = sig;
  }
}

export function mount(root) {
  charts = {};
  signatures = {};
  drawCharts(root);
  return () => { Object.values(charts).forEach((c) => c.destroy()); charts = {}; signatures = {}; };
}

export function update(root) { drawCharts(root); }

defineActions({
  "rank-quality": async () => {
    const caseId = state.caseId;
    if (!caseId) return;
    toast("Scoring every artifact (blur, contrast, blockiness)…", { tone: "info" });
    const ranking = await get(`/cases/${encodeURIComponent(caseId)}/quality-ranking`);
    if (caseId !== state.caseId) return;
    for (const row of ranking) if (row.quality) state.quality[row.artifact_id] = row.quality;
    state.qualityRanked = true;
    notify("quality");
    toast(`Quality assessed for ${number(ranking.length)} artifacts. Scores are diagnostic only.`, { tone: "success" });
  },
});

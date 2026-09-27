// Reports & exports (#reports): real-number metrics, the three-document
// dossier viewer, deliverables and the export package history.
import { getText, post } from "../api.js";
import { state, notify } from "../state.js";
import { refresh } from "../data.js";
import { defineActions } from "../actions.js";
import { $, copyText, esc } from "../dom.js";
import { icon } from "../icons.js";
import { bytes, number, shortHash, timeTag } from "../format.js";
import { exportJobs, qualityOf, totalCapacity } from "../selectors.js";
import { badge } from "../components/badge.js";
import { button } from "../components/button.js";
import { pageHeader, panel } from "../components/card.js";
import { hashChip } from "../components/hash.js";
import { emptyState } from "../components/emptyState.js";
import { tabs } from "../components/tabs.js";
import { highlightJson, jumpToKey } from "../components/jsonViewer.js";
import { openModal } from "../components/modal.js";
import { toast } from "../components/toast.js";
import { caseGuard, caseEyebrow } from "./common.js";

const TITLE = "Reports & exports";
const DESC = "Court and lab deliverables generated from this case’s verified records.";
const JUMP = [
  ["report_metadata", "metadata"],
  ["case_identification", "case"],
  ["executive_summary", "summary"],
  ["parent_storage_lineage", "lineage"],
  ["acquired_evidence_sources", "sources"],
  ["recovered_video_evidence", "video"],
  ["demuxed_audio_evidence", "audio"],
  ["multi_representation_correlation", "correlation"],
  ["chain_of_custody_audit_ledger", "audit"],
  ["statutory_declaration", "declaration"],
];

const urls = (id) => ({
  report: `/api/cases/${encodeURIComponent(id)}/report?format=html`,
  bsa: `/api/cases/${encodeURIComponent(id)}/bsa-certificate`,
  json: `/api/cases/${encodeURIComponent(id)}/report`,
});

function metric(iconName, label, value, sub, tone = "") {
  return `<div class="metric${tone ? ` metric--${tone}` : ""}"><span class="metric__label">${icon(iconName, { size: 14 })}${esc(label)}</span><strong class="metric__value tabular">${esc(value)}</strong><span class="metric__sub">${esc(sub)}</span></div>`;
}

function metrics(d) {
  const parent = d.case.parent_evidence;
  const artifacts = d.artifacts;
  const frames = artifacts.reduce((sum, a) => sum + (Number(a.validation?.frames_decoded) || 0), 0);
  const audio = artifacts.filter((a) => a.audio_path).length;
  const scored = artifacts.map(qualityOf).filter(Boolean);
  const avg = scored.length ? scored.reduce((s, q) => s + Number(q.score), 0) / scored.length : null;
  const lineage = parent
    ? metric("disk", "Storage lineage", bytes(parent.logical_size), parent.logical_verification?.verified ? "Parent E01 · published hashes matched" : "Parent E01 · checksum pending", parent.logical_verification?.verified ? "green" : "")
    : metric("sources", "Storage lineage", bytes(totalCapacity(d)), `${number(d.sources.length)} acquired ${d.sources.length === 1 ? "source" : "sources"}`);
  return `<div class="metrics" role="list">
    ${metric("scale", "Certificate format", "Sec. 63 BSA", "Corresponds to Sec. 65B IEA")}
    ${lineage}
    ${metric("film", "Decoded frames", number(frames), `${number(artifacts.length)} ${artifacts.length === 1 ? "artifact" : "artifacts"}`)}
    ${metric("audio", "Demuxed audio", number(audio), audio ? "WAV streams stored" : "No audio files stored")}
    ${metric("gauge", "Average FQI", avg === null ? "Not assessed" : `${avg.toFixed(1)} / 100`, avg === null ? "Run quality ranking to score" : `${number(scored.length)} of ${number(artifacts.length)} scored`)}
    ${metric("integrity", "Custody chain", d.audit.valid ? "Valid" : "Broken", `${number(d.audit.events.length)} events · head ${shortHash(d.audit.head_hash, 6, 4)}`, d.audit.valid ? "green" : "red")}
  </div>`;
}

function dossier(d) {
  const tab = state.reportTab;
  const u = urls(d.case.id);
  let toolbar;
  let body;
  if (tab === "json") {
    const loaded = typeof state.reportJson === "string";
    const phase = state.reportJsonError ? "error" : loaded ? "ready" : "loading";
    toolbar = button({ label: "Copy JSON", size: "sm", icon: "copy", action: "copy-report-json", disabled: !loaded })
      + button({ label: "Download .json", size: "sm", icon: "download", href: u.json, download: `trace-report-${d.case.id.slice(0, 8)}.json` })
      + button({ label: "Raw API view", size: "sm", variant: "ghost", iconRight: "external-link", href: u.json, target: "_blank" });
    body = `<div class="dossier__json">
      <div class="json-jump" role="toolbar" aria-label="Jump to section"><span class="json-jump__label">Jump to</span>${JUMP.map(([key, label]) => `<button type="button" class="chip" data-action="json-jump" data-key="${key}">#${label}</button>`).join("")}</div>
      <pre class="json-view" id="report-json" tabindex="0" aria-label="Structured evidence record" data-island data-phase="${phase}"></pre>
    </div>`;
  } else {
    const src = tab === "bsa" ? u.bsa : u.report;
    const title = tab === "bsa" ? "Courtroom certificate (Sec. 63 BSA / 65B IEA)" : "Forensic case report (ISO/IEC 27037)";
    toolbar = button({ label: tab === "bsa" ? "Open to print" : "Open printable window", size: "sm", iconRight: "external-link", href: src, target: "_blank" })
      + button({ label: "Expand", size: "sm", variant: "ghost", icon: "arrow-up-right", action: "expand-report", data: { tab } });
    body = `<iframe class="dossier__frame" src="${src}" title="${esc(title)}" loading="lazy" referrerpolicy="no-referrer"></iframe>`;
  }
  return `<section class="dossier panel" aria-label="Report viewer">
    <div class="dossier__bar">
      ${tabs({ id: "dossier", items: [
        { id: "report", label: "Forensic case report", icon: "reports" },
        { id: "bsa", label: "Courtroom certificate", icon: "scale" },
        { id: "json", label: "Structured record (JSON)", icon: "terminal" },
      ], active: tab, action: "report-tab", label: "Report documents" })}
      <div class="dossier__actions">${toolbar}</div>
    </div>
    <div class="tab-panel dossier__body" role="tabpanel" id="dossier-panel" aria-labelledby="dossier-tab-${esc(tab)}">${body}</div>
    <p class="dossier__note subtle">${icon("info", { size: 13 })}Opening a report or certificate is itself recorded in the audit log.</p>
  </section>`;
}

function deliverables(d) {
  const u = urls(d.case.id);
  const rows = [
    ["reports", "Forensic case report", "ISO/IEC 27037-framed examination report: sources, recovered artifacts, correlation and the tamper-evident audit ledger.", button({ label: "Open report", iconRight: "external-link", href: u.report, target: "_blank" })],
    ["scale", "Courtroom evidence certificate", "Section 63 Bharatiya Sakshya Adhiniyam certificate (Section 65B IEA) with source and artifact SHA-256 tables, ready to print and sign.", button({ label: "Print certificate", iconRight: "external-link", href: u.bsa, target: "_blank" })],
    ["terminal", "Structured evidence record (JSON)", "Machine-readable report with metadata, lineage, evidence and audit ledger sections.", button({ label: "View JSON", action: "report-tab", data: { tab: "json" } })],
    ["package", "Verified evidence package (ZIP)", "Recovered artifacts with a SHA-256 manifest, report and README. Original disk images stay local. Integrity is re-verified before packaging.", button({ label: "Build package", variant: "primary", icon: "package", action: "export-package" })],
  ];
  if (d.case.parent_evidence) rows.push(["search", "Recording index", `Browse the recorder-native index of ${number(d.case.parent_evidence.index_entries)} recordings on the parent image and extract individual files.`, button({ label: "Browse index", icon: "search", action: "open-recording-index" })]);
  return panel({
    title: "Case deliverables",
    icon: "download",
    body: `<ul class="deliverables" role="list">${rows.map(([i, t, p, a]) => `<li class="deliverable"><span class="icon-chip">${icon(i, { size: 16 })}</span><div class="deliverable__text"><strong>${esc(t)}</strong><p>${esc(p)}</p></div><div class="deliverable__action">${a}</div></li>`).join("")}</ul>`,
  });
}

function history(d) {
  const jobs = exportJobs(d).slice().reverse();
  return panel({
    title: "Export packages",
    icon: "package",
    count: jobs.length,
    body: jobs.length
      ? `<ul class="deliverables" role="list">${jobs.map((j) => `<li class="deliverable" data-key="${esc(j.id)}"><span class="icon-chip">${icon("package", { size: 16 })}</span><div class="deliverable__text"><strong>Evidence package · ${timeTag(j.created_at)}</strong><p>${esc(j.error || j.stage || "")}</p>${j.result?.sha256 ? `<div class="deliverable__hash">${hashChip(j.result.sha256)}</div>` : ""}</div><div class="deliverable__action">${j.status === "COMPLETED" && j.result?.download_url ? button({ label: "Download ZIP", icon: "download", href: j.result.download_url, download: "" }) : badge(j.status)}</div></li>`).join("")}</ul>`
      : emptyState({ icon: "package", title: "No packages exported", body: "Build a package when you are ready to preserve or share the case record.", compact: true }),
  });
}

export function render() {
  const guard = caseGuard(TITLE, DESC);
  if (guard) return guard;
  const d = state.detail;
  return `${pageHeader({ eyebrow: caseEyebrow(), title: TITLE, description: DESC, actions: button({ label: "Build package", variant: "primary", icon: "package", action: "export-package" }) })}
    ${metrics(d)}
    ${dossier(d)}
    <div class="grid-2 grid-2--wide-left">${deliverables(d)}${history(d)}</div>`;
}

function paintJson(root) {
  const pre = root.querySelector("#report-json");
  if (!pre) return;
  const phase = pre.dataset.phase;
  if (pre.dataset.painted === phase) return;
  pre.dataset.painted = phase;
  if (phase === "ready") pre.innerHTML = highlightJson(state.reportJson);
  else if (phase === "error") pre.innerHTML = `<span class="json-error">${esc(state.reportJsonError)}</span>`;
  else pre.innerHTML = '<span class="subtle">Fetching structured record…</span>';
}

function ensureJson() {
  if (state.reportTab !== "json" || !state.caseId || typeof state.reportJson === "string" || state.reportJsonError || ensureJson.busy) return;
  ensureJson.busy = true;
  const caseId = state.caseId;
  getText(`/cases/${encodeURIComponent(caseId)}/report`)
    .then((text) => { if (caseId === state.caseId) { state.reportJson = text; state.reportJsonError = null; } })
    .catch((err) => { if (caseId === state.caseId) state.reportJsonError = `Failed to load structured JSON: ${err.message}`; })
    .finally(() => { ensureJson.busy = false; notify("report"); });
}

export function mount(root) { ensureJson(); paintJson(root); }
export function update(root) { ensureJson(); paintJson(root); }

defineActions({
  "report-tab": ({ tab }) => {
    if (!tab || state.reportTab === tab) return;
    state.reportTab = tab;
    notify("tab");
    if (tab === "json") requestAnimationFrame(() => $("#report-json")?.focus({ preventScroll: true }));
  },
  "json-jump": ({ key, target }) => {
    const pre = document.getElementById(target || "report-json");
    if (!jumpToKey(pre, key)) toast(`Section “${key}” is not present in this record.`, { tone: "warning" });
  },
  "copy-report-json": async () => {
    if (typeof state.reportJson !== "string") return;
    const ok = await copyText(state.reportJson);
    toast(ok ? "Structured JSON copied to clipboard." : "Copy failed — use Download instead.", { tone: ok ? "success" : "warning" });
  },
  "expand-report": ({ tab }) => {
    const u = urls(state.caseId);
    const src = tab === "bsa" ? u.bsa : u.report;
    openModal({
      title: tab === "bsa" ? "Courtroom certificate" : "Forensic case report",
      size: "full",
      className: "modal--document",
      body: `<iframe class="document-frame" src="${src}" title="${tab === "bsa" ? "Courtroom certificate" : "Forensic case report"}"></iframe>`,
      footer: button({ label: "Open printable window", variant: "primary", iconRight: "external-link", href: src, target: "_blank" }),
    });
  },
  "export-package": async () => {
    if (!state.caseId) return;
    await post(`/cases/${encodeURIComponent(state.caseId)}/export`);
    await refresh();
    toast("Evidence package queued. Integrity is verified first; the ZIP appears under Export packages.", { tone: "info" });
  },
});

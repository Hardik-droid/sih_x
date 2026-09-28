// Chain of custody (#integrity): re-verify every stored hash and inspect the
// hash-chained audit ledger event by event.
import { get, post } from "../api.js";
import { state, notify } from "../state.js";
import { refresh } from "../data.js";
import { defineActions } from "../actions.js";
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { bytes, number, readable, timeTag } from "../format.js";
import { artifactById, sourceById } from "../selectors.js";
import { actorChip, toneBadge } from "../components/badge.js";
import { button } from "../components/button.js";
import { notice, pageHeader, panel } from "../components/card.js";
import { hashChip, hashField } from "../components/hash.js";
import { table } from "../components/table.js";
import { toast } from "../components/toast.js";
import { caseGuard, caseEyebrow } from "./common.js";

const TITLE = "Chain of custody";
const DESC = "A hash-linked record of acquisition, recovery, transformations and exports.";
let actorFilter = "all";

const matchBadge = (ok) => (ok ? toneBadge("green", "Match", { icon: "check", size: "sm" }) : toneBadge("red", "Mismatch", { icon: "x-circle", size: "sm" }));

function nameFor(check) {
  if (check.kind === "parent_e01_segment") return check.id;
  if (check.kind === "source") return sourceById(check.id)?.name || check.id;
  return artifactById(check.id)?.name || check.id;
}

function integrityResult() {
  const r = state.integrity;
  if (!r) return "";
  const mismatches = r.files.filter((f) => !f.match);
  const banner = r.valid
    ? notice(`All stored evidence hashes and the audit chain verify. ${number(r.files.length)} files checked · 0 mismatches.`, { tone: "success", title: "Integrity verified" })
    : notice(r.files.length ? `${number(mismatches.length)} of ${number(r.files.length)} checks failed${r.audit?.valid === false ? " and the audit chain is inconsistent" : ""}. Investigate before exporting.` : "No acquired evidence exists yet, so there is nothing to verify.", { tone: r.files.length ? "danger" : "warning", title: r.files.length ? "Integrity check failed" : "Nothing to verify" });
  return `<div class="stack" data-key="integrity-result">${banner}
    ${r.files.length ? `<details class="disclosure"${mismatches.length ? " open" : ""}><summary>${icon("chevron-right", { size: 14 })}File checks (${number(r.files.length)})</summary>${table({
      caption: "Stored file hash checks",
      columns: [
        { key: "name", label: "Record", render: (f) => `<span class="truncate-cell" title="${esc(nameFor(f))}">${esc(nameFor(f))}</span>` },
        { key: "kind", label: "Kind", className: "nowrap", render: (f) => esc(readable(f.kind)) },
        { key: "match", label: "Result", render: (f) => matchBadge(f.match) },
        { key: "actual", label: "Computed SHA-256", render: (f) => (f.actual ? hashChip(f.actual) : `<span class="text-danger">${esc(f.error || "Unavailable")}</span>`) },
      ],
      rows: r.files,
      dense: true,
    })}</details>` : ""}
  </div>`;
}

function proofResult() {
  const p = state.proof;
  if (!p) return "";
  const reports = p.sources || [];
  return notice(`${p.valid ? "Residual proof bundles verify" : "Residual proof bundle verification failed"} for ${number(reports.length)} ${reports.length === 1 ? "source" : "sources"}. Each bundle is bound to its source image SHA-256.`, { tone: p.valid ? "success" : "danger", title: "Proof bundle" });
}

function segments(parent) {
  const segs = parent?.segments || [];
  if (!segs.length) return "";
  const checks = new Map((state.integrity?.files || []).filter((f) => f.kind === "parent_e01_segment").map((f) => [f.id, f]));
  return panel({
    title: "Parent E01 segments",
    icon: "disk",
    count: segs.length,
    description: parent.name,
    body: table({
      caption: "Parent E01 segment hashes",
      columns: [
        { key: "file", label: "Segment", render: (s) => `<code>${esc(s.file)}</code>` },
        { key: "size", label: "Size", className: "nowrap tabular", render: (s) => bytes(s.size) },
        { key: "sha256", label: "Recorded SHA-256", render: (s) => hashChip(s.sha256, { head: 14, tail: 8 }) },
        { key: "check", label: "Re-verified", render: (s) => (checks.has(s.file) ? matchBadge(checks.get(s.file).match) : '<span class="subtle">Run verification</span>') },
      ],
      rows: segs,
      rowKey: (s) => s.file,
      dense: true,
    }),
  });
}

function eventsPanel(audit) {
  const actors = [
    ["all", "All"],
    ["engine", "Engine"],
    ["examiner", "Examiner"],
    ["system", "System"],
  ];
  const matches = (e) => actorFilter === "all" || (actorFilter === "examiner" ? e.actor !== "engine" && e.actor !== "system" : e.actor === actorFilter);
  const events = audit.events.filter(matches).slice().reverse();
  return panel({
    title: "Evidence history",
    icon: "clock",
    count: audit.events.length,
    description: "Newest first. Each record’s hash covers the previous record’s hash.",
    action: `<div class="segmented" role="group" aria-label="Filter by actor">${actors.map(([id, label]) => `<button type="button" class="segmented__item${actorFilter === id ? " is-active" : ""}" data-action="audit-filter" data-actor="${id}" aria-pressed="${actorFilter === id}">${label}</button>`).join("")}</div>`,
    body: events.length
      ? `<ol class="ledger" role="list">${events.map((e) => `<li class="ledger__item" data-key="${esc(e.hash)}">
          <span class="ledger__seq tabular">#${esc(e.seq)}</span>
          <div class="ledger__main">
            <div class="ledger__head"><strong>${esc(readable(e.action))}</strong>${actorChip(e.actor)}<span class="subtle ledger__time">${timeTag(e.timestamp)}</span></div>
            <details class="disclosure disclosure--inline"><summary>${icon("chevron-right", { size: 13 })}Payload &amp; hashes</summary><pre class="code-block">${esc(JSON.stringify({ details: e.details, previous_hash: e.previous_hash, hash: e.hash }, null, 2))}</pre></details>
          </div>
          <span class="ledger__hash">${hashChip(e.hash, { head: 8, tail: 4 })}</span>
        </li>`).join("")}</ol>`
      : '<p class="subtle">No events for this actor.</p>',
  });
}

export function render() {
  const guard = caseGuard(TITLE, DESC);
  if (guard) return guard;
  const d = state.detail;
  const audit = d.audit;
  const actions = (d.sources.length ? button({ label: "Verify proof bundle", icon: "shield", action: "verify-proof" }) : "")
    + button({ label: "Verify all hashes", variant: "primary", icon: "integrity", action: "verify-integrity" });
  return `${pageHeader({ eyebrow: caseEyebrow(), title: TITLE, description: DESC, actions })}
    ${integrityResult()}
    ${proofResult()}
    <div class="grid-2 grid-2--wide-left">
      ${panel({
        title: "Audit chain",
        icon: "hash",
        body: `<div class="stack">${notice(`${audit.valid ? "Audit chain is internally consistent." : "Audit chain verification failed. Investigate before exporting."} ${audit.limitation || ""}`, { tone: audit.valid ? "success" : "danger" })}${hashField(audit.head_hash, { label: "Current audit head · preserve independently", truncate: false })}</div>`,
      })}
      ${panel({
        title: "What is verified",
        icon: "shield",
        body: `<ul class="checklist" role="list">
          <li>${icon("check", { size: 14 })}Every acquired source image is re-hashed with SHA-256.</li>
          <li>${icon("check", { size: 14 })}Every recovered artifact, viewing copy and thumbnail is re-hashed.</li>
          <li>${icon("check", { size: 14 })}Every audit record is re-chained from the genesis hash.</li>
          ${d.case.parent_evidence ? `<li>${icon("check", { size: 14 })}Parent E01 segments are re-hashed (slow for large images).</li>` : ""}
        </ul>`,
      })}
    </div>
    ${segments(d.case.parent_evidence)}
    ${eventsPanel(audit)}`;
}

defineActions({
  "verify-integrity": async () => {
    const caseId = state.caseId;
    if (!caseId) return;
    toast("Re-reading source and artifact hashes…", { tone: "info" });
    const result = await get(`/cases/${encodeURIComponent(caseId)}/integrity`);
    if (caseId !== state.caseId) return;
    state.integrity = result;
    notify("integrity");
    toast(result.valid ? "All stored evidence hashes and the audit chain verify." : "Integrity check failed, or no acquired evidence exists.", { tone: result.valid ? "success" : "error" });
  },
  "verify-proof": async () => {
    const caseId = state.caseId;
    const result = await post(`/cases/${encodeURIComponent(caseId)}/proof-bundle/verify`);
    if (caseId !== state.caseId) return;
    state.proof = result.verification;
    await refresh();
    toast(result.verification?.valid ? "Residual proof bundles verify." : "Proof bundle verification failed.", { tone: result.verification?.valid ? "success" : "error" });
  },
  "audit-filter": ({ actor }) => { actorFilter = actor; notify("filter"); },
});

// Recovery engine (#recovery): live job queue, fragment adjacency decisions and
// redundancy findings — rendered exactly as the engine reports them.
import { post } from "../api.js";
import { state } from "../state.js";
import { refresh } from "../data.js";
import { defineActions } from "../actions.js";
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { number, shortHash } from "../format.js";
import { ACTIVE_JOB, artifactById } from "../selectors.js";
import { badge, toneBadge } from "../components/badge.js";
import { button } from "../components/button.js";
import { detailList, pageHeader, panel } from "../components/card.js";
import { emptyState } from "../components/emptyState.js";
import { jobRow } from "../components/jobRow.js";
import { table } from "../components/table.js";
import { confirmDialog } from "../components/modal.js";
import { toast } from "../components/toast.js";
import { caseGuard, caseEyebrow } from "./common.js";

const TITLE = "Recovery engine";
const DESC = "Acquisition, discovery, validation and reconstruction in one traceable queue.";

function queue(d) {
  const jobs = d.jobs.slice().reverse();
  const active = jobs.filter((j) => ACTIVE_JOB.has(j.status));
  const done = jobs.filter((j) => !ACTIVE_JOB.has(j.status));
  const ordered = [...active, ...done];
  const counts = ["RUNNING", "QUEUED", "COMPLETED", "FAILED"].map((s) => [s, d.jobs.filter((j) => j.status === s).length]).filter(([, n]) => n);
  return panel({
    title: "Processing queue",
    icon: "recovery",
    count: d.jobs.length,
    description: active.length ? `${number(active.length)} active · polling every 1.5 s while work is running` : "One worker per local instance · up to four pending jobs per case",
    action: counts.length ? `<div class="row">${counts.map(([s, n]) => `${badge(s, { size: "sm", label: `${number(n)} ${s.toLowerCase()}` })}`).join("")}</div>` : "",
    body: ordered.length
      ? `<div class="jobs">${ordered.map((j) => jobRow(j, d)).join("")}</div>`
      : emptyState({ icon: "recovery", title: "Engine ready", body: "Import a source to start read-only acquisition and recovery.", action: button({ label: "Import evidence", variant: "primary", icon: "upload", action: "import" }) }),
  });
}

function edgeName(id) {
  const a = artifactById(id);
  return a ? a.name.replace(/^.*·\s*/, "") : shortHash(id, 8, 4);
}

function edgesPanel(d) {
  const edges = d.edges;
  return panel({
    title: "Fragment adjacency decisions",
    icon: "link",
    count: edges.length,
    description: "Each neighbouring pair is judged on source, camera, codec, timestamps and checksums.",
    body: edges.length
      ? table({
        caption: "Fragment adjacency decisions",
        stickyFirst: true,
        columns: [
          { key: "pair", label: "From → To", render: (e) => `<span class="edge-pair"><button type="button" class="chip chip--link" data-action="view-artifact" data-id="${esc(e.from_fragment)}" title="${esc(e.from_fragment)}">${esc(edgeName(e.from_fragment))}</button>${icon("arrow", { size: 13 })}<button type="button" class="chip chip--link" data-action="view-artifact" data-id="${esc(e.to_fragment)}" title="${esc(e.to_fragment)}">${esc(edgeName(e.to_fragment))}</button></span>` },
          { key: "decision", label: "Decision", render: (e) => badge(e.decision) },
          { key: "evidence", label: "Evidence", render: (e) => `<span class="edge-evidence">${esc((e.evidence_features || []).join("; "))}</span>` },
          { key: "decode", label: "Decode", className: "nowrap", render: (e) => `<code>${esc(e.decode_result || "—")}</code>` },
        ],
        rows: edges,
        rowKey: (e) => e.id,
      })
      : emptyState({ icon: "link", title: "No fragment graph yet", body: "Relationships require compatible source, camera, codec, checksums and timestamps.", compact: true }),
  });
}

function redundancyPanel(d) {
  const sources = d.sources.filter((s) => s.redundancy);
  return panel({
    title: "Redundancy findings",
    icon: "layers",
    description: "Only what the engine found. No parity or error-correction layout is assumed.",
    body: sources.length
      ? `<div class="stack">${sources.map((s) => {
        const r = s.redundancy;
        return `<article class="redundancy" data-key="red-${esc(s.id)}">
          <div class="redundancy__head">
            <div class="redundancy__name truncate" title="${esc(s.name)}">
              ${icon("disk", { size: 15, className: "text-amber" })}
              <span>${esc(s.name)}</span>
            </div>
            ${r.verified_fragments ? toneBadge("green", `${number(r.verified_fragments)} verified`, { size: "sm" }) : toneBadge("gray", "0 verified", { size: "sm" })}
          </div>
          ${detailList([
            { label: "Duplicate indexes", value: number(r.duplicate_indexes?.length || 0) },
            { label: "Verified checksums", value: number(r.verified_fragments || 0) },
            { label: "Secondary streams", value: number(r.secondary_streams?.length || 0) },
            { label: "Parity layout", value: r.parity ? esc(r.parity) : '<span class="subtle">None assumed</span>', html: true },
            { label: "ECC layout", value: r.ecc ? esc(r.ecc) : '<span class="subtle">None assumed</span>', html: true },
            { label: "Reconstruction", value: '<span class="subtle">Unvalidated</span>', html: true },
          ], { columns: 3 })}
          <p class="redundancy__text">${icon("info", { size: 14 })}<span>${esc(r.reconstruction || "No parity reconstruction attempted without an explicit validated layout.")}</span></p>
        </article>`;
      }).join("")}</div>`
      : emptyState({ icon: "layers", title: "Discover redundancy from evidence", body: "Duplicate indexes, verified checksums and substreams appear after analysis. No parity or error-correction layout is assumed.", compact: true }),
  });
}

export function render() {
  const guard = caseGuard(TITLE, DESC);
  if (guard) return guard;
  const d = state.detail;
  return `${pageHeader({ eyebrow: caseEyebrow(), title: TITLE, description: DESC, actions: button({ label: "Import evidence", variant: "primary", icon: "upload", action: "import" }) })}
    ${queue(d)}
    <div class="grid-2 grid-2--wide-left">${edgesPanel(d)}${redundancyPanel(d)}</div>`;
}

defineActions({
  "cancel-job": async ({ id, name }) => {
    const ok = await confirmDialog({
      title: "Cancel this job?",
      message: `“${name || "This job"}” will stop at the next safe point. Artifacts already recovered are retained; the current decode may finish first.`,
      confirmLabel: "Cancel job",
      cancelLabel: "Keep running",
    });
    if (!ok) return;
    const result = await post(`/jobs/${encodeURIComponent(id)}/cancel`);
    toast(result.status || "Cancellation requested.", { tone: "info" });
    await refresh();
  },
});

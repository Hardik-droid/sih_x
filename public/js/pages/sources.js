// Evidence sources (#sources): acquired images, media exports and drives.
import { post } from "../api.js";
import { state } from "../state.js";
import { refresh } from "../data.js";
import { defineActions } from "../actions.js";
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { bytes, hexOffset, number, readable, timeTag } from "../format.js";
import { activeJobs } from "../selectors.js";
import { badge, toneBadge } from "../components/badge.js";
import { button } from "../components/button.js";
import { detailList, notice, pageHeader, panel } from "../components/card.js";
import { hashField } from "../components/hash.js";
import { emptyState } from "../components/emptyState.js";
import { table } from "../components/table.js";
import { toast } from "../components/toast.js";
import { caseGuard, caseEyebrow } from "./common.js";

const TITLE = "Evidence sources";
const DESC = "Verified forensic copies. Inspect the storage behind every recording.";

function parentPanel(parent) {
  const lv = parent.logical_verification;
  const verification = lv?.verified
    ? notice("Full logical image matches the published MD5 and SHA-1.", { tone: "success" })
    : lv && lv.verified === false
      ? notice("Full logical-image checksum verification failed. Review the verification record before relying on this image.", { tone: "danger" })
      : notice("Full logical-image checksum verification is pending.", { tone: "warning" });
  const segments = (parent.segments || []).map((s) => ({ ...s }));
  return panel({
    title: "Parent forensic image",
    description: parent.name,
    icon: "disk",
    action: button({ label: `Browse ${number(parent.index_entries)} indexed recordings`, variant: "accent", size: "sm", icon: "search", action: "open-recording-index" }),
    body: `<div class="stack">
      ${detailList([
        { label: "Logical size", value: `${bytes(parent.logical_size)} (${number(parent.logical_size)} bytes)` },
        { label: "E01 segments", value: number(segments.length) },
        { label: "Indexed recordings", value: number(parent.index_entries) },
        { label: "Search entries", value: parent.search_entries !== undefined ? number(parent.search_entries) : null },
        { label: "GPT CRC", value: parent.gpt_crc_verified ? "Verified" : parent.gpt_crc_verified === false ? "Not verified" : null },
        { label: "Catalogue", value: parent.url ? `<a class="text-link" href="${esc(parent.url)}" target="_blank" rel="noopener noreferrer"><span>Public corpus record</span>${icon("external-link", { size: 13 })}</a>` : null, html: true },
      ], { columns: 3 })}
      ${verification}
      ${segments.length ? table({
        caption: "E01 segments",
        columns: [
          { key: "file", label: "Segment", render: (s) => `<code>${esc(s.file)}</code>` },
          { key: "size", label: "Size", className: "nowrap tabular", render: (s) => bytes(s.size) },
          { key: "sha256", label: "SHA-256", render: (s) => `<code class="mono-wrap" title="${esc(s.sha256)}">${esc(s.sha256)}</code>` },
        ],
        rows: segments,
        rowKey: (s) => s.file,
        dense: true,
      }) : ""}
      <details class="disclosure"><summary>${icon("chevron-right", { size: 14 })}Image hashes, partitions and extraction provenance</summary><pre class="code-block">${esc(JSON.stringify(parent, null, 2))}</pre></details>
    </div>`,
  });
}

function health(s) {
  const h = s.health;
  if (!h) return "";
  const volumes = h.volumes || [];
  const warnings = (h.warnings || []).map((w) => notice(w, { tone: "warning" })).join("");
  const findings = s.findings || [];
  const levels = {};
  for (const e of s.deletion_evidence || []) levels[e.level] = (levels[e.level] || 0) + 1;
  const overwrite = s.overwrite_analysis;
  return `<details class="disclosure source-card__details" data-key="details-${esc(s.id)}">
    <summary>${icon("chevron-right", { size: 14 })}Storage findings · ${esc(h.scheme || "unknown layout")} · ${number(volumes.length)} ${volumes.length === 1 ? "volume" : "volumes"}</summary>
    <div class="stack">
      <p class="muted">${esc(h.bad_sectors || "")}</p>
      ${warnings}
      ${volumes.length ? table({
        caption: "Partitions and volumes",
        columns: [
          { key: "offset", label: "Offset", className: "nowrap", render: (v) => `<code>${esc(hexOffset(v.offset))}</code>` },
          { key: "length", label: "Length", className: "nowrap tabular", render: (v) => bytes(v.length) },
          { key: "filesystem", label: "Filesystem", render: (v) => esc(v.filesystem || "Unknown") },
          { key: "partition_type", label: "Type", render: (v) => esc(v.partition_type || "—") },
          { key: "status", label: "Status", render: (v) => (v.status ? badge(v.status) : '<span class="subtle">—</span>') },
        ],
        rows: volumes,
        dense: true,
      }) : ""}
      ${findings.length ? `<div><h4 class="mini-head">Index findings</h4><ul class="list list--compact" role="list">${findings.map((f) => `<li class="list__row"><span class="icon-chip icon-chip--sm">${icon("hash", { size: 14 })}</span><div class="list__main"><strong>${f.offset !== undefined ? `Index at ${esc(hexOffset(f.offset))}` : "Finding"}${f.records !== undefined ? ` · ${number(f.records)} records` : ""}${f.video_streams !== undefined ? ` · ${number(f.video_streams)} video streams` : ""}</strong><span class="list__meta">${esc(f.scope || f.reason || "")}</span></div>${f.status ? badge(f.status) : ""}</li>`).join("")}</ul></div>` : ""}
      ${Object.keys(levels).length ? `<div><h4 class="mini-head">Deletion evidence (residual analysis)</h4><div class="row">${Object.entries(levels).map(([level, n]) => `${badge(level)}<span class="subtle tabular">× ${number(n)}</span>`).join("")}</div>${overwrite ? `<p class="subtle mini-copy">Retention mechanism: ${esc(readable(overwrite.mechanism))}. ${esc(overwrite.limitation || "")}</p>` : ""}</div>` : ""}
      ${h.allocation_note ? `<p class="subtle mini-copy">${esc(h.allocation_note)}</p>` : ""}
      <details class="disclosure"><summary>${icon("chevron-right", { size: 14 })}Partition map and addressable ranges (raw)</summary><pre class="code-block">${esc(JSON.stringify({ volumes: h.volumes, regions: h.regions, allocation_note: h.allocation_note }, null, 2))}</pre></details>
    </div>
  </details>`;
}

function sourceCard(s, busy) {
  const typeIcon = s.type === "REMOVABLE_USB" ? "usb-drive" : s.type === "MEDIA_EXPORT" ? "film" : "disk";
  const redundancy = s.redundancy;
  return `<article class="source-card panel" data-key="${esc(s.id)}">
    <header class="source-card__head">
      <span class="icon-chip icon-chip--lg">${icon(typeIcon, { size: 20 })}</span>
      <div class="source-card__titles"><h2 class="source-card__title truncate" title="${esc(s.name)}">${esc(s.name)}</h2><p class="source-card__meta">${esc(s.vendor || "UNKNOWN")} · ${esc(s.model || "UNKNOWN")} · Firmware ${esc(s.firmware || "UNKNOWN")}</p></div>
      ${badge(s.status)}
    </header>
    ${detailList([
      { label: "Capacity", value: s.capacity !== undefined ? bytes(s.capacity) : null, hint: s.capacity !== undefined ? `${number(s.capacity)} bytes` : "" },
      { label: "Source type", value: readable(s.type) },
      { label: "Acquired", value: s.acquired_at ? timeTag(s.acquired_at) : null, html: true },
      { label: "Image layout", value: s.health?.scheme || (s.status === "PENDING" ? "Awaiting analysis" : null) },
      { label: "Partitions", value: s.health ? number((s.health.volumes || []).length) : null },
      { label: "Recoverable candidates", value: s.artifact_count !== undefined ? number(s.artifact_count) : null },
      { label: "Acquisition method", value: s.method || (s.status === "PENDING" ? "Pending" : null), span: 2 },
      s.read_errors?.length ? { label: "Read errors", value: number(s.read_errors.length) } : null,
    ], { columns: 3 })}
    ${hashField(s.sha256, { label: "SHA-256 · acquired image", empty: "Acquisition pending" })}
    ${redundancy ? `<p class="source-card__redundancy">${icon("layers", { size: 14 })}<span>${number(redundancy.duplicate_indexes?.length || 0)} duplicate indexes · ${number(redundancy.verified_fragments || 0)} verified checksums · ${number(redundancy.secondary_streams?.length || 0)} secondary streams</span></p>` : ""}
    ${health(s)}
    <footer class="source-card__actions">
      ${button({ label: s.status === "PENDING" ? "Retry acquisition" : "Analyze again", icon: "recovery", size: "sm", action: "analyze-source", data: { id: s.id }, disabled: busy, title: busy ? "This source already has an active job" : "Re-run acquisition checks and analysis" })}
      ${button({ label: "Inspect bytes", icon: "hash", size: "sm", action: "inspect-bytes", data: { id: s.id }, disabled: !s.sha256, title: s.sha256 ? "Read raw bytes from the verified copy" : "Available after acquisition" })}
      ${s.status === "ANALYZED" ? button({ label: "View findings", icon: "eye", size: "sm", variant: "ghost", action: "toggle-findings", data: { id: s.id } }) : ""}
    </footer>
  </article>`;
}

export function render() {
  const guard = caseGuard(TITLE, DESC);
  if (guard) return guard;
  const d = state.detail;
  const busyIds = new Set(activeJobs(d).map((j) => j.source_id).filter(Boolean));
  const actions = button({ label: "Forensic USB Ingest", variant: "accent", icon: "zap", action: "usb-ingest" }) + button({ label: "Import evidence", variant: "primary", icon: "upload", action: "import" });
  const parent = d.case.parent_evidence ? parentPanel(d.case.parent_evidence) : "";
  const list = d.sources.length
    ? `<div class="source-grid">${d.sources.slice().reverse().map((s) => sourceCard(s, busyIds.has(s.id))).join("")}</div>`
    : panel({ title: "Sources", body: emptyState({ icon: "sources", title: "Your evidence, organized.", body: "Add a forensic image or media export to begin read-only acquisition and analysis.", action: button({ label: "Add first source", variant: "primary", icon: "plus", action: "import" }) }) });
  return `${pageHeader({ eyebrow: caseEyebrow(), title: TITLE, description: DESC, actions })}${parent}${list}`;
}

defineActions({
  "analyze-source": async ({ id }) => {
    await post(`/sources/${encodeURIComponent(id)}/analyze`);
    await refresh();
    toast("Analysis queued. Progress appears in the Recovery engine.", { tone: "info", action: { label: "Open queue", onClick: () => { location.hash = "#recovery"; } } });
  },
  "toggle-findings": ({ id }) => {
    const details = document.querySelector(`[data-key="details-${CSS.escape(id)}"]`);
    if (!details) return;
    details.open = !details.open;
    if (details.open) details.scrollIntoView({ behavior: "smooth", block: "nearest" });
  },
});

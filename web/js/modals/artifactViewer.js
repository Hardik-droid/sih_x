// Artifact viewer: player + persistent evidence banner, derivative actions, and
// a full provenance panel (hashes, byte ranges, method, validation, lineage).
import { get, post } from "../api.js";
import { state, notify } from "../state.js";
import { refresh } from "../data.js";
import { defineActions } from "../actions.js";
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { bytes, duration, hexOffset, number, timeTag, utc } from "../format.js";
import { isDerivative, statusInfo } from "../statusMap.js";
import { artifactById, deletionEvidenceFor, interval, qualityOf, sourceById } from "../selectors.js";
import { openModal, topModal } from "../components/modal.js";
import { badge, derivativeTag, toneBadge } from "../components/badge.js";
import { button } from "../components/button.js";
import { detailList, notice } from "../components/card.js";
import { hashField } from "../components/hash.js";
import { emptyState } from "../components/emptyState.js";
import { fqiMeter } from "../components/artifactCard.js";
import { toast } from "../components/toast.js";

const TRANSFORMS = [
  { op: "repair", label: "Repair container", icon: "refresh", hint: "Stream-copy repair with validated-prefix fallback" },
  { op: "denoise", label: "Denoise copy", icon: "sliders", hint: "Deterministic FFmpeg denoise filter" },
  { op: "contrast", label: "Adjust contrast", icon: "sliders", hint: "Deterministic FFmpeg contrast filter" },
  { op: "adaptive_contrast", label: "Adaptive contrast", icon: "sliders", hint: "Deterministic FFmpeg adaptive contrast filter" },
  { op: "sharpen", label: "Sharpen copy", icon: "sliders", hint: "Deterministic FFmpeg sharpen filter" },
];

function banner(a) {
  if (a.status === "ENHANCED_COPY") return `<p class="evidence-banner evidence-banner--derivative">${icon("sparkles", { size: 14 })}<span>ENHANCED VIEWING COPY — transformed pixels, not original evidence.</span></p>`;
  if (isDerivative(a)) return `<p class="evidence-banner evidence-banner--derivative">${icon("sparkles", { size: 14 })}<span>DERIVATIVE COPY — repaired container, not original evidence.</span></p>`;
  return `<p class="evidence-banner">${icon("info", { size: 14 })}<span>VIEWING COPY — video-only H.264 transcode. Download original for exact recovered bytes.</span></p>`;
}

function stage(a) {
  const base = `/api/artifacts/${encodeURIComponent(a.id)}/file`;
  let media;
  if (a.preview_path) {
    media = `<video class="viewer__video" controls preload="metadata" playsinline ${a.thumbnail_path ? `poster="${base}?variant=thumbnail"` : ""} src="${base}?variant=preview" data-media></video>`;
  } else if (a.thumbnail_path) {
    media = `<img class="viewer__image" src="${base}?variant=thumbnail" alt="Recovered frame from ${esc(a.name)}" data-media>`;
  } else {
    media = emptyState({ icon: "film", title: "No decodable preview", body: "Candidate bytes and decoder diagnostics remain available for inspection.", compact: true });
  }
  return `<div class="viewer__stage${isDerivative(a) ? " viewer__stage--derivative" : ""}">${media}${banner(a)}</div>`;
}

function audio(a) {
  const base = `/api/artifacts/${encodeURIComponent(a.id)}/file?variant=audio`;
  if (a.audio_path) {
    const t = a.audio_track || {};
    const meta = [t.format, t.sample_rate ? `${number(t.sample_rate)} Hz` : "", t.channels ? `${t.channels} ch` : "", t.duration_seconds !== undefined ? duration(t.duration_seconds) : ""].filter(Boolean).join(" · ");
    return `<div class="viewer__audio"><div class="row row--between"><strong class="viewer__subhead">${icon("audio", { size: 15 })} Demuxed audio track</strong>${button({ label: "Download WAV", size: "sm", variant: "ghost", icon: "download", href: base, download: "" })}</div><audio controls preload="none" src="${base}"></audio>${meta ? `<p class="subtle viewer__caption">${esc(meta)}</p>` : ""}</div>`;
  }
  if (a.audio_track) {
    const t = a.audio_track;
    return notice(`Audio track recorded in metadata (${[t.format, t.duration_seconds !== undefined ? duration(t.duration_seconds) : ""].filter(Boolean).join(", ")}), but no demuxed audio file is stored for this artifact.`, { tone: "neutral" });
  }
  return "";
}

function qualityBlock(a) {
  const q = qualityOf(a);
  if (!q) {
    return `<div class="viewer__quality" data-quality><div class="row row--between"><span class="subtle">Forensic Quality Index not assessed.</span>${button({ label: "Assess quality", size: "sm", icon: "gauge", action: "assess-quality", data: { id: a.id } })}</div></div>`;
  }
  const m = q.metrics || {};
  return `<div class="viewer__quality" data-quality>
    ${fqiMeter(q)}
    ${detailList([
      m.blur_variance !== undefined ? { label: "Laplacian blur variance", value: m.blur_variance } : null,
      m.contrast?.dynamic_range !== undefined ? { label: "Dynamic range", value: m.contrast.dynamic_range } : null,
      m.blockiness !== undefined ? { label: "Blockiness", value: m.blockiness } : null,
      m.frames_sampled !== undefined ? { label: "Frames sampled", value: m.frames_sampled } : null,
    ], { columns: 2 })}
    ${m.evidence_policy ? `<p class="subtle viewer__caption">${esc(m.evidence_policy)}</p>` : ""}
    <div class="row">${button({ label: q.assessed ? "Re-assess" : "Assess again", size: "sm", variant: "ghost", icon: "refresh", action: "assess-quality", data: { id: a.id } })}</div>
  </div>`;
}

function lineage(a) {
  const d = state.detail;
  const items = (d?.transformations || []).filter((t) => t.input_artifact === a.id || t.output_artifact === a.id || (t.input_artifacts || []).includes(a.id));
  if (!items.length) return "";
  return `<div class="viewer__section"><h3 class="viewer__subhead">Transformation record</h3><ol class="lineage" role="list">${items.map((t) => `<li class="lineage__item"><span class="lineage__dot" aria-hidden="true"></span><div><strong>${esc(String(t.transform_type || "transformation").replace(/_/g, " "))}</strong><span class="subtle"> · ${timeTag(t.created_at)}</span>${t.output_hash ? `<div class="mono lineage__hash" title="${esc(t.output_hash)}">→ ${esc(String(t.output_hash).slice(0, 16))}…</div>` : ""}${t.parameters && typeof t.parameters === "string" ? `<div class="subtle">${esc(t.parameters)}</div>` : ""}</div></li>`).join("")}</ol></div>`;
}

function provenance(a) {
  const v = a.validation || {};
  const source = sourceById(a.source_id);
  const range = a.offset_start !== undefined && a.offset_end !== undefined ? `${hexOffset(a.offset_start)} → ${hexOffset(a.offset_end)} · ${bytes(a.offset_end - a.offset_start)}` : null;
  const span = interval(a);
  const time = span ? (span.basis === "recorder" ? `${utc(span.start * 1000)} → ${utc(span.end * 1000)}` : `${span.start} s → ${span.end} s (indexed)`) : null;
  const residual = deletionEvidenceFor(a);
  const inputs = a.input_hashes?.length ? a.input_hashes.map((h, i) => hashField(h, { label: `Input ${i + 1} SHA-256` })).join("") : hashField(a.input_hash, { label: "Input SHA-256" });
  const parent = a.parent_id ? artifactById(a.parent_id) : null;
  return `<div class="viewer__prov">
    <div class="row">${badge(a.status)}${a.kind === "DERIVATIVE" ? derivativeTag() : badge(a.kind)}${a.integrity_status ? badge(a.integrity_status, { label: `Integrity ${statusInfo(a.integrity_status).label.toLowerCase()}` }) : ""}</div>
    ${isDerivative(a) ? notice("This is a separate derivative. The recovered original is retained unchanged; its hash is listed as the input below.", { tone: "violet" }) : ""}
    ${detailList([
      { label: "Camera / channel", value: a.channel },
      { label: "Codec", value: a.codec ? String(a.codec).toUpperCase() : null },
      { label: "Decoded frames", value: v.frames_decoded !== undefined ? number(v.frames_decoded) : null },
      { label: "Decode result", value: v.decode_result },
      { label: "Resolution", value: v.width ? `${v.width} × ${v.height}` : null },
      { label: "Container duration", value: v.duration !== null && v.duration !== undefined ? duration(v.duration) : null },
      { label: "Representation", value: a.representation },
      { label: "Parser", value: a.parser },
      { label: "Completeness", value: a.completeness },
      { label: "Source", value: source?.name || null },
      range ? { label: "Source byte range", value: range, mono: true, span: 2 } : null,
      time ? { label: span.basis === "recorder" ? "Recorder clock (timezone unverified)" : "Recording interval", value: time, span: 2 } : null,
    ], { columns: 2 })}
    <div class="viewer__section"><h3 class="viewer__subhead">Recovery method</h3><p class="viewer__text">${esc(a.method || "Unknown")}</p></div>
    <div class="viewer__section"><h3 class="viewer__subhead">Confidence rationale</h3><p class="viewer__text">${esc(a.confidence_rationale || "Not recorded")}</p></div>
    ${a.salvaged_method ? `<div class="viewer__section"><h3 class="viewer__subhead">Salvage</h3><p class="viewer__text">${esc(a.salvaged_method)}</p></div>` : ""}
    ${a.time_basis ? `<div class="viewer__section"><h3 class="viewer__subhead">Time basis</h3><p class="viewer__text">${esc(a.time_basis)}</p></div>` : ""}
    ${residual ? `<div class="viewer__section"><h3 class="viewer__subhead">Deletion evidence</h3><div class="row">${badge(residual.level)}</div><p class="viewer__text subtle">${esc(residual.rationale || "")}</p></div>` : ""}
    <div class="viewer__section viewer__hashes">${hashField(a.sha256, { label: "Output SHA-256" })}${inputs}${a.preview_sha256 && a.preview_sha256 !== a.sha256 ? hashField(a.preview_sha256, { label: "Viewing copy SHA-256" }) : ""}</div>
    ${parent ? `<div class="viewer__section">${button({ label: `Open parent · ${parent.name}`, size: "sm", variant: "ghost", icon: "arrow-left", action: "view-artifact", data: { id: parent.id } })}</div>` : ""}
    <div class="viewer__section"><h3 class="viewer__subhead">Forensic quality</h3>${qualityBlock(a)}</div>
    ${lineage(a)}
    <div class="viewer__section viewer__raw">
      <details class="disclosure"><summary>${icon("chevron-right", { size: 14 })}Source fragments (${(a.source_fragments || []).length})</summary><pre class="code-block">${esc(JSON.stringify(a.source_fragments || [], null, 2))}</pre></details>
      ${a.payload_ranges ? `<details class="disclosure"><summary>${icon("chevron-right", { size: 14 })}Exact payload byte ranges (${a.payload_ranges.length})</summary><pre class="code-block">${esc(JSON.stringify(a.payload_ranges, null, 2))}</pre></details>` : ""}
      ${a.gaps?.length ? `<details class="disclosure" open><summary>${icon("chevron-right", { size: 14 })}Explicit gaps (${a.gaps.length})</summary><pre class="code-block">${esc(JSON.stringify(a.gaps, null, 2))}</pre></details>` : ""}
      <details class="disclosure"><summary>${icon("chevron-right", { size: 14 })}Validation &amp; diagnostics</summary><pre class="code-block">${esc(JSON.stringify(v, null, 2))}</pre></details>
    </div>
  </div>`;
}

function body(a) {
  const original = `/api/artifacts/${encodeURIComponent(a.id)}/file?variant=original`;
  return `<div class="viewer">
    <div class="viewer__main">
      ${stage(a)}
      ${audio(a)}
      <div class="viewer__actions">
        ${button({ label: "Download original bytes", variant: "primary", icon: "download", href: original, download: "", title: "Exact recovered bytes (download is recorded in the audit log)" })}
        ${button({ label: "Assess quality", icon: "gauge", action: "assess-quality", data: { id: a.id } })}
      </div>
      <div class="viewer__derive">
        <div class="viewer__derive-head"><h3 class="viewer__subhead">Create a separate derivative</h3><p class="subtle">Each operation writes a new file with its own hash and transformation record. The recovered original is never modified.</p></div>
        <div class="viewer__derive-actions">${TRANSFORMS.map((t) => button({ label: t.label, size: "sm", icon: t.icon, action: "transform", title: t.hint, data: { id: a.id, op: t.op } })).join("")}</div>
      </div>
    </div>
    <aside class="viewer__side" aria-label="Provenance">${provenance(a)}</aside>
  </div>`;
}

let current = null;

export function openArtifactViewer(id) {
  const a = artifactById(id);
  if (!a) return;
  if (current) { const prev = current; current = null; prev.close(); }
  const ctrl = openModal({
    title: a.name,
    description: [a.channel, a.codec ? String(a.codec).toUpperCase() : "", statusInfo(a.status).label].filter(Boolean).join(" · "),
    size: "xl",
    className: "modal--viewer",
    body: body(a),
    onClose: () => { if (current === ctrl) current = null; },
    onMount(dialog) {
      const mediaEl = dialog.querySelector("[data-media]");
      mediaEl?.addEventListener("error", () => {
        const holder = mediaEl.parentElement;
        mediaEl.remove();
        holder.insertAdjacentHTML("afterbegin", emptyState({ icon: "film", title: "Viewing copy unavailable on this server", body: "The recovered bytes and their provenance remain listed here. Open the acquisition workstation to review media.", compact: true }));
      }, { once: true });
    },
  });
  current = ctrl;
  current.artifactId = id;
}

function refreshQualityBlock(id) {
  if (!current || current.artifactId !== id) return;
  const a = artifactById(id);
  const block = current.el.querySelector("[data-quality]");
  if (a && block) block.outerHTML = qualityBlock(a);
}

defineActions({
  "view-artifact": ({ id }) => openArtifactViewer(id),
  "assess-quality": async ({ id }) => {
    const caseId = state.caseId;
    const result = await get(`/artifacts/${encodeURIComponent(id)}/quality`);
    if (caseId !== state.caseId) return;
    state.quality[id] = result;
    refreshQualityBlock(id);
    notify("quality");
    toast(`Quality assessed: ${result.forensic_quality_index} / 100 (${statusInfo(result.category).label})`, { tone: "info" });
  },
  transform: async ({ id, op }) => {
    await post(`/artifacts/${encodeURIComponent(id)}/transform`, { operation: op });
    await refresh();
    toast("Queued — check Recovery engine.", {
      tone: "info",
      action: { label: "Open queue", onClick: () => { topModal()?.close(); location.hash = "#recovery"; } },
    });
  },
});

// Timeline & notes (#timeline): per-camera recovered intervals, substream gap
// coverage, and the examiner's running log.
import { post } from "../api.js";
import { state, notify } from "../state.js";
import { loadCorrelation, refresh } from "../data.js";
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { bytes, number, readable, timeTag } from "../format.js";
import { interval } from "../selectors.js";
import { badge, toneBadge } from "../components/badge.js";
import { notice, pageHeader, panel } from "../components/card.js";
import { emptyState } from "../components/emptyState.js";
import { skeleton } from "../components/skeleton.js";
import { timelineLanes } from "../components/timelineTrack.js";
import { toastSuccess } from "../components/toast.js";
import { caseGuard, caseEyebrow } from "./common.js";

const TITLE = "Timeline & examiner notes";
const DESC = "Review indexed recording intervals. Empty intervals remain visible.";

function correlationPanel() {
  const corr = state.correlation;
  if (!corr || corr.status !== "MULTI_REPRESENTATION_CORRELATED") return "";
  const channels = Object.values(corr.channels || {});
  const body = `<div class="stack">
    <p class="muted">${esc(corr.forensic_policy?.rationale || "")}</p>
    <div class="row corr__stats">
      <span class="corr__stat"><strong class="tabular">${number(corr.total_primary_gaps)}</strong> primary-stream gaps analysed</span>
      <span class="corr__stat corr__stat--green"><strong class="tabular">${number(corr.gaps_covered_by_substreams)}</strong> covered by a secondary substream</span>
      ${corr.forensic_policy?.pixel_synthesis ? toneBadge("gray", `Pixel synthesis ${String(corr.forensic_policy.pixel_synthesis).toLowerCase()}`, { icon: "x-circle", size: "sm" }) : ""}
    </div>
    <div class="corr__grid">${channels.map((ch) => `<div class="corr__channel" data-key="corr-${esc(ch.channel)}">
      <div class="row row--between"><strong>${esc(ch.channel)}</strong>${toneBadge(ch.status === "PRIMARY_ONLY" ? "gray" : "blue", readable(ch.status), { size: "sm" })}</div>
      <p class="subtle mini-copy">${number(ch.main_fragment_count)} primary · ${number(ch.substream_fragment_count)} secondary fragments</p>
      ${(ch.gaps_in_primary || []).length
        ? (ch.gaps_in_primary || []).map((g) => g.covered_by_substream
          ? `<p class="corr__gap corr__gap--covered">${icon("check", { size: 14 })}<span>Gap ${esc(g.gap_start)}–${esc(g.gap_end)} s (${esc(g.duration_seconds)} s) fully covered by secondary substream</span></p>`
          : `<p class="corr__gap">${icon("warning", { size: 14 })}<span>Uncovered gap ${esc(g.gap_start)}–${esc(g.gap_end)} s (${esc(g.duration_seconds)} s)</span></p>`).join("")
        : '<p class="corr__gap corr__gap--none">No gaps between primary fragments.</p>'}
    </div>`).join("")}</div>
  </div>`;
  return panel({ title: "Multi-representation substream correlation", icon: "layers", count: corr.gaps_covered_by_substreams, description: "Surviving substreams can cover primary-stream gaps with lower-resolution context.", body });
}

function lanesPanel(d) {
  const clips = d.artifacts.filter((a) => a.kind === "RECOVERED").map((a) => ({ a, span: interval(a) })).filter((x) => x.span);
  const unknown = d.artifacts.filter((a) => a.kind === "RECOVERED" && !interval(a)).length;
  const groups = ["indexed", "recorder"].map((basis) => ({
    basis,
    clips: clips.filter((x) => x.span.basis === basis).map(({ a, span }) => ({
      id: a.id,
      name: a.name,
      channel: a.channel,
      start: span.start,
      end: span.end,
      status: a.status,
      representation: a.representation,
    })),
  })).filter((g) => g.clips.length);

  if (!groups.length) {
    if (!d.artifacts.length) {
      return panel({
        title: "Recovered intervals",
        icon: "timeline",
        body: emptyState({
          icon: "timeline",
          title: "No evidence ingested yet",
          body: "Acquire an evidence source or run extraction in Recovery engine to discover recording intervals.",
          action: `<a class="btn btn--primary" href="#sources">${icon("sources", { size: 16 })}<span class="btn__label">Evidence sources</span></a>`,
        }),
      });
    }

    const unindexed = d.artifacts.filter((a) => a.kind === "RECOVERED" && !interval(a));
    const listToRender = unindexed.length ? unindexed : d.artifacts;
    const tableRows = listToRender.map((a) => `<tr>
      <td><strong class="tabular">${esc(a.name)}</strong></td>
      <td>${esc(a.channel || "—")}</td>
      <td><code>${esc(a.codec || a.stream_type || "UNKNOWN")}</code></td>
      <td>${badge(a.status, { size: "sm" })}</td>
      <td class="text-right"><button type="button" class="btn btn--secondary btn--xs" data-action="view-artifact" data-id="${esc(a.id)}">${icon("eye", { size: 12 })} View</button></td>
    </tr>`).join("");

    const body = `<div class="unindexed-panel">
      <div class="unindexed-callout">
        <div class="unindexed-callout__head">
          ${icon("info", { size: 16 })}
          <span>${number(listToRender.length)} cataloged artifacts lack container recording intervals</span>
        </div>
        <p class="unindexed-callout__text">
          Container timestamp metadata or trustworthy recorder clock frames were not found in these fragments (e.g. raw dumps, stream corruption, or missing headers).
          <strong>Forensic standard:</strong> Trace strictly prohibits estimating or guessing intervals from filenames or directory timestamps.
        </p>
      </div>
      <div class="unindexed-table-wrap">
        <table class="unindexed-table">
          <thead>
            <tr>
              <th>Fragment</th>
              <th>Channel</th>
              <th>Format</th>
              <th>Status</th>
              <th class="text-right">Action</th>
            </tr>
          </thead>
          <tbody>${tableRows}</tbody>
        </table>
      </div>
      <div class="row row--between">
        <span class="subtle mini-copy">Preserved in read-only evidence store with verified SHA-256 provenance.</span>
        <a class="btn btn--secondary btn--sm" href="#evidence">${icon("evidence", { size: 14 })}<span class="btn__label">Inspect all in Evidence</span></a>
      </div>
    </div>`;

    return panel({
      title: "Recovered intervals",
      icon: "timeline",
      count: listToRender.length,
      description: "Interval metadata missing — strictly preserved without guessing",
      body,
    });
  }

  return groups.map((g) => panel({
    title: g.basis === "recorder" ? "Recorder clock intervals" : "Recovered intervals",
    description: g.basis === "recorder" ? "Raw recorder clock rendered in UTC · timezone and clock accuracy unverified" : "Source-index times (relative seconds for the laboratory fixture)",
    icon: "timeline",
    count: g.clips.length,
    body: timelineLanes({ clips: g.clips, basis: g.basis }),
    footer: unknown ? `<span>${icon("info", { size: 14 })}${number(unknown)} ${unknown === 1 ? "artifact has" : "artifacts have"} unknown recording time.</span>` : "",
  })).join("");
}

function renderNoteContent(text) {
  let parsed = null;
  if (typeof text === "string" && (text.trim().startsWith("{") || text.trim().startsWith("["))) {
    try {
      parsed = JSON.parse(text);
    } catch (_) {
      parsed = null;
    }
  }

  if (parsed && typeof parsed === "object" && !Array.isArray(parsed) && (parsed.validation || (parsed.file && parsed.sha256))) {
    const v = parsed.validation || {};
    const isPass = v.decode_result === "PASS";
    const errorMsg = v.errors && v.errors.length ? v.errors[0] : null;
    const publisherMatch = parsed.publisher_md5_match;
    const jsonStr = JSON.stringify(parsed, null, 2);

    return `<div class="note-val-card">
      <div class="note-val-card__header">
        <div class="note-val-card__file" title="${esc(parsed.file || "Validation artifact")}">
          ${icon("file", { size: 14, className: "note-val-card__icon" })}
          <strong class="note-val-card__filename">${esc(parsed.file || "Validation Sample")}</strong>
        </div>
        ${isPass
          ? `<span class="badge badge--green badge--sm">${icon("check", { size: 11 })} PASS · ${number(v.frames_decoded ?? 0)} frames</span>`
          : `<span class="badge badge--red badge--sm">${icon("x-circle", { size: 11 })} FAIL · ${number(v.frames_decoded ?? 0)} frames</span>`}
      </div>

      <div class="note-val-card__meta-grid">
        <div class="note-val-card__meta-item">
          <span class="note-val-card__meta-label">File size</span>
          <span class="note-val-card__meta-val">${bytes(parsed.bytes)}</span>
        </div>
        <div class="note-val-card__meta-item">
          <span class="note-val-card__meta-label">Publisher MD5</span>
          <span class="note-val-card__meta-val ${publisherMatch ? "text-green" : ""}">
            ${publisherMatch ? `${icon("check", { size: 10 })} Verified` : esc(parsed.publisher_md5 || "—")}
          </span>
        </div>
        <div class="note-val-card__meta-item">
          <span class="note-val-card__meta-label">Pipeline</span>
          <span class="note-val-card__meta-val">${esc(parsed.pipeline_status || "COMPLETED")} (${parsed.pipeline_result?.recoverable ?? 0} recov.)</span>
        </div>
      </div>

      ${parsed.sha256 ? `<div class="note-val-card__hash-row">
        <span class="subtle mini-copy">SHA-256</span>
        <code class="hash-code" title="${esc(parsed.sha256)}">${esc(parsed.sha256.slice(0, 16))}…${esc(parsed.sha256.slice(-8))}</code>
        <button type="button" class="btn btn--ghost btn--xs" data-action="copy-text" data-copy="${esc(parsed.sha256)}" title="Copy SHA-256">${icon("copy", { size: 12 })}</button>
      </div>` : ""}

      ${errorMsg ? `<div class="note-val-card__error">
        ${icon("warning", { size: 13, className: "flex-none" })}
        <span>${esc(errorMsg)}</span>
      </div>` : ""}

      <details class="note-val-card__details">
        <summary class="note-val-card__summary">
          <span>${icon("terminal", { size: 12 })} Diagnostic JSON payload</span>
        </summary>
        <div class="note-val-card__details-body">
          <div class="note-val-card__details-actions">
            <button type="button" class="btn btn--secondary btn--xs" data-action="copy-text" data-copy="${esc(jsonStr)}">
              ${icon("copy", { size: 12 })} Copy JSON
            </button>
          </div>
          <pre class="code-block note-val-card__pre"><code>${esc(jsonStr)}</code></pre>
        </div>
      </details>
    </div>`;
  }

  if (parsed && typeof parsed === "object") {
    const jsonStr = JSON.stringify(parsed, null, 2);
    return `<div class="note-json-card">
      <div class="note-json-card__header">
        <span class="subtle mini-copy">${icon("terminal", { size: 12 })} Structured JSON Record</span>
        <button type="button" class="btn btn--ghost btn--xs" data-action="copy-text" data-copy="${esc(jsonStr)}" title="Copy JSON">${icon("copy", { size: 12 })} Copy</button>
      </div>
      <pre class="code-block note-json-pre"><code>${esc(jsonStr)}</code></pre>
    </div>`;
  }

  return `<p class="note-item__body">${esc(text)}</p>`;
}

function notesPanel(d) {
  const notes = d.notes.slice().reverse();
  const artifacts = d.artifacts;
  return panel({
    title: "Examiner notes",
    icon: "note",
    count: notes.length,
    className: "notes-panel",
    body: `<form class="note-form" data-note-form novalidate>
        <label class="sr-only" for="note-text">New examiner note</label>
        <textarea class="textarea" id="note-text" name="text" rows="3" maxlength="10000" placeholder="Record an observation, context or decision…" data-preserve></textarea>
        <div class="note-form__row">
          ${artifacts.length ? `<div class="select-wrap select-wrap--sm"><label class="sr-only" for="note-artifact">Link to artifact</label><select class="select" id="note-artifact" name="artifact_id" data-preserve><option value="">Not linked to an artifact</option>${artifacts.map((a) => `<option value="${esc(a.id)}">${esc(a.name)}</option>`).join("")}</select></div>` : "<span></span>"}
          <button type="submit" class="btn btn--primary btn--sm"><span class="btn__label">Add note</span><span class="btn__spinner" aria-hidden="true"></span></button>
        </div>
        <p class="form__error" role="alert"></p>
      </form>
      ${notes.length ? `<div class="notes-feed" role="list">${notes.map((n) => {
        const linked = n.artifact_id ? artifacts.find((a) => a.id === n.artifact_id) : null;
        const actorName = n.actor || "Examiner";
        const actorInitials = actorName.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase() || "EX";
        return `<div class="note-item" data-key="${esc(n.id)}" role="listitem">
          <div class="note-item__head">
            <div class="note-item__author">
              <span class="note-item__avatar" aria-hidden="true">${esc(actorInitials)}</span>
              <strong class="note-item__name">${esc(actorName)}</strong>
            </div>
            <div class="note-item__time subtle">${timeTag(n.created_at)}</div>
          </div>
          ${renderNoteContent(n.text)}
          ${linked ? `<div class="note-item__footer"><button type="button" class="chip chip--link" data-action="view-artifact" data-id="${esc(linked.id)}">${icon("link", { size: 12 })}<span>Linked to ${esc(linked.name)}</span></button></div>` : ""}
        </div>`;
      }).join("")}</div>` : '<p class="subtle notes__empty">Record observations, context and investigation decisions. Notes are added to the hash-chained audit log.</p>'}`,
  });
}

export function render() {
  const guard = caseGuard(TITLE, DESC);
  if (guard) return guard;
  const d = state.detail;
  const corr = state.correlation === null && d.artifacts.length ? `<div class="panel panel--loading">${skeleton({ lines: 2 })}</div>` : correlationPanel();
  return `${pageHeader({ eyebrow: caseEyebrow(), title: TITLE, description: DESC })}
    ${notice("Timeline uses source-index times where available. The laboratory fixture uses relative seconds; unknown recording times are never guessed from filenames.", { tone: "neutral" })}
    ${corr}
    <div class="grid-main-aside">
      <div class="stack">${lanesPanel(d)}</div>
      ${notesPanel(d)}
    </div>`;
}

function ensureCorrelation() {
  if (!state.detail || state.correlation !== null || !state.detail.artifacts.length) return;
  loadCorrelation().then(() => notify("correlation")).catch(() => { state.correlation = { status: "UNAVAILABLE" }; notify("correlation"); });
}

export function mount(root) {
  ensureCorrelation();
  const onClick = async (event) => {
    const copyBtn = event.target.closest('[data-action="copy-text"]');
    if (copyBtn) {
      event.preventDefault();
      const text = copyBtn.dataset.copy || "";
      if (text) {
        try {
          await navigator.clipboard.writeText(text);
          toastSuccess("Copied to clipboard");
        } catch (_) {}
      }
      return;
    }
  };
  const onSubmit = async (event) => {
    const form = event.target.closest("[data-note-form]");
    if (!form) return;
    event.preventDefault();
    const error = form.querySelector(".form__error");
    const textarea = form.querySelector("textarea");
    const text = textarea.value.trim();
    error.textContent = "";
    if (!text) { error.textContent = "Write a note before adding it."; textarea.focus(); return; }
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    submit.dataset.loading = "true";
    try {
      const artifactId = form.querySelector("select")?.value || null;
      await post(`/cases/${encodeURIComponent(state.caseId)}/notes`, artifactId ? { text, artifact_id: artifactId } : { text });
      textarea.value = "";
      const select = form.querySelector("select");
      if (select) select.value = "";
      await refresh();
      toastSuccess("Observation added to the case.");
    } catch (err) {
      error.textContent = err.message;
    } finally {
      submit.disabled = false;
      delete submit.dataset.loading;
    }
  };
  root.addEventListener("click", onClick);
  root.addEventListener("submit", onSubmit);
  return () => {
    root.removeEventListener("click", onClick);
    root.removeEventListener("submit", onSubmit);
  };
}

export function update() { ensureCorrelation(); }

// Recovered-evidence card. Derivatives carry the dashed violet outline and a
// persistent "Derivative" corner tag in the grid itself (BUILD.md §5.6).
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { number } from "../format.js";
import { isDerivative, statusInfo } from "../statusMap.js";
import { qualityOf, isJoinable, hasAudio } from "../selectors.js";
import { badge, derivativeTag, toneBadge } from "./badge.js";

function glyph(a) {
  if (a.stream_type === "jpg") return "image";
  if (a.kind === "RECONSTRUCTED") return "link";
  return "film";
}

export function fqiMeter(quality, { compact = false } = {}) {
  if (!quality) return "";
  const info = quality.category ? statusInfo(quality.category) : { tone: "gray", label: "FQI" };
  const score = Number(quality.score);
  return `<div class="fqi${compact ? " fqi--compact" : ""}" title="Forensic Quality Index ${esc(score)} / 100${quality.category ? ` · ${esc(info.label)}` : ""}">
    <div class="fqi__row"><span class="fqi__label">FQI</span><span class="fqi__score tabular">${esc(score.toFixed(1))}</span><span class="fqi__cat fqi__cat--${esc(info.tone)}">${esc(info.label)}</span></div>
    <div class="fqi__track"><span class="fqi__fill fqi__fill--${esc(info.tone)}" style="width:${Math.max(0, Math.min(100, score))}%"></span></div>
  </div>`;
}

export function artifactCard(a, { selected = false } = {}) {
  const derivative = isDerivative(a);
  const quality = qualityOf(a);
  const joinable = isJoinable(a);
  const v = a.validation || {};
  const media = a.thumbnail_path
    ? `<img src="/api/artifacts/${esc(a.id)}/file?variant=thumbnail" alt="Recovered frame from ${esc(a.name)}" loading="lazy" decoding="async" data-fallback="glyph">`
    : "";
  const meta = [
    a.channel ? `<span class="meta-chip">${icon("camera", { size: 12 })}${esc(a.channel)}</span>` : '<span class="meta-chip meta-chip--muted">Unknown camera</span>',
    `<span class="meta-chip">${esc(String(a.codec || "unknown").toUpperCase())}</span>`,
    `<span class="meta-chip tabular">${number(v.frames_decoded ?? 0)} frames</span>`,
    v.width ? `<span class="meta-chip tabular">${esc(v.width)}×${esc(v.height)}</span>` : "",
    a.representation === "substream" ? '<span class="meta-chip">Substream</span>' : "",
    hasAudio(a) ? `<span class="meta-chip">${icon("audio", { size: 12 })}Audio</span>` : "",
  ].join("");
  return `<article class="art-card${derivative ? " art-card--derivative" : ""}${selected ? " is-selected" : ""}" data-key="${esc(a.id)}">
    <button type="button" class="art-card__media" data-action="view-artifact" data-id="${esc(a.id)}" aria-label="Review ${esc(a.name)}">
      <span class="art-card__glyph" aria-hidden="true">${icon(glyph(a), { size: 26 })}<span>${esc(String(a.codec || a.stream_type || "unknown").toUpperCase())}</span></span>
      ${media}
      ${a.preview_path ? `<span class="art-card__play" aria-hidden="true">${icon("play", { size: 16 })}</span>` : ""}
      <span class="art-card__status">${badge(a.status, { size: "sm" })}</span>
      ${derivative ? `<span class="art-card__corner">${derivativeTag()}</span>` : a.kind === "RECONSTRUCTED" ? `<span class="art-card__corner">${toneBadge("blue", "Reconstructed", { icon: "link", size: "sm" })}</span>` : ""}
    </button>
    <div class="art-card__body">
      <h3 class="art-card__title" title="${esc(a.name)}">${esc(a.name)}</h3>
      <div class="art-card__meta">${meta}</div>
      ${fqiMeter(quality, { compact: true })}
      <div class="art-card__foot">
        ${joinable
          ? `<label class="check"><input type="checkbox" class="check__input" data-select="${esc(a.id)}"${selected ? " checked" : ""}><span class="check__box" aria-hidden="true">${icon("check", { size: 12 })}</span><span class="check__label">Select for join</span></label>`
          : `<span class="art-card__hint" title="Joining requires indexed Annex-B H.264 fragments recovered from this case">${derivative ? "Derivative · not joinable" : a.kind === "RECONSTRUCTED" ? "Joined output" : "Not joinable"}</span>`}
        <button type="button" class="text-link" data-action="view-artifact" data-id="${esc(a.id)}"><span>Provenance</span>${icon("arrow", { size: 14 })}</button>
      </div>
    </div>
  </article>`;
}

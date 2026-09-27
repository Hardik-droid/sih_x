// Compatibility (#registry): exact validation scope for every vendor/format.
// Limitations are always shown in full — never collapsed.
import { state } from "../state.js";
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { number } from "../format.js";
import { badge, toneBadge } from "../components/badge.js";
import { button } from "../components/button.js";
import { notice, pageHeader } from "../components/card.js";
import { emptyState } from "../components/emptyState.js";

const TITLE = "Compatibility & capabilities";
const DESC = "Precise validation scope. No vendor-wide claims from a single recording.";

function card(r) {
  return `<article class="reg-card panel" data-key="${esc(r.format_id)}">
    <header class="reg-card__head">
      <div class="reg-card__titles"><h2 class="reg-card__title">${esc(r.vendor)}</h2><code class="reg-card__id">${esc(r.format_id)}</code></div>
      ${badge(r.status)}
    </header>
    <dl class="reg-card__scope">
      <div><dt>Model scope</dt><dd>${esc(r.model_scope)}</dd></div>
      <div><dt>Firmware scope</dt><dd>${esc(r.firmware_scope)}</dd></div>
      <div><dt>Parser version</dt><dd>${r.parser_version ? `<code>${esc(r.parser_version)}</code>` : '<span class="subtle">No parser</span>'}</dd></div>
    </dl>
    <div class="reg-card__section"><h3 class="mini-head">Capabilities</h3>${r.capabilities.length ? `<div class="tag-list">${r.capabilities.map((c) => `<span class="tag">${esc(c)}</span>`).join("")}</div>` : '<p class="subtle">No validated parser.</p>'}</div>
    <div class="reg-card__section"><h3 class="mini-head">Validation cases</h3><p class="reg-card__caption">${r.validation_cases.length ? esc(r.validation_cases.join(" · ")) : "None"}</p></div>
    <div class="reg-card__section reg-card__limits"><h3 class="mini-head">${icon("warning", { size: 13 })}Known limitations</h3><ul role="list">${r.known_limitations.map((l) => `<li>${esc(l)}</li>`).join("")}</ul></div>
  </article>`;
}

export function render() {
  const reg = state.registry || [];
  const counts = ["VALIDATED", "EXPERIMENTAL", "UNSUPPORTED"].map((s) => [s, reg.filter((r) => r.status === s).length]);
  const media = state.session?.media_engine || "Unknown";
  const actions = button({ label: "Run controlled demo", variant: "primary", icon: "play", action: "demo" });
  return `${pageHeader({ eyebrow: "Radical honesty about scope", title: TITLE, description: DESC, actions })}
    <div class="row reg-summary">${counts.map(([s, n]) => `${badge(s, { label: `${number(n)} ${s.toLowerCase()}` })}`).join("")}${state.session?.real_vendor_validation === false ? toneBadge("yellow", "Real-vendor validation gate not passed", { icon: "warning" }) : ""}</div>
    ${notice("The Heimvision public corpus uses an experimental DAT parser. Firmware and other recorder models remain unvalidated. A labeled export from a vendor does not validate that vendor’s storage layout.", { tone: "warning" })}
    ${reg.length ? `<div class="reg-grid">${reg.map(card).join("")}
      <article class="reg-card panel reg-card--derivative">
        <header class="reg-card__head"><div class="reg-card__titles"><h2 class="reg-card__title">Separate viewing enhancements</h2><code class="reg-card__id">FFMPEG-DERIVATIVES</code></div>${toneBadge("violet", "Derivative only", { icon: "sparkles" })}</header>
        <p class="reg-card__text">Repeatable FFmpeg denoise, contrast, adaptive contrast and sharpening filters create labelled derivatives. Input hashes and processing parameters are recorded for every transformation.</p>
        <p class="reg-card__text">No generative AI or super-resolution model is bundled. Enhancement never recreates missing original pixels.</p>
        <div class="reg-card__section"><h3 class="mini-head">Media engine</h3><code class="reg-card__engine">${esc(media)}</code></div>
      </article></div>`
      : emptyState({ icon: "registry", title: "Registry unavailable", body: "The compatibility registry could not be loaded from the local server." })}`;
}

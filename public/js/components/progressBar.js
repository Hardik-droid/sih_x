// Progress bar. Width animates via CSS transition because the DOM morph keeps
// the same element between polls (BUILD.md §5.9).
import { esc } from "../dom.js";

export function progressBar(value, { tone = "amber", label = "Progress", indeterminate = false, size = "md" } = {}) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  const text = `${Number.isInteger(pct) ? pct : pct.toFixed(1)}%`;
  return `<div class="progress progress--${tone}${size === "sm" ? " progress--sm" : ""}${indeterminate ? " progress--indeterminate" : ""}" role="progressbar" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}" aria-valuetext="${text}"><span class="progress__bar" style="width:${pct}%"></span></div>`;
}

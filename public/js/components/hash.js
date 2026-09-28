// Hash display: always monospace, truncatable, full value on hover and one
// click away via copy (BUILD.md §10 — never show a hash you cannot copy).
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { shortHash } from "../format.js";

export function hashField(value, { label = "SHA-256", truncate = true, empty = "Pending verification" } = {}) {
  if (!value) return `<div class="hash hash--empty"><span class="hash__label">${esc(label)}</span><span class="hash__value subtle">${esc(empty)}</span></div>`;
  const text = String(value);
  return `<div class="hash"><span class="hash__label">${esc(label)}</span><code class="hash__value${truncate ? " hash__value--truncate" : ""}" title="${esc(text)}">${esc(text)}</code><button type="button" class="hash__copy" data-action="copy" data-value="${esc(text)}" data-label="${esc(label)}" aria-label="Copy full ${esc(label)}" title="Copy">${icon("copy", { size: 14 })}</button></div>`;
}

/** Compact inline hash chip (e.g. inside tables). */
export function hashChip(value, { head = 10, tail = 6 } = {}) {
  if (!value) return '<span class="subtle">—</span>';
  const text = String(value);
  return `<span class="hash-chip"><code title="${esc(text)}">${esc(shortHash(text, head, tail))}</code><button type="button" class="hash__copy" data-action="copy" data-value="${esc(text)}" data-label="Hash" aria-label="Copy full hash" title="Copy">${icon("copy", { size: 13 })}</button></span>`;
}

// Empty state: honest one-line status, what would change it, one clear action.
import { esc } from "../dom.js";
import { icon } from "../icons.js";

export function emptyState({ icon: iconName = "folder", title, body = "", action = "", compact = false }) {
  return `<div class="empty${compact ? " empty--compact" : ""}">
    <span class="empty__icon">${icon(iconName, { size: 22 })}</span>
    <strong class="empty__title">${esc(title)}</strong>
    ${body ? `<p class="empty__body">${esc(body)}</p>` : ""}
    ${action ? `<div class="empty__action">${action}</div>` : ""}
  </div>`;
}

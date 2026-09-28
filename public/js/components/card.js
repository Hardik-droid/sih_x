// Panels/cards (BUILD.md §5.7) and the shared page header.
import { attrs, cx, esc } from "../dom.js";
import { icon } from "../icons.js";

/**
 * Panel with optional header (icon chip, title, count, description, action).
 * `body` is trusted HTML produced by other components.
 */
export function panel({ title = "", description = "", icon: iconName, count = null, action = "", body = "", footer = "", className = "", flush = false, id, key, titleTag = "h2", headingId } = {}) {
  const header = title || action
    ? `<header class="panel__head">
        ${iconName ? `<span class="icon-chip">${icon(iconName, { size: 16 })}</span>` : ""}
        <div class="panel__titles">
          <div class="panel__title-row"><${titleTag} class="panel__title"${headingId ? ` id="${esc(headingId)}"` : ""}>${esc(title)}</${titleTag}>${count !== null && count !== undefined ? `<span class="count-chip tabular">${esc(count)}</span>` : ""}</div>
          ${description ? `<p class="panel__desc">${esc(description)}</p>` : ""}
        </div>
        ${action ? `<div class="panel__action">${action}</div>` : ""}
      </header>`
    : "";
  return `<section ${attrs({ class: cx("panel", flush && "panel--flush", className), id: id || null, "data-key": key || null, "aria-labelledby": headingId || null })}>${header}<div class="panel__body">${body}</div>${footer ? `<footer class="panel__foot">${footer}</footer>` : ""}</section>`;
}

/** Page header: eyebrow, H1, description, right-aligned actions. */
export function pageHeader({ eyebrow = "", title, description = "", actions = "" }) {
  return `<header class="page-head">
    <div class="page-head__text">
      ${eyebrow ? `<p class="eyebrow page-head__eyebrow">${esc(eyebrow)}</p>` : ""}
      <h1 class="page-head__title">${esc(title)}</h1>
      ${description ? `<p class="page-head__desc">${esc(description)}</p>` : ""}
    </div>
    ${actions ? `<div class="page-head__actions">${actions}</div>` : ""}
  </header>`;
}

/** Label/value definition grid. Values are escaped; pass {html:true} to inject markup. */
export function detailList(items, { columns = 3, className = "" } = {}) {
  const rows = items
    .filter(Boolean)
    .map(({ label, value, html = false, mono = false, span = 1, hint = "" }) => {
      const empty = value === null || value === undefined || value === "";
      const content = empty ? '<span class="subtle">Unknown</span>' : html ? value : esc(value);
      return `<div class="detail${span > 1 ? ` detail--span-${span}` : ""}"><dt class="detail__label">${esc(label)}</dt><dd class="detail__value${mono ? " mono" : ""}"${hint ? ` title="${esc(hint)}"` : ""}>${content}</dd></div>`;
    })
    .join("");
  return `<dl class="details details--${columns} ${className}">${rows}</dl>`;
}

/** Inline notice/callout. tone: info | success | warning | danger | violet | neutral */
export function notice(body, { tone = "info", title = "", icon: iconName, html = false, className = "" } = {}) {
  const icons = { info: "info", success: "check", warning: "warning", danger: "x-circle", violet: "sparkles", neutral: "info" };
  return `<div class="notice notice--${tone} ${className}" role="note">${icon(iconName || icons[tone] || "info", { size: 16, className: "notice__icon" })}<div class="notice__body">${title ? `<strong class="notice__title">${esc(title)}</strong>` : ""}<div class="notice__text">${html ? body : esc(body)}</div></div></div>`;
}

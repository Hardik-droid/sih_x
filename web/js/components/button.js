// Buttons (BUILD.md §5.4): primary · secondary · ghost · danger · icon, sm/md/lg.
// Pill shape is reserved for filter/period/menu triggers (variant "pill").
import { attrs, cx, esc } from "../dom.js";
import { icon } from "../icons.js";

/**
 * @param {object} o
 * @param {string} [o.label]
 * @param {"primary"|"secondary"|"ghost"|"danger"|"icon"|"pill"|"accent"} [o.variant]
 * @param {"sm"|"md"|"lg"} [o.size]
 * @param {string} [o.icon]      leading icon name
 * @param {string} [o.iconRight] trailing icon name
 * @param {string} [o.action]    data-action handler name
 * @param {string} [o.href]      render as a link instead of a button
 * @param {object} [o.data]      extra data-* attributes
 */
export function button({ label = "", variant = "secondary", size = "md", icon: lead, iconRight, action, href, data = {}, type = "button", disabled = false, title, ariaLabel, className = "", download, target, attrs: extra = {} } = {}) {
  const classes = cx("btn", `btn--${variant}`, size !== "md" && `btn--${size}`, variant === "icon" && "btn--icon-only", className);
  const dataAttrs = Object.fromEntries(Object.entries(data).map(([k, v]) => [`data-${k}`, v]));
  const iconSize = size === "sm" ? 14 : size === "lg" ? 18 : 16;
  const inner = `${lead ? icon(lead, { size: iconSize }) : ""}${label ? `<span class="btn__label">${esc(label)}</span>` : ""}${iconRight ? icon(iconRight, { size: iconSize }) : ""}<span class="btn__spinner" aria-hidden="true"></span>`;
  const common = {
    class: classes,
    "data-action": action || null,
    title: title || null,
    "aria-label": ariaLabel || (!label && title ? title : null),
    ...dataAttrs,
    ...extra,
  };
  if (href) {
    return `<a ${attrs({ ...common, href, download: download === undefined ? null : download || true, target: target || null, rel: target === "_blank" ? "noopener" : null, "aria-disabled": disabled ? "true" : null, tabindex: disabled ? "-1" : null })}>${inner}</a>`;
  }
  return `<button ${attrs({ ...common, type, disabled })}>${inner}</button>`;
}

/** Icon-only round button (requires an accessible label). */
export const iconButton = (name, label, options = {}) => button({ ...options, variant: "icon", icon: name, title: label, ariaLabel: label });

/** Inline text link with trailing arrow, e.g. "View all →". */
export function textLink({ label, href, action, data = {}, iconName = "arrow" }) {
  const dataAttrs = Object.fromEntries(Object.entries(data).map(([k, v]) => [`data-${k}`, v]));
  const tag = href ? "a" : "button";
  return `<${tag} ${attrs({ class: "text-link", href: href || null, type: href ? null : "button", "data-action": action || null, ...dataAttrs })}><span>${esc(label)}</span>${icon(iconName, { size: 14 })}</${tag}>`;
}

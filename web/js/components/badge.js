// Status badge — always icon + text, never colour alone (BUILD.md §5.5, §5.10).
import { attrs, esc } from "../dom.js";
import { icon } from "../icons.js";
import { statusInfo, actorTone } from "../statusMap.js";

/** Badge for any backend status code, resolved through statusMap.js. */
export function badge(code, { label, size = "md", title, showIcon = true } = {}) {
  const info = statusInfo(code);
  return toneBadge(info.tone, label || info.label, { icon: showIcon ? info.icon : null, pulse: info.pulse, size, title: title || String(code ?? "") });
}

/** Low-level badge for a tone; used for non-status tags (e.g. "Derivative", "sub"). */
export function toneBadge(tone, label, { icon: iconName = null, pulse = false, size = "md", title, className = "" } = {}) {
  const classes = ["badge", `badge--${tone}`, size === "sm" ? "badge--sm" : "", pulse ? "badge--pulse" : "", className].filter(Boolean).join(" ");
  return `<span ${attrs({ class: classes, title: title || null })}>${iconName ? icon(iconName, { size: size === "sm" ? 11 : 12, className: "badge__icon" }) : ""}<span>${esc(label)}</span></span>`;
}

/** Persistent corner tag for derivative / enhanced artifacts (BUILD.md §5.6). */
export const derivativeTag = () => toneBadge("violet", "Derivative", { icon: "sparkles", size: "sm", className: "derivative-tag", title: "Derivative viewing copy — not original evidence" });

/** Audit actor chip with tone dot (engine = blue, examiner = amber, system = gray). */
export function actorChip(actor) {
  const tone = actorTone(actor);
  const role = actor === "engine" ? "Engine" : actor === "system" ? "System" : "Examiner";
  return `<span class="actor actor--${tone}" title="${esc(role)}"><span class="actor__dot" aria-hidden="true"></span><span class="actor__name">${esc(actor || "unknown")}</span></span>`;
}

/** Up/down trend pill: ▲ always green, ▼ always red (BUILD.md §5.1 convention). */
export function trendPill(direction, text) {
  const up = direction === "up";
  return `<span class="trend trend--${up ? "up" : "down"}">${icon(up ? "tri-up" : "tri-down", { size: 10 })}<span>${esc(text)}</span></span>`;
}

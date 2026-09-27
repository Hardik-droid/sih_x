// KPI stat card: eyebrow label + icon chip, big tabular value, trend pill + note.
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { trendPill } from "./badge.js";

/**
 * @param {{label:string, value:string|number, icon:string, note?:string, trend?:{direction:"up"|"down", text:string}, tone?:string, href?:string}} o
 */
export function statCard({ label, value, icon: iconName, note = "", trend = null, tone = "", href = "" }) {
  const tag = href ? "a" : "article";
  return `<${tag} class="stat${href ? " stat--link" : ""}${tone ? ` stat--${tone}` : ""}"${href ? ` href="${esc(href)}"` : ""}>
    <div class="stat__top"><span class="stat__label">${esc(label)}</span><span class="icon-chip">${icon(iconName, { size: 16 })}</span></div>
    <div class="stat__value tabular">${esc(value)}</div>
    <div class="stat__bottom">${trend ? trendPill(trend.direction, trend.text) : '<span class="stat__dot" aria-hidden="true"></span>'}<span class="stat__note">${esc(note)}</span></div>
  </${tag}>`;
}

// Data table with horizontal scroll affordance and optional sticky first column.
import { cx, esc } from "../dom.js";

/**
 * @param {{columns:{key:string,label:string,className?:string,render?:(row)=>string}[], rows:object[], rowKey?:(row)=>string, caption?:string, stickyFirst?:boolean, empty?:string, className?:string, dense?:boolean}} o
 */
export function table({ columns, rows, rowKey, caption = "", stickyFirst = false, empty = "", className = "", dense = false }) {
  if (!rows.length && empty) return empty;
  const head = columns.map((c) => `<th scope="col" class="${esc(c.className || "")}">${esc(c.label)}</th>`).join("");
  const body = rows
    .map((row) => {
      const key = rowKey ? ` data-key="${esc(rowKey(row))}"` : "";
      const cells = columns
        .map((c, index) => {
          const content = c.render ? c.render(row) : esc(row[c.key] ?? "—");
          return index === 0 && stickyFirst ? `<th scope="row" class="${esc(c.className || "")}">${content}</th>` : `<td class="${esc(c.className || "")}">${content}</td>`;
        })
        .join("");
      return `<tr${key}>${cells}</tr>`;
    })
    .join("");
  return `<div class="table-wrap${stickyFirst ? " table-wrap--sticky" : ""}" tabindex="0" role="region" aria-label="${esc(caption || "Data table")}">
    <table class="${cx("table", dense && "table--dense", className)}">${caption ? `<caption class="sr-only">${esc(caption)}</caption>` : ""}<thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>
  </div>`;
}

// Hex/ASCII dump renderer for the read-only byte inspector.
import { esc } from "../dom.js";

/** @param {{offset:number, length:number, hex:string, ascii:string}} result */
export function hexDump(result) {
  const bytes = result.hex ? result.hex.split(" ") : [];
  if (!bytes.length) return '<p class="subtle">No bytes returned for this range (offset beyond the end of the image).</p>';
  const rows = [];
  for (let i = 0; i < bytes.length; i += 16) {
    const chunk = bytes.slice(i, i + 16);
    const offset = (result.offset + i).toString(16).padStart(10, "0");
    const cells = chunk.map((b, j) => `<span class="hx__b${b === "00" ? " hx__b--zero" : ""}${j === 8 ? " hx__b--gap" : ""}">${b}</span>`).join("");
    const pad = 16 - chunk.length;
    const filler = pad ? `<span class="hx__pad" style="--pad:${pad}"></span>` : "";
    const ascii = esc(result.ascii.slice(i, i + 16));
    rows.push(`<div class="hx__row"><span class="hx__off">${offset}</span><span class="hx__bytes">${cells}${filler}</span><span class="hx__ascii">${ascii}</span></div>`);
  }
  return `<div class="hexdump" role="region" aria-label="Hex dump from offset ${result.offset}, ${result.length} bytes" tabindex="0">
    <div class="hx__row hx__row--head" aria-hidden="true"><span class="hx__off">OFFSET</span><span class="hx__bytes">${Array.from({ length: 16 }, (_, i) => `<span class="hx__b${i === 8 ? " hx__b--gap" : ""}">${i.toString(16).padStart(2, "0").toUpperCase()}</span>`).join("")}</span><span class="hx__ascii">ASCII</span></div>
    ${rows.join("")}
  </div>`;
}

/** Plain-text dump (for copy to clipboard). */
export function hexText(result) {
  const bytes = result.hex ? result.hex.split(" ") : [];
  const lines = [];
  for (let i = 0; i < bytes.length; i += 16) {
    lines.push(`${(result.offset + i).toString(16).padStart(10, "0")}  ${bytes.slice(i, i + 16).join(" ").padEnd(47)}  ${result.ascii.slice(i, i + 16)}`);
  }
  return lines.join("\n");
}

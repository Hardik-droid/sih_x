// Multi-lane recording timeline: one lane per camera, clips placed on the real
// span, substreams thinner/dashed with a "sub" tag, and gaps between main
// clips left visible as hatched intervals (never filled or guessed).
import { esc } from "../dom.js";
import { duration, utc } from "../format.js";
import { statusInfo } from "../statusMap.js";

function tickLabel(value, basis, span) {
  if (basis === "recorder") {
    const d = new Date(value * 1000);
    const hh = String(d.getUTCHours()).padStart(2, "0");
    const mm = String(d.getUTCMinutes()).padStart(2, "0");
    const ss = String(d.getUTCSeconds()).padStart(2, "0");
    return span > 7200 ? `${hh}:${mm}` : `${hh}:${mm}:${ss}`;
  }
  const rounded = Math.round(value * 10) / 10;
  return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(1)} s`;
}

function describe(clip, basis) {
  if (basis === "recorder") return `${utc(clip.start * 1000)} → ${utc(clip.end * 1000)} (${duration(clip.end - clip.start)})`;
  return `${clip.start} s → ${clip.end} s (${duration(clip.end - clip.start)})`;
}

/**
 * @param {{clips:{id:string,name:string,channel:string,start:number,end:number,status:string,representation?:string}[], basis:"indexed"|"recorder"}} o
 */
export function timelineLanes({ clips, basis }) {
  const min = Math.min(...clips.map((c) => c.start));
  const max = Math.max(...clips.map((c) => c.end));
  const span = Math.max(max - min, 1e-6);
  const pos = (v) => ((v - min) / span) * 100;
  const lanes = [...new Set(clips.map((c) => c.channel || "Unknown camera"))].sort();
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => `<span class="tl__tick" style="left:${f * 100}%"><span>${esc(tickLabel(min + span * f, basis, span))}</span></span>`).join("");

  const rows = lanes.map((lane) => {
    const laneClips = clips.filter((c) => (c.channel || "Unknown camera") === lane).sort((a, b) => a.start - b.start);
    const main = laneClips.filter((c) => c.representation !== "substream");
    const gaps = [];
    for (let i = 1; i < main.length; i += 1) {
      const prevEnd = Math.max(...main.slice(0, i).map((c) => c.end));
      if (main[i].start > prevEnd) gaps.push({ start: prevEnd, end: main[i].start });
    }
    const gapHtml = gaps.map((g) => `<span class="tl__gap" style="left:${pos(g.start)}%;width:${pos(g.end) - pos(g.start)}%" title="No recovered bytes for this interval (${esc(describe(g, basis))})"><span class="sr-only">Gap ${esc(describe(g, basis))}</span></span>`).join("");
    const clipHtml = laneClips.map((c) => {
      const sub = c.representation === "substream";
      const tone = statusInfo(c.status).tone;
      const left = pos(c.start);
      const width = Math.max(pos(c.end) - left, 0.8);
      return `<button type="button" class="tl__clip tl__clip--${esc(tone)}${sub ? " tl__clip--sub" : ""}" style="left:${left}%;width:${width}%" data-action="view-artifact" data-id="${esc(c.id)}" title="${esc(c.name)} · ${esc(describe(c, basis))}" aria-label="${esc(c.name)}, ${esc(describe(c, basis))}${sub ? ", substream" : ""}"><span class="tl__clip-label">${esc(tickLabel(c.start, basis, span))}${sub ? " · sub" : ""}</span></button>`;
    }).join("");
    return `<div class="tl__lane" data-key="lane-${esc(lane)}"><div class="tl__name" title="${esc(lane)}">${esc(lane)}</div><div class="tl__track">${gapHtml}${clipHtml}</div></div>`;
  }).join("");

  return `<div class="tl" data-basis="${esc(basis)}">
    <div class="tl__axis" aria-hidden="true"><div class="tl__name"></div><div class="tl__ticks">${ticks}</div></div>
    <div class="tl__lanes" role="group" aria-label="Recovered intervals by camera">${rows}</div>
    <div class="tl__legend">
      <span><i class="tl__swatch tl__swatch--main"></i>Main stream</span>
      <span><i class="tl__swatch tl__swatch--sub"></i>Substream</span>
      <span><i class="tl__swatch tl__swatch--gap"></i>Gap · no recovered bytes</span>
    </div>
  </div>`;
}

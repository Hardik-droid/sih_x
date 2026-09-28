// Two tiny hand-rolled SVG charts (no chart library): a monotone line/area
// chart and a rounded bar chart. Both redraw on resize, expose a hover/focus
// tooltip and ship a visually hidden data table for screen readers.
import { esc } from "./dom.js";

const PAD = { top: 18, right: 18, bottom: 30, left: 38 };

function niceMax(value) {
  if (value <= 5) return Math.max(1, Math.ceil(value));
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => value <= s * magnitude) || 10;
  return step * magnitude;
}

/** Monotone cubic path (Fritsch–Carlson): smooth, never overshoots the data. */
function monotonePath(pts) {
  if (pts.length === 1) return `M${pts[0][0]},${pts[0][1]}`;
  const n = pts.length;
  const dx = [], m = [];
  for (let i = 0; i < n - 1; i += 1) {
    dx[i] = Math.max(pts[i + 1][0] - pts[i][0], 1e-6);
    m[i] = (pts[i + 1][1] - pts[i][1]) / dx[i];
  }
  const t = [m[0]];
  for (let i = 1; i < n - 1; i += 1) {
    t[i] = m[i - 1] * m[i] <= 0 ? 0 : (3 * (dx[i - 1] + dx[i])) / ((2 * dx[i] + dx[i - 1]) / m[i - 1] + (dx[i] + 2 * dx[i - 1]) / m[i]);
  }
  t[n - 1] = m[n - 2];
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < n - 1; i += 1) {
    const h = dx[i] / 3;
    d += ` C${pts[i][0] + h},${pts[i][1] + h * t[i]} ${pts[i + 1][0] - h},${pts[i + 1][1] - h * t[i + 1]} ${pts[i + 1][0]},${pts[i + 1][1]}`;
  }
  return d;
}

function srTable(caption, rows) {
  return `<table class="sr-only"><caption>${esc(caption)}</caption><tbody>${rows.map(([k, v]) => `<tr><th scope="row">${esc(k)}</th><td>${esc(v)}</td></tr>`).join("")}</tbody></table>`;
}

function observe(el, draw) {
  let lastWidth = 0;
  const ro = new ResizeObserver((entries) => {
    const width = Math.round(entries[0].contentRect.width);
    if (width && width !== lastWidth) { lastWidth = width; draw(width); }
  });
  ro.observe(el);
  lastWidth = Math.round(el.clientWidth);
  draw(lastWidth || 480);
  return { destroy: () => ro.disconnect() };
}

function placeTip(el, tip, x, y, html) {
  tip.innerHTML = html;
  tip.hidden = false;
  const w = tip.offsetWidth;
  const left = Math.min(Math.max(x - w / 2, 4), el.clientWidth - w - 4);
  tip.style.transform = `translate(${left}px, ${Math.max(y - tip.offsetHeight - 12, 0)}px)`;
}

/**
 * Line/area chart.
 * @param {HTMLElement} el
 * @param {{points:{x:number,y:number,label:string}[], height?:number, label:string, valueLabel?:(v:number)=>string, tickLabel?:(x:number)=>string}} o
 */
export function lineChart(el, { points, height = 220, label, valueLabel = String, tickLabel = String }) {
  el.classList.add("chart");
  el.style.height = `${height}px`;
  return observe(el, (width) => {
    const w = width - PAD.left - PAD.right;
    const h = height - PAD.top - PAD.bottom;
    const xs = points.map((p) => p.x);
    const minX = Math.min(...xs);
    const spanX = Math.max(...xs) - minX || 1;
    const maxY = niceMax(Math.max(...points.map((p) => p.y), 1));
    const xAt = (x) => PAD.left + ((x - minX) / spanX) * w;
    const yAt = (v) => PAD.top + h - (v / maxY) * h;
    const coords = points.map((p) => [xAt(p.x), yAt(p.y)]);
    const line = monotonePath(coords);
    const base = PAD.top + h;
    const area = `${line} L${coords[coords.length - 1][0]},${base} L${coords[0][0]},${base} Z`;
    const gridLines = [0, 0.25, 0.5, 0.75, 1].map((f) => {
      const y = PAD.top + h - f * h;
      const v = maxY * f;
      return `<line class="chart__grid" x1="${PAD.left}" x2="${width - PAD.right}" y1="${y}" y2="${y}"/><text class="chart__axis" x="${PAD.left - 8}" y="${y + 4}" text-anchor="end">${esc(Number.isInteger(v) ? v : v.toFixed(1))}</text>`;
    }).join("");
    const tickCount = Math.max(2, Math.min(6, Math.floor(w / 110)));
    const ticks = Array.from({ length: tickCount }, (_, i) => minX + (spanX * i) / (tickCount - 1))
      .map((x, i, all) => `<text class="chart__axis" x="${xAt(x)}" y="${height - 8}" text-anchor="${i === 0 ? "start" : i === all.length - 1 ? "end" : "middle"}">${esc(tickLabel(x))}</text>`).join("");
    const gid = `g${Math.random().toString(36).slice(2, 8)}`;
    el.innerHTML = `<svg class="chart__svg" viewBox="0 0 ${width} ${height}" width="100%" height="${height}" role="img" aria-label="${esc(label)}">
        <defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" class="chart__stop-a"/><stop offset="100%" class="chart__stop-b"/></linearGradient></defs>
        ${gridLines}${ticks}
        <path class="chart__area" d="${area}" fill="url(#${gid})"/>
        <path class="chart__line" d="${line}"/>
        ${coords.map(([x, y]) => `<circle class="chart__point" cx="${x}" cy="${y}" r="2.5"/>`).join("")}
        <line class="chart__guide" x1="0" x2="0" y1="${PAD.top}" y2="${base}" visibility="hidden"/>
        <circle class="chart__focus" r="5" cx="0" cy="0" visibility="hidden"/>
        <rect class="chart__hit" x="${PAD.left}" y="${PAD.top}" width="${w}" height="${h}" tabindex="0" aria-label="Inspect ${esc(label)} data points"/>
      </svg><div class="chart-tip" hidden></div>${srTable(label, points.map((p) => [p.label, valueLabel(p.y)]))}`;
    const svg = el.querySelector("svg");
    const tip = el.querySelector(".chart-tip");
    const guide = el.querySelector(".chart__guide");
    const focus = el.querySelector(".chart__focus");
    const hit = el.querySelector(".chart__hit");
    let index = points.length - 1;
    const show = (i) => {
      index = Math.max(0, Math.min(points.length - 1, i));
      const [x, y] = coords[index];
      guide.setAttribute("x1", x); guide.setAttribute("x2", x); guide.setAttribute("visibility", "visible");
      focus.setAttribute("cx", x); focus.setAttribute("cy", y); focus.setAttribute("visibility", "visible");
      const scale = el.clientWidth / width;
      placeTip(el, tip, x * scale, y, `<span class="chart-tip__label">${esc(points[index].label)}</span><strong class="chart-tip__value tabular">${esc(valueLabel(points[index].y))}</strong>`);
    };
    const hide = () => { tip.hidden = true; guide.setAttribute("visibility", "hidden"); focus.setAttribute("visibility", "hidden"); };
    svg.addEventListener("pointermove", (event) => {
      const rect = svg.getBoundingClientRect();
      const px = ((event.clientX - rect.left) / rect.width) * width;
      let best = 0;
      coords.forEach(([x], i) => { if (Math.abs(x - px) < Math.abs(coords[best][0] - px)) best = i; });
      show(best);
    });
    svg.addEventListener("pointerleave", hide);
    hit.addEventListener("focus", () => show(index));
    hit.addEventListener("blur", hide);
    hit.addEventListener("keydown", (event) => {
      if (event.key === "ArrowRight") { event.preventDefault(); show(index + 1); }
      if (event.key === "ArrowLeft") { event.preventDefault(); show(index - 1); }
    });
  });
}

/**
 * Vertical rounded-top bar chart.
 * @param {HTMLElement} el
 * @param {{bars:{label:string,value:number,tone?:string,hint?:string}[], height?:number, label:string, valueLabel?:(v:number)=>string}} o
 */
export function barChart(el, { bars, height = 220, label, valueLabel = String }) {
  el.classList.add("chart");
  el.style.height = `${height}px`;
  return observe(el, (width) => {
    const w = width - PAD.left - PAD.right;
    const h = height - PAD.top - PAD.bottom;
    const maxY = niceMax(Math.max(...bars.map((b) => b.value), 1));
    const slot = w / bars.length;
    const barW = Math.max(10, Math.min(56, slot * 0.56));
    const base = PAD.top + h;
    const gridLines = [0, 0.5, 1].map((f) => {
      const y = PAD.top + h - f * h;
      const v = maxY * f;
      return `<line class="chart__grid" x1="${PAD.left}" x2="${width - PAD.right}" y1="${y}" y2="${y}"/><text class="chart__axis" x="${PAD.left - 8}" y="${y + 4}" text-anchor="end">${esc(Number.isInteger(v) ? v : v.toFixed(1))}</text>`;
    }).join("");
    const shapes = bars.map((b, i) => {
      const x = PAD.left + slot * i + (slot - barW) / 2;
      const bh = (b.value / maxY) * h;
      const y = base - bh;
      const r = Math.min(7, barW / 2, bh);
      const d = bh <= 0 ? "" : `M${x},${base} V${y + r} Q${x},${y} ${x + r},${y} H${x + barW - r} Q${x + barW},${y} ${x + barW},${y + r} V${base} Z`;
      const text = b.label.length > 14 && slot < 110 ? `${b.label.slice(0, 12)}…` : b.label;
      return `<g class="chart__bar-group" data-index="${i}">
          <rect class="chart__bar-track" x="${x}" y="${PAD.top}" width="${barW}" height="${h}" rx="7"/>
          ${d ? `<path class="chart__bar chart__bar--${esc(b.tone || "amber")}" d="${d}"/>` : ""}
          <text class="chart__axis chart__axis--x" x="${x + barW / 2}" y="${height - 8}" text-anchor="middle">${esc(text)}</text>
        </g>`;
    }).join("");
    el.innerHTML = `<svg class="chart__svg" viewBox="0 0 ${width} ${height}" width="100%" height="${height}" role="img" aria-label="${esc(label)}">${gridLines}${shapes}</svg><div class="chart-tip" hidden></div>${srTable(label, bars.map((b) => [b.label, valueLabel(b.value)]))}`;
    const svg = el.querySelector("svg");
    const tip = el.querySelector(".chart-tip");
    svg.addEventListener("pointermove", (event) => {
      const group = event.target.closest?.(".chart__bar-group");
      svg.querySelectorAll(".chart__bar-group").forEach((g) => g.classList.toggle("is-hover", g === group));
      if (!group) { tip.hidden = true; return; }
      const i = Number(group.dataset.index);
      const b = bars[i];
      const scale = el.clientWidth / width;
      const x = (PAD.left + slot * i + slot / 2) * scale;
      const y = base - (b.value / maxY) * h;
      placeTip(el, tip, x, y, `<span class="chart-tip__label">${esc(b.label)}</span><strong class="chart-tip__value tabular">${esc(valueLabel(b.value))}</strong>${b.hint ? `<span class="chart-tip__hint">${esc(b.hint)}</span>` : ""}`);
    });
    svg.addEventListener("pointerleave", () => {
      tip.hidden = true;
      svg.querySelectorAll(".chart__bar-group").forEach((g) => g.classList.remove("is-hover"));
    });
  });
}

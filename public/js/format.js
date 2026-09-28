// Formatting helpers. Numbers are never rounded away from meaning: counts are
// shown exactly, sizes use binary units with the raw byte count available on hover.

const nf = new Intl.NumberFormat();

/** Binary-unit size, e.g. 1048576 → "1.0 MiB". */
export function bytes(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  const value = Number(n);
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KiB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MiB`;
  if (value < 1024 ** 4) return `${(value / 1024 ** 3).toFixed(2)} GiB`;
  return `${(value / 1024 ** 4).toFixed(2)} TiB`;
}

/** Exact integer with locale grouping, e.g. 150039945216 → "150,039,945,216". */
export const number = (n) => (n === null || n === undefined || Number.isNaN(Number(n)) ? "—" : nf.format(Number(n)));

/** Two-digit padding used by KPI cards ("04"). */
export const pad2 = (n) => String(n ?? 0).padStart(2, "0");

const dateFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" });
const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit", second: "2-digit" });
const utcFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false, timeZone: "UTC" });

const valid = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
};

/** Local-time human date, e.g. "Sep 27, 2026, 4:12 PM". */
export const date = (value) => { const d = valid(value); return d ? dateFmt.format(d) : "—"; };
export const day = (value) => { const d = valid(value); return d ? dayFmt.format(d) : "—"; };
export const time = (value) => { const d = valid(value); return d ? timeFmt.format(d) : "—"; };
/** Recorder clock values rendered in UTC (timezone is unverified by the engine). */
export const utc = (value) => { const d = valid(value); return d ? `${utcFmt.format(d)} UTC` : "—"; };

/** <time> element with the raw ISO timestamp available on hover. */
export function timeTag(value, formatter = date) {
  const d = valid(value);
  if (!d) return '<span class="subtle">—</span>';
  const iso = typeof value === "string" ? value : d.toISOString();
  return `<time datetime="${iso.replace(/"/g, "")}" title="${iso.replace(/"/g, "")}">${formatter(d)}</time>`;
}

const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
export function relative(value) {
  const d = valid(value);
  if (!d) return "—";
  const seconds = Math.round((d.getTime() - Date.now()) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 45) return rtf.format(seconds, "second");
  if (abs < 2700) return rtf.format(Math.round(seconds / 60), "minute");
  if (abs < 64800) return rtf.format(Math.round(seconds / 3600), "hour");
  return rtf.format(Math.round(seconds / 86400), "day");
}

/** Truncated hash for display; always pair with a way to copy the full value. */
export function shortHash(hash, head = 10, tail = 6) {
  if (!hash) return "";
  const value = String(hash);
  return value.length <= head + tail + 1 ? value : `${value.slice(0, head)}…${value.slice(-tail)}`;
}

/** Duration in seconds → "48.0 s", "1 min 41 s", "2 h 3 min". */
export function duration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return "—";
  const s = Number(seconds);
  if (s < 60) return `${Number.isInteger(s) ? s : s.toFixed(1)} s`;
  if (s < 3600) {
    const m = Math.floor(s / 60);
    const rest = Math.round(s % 60);
    return rest ? `${m} min ${rest} s` : `${m} min`;
  }
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  return m ? `${h} h ${m} min` : `${h} h`;
}

/** ENUM_STYLE → "Enum style" for non-status vocabulary (actions, types). */
export function readable(code) {
  const text = String(code ?? "Unknown").replace(/[_-]+/g, " ").trim().toLowerCase();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Unknown";
}

export const plural = (n, one, many = `${one}s`) => `${number(n)} ${Number(n) === 1 ? one : many}`;

export function initials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "EX";
  return parts.slice(0, 2).map((p) => p[0]).join("").toUpperCase();
}

/** Parse "4096", "0x1000" or "1000h" into a byte offset. */
export function parseOffset(input) {
  const text = String(input ?? "").trim().toLowerCase();
  if (!text) return NaN;
  if (text.startsWith("0x")) return parseInt(text.slice(2), 16);
  if (text.endsWith("h")) return parseInt(text.slice(0, -1), 16);
  return /^\d+$/.test(text) ? Number(text) : NaN;
}

/** Hex offset label, e.g. 16384 → "0x00004000". */
export const hexOffset = (n, width = 8) => `0x${Number(n).toString(16).padStart(width, "0")}`;

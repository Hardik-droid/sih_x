// Small DOM helpers shared by every module: escaping, querying and an in-place
// DOM morph so polling refreshes update the page without flashing, losing focus,
// resetting scroll or restarting media (progress bars animate instead of snapping).

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const ENTITIES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
/** Escape any value for safe use in HTML text or attribute context. */
export const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ENTITIES[c]);

/** Join class names, skipping falsy parts. */
export const cx = (...parts) => parts.flat().filter(Boolean).join(" ");

/** Serialise an attribute map; `true` renders a bare attribute, false/null are skipped. */
export function attrs(map = {}) {
  return Object.entries(map)
    .filter(([, value]) => value !== false && value !== null && value !== undefined)
    .map(([key, value]) => (value === true ? key : `${key}="${esc(value)}"`))
    .join(" ");
}

let counter = 0;
export const uid = (prefix = "tr") => `${prefix}-${Date.now().toString(36)}-${(counter++).toString(36)}`;

/** Debounce helper for search inputs. */
export function debounce(fn, wait = 200) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

/** Copy text to the clipboard with a fallback for non-secure contexts. */
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    area.remove();
    return ok;
  }
}

// ---------------------------------------------------------------------------
// morph(target, html): patch target's children to match `html`.
//  - children keyed by data-key (or id) are matched by key, others by position
//  - [data-island] elements keep their children (JS-drawn charts, etc.)
//  - <details> keeps the examiner's open/closed choice
//  - focused or [data-preserve] form fields keep their current value
//  - media/iframes are never re-created when their attributes are unchanged
// ---------------------------------------------------------------------------
export function morph(target, html) {
  const template = document.createElement("template");
  template.innerHTML = html;
  morphChildren(target, template.content);
}

const keyOf = (node) => (node.nodeType === 1 ? node.getAttribute("data-key") || node.id || null : null);
const sameType = (a, b) => a.nodeType === b.nodeType && a.nodeName === b.nodeName;

function morphChildren(from, to) {
  const incoming = [...to.childNodes];
  const keyed = new Map();
  for (const child of from.childNodes) {
    const key = keyOf(child);
    if (key) keyed.set(key, child);
  }
  let cursor = from.firstChild;
  for (const next of incoming) {
    const key = keyOf(next);
    let match = null;
    if (key && keyed.has(key)) {
      match = keyed.get(key);
      keyed.delete(key);
      if (!sameType(match, next)) match = null;
    } else if (!key && cursor && !keyOf(cursor) && sameType(cursor, next)) {
      match = cursor;
    }
    if (match) {
      if (match === cursor) cursor = cursor.nextSibling;
      else from.insertBefore(match, cursor);
      patchNode(match, next);
    } else {
      from.insertBefore(next, cursor);
    }
  }
  while (cursor) {
    const following = cursor.nextSibling;
    from.removeChild(cursor);
    cursor = following;
  }
}

const OPAQUE = new Set(["VIDEO", "AUDIO", "IFRAME", "CANVAS"]);

function patchNode(current, next) {
  if (current.nodeType === 3 || current.nodeType === 8) {
    if (current.nodeValue !== next.nodeValue) current.nodeValue = next.nodeValue;
    return;
  }
  if (current.nodeType !== 1) return;
  const tag = current.tagName;
  const isDetails = tag === "DETAILS";
  for (const { name } of [...current.attributes]) {
    if (isDetails && name === "open") continue;
    if (!next.hasAttribute(name)) current.removeAttribute(name);
  }
  for (const { name, value } of [...next.attributes]) {
    if (isDetails && name === "open") continue;
    if (current.getAttribute(name) !== value) current.setAttribute(name, value);
  }
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
    const locked = document.activeElement === current || current.hasAttribute("data-preserve");
    if (!locked) {
      if (tag === "INPUT" && (current.type === "checkbox" || current.type === "radio")) {
        current.checked = next.hasAttribute("checked");
      } else if (tag === "INPUT") {
        const value = next.getAttribute("value") ?? "";
        if (current.value !== value) current.value = value;
      } else if (tag === "TEXTAREA") {
        if (current.value !== next.textContent) current.value = next.textContent;
      }
    }
    if (tag === "TEXTAREA") return;
    if (tag === "SELECT") {
      morphChildren(current, next);
      if (!locked) {
        const index = [...next.children].findIndex((option) => option.hasAttribute("selected"));
        current.selectedIndex = index >= 0 ? index : current.selectedIndex;
      }
      return;
    }
  }
  if (OPAQUE.has(tag) || current.hasAttribute("data-island")) return;
  morphChildren(current, next);
}

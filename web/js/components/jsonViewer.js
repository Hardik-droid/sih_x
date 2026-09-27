// Syntax-highlighted JSON viewer with "jump to section" chips.
import { esc } from "../dom.js";

const TOKEN = /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g;

/** Escape and colourise a JSON string. Keys get data-json-key for jump links. */
export function highlightJson(text) {
  let out = "";
  let last = 0;
  const source = String(text ?? "");
  for (const match of source.matchAll(TOKEN)) {
    out += esc(source.slice(last, match.index));
    const token = match[0];
    let cls = "json-number";
    let extra = "";
    if (token.startsWith('"')) {
      if (/:$/.test(token)) {
        cls = "json-key";
        const name = token.replace(/\s*:$/, "").slice(1, -1);
        extra = ` data-json-key="${esc(name)}"`;
      } else cls = "json-string";
    } else if (token === "true" || token === "false") cls = "json-boolean";
    else if (token === "null") cls = "json-null";
    out += `<span class="${cls}"${extra}>${esc(token)}</span>`;
    last = match.index + token.length;
  }
  return out + esc(source.slice(last));
}

export function jsonViewer({ id, text, jumpKeys = [], loading = false, error = "" }) {
  const chips = jumpKeys.length
    ? `<div class="json-jump" role="toolbar" aria-label="Jump to section"><span class="json-jump__label">Jump to</span>${jumpKeys.map((k) => `<button type="button" class="chip" data-action="json-jump" data-target="${esc(id)}" data-key="${esc(k.key)}">#${esc(k.label || k.key)}</button>`).join("")}</div>`
    : "";
  const body = error ? `<span class="json-error">${esc(error)}</span>` : loading ? '<span class="subtle">Fetching structured record…</span>' : highlightJson(text);
  return `${chips}<pre class="json-view" id="${esc(id)}" tabindex="0" aria-label="Structured JSON record" data-island>${body}</pre>`;
}

/** Scroll a viewer to a top-level key and briefly highlight it. */
export function jumpToKey(pre, key) {
  if (!pre) return false;
  const target = [...pre.querySelectorAll(".json-key")].find((el) => el.dataset.jsonKey === key);
  if (!target) return false;
  pre.scrollTo({ top: target.offsetTop - pre.offsetTop - 16, behavior: "smooth" });
  pre.querySelectorAll(".json-key.is-target").forEach((el) => el.classList.remove("is-target"));
  target.classList.add("is-target");
  setTimeout(() => target.classList.remove("is-target"), 2400);
  return true;
}

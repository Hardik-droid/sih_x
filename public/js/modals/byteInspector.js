// Read-only byte inspector over GET /api/sources/{id}/bytes (1–4096 bytes/read).
import { get } from "../api.js";
import { state } from "../state.js";
import { defineActions } from "../actions.js";
import { copyText, esc } from "../dom.js";
import { icon } from "../icons.js";
import { bytes, hexOffset, number, parseOffset } from "../format.js";
import { sourceById } from "../selectors.js";
import { openModal } from "../components/modal.js";
import { hexDump, hexText } from "../components/hexViewer.js";
import { toast } from "../components/toast.js";

function jumpTargets(source) {
  const targets = [{ label: "Start", offset: 0 }];
  for (const v of source.health?.volumes || []) targets.push({ label: `Volume · ${v.filesystem || v.partition_type || "unknown"}`, offset: v.offset });
  for (const f of source.findings || []) if (typeof f.offset === "number") targets.push({ label: `Index @ ${hexOffset(f.offset, 4)}`, offset: f.offset });
  for (const a of (state.detail?.artifacts || []).filter((x) => x.source_id === source.id && x.kind === "RECOVERED" && typeof x.offset_start === "number").slice(0, 12)) {
    targets.push({ label: a.name.replace(/^.*·\s*/, ""), offset: a.offset_start });
  }
  const seen = new Set();
  return targets.filter((t) => (seen.has(t.offset) ? false : seen.add(t.offset)));
}

export function openByteInspector(sourceId) {
  const source = sourceById(sourceId);
  if (!source) return;
  let last = null;
  openModal({
    title: "Read-only byte inspector",
    description: `${source.name} · ${bytes(source.capacity)}${source.capacity ? ` (${number(source.capacity)} bytes)` : ""}`,
    size: "lg",
    body: `<form class="form" data-bytes novalidate>
        <div class="form__row form__row--bytes">
          <div class="field"><label class="field__label" for="bytes-offset">Offset</label><input class="input mono" id="bytes-offset" name="offset" value="0" inputmode="text" autocomplete="off" spellcheck="false" aria-describedby="bytes-offset-hint"><p class="field__hint" id="bytes-offset-hint">Decimal or hex (0x4000)</p></div>
          <div class="field"><label class="field__label" for="bytes-length">Length</label><input class="input mono" id="bytes-length" name="length" type="number" min="1" max="4096" value="256" required><p class="field__hint">1–4096 bytes per read</p></div>
          <div class="field field--actions">
            <button type="button" class="btn btn--secondary btn--icon-only" data-page="-1" aria-label="Previous range" title="Previous range">${icon("chevron-left", { size: 16 })}</button>
            <button type="submit" class="btn btn--primary"><span class="btn__label">Read range</span><span class="btn__spinner" aria-hidden="true"></span></button>
            <button type="button" class="btn btn--secondary btn--icon-only" data-page="1" aria-label="Next range" title="Next range">${icon("chevron-right", { size: 16 })}</button>
          </div>
        </div>
        <div class="json-jump" role="toolbar" aria-label="Jump to a known offset"><span class="json-jump__label">Jump to</span>${jumpTargets(source).map((t) => `<button type="button" class="chip" data-offset="${t.offset}" title="${esc(hexOffset(t.offset))}">${esc(t.label)}</button>`).join("")}</div>
        <p class="form__error" role="alert"></p>
      </form>
      <div class="bytes-result" data-result aria-live="polite"><p class="subtle">Reading…</p></div>`,
    footer: `<span class="subtle modal__foot-note">${icon("lock", { size: 14 })} Reads come from the verified case copy; the original source is never reopened for writing.</span><button type="button" class="btn btn--ghost" data-copy-dump>${icon("copy", { size: 16 })}<span class="btn__label">Copy dump</span></button>`,
    onMount(dialog) {
      const form = dialog.querySelector("[data-bytes]");
      const error = form.querySelector(".form__error");
      const out = dialog.querySelector("[data-result]");
      const submit = form.querySelector('[type="submit"]');
      const read = async () => {
        error.textContent = "";
        const offset = parseOffset(form.elements.namedItem("offset").value);
        const length = Number(form.elements.namedItem("length").value);
        if (!Number.isFinite(offset) || offset < 0) { error.textContent = "Enter a non-negative decimal or 0x-prefixed hex offset."; return; }
        if (!Number.isInteger(length) || length < 1 || length > 4096) { error.textContent = "Raw inspection supports 1–4096 bytes per request"; return; }
        submit.disabled = true;
        submit.dataset.loading = "true";
        try {
          const result = await get(`/sources/${encodeURIComponent(sourceId)}/bytes?offset=${offset}&length=${length}`);
          last = result;
          out.innerHTML = `<p class="bytes-result__meta"><span>Read <strong class="tabular">${number(result.length)}</strong> bytes from offset <code>${esc(hexOffset(result.offset))}</code> (${number(result.offset)})</span></p>${hexDump(result)}`;
        } catch (err) {
          error.textContent = err.message;
          out.innerHTML = "";
        } finally {
          submit.disabled = false;
          delete submit.dataset.loading;
        }
      };
      form.addEventListener("submit", (event) => { event.preventDefault(); read(); });
      form.addEventListener("click", (event) => {
        const chip = event.target.closest("[data-offset]");
        const page = event.target.closest("[data-page]");
        if (chip) {
          form.elements.namedItem("offset").value = hexOffset(chip.dataset.offset);
          read();
        } else if (page) {
          const length = Number(form.elements.namedItem("length").value) || 256;
          const offset = parseOffset(form.elements.namedItem("offset").value) || 0;
          form.elements.namedItem("offset").value = hexOffset(Math.max(0, offset + Number(page.dataset.page) * length));
          read();
        }
      });
      dialog.querySelector("[data-copy-dump]").addEventListener("click", async () => {
        if (!last) return;
        const ok = await copyText(hexText(last));
        toast(ok ? "Hex dump copied." : "Copy failed — select the dump manually.", { tone: ok ? "success" : "warning" });
      });
      read();
    },
  });
}

defineActions({ "inspect-bytes": ({ id }) => openByteInspector(id) });

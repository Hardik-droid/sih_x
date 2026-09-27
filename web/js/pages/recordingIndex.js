// Recorder-native recording index browser (Heimvision E01 corpus). Paginated
// server-side (limit/offset) — never loads all 800+ rows. Row state combines the
// endpoint's status with this case's real extraction jobs.
import { get, post } from "../api.js";
import { state } from "../state.js";
import { refresh } from "../data.js";
import { defineActions } from "../actions.js";
import { debounce, esc } from "../dom.js";
import { icon } from "../icons.js";
import { duration, number, utc } from "../format.js";
import { openModal } from "../components/modal.js";
import { badge } from "../components/badge.js";
import { button } from "../components/button.js";
import { notice } from "../components/card.js";
import { toast } from "../components/toast.js";

const PAGE = 50;

function jobFor(path) {
  const jobs = (state.detail?.jobs || []).filter((j) => j.action === `Extract E01 · ${path}`);
  return jobs[jobs.length - 1] || null;
}

function stateCell(row) {
  const job = jobFor(row.relative_path);
  if (row.status === "EXTRACTED") return badge("EXTRACTED");
  if (job) {
    if (job.status === "COMPLETED") return badge("EXTRACTED");
    return badge(job.status, { title: job.error || job.stage });
  }
  return badge("AVAILABLE_ON_E01");
}

function actionCell(row) {
  const job = jobFor(row.relative_path);
  if (row.status === "EXTRACTED" || job?.status === "COMPLETED") return '<span class="subtle">In case</span>';
  if (job && (job.status === "QUEUED" || job.status === "RUNNING")) return '<span class="subtle">Extracting…</span>';
  return button({ label: job ? "Retry extract" : "Extract", size: "sm", icon: "download", action: "extract-recording", data: { folder: row.folder, file: row.file, path: row.relative_path } });
}

function rowsHtml(entries) {
  if (!entries.length) return `<tr><td colspan="6" class="table__empty">No recordings match this search.</td></tr>`;
  return entries.map((r) => `<tr data-key="${esc(r.relative_path)}">
      <th scope="row"><code>${esc(r.relative_path)}</code><span class="subtle table__sub">Index #${esc(r.id)}</span></th>
      <td class="nowrap tabular" title="${esc(r.start_iso)}">${esc(utc(r.start_iso))}</td>
      <td class="nowrap tabular" title="${esc(r.end_iso)}">${esc(utc(r.end_iso))}</td>
      <td class="nowrap tabular">${esc(duration(r.duration_seconds))}</td>
      <td>${stateCell(r)}</td>
      <td class="table__actions">${actionCell(r)}</td>
    </tr>`).join("");
}

let active = null;

export function openRecordingIndex() {
  const parent = state.detail?.case?.parent_evidence;
  if (!parent) return;
  const view = { search: "", offset: 0, total: 0, data: null, seq: 0 };
  const ctrl = openModal({
    title: "Recording index",
    description: `${parent.name || "Parent image"} · ${number(parent.index_entries)} indexed recordings`,
    size: "xl",
    body: `<div class="rindex">
        <div data-rindex-span></div>
        <div class="toolbar">
          <label class="search-field">${icon("search", { size: 16 })}<span class="sr-only">Search recordings</span><input class="search-field__input" type="search" placeholder="Search path, date or time…" autocomplete="off" data-rindex-search></label>
          <span class="subtle tabular" data-rindex-count aria-live="polite"></span>
        </div>
        <div class="table-wrap table-wrap--sticky rindex__table" tabindex="0" role="region" aria-label="Recording index">
          <table class="table table--dense"><caption class="sr-only">Recorder-native recording index</caption>
            <thead><tr><th scope="col">Recording path</th><th scope="col">Start (UTC)</th><th scope="col">End (UTC)</th><th scope="col">Duration</th><th scope="col">State</th><th scope="col"><span class="sr-only">Action</span></th></tr></thead>
            <tbody data-rindex-rows><tr><td colspan="6" class="table__empty">Loading index…</td></tr></tbody>
          </table>
        </div>
        <div class="pager"><button type="button" class="btn btn--secondary btn--sm" data-rindex-page="-1">${icon("chevron-left", { size: 14 })}<span class="btn__label">Previous</span></button><span class="subtle tabular" data-rindex-range></span><button type="button" class="btn btn--secondary btn--sm" data-rindex-page="1"><span class="btn__label">Next</span>${icon("chevron-right", { size: 14 })}</button></div>
        <p class="form__error" role="alert" data-rindex-error></p>
      </div>`,
    onClose: () => { active = null; },
    onMount(dialog) {
      const $ = (sel) => dialog.querySelector(sel);
      const load = async () => {
        const seq = ++view.seq;
        $("[data-rindex-error]").textContent = "";
        try {
          const params = new URLSearchParams({ search: view.search, limit: String(PAGE), offset: String(view.offset) });
          const data = await get(`/cases/${encodeURIComponent(state.caseId)}/recording-index?${params}`);
          if (seq !== view.seq) return;
          view.data = data;
          view.total = data.total || 0;
          paint();
        } catch (err) {
          if (seq === view.seq) $("[data-rindex-error]").textContent = err.message;
        }
      };
      const paint = () => {
        const data = view.data;
        if (!data) return;
        const span = data.time_span;
        $("[data-rindex-span]").innerHTML = span?.start_iso
          ? notice(`Recorder index covers ${utc(span.start_iso)} → ${utc(span.end_iso)} (${span.total_surveillance_hours} hours). Recorder clock; timezone and clock accuracy are unverified.`, { tone: "info" })
          : data.message ? notice(data.message, { tone: "neutral" }) : "";
        $("[data-rindex-rows]").innerHTML = rowsHtml(data.entries || []);
        $("[data-rindex-count]").textContent = `${number(view.total)} ${view.search ? "matching" : "indexed"} recordings`;
        const from = view.total ? view.offset + 1 : 0;
        const to = Math.min(view.offset + PAGE, view.total);
        $("[data-rindex-range]").textContent = `${number(from)}–${number(to)} of ${number(view.total)}`;
        $('[data-rindex-page="-1"]').disabled = view.offset <= 0;
        $('[data-rindex-page="1"]').disabled = view.offset + PAGE >= view.total;
      };
      $("[data-rindex-search]").addEventListener("input", debounce((event) => { view.search = event.target.value.trim(); view.offset = 0; load(); }, 250));
      dialog.addEventListener("click", (event) => {
        const page = event.target.closest("[data-rindex-page]");
        if (!page || page.disabled) return;
        view.offset = Math.max(0, view.offset + Number(page.dataset.rindexPage) * PAGE);
        load();
      });
      active = { repaint: paint };
      load();
    },
  });
  return ctrl;
}

/** Called after data refreshes so job-derived row states stay current. */
export function repaintRecordingIndex() { active?.repaint(); }

defineActions({
  "open-recording-index": () => openRecordingIndex(),
  "extract-recording": async ({ folder, file, path }) => {
    await post(`/cases/${encodeURIComponent(state.caseId)}/recording-index/extract`, { folder: Number(folder), file: Number(file) });
    await refresh();
    repaintRecordingIndex();
    toast(`Extraction of ${path} queued — check Recovery engine.`, { tone: "info" });
  },
});

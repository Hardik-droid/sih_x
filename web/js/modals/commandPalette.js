// Command palette (Ctrl/⌘ K): jump to any page, case or artifact and run the
// main actions. WAI-ARIA combobox + listbox with aria-activedescendant.
import { state } from "../state.js";
import { selectCase } from "../data.js";
import { runAction } from "../actions.js";
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { statusInfo } from "../statusMap.js";
import { openModal, topModal } from "../components/modal.js";

const PAGES = [
  ["home", "Product overview", "home", "website landing"],
  ["overview", "Overview", "overview", "dashboard kpi"],
  ["sources", "Evidence sources", "sources", "images drives acquisition"],
  ["evidence", "Recovered evidence", "evidence", "artifacts clips fragments"],
  ["timeline", "Timeline & notes", "timeline", "notes lanes"],
  ["recovery", "Recovery engine", "recovery", "jobs queue edges redundancy"],
  ["integrity", "Chain of custody", "integrity", "audit hashes verify"],
  ["reports", "Reports & exports", "reports", "certificate json zip bsa"],
  ["registry", "Compatibility", "registry", "vendors formats registry"],
];

function commands() {
  const list = [];
  for (const [id, label, iconName, keywords] of PAGES) {
    list.push({ group: "Go to", label, icon: iconName, keywords, run: () => { location.hash = `#${id}`; } });
  }
  list.push(
    { group: "Actions", label: "Create a case", icon: "plus", keywords: "new investigation", run: () => runAction("new-case") },
    { group: "Actions", label: "Import evidence from a local path", icon: "folder", keywords: "acquire image", run: () => runAction("import", { tab: "path" }) },
    { group: "Actions", label: "Upload an evidence file", icon: "upload", keywords: "browser upload", run: () => runAction("import", { tab: "upload" }) },
    { group: "Actions", label: "Forensic USB ingest", icon: "usb-drive", keywords: "removable drive scan", run: () => runAction("usb-ingest") },
    { group: "Actions", label: "Run controlled demo", icon: "play", keywords: "synthetic lab test", run: () => runAction("demo") },
  );
  if (state.detail) {
    list.push(
      { group: "Actions", label: "Verify all hashes", icon: "integrity", keywords: "integrity audit chain", run: () => { location.hash = "#integrity"; setTimeout(() => runAction("verify-integrity"), 60); } },
      { group: "Actions", label: "Build evidence package (ZIP)", icon: "package", keywords: "export manifest", run: () => runAction("export-package") },
    );
    if (state.detail.case.parent_evidence) list.push({ group: "Actions", label: "Browse recording index", icon: "search", keywords: "e01 heimvision recordings", run: () => runAction("open-recording-index") });
  }
  for (const c of state.cases.slice().reverse()) {
    list.push({ group: "Cases", label: c.name, hint: c.examiner || "", icon: c.id === state.caseId ? "check" : "folder", keywords: `case ${c.examiner || ""}`, run: () => selectCase(c.id) });
  }
  for (const a of state.detail?.artifacts || []) {
    list.push({ group: "Artifacts", label: a.name, hint: statusInfo(a.status).label, icon: a.kind === "DERIVATIVE" ? "sparkles" : "film", keywords: `${a.channel || ""} ${a.codec || ""} ${a.sha256 || ""} ${a.status}`, run: () => runAction("view-artifact", { id: a.id }) });
  }
  return list;
}

function score(item, q) {
  if (!q) return 1;
  const label = item.label.toLowerCase();
  const hay = `${label} ${item.keywords || ""} ${item.hint || ""}`.toLowerCase();
  if (label.startsWith(q)) return 3;
  if (label.includes(q)) return 2;
  return q.split(/\s+/).every((part) => hay.includes(part)) ? 1 : 0;
}

let open = null;

export function togglePalette() {
  if (open) { open.close(); return; }
  if (topModal()) return;
  const all = commands();
  let results = all;
  let activeIndex = 0;
  open = openModal({
    title: "Command menu",
    size: "palette",
    className: "modal--palette",
    body: `<div class="palette">
        <div class="palette__input-row">${icon("search", { size: 18 })}<input class="palette__input" type="text" role="combobox" aria-expanded="true" aria-controls="palette-list" aria-autocomplete="list" aria-label="Search pages, cases, artifacts and actions" placeholder="Search pages, cases, artifacts and actions…" autocomplete="off" spellcheck="false"><kbd class="kbd">Esc</kbd></div>
        <div class="palette__list" id="palette-list" role="listbox" aria-label="Results"></div>
      </div>`,
    initialFocus: ".palette__input",
    onClose: () => { open = null; },
    onMount(dialog, ctrl) {
      const input = dialog.querySelector(".palette__input");
      const listEl = dialog.querySelector(".palette__list");
      const paint = () => {
        if (!results.length) {
          listEl.innerHTML = '<p class="palette__empty">No matches. Try a page name, camera, codec or hash.</p>';
          input.removeAttribute("aria-activedescendant");
          return;
        }
        let html = "";
        let group = "";
        results.forEach((item, i) => {
          if (item.group !== group) { group = item.group; html += `<div class="palette__group" role="presentation">${esc(group)}</div>`; }
          html += `<div class="palette__item${i === activeIndex ? " is-active" : ""}" role="option" id="palette-opt-${i}" aria-selected="${i === activeIndex}" data-index="${i}">${icon(item.icon, { size: 16 })}<span class="palette__label truncate">${esc(item.label)}</span>${item.hint ? `<span class="palette__hint truncate">${esc(item.hint)}</span>` : ""}</div>`;
        });
        listEl.innerHTML = html;
        input.setAttribute("aria-activedescendant", `palette-opt-${activeIndex}`);
        listEl.querySelector(".is-active")?.scrollIntoView({ block: "nearest" });
      };
      const filter = () => {
        const q = input.value.trim().toLowerCase();
        results = all.map((item) => ({ item, s: score(item, q) })).filter((r) => r.s > 0).sort((a, b) => b.s - a.s).map((r) => r.item);
        if (!q) results = all;
        // keep groups contiguous after sorting
        const order = ["Go to", "Actions", "Cases", "Artifacts"];
        results = order.flatMap((g) => results.filter((r) => r.group === g)).slice(0, 60);
        activeIndex = 0;
        paint();
      };
      const choose = async (index) => {
        const item = results[index];
        if (!item) return;
        await ctrl.close();
        item.run();
      };
      input.addEventListener("input", filter);
      input.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown") { event.preventDefault(); activeIndex = Math.min(results.length - 1, activeIndex + 1); paint(); }
        else if (event.key === "ArrowUp") { event.preventDefault(); activeIndex = Math.max(0, activeIndex - 1); paint(); }
        else if (event.key === "Home") { event.preventDefault(); activeIndex = 0; paint(); }
        else if (event.key === "End") { event.preventDefault(); activeIndex = results.length - 1; paint(); }
        else if (event.key === "Enter") { event.preventDefault(); choose(activeIndex); }
      });
      listEl.addEventListener("pointermove", (event) => {
        const option = event.target.closest(".palette__item");
        if (!option || Number(option.dataset.index) === activeIndex) return;
        activeIndex = Number(option.dataset.index);
        listEl.querySelectorAll(".palette__item").forEach((el) => {
          const on = Number(el.dataset.index) === activeIndex;
          el.classList.toggle("is-active", on);
          el.setAttribute("aria-selected", String(on));
        });
        input.setAttribute("aria-activedescendant", `palette-opt-${activeIndex}`);
      });
      listEl.addEventListener("click", (event) => {
        const option = event.target.closest(".palette__item");
        if (option) choose(Number(option.dataset.index));
      });
      paint();
    },
  });
}

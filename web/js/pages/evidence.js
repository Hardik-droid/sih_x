// Recovered evidence (#evidence): browse, filter, sort, multi-select and join.
import { post } from "../api.js";
import { state, notify } from "../state.js";
import { refresh } from "../data.js";
import { defineActions, runAction } from "../actions.js";
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { number } from "../format.js";
import { STATUS, KIND } from "../statusMap.js";
import { channels, derivativeCount, filteredArtifacts, isJoinable, qualityOf } from "../selectors.js";
import { button } from "../components/button.js";
import { pageHeader, panel } from "../components/card.js";
import { emptyState } from "../components/emptyState.js";
import { artifactCard } from "../components/artifactCard.js";
import { toast, toastSuccess } from "../components/toast.js";
import { caseGuard, caseEyebrow } from "./common.js";

const TITLE = "Recovered evidence";
const DESC = "Every output is tied to its source bytes, method and validation result.";

const option = (value, label, current) => `<option value="${esc(value)}"${value === current ? " selected" : ""}>${esc(label)}</option>`;

function toolbar(d) {
  const f = state.filters;
  const statuses = [...new Set(d.artifacts.map((a) => a.status))];
  const kinds = [...new Set(d.artifacts.map((a) => a.kind))];
  return `<div class="toolbar toolbar--evidence" role="search">
    <label class="search-field">${icon("search", { size: 16 })}<span class="sr-only">Search evidence</span><input class="search-field__input" type="search" id="evidence-search" placeholder="Search name, camera, codec or hash…" value="${esc(f.search)}" autocomplete="off"></label>
    <div class="select-wrap select-wrap--pill"><label class="sr-only" for="filter-status">Recovery status</label><select class="select" id="filter-status" data-filter="status">${option("all", "All recovery states", f.status)}${Object.keys(STATUS).filter((k) => statuses.includes(k)).map((k) => option(k, STATUS[k].label, f.status)).join("")}</select></div>
    <div class="select-wrap select-wrap--pill"><label class="sr-only" for="filter-channel">Camera</label><select class="select" id="filter-channel" data-filter="channel">${option("all", "All cameras", f.channel)}${channels(d).map((c) => option(c, c, f.channel)).join("")}</select></div>
    ${kinds.length > 1 ? `<div class="select-wrap select-wrap--pill"><label class="sr-only" for="filter-kind">Artifact kind</label><select class="select" id="filter-kind" data-filter="kind">${option("all", "All kinds", f.kind)}${kinds.map((k) => option(k, KIND[k]?.label || k, f.kind)).join("")}</select></div>` : ""}
    <div class="select-wrap select-wrap--pill"><label class="sr-only" for="filter-sort">Sort by</label><select class="select" id="filter-sort" data-filter="sort">${option("default", "Sort · Recovery order", f.sort)}${option("newest", "Sort · Newest first", f.sort)}${option("quality", "Sort · Quality (FQI)", f.sort)}${option("frames", "Sort · Decoded frames", f.sort)}</select></div>
  </div>`;
}

function selectionBar(d) {
  const selected = [...state.selected].filter((id) => d.artifacts.some((a) => a.id === id && isJoinable(a)));
  const n = selected.length;
  return `<div class="selection-bar${n ? " is-active" : ""}" role="region" aria-label="Selection" aria-live="polite">
    <span class="selection-bar__count"><span class="count-chip tabular">${number(n)}</span> selected</span>
    <span class="selection-bar__hint subtle">${n >= 2 ? "Fragments are joined only if source, camera, codec, timestamps and checksums agree — and the result decodes." : "Select two or more recovered H.264 fragments to verify a join."}</span>
    ${n ? button({ label: "Clear", variant: "ghost", size: "sm", action: "clear-selection" }) : ""}
    ${button({ label: `Join selected${n ? ` (${n})` : ""}`, variant: n >= 2 ? "primary" : "secondary", size: "sm", icon: "link", action: "join-selected", disabled: n < 2 })}
  </div>`;
}

function results(d) {
  const list = filteredArtifacts(d);
  if (!list.length) {
    return panel({
      title: "Artifacts",
      body: d.artifacts.length
        ? emptyState({ icon: "filter", title: "No matching evidence", body: "Adjust the search or filters to see more artifacts.", action: button({ label: "Reset filters", action: "reset-filters" }) })
        : emptyState({ icon: "evidence", title: "Nothing recovered yet", body: "Import a source and let the recovery engine inspect its surviving media.", action: `${button({ label: "Evidence sources", href: "#sources", icon: "sources" })}${button({ label: "Recovery engine", href: "#recovery", icon: "recovery" })}` }),
    });
  }
  return `<div class="evidence-grid" id="evidence-grid">${list.map((a) => artifactCard(a, { selected: state.selected.has(a.id) })).join("")}</div>`;
}

export function render() {
  const guard = caseGuard(TITLE, DESC);
  if (guard) return guard;
  const d = state.detail;
  const derivatives = derivativeCount(d);
  const scored = d.artifacts.filter((a) => qualityOf(a)).length;
  const summary = `<p class="result-summary subtle" aria-live="polite"><span class="tabular">${number(filteredArtifacts(d).length)}</span> of <span class="tabular">${number(d.artifacts.length)}</span> artifacts${derivatives ? ` · <span class="text-violet">${number(derivatives)} derivative${derivatives === 1 ? "" : "s"}</span>` : ""}${scored ? ` · ${number(scored)} quality-scored` : ""}</p>`;
  const actions = button({ label: "Rank by quality", icon: "gauge", action: "rank-quality", disabled: !d.artifacts.length });
  return `${pageHeader({ eyebrow: caseEyebrow(), title: TITLE, description: DESC, actions })}
    ${d.artifacts.length ? toolbar(d) : ""}
    ${d.artifacts.length ? selectionBar(d) : ""}
    ${d.artifacts.length ? summary : ""}
    ${results(d)}`;
}

export function mount(root) {
  const onInput = (event) => {
    if (event.target.id !== "evidence-search") return;
    state.filters.search = event.target.value;
    notify("filter");
  };
  const onChange = (event) => {
    const el = event.target;
    if (el.dataset.filter) {
      state.filters[el.dataset.filter] = el.value;
      notify("filter");
      if (el.dataset.filter === "sort" && el.value === "quality" && !state.detail.artifacts.some((a) => qualityOf(a))) {
        toast("No quality scores yet — ranking every artifact first.", { tone: "info" });
        runAction("rank-quality");
      }
    }
    if (el.dataset.select) {
      if (el.checked) state.selected.add(el.dataset.select);
      else state.selected.delete(el.dataset.select);
      notify("selection");
    }
  };
  root.addEventListener("input", onInput);
  root.addEventListener("change", onChange);
  return () => {
    root.removeEventListener("input", onInput);
    root.removeEventListener("change", onChange);
  };
}

defineActions({
  "clear-selection": () => { state.selected.clear(); notify("selection"); },
  "reset-filters": () => { state.filters = { search: "", status: "all", channel: "all", kind: "all", sort: "default" }; notify("filter"); },
  "join-selected": async () => {
    const ids = [...state.selected].filter((id) => state.detail?.artifacts.some((a) => a.id === id && isJoinable(a)));
    if (ids.length < 2) throw new Error("Select at least two recovered fragments.");
    await post(`/cases/${encodeURIComponent(state.caseId)}/reconstruct`, { artifact_ids: ids });
    state.selected.clear();
    await refresh();
    toastSuccess("Reconstruction queued; the joined output must pass full decoding.", { action: { label: "Open queue", onClick: () => { location.hash = "#recovery"; } } });
  },
});

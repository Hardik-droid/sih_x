// Tiny observable store. Pages read directly from `state`; mutations go through
// api.js, then data.refresh(), then notify().

const listeners = new Set();

function storedCase() {
  try { return localStorage.getItem("trace-case"); } catch { return null; }
}

export const state = {
  session: null,
  sessionError: null,
  registry: [],
  cases: [],
  caseId: storedCase(),
  detail: null,
  detailError: null,
  loadingCase: false,
  route: { id: "home", section: null },
  selected: new Set(),
  filters: { search: "", status: "all", channel: "all", kind: "all", sort: "default" },
  // Per-case, on-demand results (reset on case switch)
  correlation: null,
  quality: {},            // artifact_id → quality record from /quality or /quality-ranking
  qualityRanked: false,
  integrity: null,
  proof: null,
  reportTab: "report",
  reportJson: null,
  reportJsonError: null,
  connection: "ok",
};

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function notify(reason = "data") {
  for (const fn of listeners) fn(state, reason);
}

export function persistCase(id) {
  try {
    if (id) localStorage.setItem("trace-case", id);
    else localStorage.removeItem("trace-case");
  } catch { /* storage unavailable: keep in memory only */ }
}

/** Clear everything that belongs to the previously active case. */
export function resetCaseScope() {
  state.selected = new Set();
  state.filters = { search: "", status: "all", channel: "all", kind: "all", sort: "default" };
  state.correlation = null;
  state.quality = {};
  state.qualityRanked = false;
  state.integrity = null;
  state.proof = null;
  state.reportJson = null;
  state.reportJsonError = null;
}

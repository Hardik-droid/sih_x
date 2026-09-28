// Data orchestration: case list, case detail, polling and derived per-case data.
// Guarantees: never more than one in-flight /api/cases/{id} request per case,
// polling every 1500 ms only while jobs are QUEUED/RUNNING, paused while the tab
// is hidden, and a monotonically increasing sequence guards against races.
import { get, setToken } from "./api.js";
import { state, notify, persistCase, resetCaseScope } from "./state.js";

const POLL_MS = 1500;
const ACTIVE = new Set(["QUEUED", "RUNNING"]);

let refreshSequence = 0;
let pollTimer = null;
const inflight = new Map();
const followups = new Map();

export const hasActiveJobs = (detail = state.detail) => Boolean(detail && detail.jobs.some((job) => ACTIVE.has(job.status)));

/** One request per case at a time; later callers get a single fresh follow-up. */
function fetchDetail(caseId) {
  const current = inflight.get(caseId);
  if (current) {
    if (!followups.has(caseId)) {
      const next = current.catch(() => null).then(() => {
        followups.delete(caseId);
        return fetchDetail(caseId);
      });
      followups.set(caseId, next);
    }
    return followups.get(caseId);
  }
  const request = get(`/cases/${encodeURIComponent(caseId)}`).finally(() => inflight.delete(caseId));
  inflight.set(caseId, request);
  return request;
}

let lastSignature = "";
let lastArtifactSignature = "";

function applyDetail(detail) {
  const signature = JSON.stringify(detail);
  const changed = signature !== lastSignature;
  lastSignature = signature;
  state.detail = detail;
  state.detailError = null;
  const artifactSignature = detail.artifacts.map((a) => `${a.id}:${a.status}`).join("|");
  if (artifactSignature !== lastArtifactSignature) {
    lastArtifactSignature = artifactSignature;
    state.correlation = null;       // refetched lazily by pages that need it
    state.reportJson = null;
  }
  return changed;
}

export async function loadSession() {
  const session = await get("/session");
  setToken(session.token);
  state.session = { ...session, token: undefined };
  state.sessionError = null;
  return state.session;
}

export async function loadRegistry() {
  try {
    state.registry = await get("/registry");
  } catch {
    state.registry = [];
  }
  return state.registry;
}

/** Refresh the case list and the active case detail, then notify. */
export async function refresh({ quiet = false } = {}) {
  const sequence = ++refreshSequence;
  const cases = await get("/cases");
  if (sequence !== refreshSequence) return;
  state.cases = cases;
  if (!cases.some((c) => c.id === state.caseId)) {
    const fallback = cases.at(-1)?.id || null;
    if (fallback !== state.caseId) {
      resetCaseScope();
      state.detail = null;
      lastSignature = "";
      lastArtifactSignature = "";
    }
    state.caseId = fallback;
  }
  persistCase(state.caseId);
  if (!state.caseId) {
    state.detail = null;
    state.loadingCase = false;
    notify(quiet ? "poll" : "data");
    schedulePoll();
    return;
  }
  const caseId = state.caseId;
  state.loadingCase = !state.detail || state.detail.case.id !== caseId;
  try {
    const detail = await fetchDetail(caseId);
    if (sequence !== refreshSequence || caseId !== state.caseId) return;
    applyDetail(detail);
  } catch (error) {
    if (sequence !== refreshSequence || caseId !== state.caseId) return;
    state.detailError = error.message;
  } finally {
    if (sequence === refreshSequence) state.loadingCase = false;
  }
  notify(quiet ? "poll" : "data");
  schedulePoll();
}

/** Switch the active case (debounced by the sequence guard). */
export async function selectCase(caseId) {
  if (caseId === state.caseId && state.detail) return;
  state.caseId = caseId;
  persistCase(caseId);
  resetCaseScope();
  state.detail = null;
  lastSignature = "";
  lastArtifactSignature = "";
  state.loadingCase = true;
  notify("case");
  await refresh();
}

// ---------------------------------------------------------------- polling --
export function schedulePoll() {
  clearTimeout(pollTimer);
  pollTimer = null;
  if (document.visibilityState === "hidden") return;
  if (!state.caseId || !hasActiveJobs()) return;
  pollTimer = setTimeout(poll, POLL_MS);
}

async function poll() {
  pollTimer = null;
  if (document.visibilityState === "hidden" || !state.caseId) return;
  const caseId = state.caseId;
  try {
    const detail = await fetchDetail(caseId);
    if (caseId !== state.caseId) return;
    const hadActive = hasActiveJobs();
    const changed = applyDetail(detail);
    if (state.connection !== "ok") state.connection = "ok";
    if (changed) notify("poll");
    // A job just finished: refresh the case list too (names/counts may change)
    if (hadActive && !hasActiveJobs()) refresh({ quiet: true }).catch(() => {});
  } catch (error) {
    state.connection = "lost";
    notify("connection");
  } finally {
    schedulePoll();
  }
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    clearTimeout(pollTimer);
    pollTimer = null;
    return;
  }
  // Resume: refetch immediately, then continue polling if work is active
  if (state.caseId) refresh({ quiet: true }).catch(() => {});
});

// ------------------------------------------------------- derived fetchers --
export async function loadCorrelation() {
  if (!state.caseId) return null;
  const caseId = state.caseId;
  const result = await get(`/cases/${encodeURIComponent(caseId)}/correlation`);
  if (caseId === state.caseId) state.correlation = result;
  return result;
}

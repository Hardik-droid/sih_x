// Derived, read-only views of the case detail. Every value comes from a real
// backend field; missing data stays missing (callers render "Unknown").
import { state } from "./state.js";
import { isDerivative } from "./statusMap.js";

export const ACTIVE_JOB = new Set(["QUEUED", "RUNNING"]);

export const activeJobs = (d = state.detail) => (d ? d.jobs.filter((j) => ACTIVE_JOB.has(j.status)) : []);
export const sourceById = (id, d = state.detail) => d?.sources.find((s) => s.id === id) || null;
export const artifactById = (id, d = state.detail) => d?.artifacts.find((a) => a.id === id) || null;
export const totalCapacity = (d = state.detail) => (d ? d.sources.reduce((sum, s) => sum + (Number(s.capacity) || 0), 0) : 0);

/** Recovered artifacts per the Overview KPI definition (BUILD.md §7.1). */
export const recoveredArtifacts = (d = state.detail) => (d ? d.artifacts.filter((a) => a.kind === "RECOVERED" && a.status !== "UNRECOVERABLE") : []);

export const channels = (d = state.detail) => [...new Set((d?.artifacts || []).map((a) => a.channel).filter(Boolean))].sort();

/** Joining requires distinct RECOVERED Annex-B H.264 fragments (core/recovery.py). */
export const isJoinable = (a) => a.kind === "RECOVERED" && a.stream_type === "h264";

/** Quality record for an artifact: on-demand assessment first, then persisted fields. */
export function qualityOf(a) {
  const assessed = state.quality[a.id];
  if (assessed && assessed.forensic_quality_index !== undefined) {
    return { score: assessed.forensic_quality_index, category: assessed.category, metrics: assessed, assessed: true };
  }
  if (a.quality_score !== undefined && a.quality_score !== null) {
    return { score: a.quality_score, category: a.quality_category || null, metrics: a.quality_metrics || null, assessed: false };
  }
  return null;
}

export const hasAudio = (a) => Boolean(a.audio_path);

/** Recording interval with its time basis; null when the engine has no trustworthy time. */
export function interval(a) {
  if (a.timestamp_start !== null && a.timestamp_start !== undefined && a.timestamp_end !== null && a.timestamp_end !== undefined) {
    return { start: Number(a.timestamp_start), end: Number(a.timestamp_end), basis: "indexed" };
  }
  const raw = a.recorder_time_raw;
  if (Array.isArray(raw) && raw.length === 2 && raw.every((n) => typeof n === "number")) {
    return { start: raw[0], end: raw[1], basis: "recorder" };
  }
  return null;
}

export function filteredArtifacts(d = state.detail) {
  if (!d) return [];
  const { search, status, channel, kind, sort } = state.filters;
  const q = search.trim().toLowerCase();
  let list = d.artifacts.filter((a) => {
    if (status !== "all" && a.status !== status) return false;
    if (channel !== "all" && a.channel !== channel) return false;
    if (kind !== "all" && a.kind !== kind) return false;
    if (!q) return true;
    return `${a.name} ${a.channel || ""} ${a.codec || ""} ${a.sha256 || ""} ${a.status} ${a.kind}`.toLowerCase().includes(q);
  });
  if (sort === "newest") {
    list = [...list].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  } else if (sort === "quality") {
    list = [...list].sort((a, b) => (qualityOf(b)?.score ?? -1) - (qualityOf(a)?.score ?? -1));
  } else if (sort === "frames") {
    list = [...list].sort((a, b) => (b.validation?.frames_decoded || 0) - (a.validation?.frames_decoded || 0));
  }
  return list;
}

export const derivativeCount = (d = state.detail) => (d ? d.artifacts.filter(isDerivative).length : 0);
export const exportJobs = (d = state.detail) => (d ? d.jobs.filter((j) => j.action === "Export evidence package") : []);

/** Residual deletion-evidence record for one artifact, if the engine produced one. */
export function deletionEvidenceFor(a, d = state.detail) {
  const source = sourceById(a.source_id, d);
  return source?.deletion_evidence?.find((e) => e.artifact_id === a.id) || null;
}

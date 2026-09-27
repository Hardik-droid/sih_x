// The single source of truth for every status colour, label and icon in the app.
// Codes are the backend's exact vocabulary; labels are light human-readable forms.
// Never style a status anywhere else — always go through statusInfo()/badge().
import { readable } from "./format.js";

export const STATUS = {
  // Artifact.status
  EXACT_RECOVERED: { tone: "green", label: "Exact recovered", icon: "check" },
  PARTIAL_RECOVERED: { tone: "yellow", label: "Partial recovered", icon: "warning" },
  INFERRED: { tone: "blue", label: "Inferred", icon: "link" },
  ENHANCED_COPY: { tone: "violet", label: "Enhanced copy", icon: "sparkles" },
  UNRECOVERABLE: { tone: "red", label: "Unrecoverable", icon: "x-circle" },
  // Source.status
  PENDING: { tone: "gray", label: "Pending", icon: "clock" },
  VERIFIED: { tone: "blue", label: "Verified", icon: "shield" },
  ANALYZED: { tone: "green", label: "Analyzed", icon: "check" },
  // Job.status
  QUEUED: { tone: "gray", label: "Queued", icon: "clock" },
  RUNNING: { tone: "blue", label: "Running", icon: "clock", pulse: true },
  COMPLETED: { tone: "green", label: "Completed", icon: "check" },
  FAILED: { tone: "red", label: "Failed", icon: "x-circle" },
  CANCELLED: { tone: "gray", label: "Cancelled", icon: "x-circle" },
  INTERRUPTED: { tone: "yellow", label: "Interrupted", icon: "warning" },
  // Edge.decision
  CANDIDATE: { tone: "blue", label: "Candidate", icon: "link" },
  ACCEPTED: { tone: "green", label: "Accepted", icon: "check" },
  REJECTED: { tone: "red", label: "Rejected", icon: "x-circle" },
  // Registry.status
  VALIDATED: { tone: "green", label: "Validated", icon: "check" },
  EXPERIMENTAL: { tone: "yellow", label: "Experimental", icon: "warning" },
  UNSUPPORTED: { tone: "gray", label: "Unsupported", icon: "x-circle" },
};

// Secondary backend vocabularies that also surface in the UI. Same rules apply.
export const KIND = {
  RECOVERED: { tone: "gray", label: "Recovered", icon: "fragment" },
  RECONSTRUCTED: { tone: "blue", label: "Reconstructed", icon: "link" },
  DERIVATIVE: { tone: "violet", label: "Derivative", icon: "sparkles" },
};

// core/quality.py FQI categories
export const QUALITY = {
  PRIME: { tone: "green", label: "Prime", icon: "check" },
  STANDARD: { tone: "blue", label: "Standard", icon: "gauge" },
  DEGRADED: { tone: "yellow", label: "Degraded", icon: "warning" },
  SEVERE_BLUR_OR_LOW_CONTRAST: { tone: "red", label: "Severe blur / low contrast", icon: "x-circle" },
  UNINSPECTABLE: { tone: "gray", label: "Uninspectable", icon: "x-circle" },
  UNAVAILABLE: { tone: "gray", label: "Unavailable", icon: "info" },
};
export const QUALITY_ORDER = ["PRIME", "STANDARD", "DEGRADED", "SEVERE_BLUR_OR_LOW_CONTRAST", "UNINSPECTABLE", "UNAVAILABLE"];

// core/residual.py deletion-evidence levels and reconstruction confidence
export const RESIDUAL = {
  DELETION_CONFIRMED_BY_METADATA: { tone: "blue", label: "Deletion confirmed by metadata", icon: "shield" },
  DELETION_CORROBORATED: { tone: "blue", label: "Deletion corroborated", icon: "link" },
  RESIDUAL_CONTENT_RECOVERED: { tone: "yellow", label: "Residual content recovered", icon: "fragment" },
  CONTENT_RECOVERED_ONLY: { tone: "gray", label: "Content recovered only", icon: "info" },
  DELETION_UNSUPPORTED: { tone: "red", label: "Deletion claim unsupported", icon: "x-circle" },
  HIGH: { tone: "green", label: "High confidence", icon: "check" },
  MEDIUM: { tone: "yellow", label: "Medium confidence", icon: "warning" },
  LOW: { tone: "red", label: "Low confidence", icon: "x-circle" },
};

// Recording index row state (recording-index endpoint)
export const INDEX_STATE = {
  EXTRACTED: { tone: "green", label: "Extracted", icon: "check" },
  AVAILABLE_ON_E01: { tone: "gray", label: "On E01 image", icon: "disk" },
};

export const TONE_VARS = {
  green: { fg: "var(--tr-green-500)", bg: "var(--tr-green-bg)", bd: "var(--tr-green-border)" },
  red: { fg: "var(--tr-red-500)", bg: "var(--tr-red-bg)", bd: "var(--tr-red-border)" },
  yellow: { fg: "var(--tr-yellow-500)", bg: "var(--tr-yellow-bg)", bd: "var(--tr-yellow-border)" },
  blue: { fg: "var(--tr-blue-500)", bg: "var(--tr-blue-bg)", bd: "var(--tr-blue-border)" },
  violet: { fg: "var(--tr-violet-500)", bg: "var(--tr-violet-bg)", bd: "var(--tr-violet-border)" },
  gray: { fg: "var(--tr-gray-500)", bg: "var(--tr-gray-bg)", bd: "var(--tr-gray-border)" },
  amber: { fg: "var(--tr-amber-400)", bg: "var(--tr-amber-wash)", bd: "var(--tr-amber-line)" },
};

const TABLES = [STATUS, KIND, QUALITY, RESIDUAL, INDEX_STATE];

/** Resolve any backend code to {tone,label,icon}. Unknown codes render neutral, never invented. */
export function statusInfo(code) {
  for (const table of TABLES) {
    if (code in table) return { code, ...table[code] };
  }
  return { code, tone: "gray", label: readable(code), icon: "info" };
}

/** Audit actor → tone (engine = blue, examiner = amber, system = gray). */
export function actorTone(actor) {
  if (actor === "engine") return "blue";
  if (actor === "system") return "gray";
  return "amber";
}

export const isDerivative = (artifact) => artifact?.kind === "DERIVATIVE" || artifact?.status === "ENHANCED_COPY";

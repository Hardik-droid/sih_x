// Same-origin API client. The session token is a rotating per-process secret:
// it lives only in this module's memory, never in localStorage.

let token = "";
let authFailureHandler = null;

export function setToken(value) { token = value || ""; }
export function onAuthFailure(handler) { authFailureHandler = handler; }

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function normalizeDetail(detail, fallback) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: surface each message verbatim
    return detail.map((item) => (item && item.msg ? `${(item.loc || []).slice(1).join(".") || "input"}: ${item.msg}` : JSON.stringify(item))).join("; ");
  }
  if (detail) return JSON.stringify(detail);
  return fallback;
}

async function failure(res) {
  const body = await res.json().catch(() => ({ detail: res.statusText }));
  const message = normalizeDetail(body.detail, res.statusText || `Request failed (${res.status})`);
  if (res.status === 403 && authFailureHandler) authFailureHandler(message);
  return new ApiError(message, res.status, body.detail);
}

/** Core request. Mutating requests always carry x-trace-token. */
export async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { ...(options.headers || {}) };
  if (method !== "GET" && method !== "HEAD") headers["x-trace-token"] = token;
  if (options.body && typeof options.body === "string") headers["Content-Type"] = "application/json";
  let res;
  try {
    res = await fetch(`/api${path}`, { ...options, method, headers, credentials: "same-origin" });
  } catch (error) {
    throw new ApiError("Connection interrupted. Check that the local Trace server is running.", 0, null);
  }
  if (!res.ok) throw await failure(res);
  if (options.raw) return res;
  const type = res.headers.get("content-type") || "";
  return type.includes("json") ? res.json() : res.text();
}

export const get = (path, options) => api(path, options);
export const post = (path, body) => api(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

/** Fetch a text payload (e.g. the structured JSON report) without parsing it. */
export async function getText(path) {
  const res = await api(path, { raw: true });
  return res.text();
}

/**
 * Streamed browser upload with byte-accurate progress (fetch cannot report
 * upload progress). Resolves with the queued acquisition job.
 */
export function uploadWithProgress(caseId, file, onProgress, { signal } = {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/cases/${encodeURIComponent(caseId)}/upload?filename=${encodeURIComponent(file.name)}`);
    xhr.setRequestHeader("x-trace-token", token);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) onProgress(event.loaded, event.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) return resolve(xhr.response);
      const detail = xhr.response && xhr.response.detail;
      const message = normalizeDetail(detail, xhr.statusText || `Upload failed (${xhr.status})`);
      if (xhr.status === 403 && authFailureHandler) authFailureHandler(message);
      reject(new ApiError(message, xhr.status, detail));
    };
    xhr.onerror = () => reject(new ApiError("Upload interrupted. Check the local server and try again.", 0, null));
    xhr.onabort = () => reject(new ApiError("Upload cancelled.", 0, null));
    if (signal) signal.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.send(file);
  });
}

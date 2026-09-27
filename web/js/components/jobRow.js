// Processing-queue row: action, status, stage, live progress, timing and the
// one action that applies (cancel an active job / download a finished package).
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { number, relative, timeTag } from "../format.js";
import { ACTIVE_JOB, sourceById } from "../selectors.js";
import { badge } from "./badge.js";
import { button } from "./button.js";
import { progressBar } from "./progressBar.js";

function jobIcon(action = "") {
  const a = action.toLowerCase();
  if (a.includes("export")) return "package";
  if (a.includes("acquire") || a.includes("extract")) return "download";
  if (a.includes("reconstruct")) return "link";
  if (a.includes("analy")) return "scan";
  if (a.includes("repair")) return "refresh";
  return "sparkles";
}

const TONE = { FAILED: "red", COMPLETED: "green", CANCELLED: "gray", INTERRUPTED: "yellow" };

function resultSummary(job) {
  const r = job.result;
  if (!r || typeof r !== "object") return "";
  const parts = [];
  if (r.artifacts !== undefined) parts.push(`${number(r.artifacts)} candidate ranges`);
  if (r.recoverable !== undefined) parts.push(`${number(r.recoverable)} recoverable`);
  if (r.sha256 && job.action === "Export evidence package") parts.push(`package SHA-256 ${String(r.sha256).slice(0, 12)}…`);
  if (r.file) parts.push(r.file);
  if (r.name && r.kind) parts.push(`Created ${r.name}`);
  return parts.length ? `<p class="job__result">${icon("check", { size: 13 })}<span>${parts.map(esc).join(" · ")}</span></p>` : "";
}

export function jobRow(job, detail) {
  const active = ACTIVE_JOB.has(job.status);
  const source = job.source_id ? sourceById(job.source_id, detail) : null;
  const pct = Number(job.progress) || 0;
  const tone = TONE[job.status] || "amber";
  let actions = "";
  if (active) {
    actions = button({ label: "Cancel", variant: "danger", size: "sm", icon: "x-circle", action: "cancel-job", data: { id: job.id, name: job.action } });
  } else if (job.status === "COMPLETED" && job.result?.download_url) {
    actions = button({ label: "Download package", variant: "secondary", size: "sm", icon: "download", href: job.result.download_url, download: "" });
  }
  return `<article class="job${active ? " job--active" : ""}" data-key="${esc(job.id)}">
    <span class="icon-chip job__icon">${icon(jobIcon(job.action), { size: 16 })}</span>
    <div class="job__main">
      <div class="job__head"><strong class="job__title">${esc(job.action)}</strong>${badge(job.status)}</div>
      <p class="job__stage">${esc(job.stage || "—")}${source ? ` <span class="subtle">· ${esc(source.name)}</span>` : ""}</p>
      ${progressBar(pct, { tone, label: `${job.action} progress`, indeterminate: job.status === "RUNNING" && pct === 0 })}
      <div class="job__meta"><span class="tabular">${esc(Number.isInteger(pct) ? pct : pct.toFixed(1))}%</span><span aria-hidden="true">·</span>${timeTag(job.created_at)}${job.updated_at && !active ? `<span aria-hidden="true">·</span><span title="${esc(job.updated_at)}">finished ${esc(relative(job.updated_at))}</span>` : ""}</div>
      ${job.error ? `<p class="job__error">${icon("warning", { size: 14 })}<span>${esc(job.error)}</span></p>` : ""}
      ${job.status === "COMPLETED" ? resultSummary(job) : ""}
    </div>
    ${actions ? `<div class="job__actions">${actions}</div>` : ""}
  </article>`;
}

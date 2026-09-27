// Toasts: bottom-right stack, spring in, auto-dismiss (4 s; 8 s for errors),
// paused while hovered or focused. Polite region for status, assertive for errors.
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { animate, springs } from "../motion.js";

const TONE_ICON = { success: "check", error: "x-circle", warning: "warning", info: "info", neutral: "info" };
const MAX_VISIBLE = 4;

function host(assertive) {
  return document.getElementById(assertive ? "toasts-alert" : "toasts-status");
}

export function toast(message, { tone = "neutral", title = "", duration, action = null } = {}) {
  const assertive = tone === "error";
  const list = host(assertive);
  if (!list) return () => {};
  const item = document.createElement("li");
  item.className = `toast toast--${tone}`;
  item.innerHTML = `
    <span class="toast__icon">${icon(TONE_ICON[tone] || "info", { size: 16 })}</span>
    <div class="toast__body">
      ${title ? `<strong class="toast__title">${esc(title)}</strong>` : ""}
      <p class="toast__message">${esc(message)}</p>
      ${action ? `<button type="button" class="toast__action">${esc(action.label)}</button>` : ""}
    </div>
    <button type="button" class="toast__close" aria-label="Dismiss notification">${icon("close", { size: 14 })}</button>`;
  list.appendChild(item);

  const all = document.querySelectorAll(".toast:not(.is-leaving)");
  if (all.length > MAX_VISIBLE) dismiss(all[0]);

  animate(item, { opacity: [0, 1], y: [16, 0], scale: [0.98, 1] }, springs.bouncy);

  const total = duration ?? (assertive ? 8000 : 4000);
  let remaining = total;
  let started = Date.now();
  let timer = setTimeout(() => dismiss(item), remaining);
  const pause = () => { clearTimeout(timer); remaining -= Date.now() - started; };
  const resume = () => { started = Date.now(); clearTimeout(timer); timer = setTimeout(() => dismiss(item), Math.max(remaining, 1200)); };
  item.addEventListener("mouseenter", pause);
  item.addEventListener("mouseleave", resume);
  item.addEventListener("focusin", pause);
  item.addEventListener("focusout", resume);
  item.querySelector(".toast__close").addEventListener("click", () => { clearTimeout(timer); dismiss(item); });
  if (action) {
    item.querySelector(".toast__action").addEventListener("click", () => {
      clearTimeout(timer);
      dismiss(item);
      action.onClick?.();
    });
  }
  return () => { clearTimeout(timer); dismiss(item); };
}

function dismiss(item) {
  if (!item || item.classList.contains("is-leaving")) return;
  item.classList.add("is-leaving");
  animate(item, { opacity: 0, x: 24 }, { duration: 0.18, ease: [0.4, 0, 1, 1] }).finished.then(() => item.remove());
}

export const toastError = (message, options = {}) => toast(message, { ...options, tone: "error" });
export const toastSuccess = (message, options = {}) => toast(message, { ...options, tone: "success" });
export const toastInfo = (message, options = {}) => toast(message, { ...options, tone: "info" });

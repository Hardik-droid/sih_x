// Modal dialogs on the native <dialog> element: top layer, inert background
// (focus trap), Escape to close, focus returned to the trigger on close,
// spring entrance via Motion. Below 1180px they render as full-screen sheets.
import { esc, uid } from "../dom.js";
import { icon } from "../icons.js";
import { animate, springs } from "../motion.js";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
const openStack = [];

export const topModal = () => openStack[openStack.length - 1] || null;
export const anyModalOpen = () => openStack.length > 0;

/**
 * @param {object} o
 * @param {string} o.title
 * @param {string} [o.description]
 * @param {string} o.body               trusted HTML
 * @param {string} [o.footer]           trusted HTML
 * @param {"sm"|"md"|"lg"|"xl"|"full"} [o.size]
 * @param {(el: HTMLDialogElement, ctrl: object) => (void|Function)} [o.onMount]
 * @param {() => void} [o.onClose]
 * @param {boolean} [o.dismissible]
 * @param {string} [o.role]              "dialog" | "alertdialog"
 * @param {string} [o.initialFocus]      selector inside the dialog
 */
export function openModal({ title, description = "", body = "", footer = "", size = "md", onMount, onClose, dismissible = true, role = "dialog", initialFocus = "", className = "", headerExtra = "" }) {
  const id = uid("dlg");
  const dialog = document.createElement("dialog");
  dialog.className = `modal modal--${size}${className ? ` ${className}` : ""}`;
  dialog.setAttribute("aria-labelledby", `${id}-title`);
  if (description) dialog.setAttribute("aria-describedby", `${id}-desc`);
  if (role === "alertdialog") dialog.setAttribute("role", "alertdialog");
  dialog.innerHTML = `<div class="modal__panel">
      <header class="modal__head">
        <div class="modal__titles"><h2 class="modal__title" id="${id}-title">${esc(title)}</h2>${description ? `<p class="modal__desc" id="${id}-desc">${esc(description)}</p>` : ""}</div>
        ${headerExtra}
        <button type="button" class="btn btn--icon btn--icon-only modal__close" data-modal-close aria-label="Close dialog" title="Close (Esc)">${icon("close", { size: 16 })}</button>
      </header>
      <div class="modal__body">${body}</div>
      ${footer ? `<footer class="modal__foot">${footer}</footer>` : ""}
    </div>`;
  document.body.appendChild(dialog);

  const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const panel = dialog.querySelector(".modal__panel");
  let closing = false;
  let finalized = false;
  let cleanup = null;

  const finalize = () => {
    if (finalized) return;
    finalized = true;
    const index = openStack.indexOf(controller);
    if (index >= 0) openStack.splice(index, 1);
    if (typeof cleanup === "function") { try { cleanup(); } catch { /* ignore */ } }
    if (dialog.open) dialog.close();
    dialog.remove();
    onClose?.();
    const fallback = document.getElementById("content");
    if (opener && opener.isConnected) opener.focus({ preventScroll: true });
    else if (fallback && !fallback.closest("[hidden]")) fallback.focus({ preventScroll: true });
  };

  const close = () => {
    if (closing || finalized) return Promise.resolve();
    closing = true;
    dialog.classList.add("is-closing");
    return animate(panel, { opacity: 0, scale: 0.98, y: 6 }, { duration: 0.14, ease: [0.4, 0, 1, 1] }).finished.then(finalize, finalize);
  };

  const controller = {
    el: dialog,
    id,
    close,
    get body() { return dialog.querySelector(".modal__body"); },
    setBody(html) { dialog.querySelector(".modal__body").innerHTML = html; },
    setFooter(html) {
      let foot = dialog.querySelector(".modal__foot");
      if (!html) { foot?.remove(); return; }
      if (!foot) {
        foot = document.createElement("footer");
        foot.className = "modal__foot";
        panel.appendChild(foot);
      }
      foot.innerHTML = html;
    },
    setTitle(text) { dialog.querySelector(".modal__title").textContent = text; },
  };
  openStack.push(controller);

  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    if (dismissible) close();
  });
  dialog.addEventListener("close", finalize);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog && dismissible) close();
    if (event.target.closest("[data-modal-close]")) close();
  });

  dialog.showModal();
  animate(panel, { opacity: [0, 1], scale: [0.97, 1], y: [8, 0] }, springs.gentle);

  const result = onMount ? onMount(dialog, controller) : null;
  if (typeof result === "function") cleanup = result;

  const target = (initialFocus && dialog.querySelector(initialFocus))
    || dialog.querySelector("[autofocus]")
    || dialog.querySelector(`.modal__body ${FOCUSABLE}`)
    || dialog.querySelector(".modal__close");
  if (target) requestAnimationFrame(() => target.focus({ preventScroll: true }));
  return controller;
}

/** Confirmation for destructive/irreversible actions. Resolves true on confirm. */
export function confirmDialog({ title, message, confirmLabel = "Confirm", cancelLabel = "Keep working", tone = "danger" }) {
  return new Promise((resolve) => {
    let answered = false;
    const ctrl = openModal({
      title,
      size: "sm",
      role: "alertdialog",
      body: `<p class="confirm__message">${esc(message)}</p>`,
      footer: `<button type="button" class="btn btn--secondary" data-confirm="no" autofocus><span class="btn__label">${esc(cancelLabel)}</span></button>
               <button type="button" class="btn btn--${tone === "danger" ? "danger" : "primary"}" data-confirm="yes"><span class="btn__label">${esc(confirmLabel)}</span></button>`,
      initialFocus: '[data-confirm="no"]',
      onClose: () => { if (!answered) resolve(false); },
      onMount: (el) => {
        el.addEventListener("click", (event) => {
          const choice = event.target.closest("[data-confirm]");
          if (!choice) return;
          answered = true;
          resolve(choice.dataset.confirm === "yes");
          ctrl.close();
        });
      },
    });
  });
}

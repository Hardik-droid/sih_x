// Delegated action registry. Any element with data-action="name" triggers the
// registered handler; data-* attributes are passed through. Buttons show a
// width-stable loading state while an async handler runs, and every failure
// surfaces the backend's own message verbatim.
import { toastError } from "./components/toast.js";

const handlers = new Map();

export function defineActions(map) {
  for (const [name, handler] of Object.entries(map)) handlers.set(name, handler);
}

export const hasAction = (name) => handlers.has(name);

export async function runAction(name, detail = {}) {
  const handler = handlers.get(name);
  if (!handler) return undefined;
  return handler(detail);
}

export async function dispatch(element, event) {
  const name = element.dataset.action;
  const handler = handlers.get(name);
  if (!handler) return;
  if (element.tagName === "A" && !element.hasAttribute("data-allow-default")) event.preventDefault();
  if (element.getAttribute("aria-disabled") === "true" || element.disabled || element.dataset.loading === "true") return;
  const trackBusy = element.tagName === "BUTTON" && element.dataset.busy !== "off";
  let slow = null;
  if (trackBusy) {
    // Only show the spinner if the action takes a moment (avoids flicker)
    slow = setTimeout(() => { element.dataset.loading = "true"; element.setAttribute("aria-busy", "true"); }, 140);
  }
  try {
    await handler({ ...element.dataset, element, event });
  } catch (error) {
    toastError(error?.message || String(error));
  } finally {
    if (slow) clearTimeout(slow);
    if (trackBusy && element.isConnected) {
      delete element.dataset.loading;
      element.removeAttribute("aria-busy");
    }
  }
}

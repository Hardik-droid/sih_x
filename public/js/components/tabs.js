// Tabs (WAI-ARIA tabs pattern, shadcn anatomy): roving focus with arrow keys,
// Home/End, automatic activation. Activation calls data-action with data-tab.
import { attrs, esc } from "../dom.js";
import { icon } from "../icons.js";

/**
 * @param {{id:string, items:{id:string,label:string,icon?:string}[], active:string, action?:string, label:string, size?:string}} o
 */
export function tabs({ id, items, active, action = "", label, size = "md" }) {
  const buttons = items
    .map((item) => {
      const selected = item.id === active;
      return `<button ${attrs({
        type: "button",
        role: "tab",
        class: `tab${selected ? " is-active" : ""}`,
        id: `${id}-tab-${item.id}`,
        "aria-selected": selected ? "true" : "false",
        "aria-controls": `${id}-panel`,
        tabindex: selected ? "0" : "-1",
        "data-action": action || null,
        "data-tab": item.id,
        "data-tabs": id,
      })}>${item.icon ? icon(item.icon, { size: 15 }) : ""}<span>${esc(item.label)}</span></button>`;
    })
    .join("");
  return `<div class="tabs tabs--${size}" role="tablist" aria-label="${esc(label)}" data-tablist="${esc(id)}">${buttons}</div>`;
}

/** Tab panel wrapper, labelled by the active tab. */
export function tabPanel(id, active, body) {
  return `<div class="tab-panel" role="tabpanel" id="${esc(id)}-panel" aria-labelledby="${esc(id)}-tab-${esc(active)}" tabindex="0">${body}</div>`;
}

/** Global keyboard handling for every [role=tablist] (installed once in main.js). */
export function installTabKeyboard(root = document) {
  root.addEventListener("keydown", (event) => {
    const tab = event.target.closest?.('[role="tab"]');
    if (!tab) return;
    const list = tab.closest('[role="tablist"]');
    const all = [...list.querySelectorAll('[role="tab"]')];
    const index = all.indexOf(tab);
    let next = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = all[(index + 1) % all.length];
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = all[(index - 1 + all.length) % all.length];
    else if (event.key === "Home") next = all[0];
    else if (event.key === "End") next = all[all.length - 1];
    if (!next) return;
    event.preventDefault();
    next.focus();
    next.click();
  });
}

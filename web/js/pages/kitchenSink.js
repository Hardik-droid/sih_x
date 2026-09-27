// Debug-only component gallery (#kitchen-sink, requires ?debug=1). Not in nav.
import { defineActions } from "../actions.js";
import { STATUS, KIND, QUALITY, RESIDUAL, INDEX_STATE } from "../statusMap.js";
import { badge, derivativeTag, trendPill, actorChip } from "../components/badge.js";
import { button } from "../components/button.js";
import { detailList, notice, pageHeader, panel } from "../components/card.js";
import { statCard } from "../components/statCard.js";
import { emptyState } from "../components/emptyState.js";
import { skeleton, skeletonBlock } from "../components/skeleton.js";
import { progressBar } from "../components/progressBar.js";
import { tabs } from "../components/tabs.js";
import { table } from "../components/table.js";
import { hashField } from "../components/hash.js";
import { openModal, confirmDialog } from "../components/modal.js";
import { toast } from "../components/toast.js";

const SAMPLE_HASH = "0".repeat(64);

export function render() {
  const all = { ...STATUS, ...KIND, ...QUALITY, ...RESIDUAL, ...INDEX_STATE };
  const variants = ["primary", "secondary", "ghost", "danger", "accent", "pill"];
  return `${pageHeader({ eyebrow: "Debug", title: "Component kitchen sink", description: "Every component, tone and state. Visible only with ?debug=1." })}
    ${panel({ title: "Buttons", body: `<div class="stack">${["sm", "md", "lg"].map((size) => `<div class="row">${variants.map((v) => button({ label: v, variant: v, size, icon: "plus" })).join("")}${button({ variant: "icon", icon: "menu", title: "Icon button", size })}</div>`).join("")}<div class="row">${button({ label: "Disabled", variant: "primary", disabled: true })}${button({ label: "Loading", variant: "primary", attrs: { "data-loading": "true" } })}${button({ label: "Link button", href: "#kitchen-sink" })}</div></div>` })}
    ${panel({ title: "Status badges", body: `<div class="row">${Object.keys(all).map((code) => badge(code)).join("")}${derivativeTag()}${trendPill("up", "4 in 24 h")}${trendPill("down", "1 fewer")}${actorChip("engine")}${actorChip("Lab examiner")}${actorChip("system")}</div>` })}
    <div class="grid-kpi">${statCard({ label: "Evidence sources", value: "01", icon: "sources", note: "1.0 MiB total evidence", trend: { direction: "up", text: "1 in 24 h" } })}${statCard({ label: "Active operations", value: "00", icon: "recovery", note: "Ready for your next source" })}${skeletonBlock(132)}${statCard({ label: "Audit events", value: "17", icon: "integrity", note: "Hash chain verified" })}</div>
    <div class="grid-2">
      ${panel({ title: "Progress", body: `<div class="stack">${progressBar(0, { indeterminate: true })}${progressBar(35)}${progressBar(72, { tone: "green" })}${progressBar(100, { tone: "red" })}</div>` })}
      ${panel({ title: "Tabs", body: tabs({ id: "ks", items: [{ id: "a", label: "Forensic case report", icon: "reports" }, { id: "b", label: "Certificate", icon: "scale" }, { id: "c", label: "JSON", icon: "terminal" }], active: "a", label: "Demo tabs" }) })}
    </div>
    <div class="grid-2">
      ${panel({ title: "Notices", body: `<div class="stack">${["info", "success", "warning", "danger", "violet", "neutral"].map((t) => notice(`A ${t} notice with calm, specific copy.`, { tone: t })).join("")}</div>` })}
      ${panel({ title: "Details & hash", body: `<div class="stack">${detailList([{ label: "Codec", value: "H264" }, { label: "Frames", value: "30" }, { label: "Resolution", value: null }])}${hashField(SAMPLE_HASH, { label: "Example SHA-256 (all zero)" })}${hashField(null)}</div>` })}
    </div>
    <div class="grid-2">
      ${panel({ title: "Empty state", body: emptyState({ icon: "evidence", title: "Nothing recovered yet", body: "Import a source and let the recovery engine inspect its surviving media.", action: button({ label: "Import evidence", variant: "primary", icon: "upload" }) }) })}
      ${panel({ title: "Skeleton & table", body: `${skeleton({ lines: 3 })}${table({ caption: "Example", columns: [{ key: "a", label: "Column A" }, { key: "b", label: "Column B" }], rows: [{ a: "Row 1", b: "Value" }, { a: "Row 2", b: "Value" }] })}` })}
    </div>
    ${panel({ title: "Overlays", body: `<div class="row">${button({ label: "Open modal", action: "ks-modal" })}${button({ label: "Confirm dialog", variant: "danger", action: "ks-confirm" })}${["success", "info", "warning", "error", "neutral"].map((t) => button({ label: `${t} toast`, variant: "ghost", action: "ks-toast", data: { tone: t } })).join("")}</div>` })}`;
}

defineActions({
  "ks-modal": () => openModal({ title: "Example dialog", description: "Focus is trapped; Escape closes; focus returns to the trigger.", body: `<form class="form"><div class="field"><label class="field__label" for="ks-input">Example field</label><input class="input" id="ks-input" autofocus></div></form>`, footer: button({ label: "Done", variant: "primary", attrs: { "data-modal-close": "" } }) }),
  "ks-confirm": async () => { const ok = await confirmDialog({ title: "Cancel this job?", message: "Example destructive confirmation.", confirmLabel: "Cancel job" }); toast(ok ? "Confirmed" : "Kept", { tone: "info" }); },
  "ks-toast": ({ tone }) => toast(`Example ${tone} notification.`, { tone }),
});

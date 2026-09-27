// Entry point: boot the local session, build the shell, wire global events,
// then hand rendering to the router. No build step — native ES modules only.
import { $, $$, copyText, esc } from "./dom.js";
import { icon } from "./icons.js";
import { day, initials } from "./format.js";
import { state, subscribe } from "./state.js";
import { onAuthFailure, post } from "./api.js";
import { loadRegistry, loadSession, refresh, selectCase } from "./data.js";
import { defineActions, dispatch } from "./actions.js";
import { NAV_ROUTES, moveIndicator, navigate, parseHash, render } from "./router.js";
import { toast, toastError, toastSuccess } from "./components/toast.js";
import { installTabKeyboard } from "./components/tabs.js";
import { topModal } from "./components/modal.js";
import "./modals/newCase.js";
import "./modals/importEvidence.js";
import "./modals/artifactViewer.js";
import "./modals/byteInspector.js";
import { repaintRecordingIndex } from "./pages/recordingIndex.js";
import { togglePalette } from "./modals/commandPalette.js";

const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

// ------------------------------------------------------------- sidebar ----
function buildNavigation() {
  const nav = $("#navigation");
  const links = NAV_ROUTES.map((route, index) => `${index === 5 ? '<div class="nav-divider" role="separator"></div>' : ""}<a class="nav-link" href="#${route.id}" data-route="${route.id}">${icon(route.icon, { size: 18 })}<span>${esc(route.title)}</span></a>`).join("");
  nav.insertAdjacentHTML("beforeend", links);
}

function updateShell() {
  const select = $("#case-select");
  if (select && document.activeElement !== select) {
    select.innerHTML = state.cases.length
      ? state.cases.map((c) => `<option value="${esc(c.id)}"${c.id === state.caseId ? " selected" : ""}>${esc(c.name)}</option>`).join("")
      : '<option value="">No case selected</option>';
    select.disabled = !state.cases.length;
  }
  const examiner = state.detail?.case?.examiner || "Examiner workspace";
  $("#profile-name").textContent = examiner;
  $("#profile-initials").textContent = initials(state.detail?.case?.examiner || "Examiner");
  $("#topbar-initials").textContent = initials(state.detail?.case?.examiner || "Examiner");
  const pill = $("#session-pill");
  const lost = state.connection === "lost";
  pill.classList.toggle("is-lost", lost);
  pill.querySelector(".live-dot").classList.toggle("live-dot--lost", lost);
  pill.querySelector("span:last-child").textContent = lost ? "CONNECTION LOST" : "LOCAL SESSION";
  pill.title = lost ? "The local Trace server is not responding" : "Connected to the local Trace server";
}

function setSidebar(open) {
  const shell = $("#app-shell");
  shell.classList.toggle("sidebar-open", open);
  $("#scrim").hidden = !open;
  const toggle = $(".topbar__menu");
  toggle?.setAttribute("aria-expanded", String(open));
  if (open) $("#navigation .nav-link")?.focus();
  else if (shell.contains(document.activeElement) && $("#sidebar").contains(document.activeElement)) toggle?.focus();
}

// ------------------------------------------------------------- actions ----
defineActions({
  go: ({ to }) => { setSidebar(false); navigate(to); },
  copy: async ({ value, label }) => {
    const ok = await copyText(value || "");
    toast(ok ? `${label || "Value"} copied to clipboard.` : "Copy failed — select the value manually.", { tone: ok ? "success" : "warning" });
  },
  demo: async () => {
    const item = await post("/demo");
    await selectCase(item.id);
    location.hash = "#recovery";
    toastSuccess("Controlled synthetic case created. Recovery is running.");
  },
  palette: () => togglePalette(),
  "toggle-sidebar": () => setSidebar(!$("#app-shell").classList.contains("sidebar-open")),
  "close-sidebar": () => setSidebar(false),
  skip: () => {
    const target = state.route.id === "home" ? $("#site-main") : $("#content");
    target?.setAttribute("tabindex", "-1");
    target?.focus();
  },
  "retry-boot": () => boot(),
});

// -------------------------------------------------------- global events ----
document.addEventListener("click", (event) => {
  const el = event.target.closest("[data-action]");
  if (el) dispatch(el, event);
  // Close the mobile sidebar after following a nav link
  if (event.target.closest("#navigation .nav-link")) setSidebar(false);
});

document.addEventListener("change", (event) => {
  if (event.target.id === "case-select" && event.target.value) {
    selectCase(event.target.value).catch((error) => toastError(error.message));
  }
});

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    togglePalette();
    return;
  }
  if (event.key === "Escape" && $("#app-shell").classList.contains("sidebar-open") && !topModal()) setSidebar(false);
});

// Broken thumbnails fall back to the codec glyph (never a fake image)
document.addEventListener("error", (event) => {
  const img = event.target;
  if (img instanceof HTMLImageElement && img.dataset.fallback) {
    img.hidden = true;
    img.closest(".art-card__media")?.classList.add("is-fallback");
  }
}, true);

window.addEventListener("hashchange", () => {
  const next = parseHash();
  const sameRoute = next.id === state.route.id;
  state.route = next;
  setSidebar(false);
  render(sameRoute ? "route-same" : "route");
});

window.addEventListener("resize", () => moveIndicator());

let authToastAt = 0;
onAuthFailure(async () => {
  if (Date.now() - authToastAt > 5000) {
    authToastAt = Date.now();
    toastError("Local session expired or invalid — refresh the app.");
  }
  try { await loadSession(); } catch { /* server unreachable; the poll loop reports it */ }
});

let connectionToast = null;
subscribe((_, reason) => {
  updateShell();
  if (reason === "connection") {
    if (state.connection === "lost" && !connectionToast) connectionToast = toastError("Connection interrupted. Check the local server.");
    return;
  }
  if (state.connection === "ok") connectionToast = null;
  render(reason);
  repaintRecordingIndex();
});

// ---------------------------------------------------------------- boot ----
async function boot() {
  const bootEl = $("#boot");
  bootEl.classList.remove("boot--error");
  bootEl.innerHTML = `<span class="brand__mark brand__mark--lg" aria-hidden="true">t<span>·</span></span><p class="boot__text">Connecting to your local workspace…</p>`;
  try {
    state.route = parseHash();
    await loadSession();
    $("#footer-version").textContent = `v${state.session.version}`;
    $("#today").textContent = day(new Date());
    $("#palette-kbd").textContent = isMac ? "⌘K" : "Ctrl K";
    await Promise.all([loadRegistry(), refresh()]);
    updateShell();
    render("route");
    if (state.route.section) render("route-same");
  } catch (error) {
    document.body.dataset.mode = "boot";
    bootEl.classList.add("boot--error");
    bootEl.innerHTML = `<span class="brand__mark brand__mark--lg" aria-hidden="true">t<span>·</span></span>
      <div class="boot__error"><strong>Unable to reach the local Trace server</strong><p>${esc(error.message)}</p><p class="subtle">Start it with <code>python run.py</code>, then retry.</p></div>
      <button type="button" class="btn btn--primary" data-action="retry-boot"><span class="btn__label">Retry connection</span></button>`;
  }
}

buildNavigation();
installTabKeyboard();
boot();

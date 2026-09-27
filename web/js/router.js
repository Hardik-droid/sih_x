// Hash router. Routes: #home (product website) plus the eight workspace pages.
// A route change re-renders with an entrance animation; a data refresh on the
// same route morphs the DOM in place (no flash, focus and scroll preserved).
import { $, $$, morph } from "./dom.js";
import { enter, animate, springs } from "./motion.js";
import { state } from "./state.js";
import * as home from "./pages/home.js";
import * as overview from "./pages/overview.js";
import * as sources from "./pages/sources.js";
import * as evidence from "./pages/evidence.js";
import * as timeline from "./pages/timeline.js";
import * as recovery from "./pages/recovery.js";
import * as integrity from "./pages/integrity.js";
import * as reports from "./pages/reports.js";
import * as registry from "./pages/registry.js";
import * as kitchenSink from "./pages/kitchenSink.js";

export const ROUTES = [
  { id: "home", title: "Trace", page: home, site: true },
  { id: "overview", title: "Overview", icon: "overview", page: overview },
  { id: "sources", title: "Evidence sources", icon: "sources", page: sources },
  { id: "evidence", title: "Recovered evidence", icon: "evidence", page: evidence },
  { id: "timeline", title: "Timeline & notes", icon: "timeline", page: timeline },
  { id: "recovery", title: "Recovery engine", icon: "recovery", page: recovery },
  { id: "integrity", title: "Chain of custody", icon: "integrity", page: integrity },
  { id: "reports", title: "Reports & exports", icon: "reports", page: reports },
  { id: "registry", title: "Compatibility", icon: "registry", page: registry },
  { id: "kitchen-sink", title: "Component kitchen sink", icon: "layers", page: kitchenSink, debug: true },
];

export const NAV_ROUTES = ROUTES.filter((r) => !r.site && !r.debug);
const byId = new Map(ROUTES.map((r) => [r.id, r]));
export const debugEnabled = () => new URLSearchParams(location.search).get("debug") === "1";

export function parseHash(hash = location.hash) {
  const raw = decodeURIComponent(hash.replace(/^#\/?/, ""));
  const [id, ...rest] = raw.split("/");
  const section = rest.join("/") || null;
  if (!id) return { id: "home", section: null };
  const route = byId.get(id);
  if (!route || (route.debug && !debugEnabled())) return { id: "overview", section: null };
  return { id, section };
}

export const routeById = (id) => byId.get(id) || byId.get("overview");
export const currentRoute = () => routeById(state.route.id);

export function navigate(id, section = null) {
  const target = `#${id}${section ? `/${section}` : ""}`;
  if (location.hash === target) render("route-same");
  else location.hash = target;
}

let mounted = { id: null, cleanup: null, root: null };

function context(reason) {
  return { state, route: state.route, reason };
}

/** Render the current route. reason: "route" | "data" | "poll" | "case" | ... */
export function render(reason = "data") {
  const route = currentRoute();
  const isSite = Boolean(route.site);
  document.body.dataset.mode = isSite ? "site" : "app";
  $("#site-root").hidden = !isSite;
  $("#app-shell").hidden = isSite;
  const root = isSite ? $("#site-root") : $("#content");
  const ctx = context(reason);

  if (mounted.id !== route.id || (reason === "case" && !route.page.isStatic)) {
    if (mounted.cleanup) { try { mounted.cleanup(); } catch { /* ignore */ } }
    if (mounted.root && mounted.root !== root) mounted.root.replaceChildren();
    root.innerHTML = route.page.render(ctx);
    const cleanup = route.page.mount ? route.page.mount(root, ctx) : null;
    mounted = { id: route.id, cleanup: typeof cleanup === "function" ? cleanup : null, root };
    updateChrome(route);
    if (!isSite) {
      window.scrollTo({ top: 0, behavior: "instant" });
      enter($$(":scope > *", root), { y: 6, each: 0.03 });
    }
    if (reason === "route" && !isSite) root.focus({ preventScroll: true });
    return;
  }
  if (reason === "route-same") {
    route.page.onSection?.(root, ctx);
    return;
  }
  if (route.page.isStatic) {
    route.page.update?.(root, ctx);
    updateChrome(route);
    return;
  }
  morph(root, route.page.render(ctx));
  route.page.update?.(root, ctx);
  updateChrome(route);
}

// ------------------------------------------------------- shell chrome ----
function updateChrome(route) {
  document.title = route.site ? "Trace · DVR & NVR forensic recovery" : `${route.title} · Trace`;
  const crumb = $("#breadcrumb");
  if (crumb) crumb.textContent = route.title;
  for (const link of $$("#navigation .nav-link")) {
    const active = link.dataset.route === route.id;
    link.classList.toggle("is-active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  moveIndicator();
}

let indicatorReady = false;
export function moveIndicator() {
  const indicator = $("#nav-indicator");
  const active = $("#navigation .nav-link.is-active");
  if (!indicator) return;
  if (!active || active.offsetParent === null) {
    indicator.style.opacity = "0";
    return;
  }
  const top = active.offsetTop;
  const height = active.offsetHeight;
  if (!indicatorReady) {
    animate(indicator, { y: top, height }, { duration: 0 });
    indicator.style.opacity = "1";
    indicatorReady = true;
    return;
  }
  indicator.style.opacity = "1";
  animate(indicator, { y: top, height }, springs.snappy);
}

// Skeleton placeholders shown while a case is loading (never fake content).

export function skeleton({ lines = 3, className = "" } = {}) {
  const widths = [92, 76, 84, 60, 70];
  return `<div class="skeleton-stack ${className}" aria-hidden="true">${Array.from({ length: lines }, (_, i) => `<span class="skeleton skeleton--line" style="width:${widths[i % widths.length]}%"></span>`).join("")}</div>`;
}

export function skeletonBlock(height = 120, className = "") {
  return `<span class="skeleton skeleton--block ${className}" style="height:${Number(height)}px" aria-hidden="true"></span>`;
}

/** Full-page loading layout: header, KPI row and two panels. */
export function pageSkeleton(label = "Loading case") {
  return `<div class="page-skeleton" role="status" aria-live="polite">
    <span class="sr-only">${label}…</span>
    <div class="page-skeleton__head"><span class="skeleton skeleton--line" style="width:180px"></span><span class="skeleton skeleton--title"></span><span class="skeleton skeleton--line" style="width:320px"></span></div>
    <div class="grid-kpi">${Array.from({ length: 4 }, () => skeletonBlock(128)).join("")}</div>
    <div class="grid-2">${skeletonBlock(260)}${skeletonBlock(260)}</div>
  </div>`;
}

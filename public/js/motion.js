// Motion (motion.dev, MIT) is vendored at /assets/vendor/motion — no CDN, no build.
// The UMD bundle registers globalThis.Motion when evaluated as a module side effect.
// This wrapper adds reduced-motion handling and safe no-op fallbacks.
import "../assets/vendor/motion/motion.js";

const Motion = globalThis.Motion || null;
const media = typeof matchMedia === "function" ? matchMedia("(prefers-reduced-motion: reduce)") : null;

export const prefersReducedMotion = () => Boolean(media && media.matches);

const TRANSFORM_KEYS = new Set(["x", "y", "z", "scale", "scaleX", "scaleY", "rotate", "rotateX", "rotateY", "skew", "transform", "filter", "height", "width"]);

const noop = { finished: Promise.resolve(), then: (fn) => Promise.resolve().then(fn), stop() {}, cancel() {}, complete() {} };

function resolveTargets(target) {
  if (!target) return [];
  if (typeof target === "string") return [...document.querySelectorAll(target)];
  if (target instanceof Element) return [target];
  return [...target].filter(Boolean);
}

/**
 * animate(target, keyframes, options) — Motion's animate with reduced-motion
 * support: transform keyframes are dropped and durations shortened, keeping
 * opacity-only fades as BUILD.md §5.9 requires.
 */
export function animate(target, keyframes, options = {}) {
  const nodes = resolveTargets(target);
  if (!nodes.length) return noop;
  if (!Motion) {
    for (const node of nodes) applyFinal(node, keyframes);
    return noop;
  }
  if (prefersReducedMotion()) {
    const reduced = {};
    for (const [key, value] of Object.entries(keyframes)) {
      if (!TRANSFORM_KEYS.has(key)) reduced[key] = value;
    }
    for (const [key, value] of Object.entries(keyframes)) {
      if (TRANSFORM_KEYS.has(key)) applyProperty(nodes, key, value);
    }
    if (!Object.keys(reduced).length) return noop;
    return Motion.animate(nodes, reduced, { duration: 0.12, ease: "linear", delay: 0 });
  }
  return Motion.animate(nodes, keyframes, options);
}

function finalValue(value) {
  return Array.isArray(value) ? value[value.length - 1] : value;
}

function applyProperty(nodes, key, value) {
  const final = finalValue(value);
  for (const node of nodes) {
    if (key === "height" || key === "width") node.style[key] = typeof final === "number" ? `${final}px` : final;
    else if (key === "x" || key === "y") node.style.translate = key === "x" ? `${final}px 0` : `0 ${final}px`;
  }
}

function applyFinal(node, keyframes) {
  for (const [key, value] of Object.entries(keyframes)) {
    const final = finalValue(value);
    if (key === "opacity") node.style.opacity = String(final);
    else applyProperty([node], key, value);
  }
}

export const stagger = (each = 0.04, options) => (Motion ? Motion.stagger(each, options) : 0);

/** Motion's inView with a fallback that simply calls the handler once. */
export function inView(target, onEnter, options) {
  if (Motion && typeof IntersectionObserver === "function") return Motion.inView(target, onEnter, options);
  for (const node of resolveTargets(target)) onEnter(node, {});
  return () => {};
}

/** Scroll-linked callback (progress 0→1). Returns a cancel function. */
export function scroll(callback, options) {
  if (!Motion || prefersReducedMotion()) return () => {};
  return Motion.scroll(callback, options);
}

export const springs = {
  gentle: { type: "spring", stiffness: 260, damping: 30, mass: 1 },
  snappy: { type: "spring", stiffness: 420, damping: 34, mass: 0.9 },
  bouncy: { type: "spring", stiffness: 360, damping: 22, mass: 0.9 },
};

/** Fade + rise entrance used on route changes and freshly revealed content. */
export function enter(target, { y = 6, delay = 0, each = 0.035, duration = 0.18 } = {}) {
  const nodes = resolveTargets(target);
  if (!nodes.length) return noop;
  return animate(nodes, { opacity: [0, 1], y: [y, 0] }, { duration, delay: Motion ? Motion.stagger(each, { startDelay: delay }) : 0, ease: [0.2, 0.8, 0.2, 1] });
}

// Product website (#home). Apple-style storytelling with Motion scroll reveals.
// Every figure on this page is either an engineering fact from the codebase or
// live data from this local server (session + compatibility registry). No
// invented statistics, thumbnails or testimonials.
import { state } from "../state.js";
import { defineActions } from "../actions.js";
import { $, $$, esc } from "../dom.js";
import { icon } from "../icons.js";
import { number } from "../format.js";
import { STATUS } from "../statusMap.js";
import { animate, inView, prefersReducedMotion, scroll, stagger } from "../motion.js";
import { badge, derivativeTag, toneBadge } from "../components/badge.js";
import { platter } from "../components/visuals.js";

// The website never re-renders on data polls (it would reset scroll reveals).
export const isStatic = true;

const SECTIONS = [
  ["engine", "Recovery"],
  ["separation", "Evidence"],
  ["custody", "Custody"],
  ["output", "Reports"],
  ["compatibility", "Compatibility"],
  ["local", "Local by design"],
];

const cta = (size = "lg") => `
  <a class="btn btn--primary btn--${size} btn--round" href="#overview"><span class="btn__label">Open workspace</span>${icon("arrow", { size: size === "lg" ? 18 : 16 })}</a>
  <button type="button" class="btn btn--secondary btn--${size} btn--round" data-action="demo">${icon("play", { size: size === "lg" ? 16 : 14 })}<span class="btn__label">Run the controlled demo</span><span class="btn__spinner" aria-hidden="true"></span></button>`;

function nav() {
  return `<header class="site-nav" data-site-nav>
    <div class="site-nav__inner">
      <a class="brand brand--site" href="#home" aria-label="Trace — home"><span class="brand__mark" aria-hidden="true">t<span>·</span></span><span class="brand__name">trace</span></a>
      <nav class="site-nav__links" aria-label="Product sections">${SECTIONS.map(([id, label]) => `<a href="#home/${id}" data-section-link="${id}">${label}</a>`).join("")}</nav>
      <div class="site-nav__cta">
        <button type="button" class="btn btn--ghost btn--sm site-nav__demo" data-action="demo"><span class="btn__label">Run demo</span><span class="btn__spinner" aria-hidden="true"></span></button>
        <a class="btn btn--primary btn--sm btn--round" href="#overview"><span class="btn__label">Open workspace</span></a>
        <button type="button" class="btn btn--icon btn--icon-only site-nav__menu" data-action="site-menu" aria-expanded="false" aria-controls="site-menu" aria-label="Open menu">${icon("menu", { size: 18 })}</button>
      </div>
    </div>
    <div class="site-menu" id="site-menu" hidden>
      <nav aria-label="Product sections">${SECTIONS.map(([id, label]) => `<a href="#home/${id}">${label}</a>`).join("")}<a href="#overview">Open workspace</a></nav>
    </div>
  </header>`;
}

function hero() {
  return `<section class="s-hero" aria-labelledby="hero-h">
    <div class="s-hero__inner">
      <p class="s-kicker" data-hero-fade>SIH26150 · DVR &amp; NVR forensic recovery</p>
      <h1 class="s-hero__title" id="hero-h"><span class="s-hero__line" data-hero-line>Every fragment has a story.</span><span class="s-hero__line s-hero__line--accent" data-hero-line>Prove every byte of it.</span></h1>
      <p class="s-hero__lede" data-hero-fade>Trace acquires CCTV recorder storage read-only, recovers what survives and keeps every step traceable — from the first sector to a courtroom certificate.</p>
      <div class="s-hero__cta" data-hero-fade>${cta("lg")}</div>
      <p class="s-hero__fine" data-hero-fade>Runs on this workstation. No cloud upload, no account, no AI key.</p>
    </div>
    <div class="s-hero__stage" data-hero-stage aria-hidden="true">
      <div class="s-hero__stage-inner" data-hero-intro>
        <div class="s-hero__halo"></div>
        ${platter({ className: "platter--hero" })}
        <span class="float-chip float-chip--a">${icon("lock", { size: 13 })}Source · read only</span>
        <span class="float-chip float-chip--b">${icon("integrity", { size: 13 })}SHA-256 verified before and after analysis</span>
        <span class="float-chip float-chip--c"><i class="float-chip__hatch"></i>Gap preserved · not filled</span>
        <span class="float-chip float-chip--d float-chip--violet">${icon("sparkles", { size: 13 })}Derivatives labelled</span>
      </div>
    </div>
  </section>`;
}

function principles() {
  const items = [
    ["lock", "Read-only acquisition"],
    ["hash", "SHA-256 at every step"],
    ["split", "Explicit gaps, never guesses"],
    ["sparkles", "Derivatives stay labelled"],
    ["link", "Hash-chained audit"],
    ["cloud-off", "Local only"],
  ];
  return `<section class="s-principles" aria-label="Principles"><ul class="principles" role="list">${items.map(([i, t]) => `<li data-reveal>${icon(i, { size: 18 })}<span>${t}</span></li>`).join("")}</ul></section>`;
}

function tierVisual() {
  const cells = Array.from({ length: 20 }, (_, i) => `<rect class="tv-cell" x="${20 + i * 26}" y="206" width="22" height="44" rx="5"/>`).join("");
  const span = (from, to, cls) => Array.from({ length: to - from + 1 }, (_, k) => `<rect class="${cls}" x="${20 + (from + k) * 26}" y="206" width="22" height="44" rx="5"/>`).join("");
  return `<svg class="tier-svg" viewBox="0 0 560 330" aria-hidden="true" focusable="false">
    <defs><pattern id="tv-hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="2.2" height="7" class="tv-hatch-line"/></pattern></defs>
    <text class="tv-caption" x="20" y="286">SECTORS OF THE VERIFIED COPY</text>
    ${cells}
    <g class="tv-layer tv-layer--1">
      <rect class="tv-box" x="70" y="58" width="170" height="46" rx="10"/><text class="tv-box-text" x="155" y="86" text-anchor="middle">Surviving index · CRC</text>
      <rect class="tv-box tv-box--dim" x="300" y="58" width="170" height="46" rx="10"/><text class="tv-box-text" x="385" y="86" text-anchor="middle">Duplicate index</text>
      <path class="tv-link" d="M130 104 C130 150 124 170 124 204"/><path class="tv-link" d="M190 104 C190 150 202 170 202 204"/>
      ${span(4, 7, "tv-fill tv-fill--green")}
      <text class="tv-note tv-note--green" x="124" y="316">exact offsets · decoded · hash recorded</text>
    </g>
    <g class="tv-layer tv-layer--2">
      ${span(2, 5, "tv-fill tv-fill--amber")}${span(11, 14, "tv-fill tv-fill--amber")}
      <path class="tv-arc" d="M150 204 C 190 110, 290 110, 314 204"/>
      <circle class="tv-seam" cx="232" cy="138" r="17"/><path class="tv-seam-check" d="m224 138 5.5 5.5 10-11"/>
      <text class="tv-note" x="232" y="100" text-anchor="middle">decoder-validated seam</text>
      <text class="tv-note tv-note--amber" x="280" y="316" text-anchor="middle">source · camera · codec · time · checksum must agree</text>
    </g>
    <g class="tv-layer tv-layer--3">
      ${span(2, 6, "tv-fill tv-fill--yellow")}${span(7, 9, "tv-gap")}${span(10, 14, "tv-fill tv-fill--yellow")}${span(15, 16, "tv-gap")}
      <path class="tv-bracket" d="M202 196 V184 H276 V196"/>
      <text class="tv-note tv-note--gap" x="239" y="172" text-anchor="middle">gap · reported, not filled</text>
      <text class="tv-note tv-note--yellow" x="280" y="316" text-anchor="middle">what survives is kept · missing intervals stay visible</text>
    </g>
  </svg>`;
}

function engine() {
  const tiers = [
    ["01", "Deterministic structural recovery", "When a recorder’s index or journal survives, Trace maps its records straight to byte ranges on the verified copy — exact offsets, exact hashes, confirmed by a full decode.", ["Duplicate indexes are discovered, not assumed", "Every fragment keeps its source offsets"]],
    ["02", "Verified fragment reconstruction", "Candidate fragments are joined only when source, camera, codec, timestamps and checksums agree, and the joined stream must decode end to end. Otherwise the join is refused and the reason is recorded.", ["Rejected pairs stay visible with evidence", "Joins produce a new artifact; fragments remain"]],
    ["03", "Partial recovery, explicit gaps", "Whatever survives is preserved. Missing intervals are reported as gaps on the timeline and in the report. Nothing is interpolated and nothing is filled in.", ["Partial streams keep their validated prefix", "Substreams can cover gaps — at their own resolution"]],
  ];
  return `<section class="s-section s-engine" id="sec-engine" aria-labelledby="engine-h">
    <div class="s-head" data-reveal><p class="s-kicker">The recovery engine</p><h2 class="s-title" id="engine-h">Three tiers.<br>One rule: never guess.</h2><p class="s-lede">Recovery escalates only as far as the evidence allows — and every result says exactly how it was obtained.</p></div>
    <div class="tiers" data-tiers>
      <div class="tiers__visual"><div class="tiers__sticky"><div class="tier-vis" data-step="1">${tierVisual()}<div class="tier-vis__legend"><span class="tier-vis__dot tier-vis__dot--1"></span><span class="tier-vis__dot tier-vis__dot--2"></span><span class="tier-vis__dot tier-vis__dot--3"></span></div></div></div></div>
      <ol class="tiers__steps" role="list">${tiers.map(([n, t, p, facts], i) => `<li class="tier${i === 0 ? " is-active" : ""}" data-tier="${i + 1}"><span class="tier__num tabular">${n}</span><h3 class="tier__title">${t}</h3><p class="tier__text">${p}</p><ul class="tier__facts" role="list">${facts.map((f) => `<li>${icon("check", { size: 14 })}${f}</li>`).join("")}</ul></li>`).join("")}</ol>
    </div>
  </section>`;
}

function separation() {
  return `<section class="s-section s-separation" id="sec-separation" aria-labelledby="sep-h">
    <div class="s-split">
      <div class="s-copy" data-reveal>
        <p class="s-kicker">Evidence separation</p>
        <h2 class="s-title" id="sep-h">The original<br>stays original.</h2>
        <p class="s-lede">Denoise, contrast and sharpen create separate viewing copies with their own hashes and transformation records. Each carries a violet derivative label everywhere it appears — grid, viewer and report.</p>
        <ul class="s-list" role="list">
          <li>${icon("check", { size: 16 })}Recovered bytes are never overwritten</li>
          <li>${icon("check", { size: 16 })}Deterministic FFmpeg filters, not generative AI</li>
          <li>${icon("check", { size: 16 })}Missing pixels are never recreated</li>
        </ul>
      </div>
      <div class="compare" data-reveal>
        <article class="compare__card">
          <div class="compare__media">${icon("film", { size: 30 })}<span class="compare__label">Illustration</span></div>
          <div class="compare__body">${badge("EXACT_RECOVERED")}<strong>Recovered original</strong><p>Byte-exact range · decoded · SHA-256 recorded with source offsets.</p></div>
        </article>
        <article class="compare__card compare__card--derivative">
          <span class="compare__tag">${derivativeTag()}</span>
          <div class="compare__media compare__media--derivative">${icon("sliders", { size: 30 })}<span class="compare__label">Illustration</span><p class="evidence-banner evidence-banner--derivative">${icon("sparkles", { size: 13 })}<span>ENHANCED VIEWING COPY — transformed pixels, not original evidence.</span></p></div>
          <div class="compare__body">${badge("ENHANCED_COPY")}<strong>Denoised viewing copy</strong><p>A new file with its own hash. Its parent and filter parameters are on record.</p></div>
        </article>
      </div>
    </div>
  </section>`;
}

function custody() {
  const chain = [
    ["folder", "case_created", "Case opened"],
    ["sources", "source_registered", "Source registered"],
    ["integrity", "acquisition_verified", "Copy verified by SHA-256"],
    ["fragment", "artifact_recovered", "Fragment decoded"],
    ["reports", "report_generated", "Report generated"],
    ["package", "export_packaged", "Package manifested"],
  ];
  return `<section class="s-section s-custody" id="sec-custody" aria-labelledby="cus-h">
    <div class="s-head" data-reveal><p class="s-kicker">Chain of custody</p><h2 class="s-title" id="cus-h">Every step, hash-linked.</h2><p class="s-lede">Acquisition, recovery, transformation, notes, reports and exports are chained to the event before them with SHA-256. Re-verify every stored hash whenever you need to.</p></div>
    <ol class="chain" role="list" data-chain>${chain.map(([i, code, label], k) => `<li class="chain__block" data-chain-block><span class="chain__icon">${icon(i, { size: 18 })}</span><code class="chain__code">${code}</code><span class="chain__label">${label}</span>${k < chain.length - 1 ? '<span class="chain__link" aria-hidden="true"></span>' : ""}</li>`).join("")}</ol>
    <div class="bento">
      <article class="bento__card" data-reveal>${icon("refresh", { size: 20 })}<h3>Re-verify on demand</h3><p>One action re-reads every source, artifact, viewing copy and thumbnail, and re-chains the audit log from its genesis hash.</p></article>
      <article class="bento__card" data-reveal>${icon("shield", { size: 20 })}<h3>Tamper-evident, honestly</h3><p>The local chain detects edits. Export and retain the audit head independently to detect a full rewrite or deleted tail.</p></article>
      <article class="bento__card" data-reveal>${icon("note", { size: 20 })}<h3>Notes on the record</h3><p>Examiner observations join the same ledger, linked to the artifact they describe.</p></article>
    </div>
  </section>`;
}

function output() {
  const items = [
    ["reports", "Forensic case report", "ISO/IEC 27037 framing", "Sources, recovered artifacts, correlation and the tamper-evident audit ledger in one printable examination report."],
    ["scale", "Courtroom certificate", "Sec. 63 BSA · Sec. 65B IEA", "A certificate of digital evidence with source and artifact SHA-256 tables, ready to print and sign."],
    ["terminal", "Structured evidence record", "Machine-readable JSON", "Metadata, lineage, evidence and ledger sections for lab systems and independent verification."],
    ["package", "Hash-manifested package", "ZIP · SHA-256 manifest", "Recovered artifacts, manifest, report and README. Integrity is re-verified before anything is packaged."],
  ];
  return `<section class="s-section s-output" id="sec-output" aria-labelledby="out-h">
    <div class="s-head" data-reveal><p class="s-kicker">Court-ready output</p><h2 class="s-title" id="out-h">From recovered bytes to a record<br>a court can read.</h2></div>
    <div class="out-grid">${items.map(([i, t, tag, p]) => `<article class="out-card" data-reveal><span class="out-card__icon">${icon(i, { size: 22 })}</span><span class="out-card__tag">${tag}</span><h3>${t}</h3><p>${p}</p></article>`).join("")}</div>
  </section>`;
}

function compatibility() {
  const reg = state.registry || [];
  const rows = reg.length
    ? reg.map((r) => `<li class="compat__row" data-reveal><div class="compat__main"><strong>${esc(r.vendor)}</strong><span>${esc(r.model_scope)}</span></div><span class="compat__limit">${esc(r.known_limitations[0] || "")}</span>${badge(r.status)}</li>`).join("")
    : '<li class="compat__row"><span class="subtle">The compatibility registry is unavailable from this server.</span></li>';
  const counts = ["VALIDATED", "EXPERIMENTAL", "UNSUPPORTED"].map((s) => `${number(reg.filter((r) => r.status === s).length)} ${s.toLowerCase()}`).join(" · ");
  return `<section class="s-section s-compat" id="sec-compatibility" aria-labelledby="com-h">
    <div class="s-head" data-reveal><p class="s-kicker">Honest compatibility</p><h2 class="s-title" id="com-h">Validated means validated.</h2><p class="s-lede">Trace never claims vendor-wide support from a single tested file. Every format carries its exact scope and known limits.</p></div>
    <div class="compat" data-reveal>
      <div class="compat__head"><span class="live-dot" aria-hidden="true"></span><span>Live from this workstation’s registry · ${esc(counts)}</span></div>
      <ul class="compat__list" role="list">${rows}</ul>
      <a class="text-link compat__more" href="#registry"><span>See every limitation in the workspace</span>${icon("arrow", { size: 14 })}</a>
    </div>
  </section>`;
}

function local() {
  const s = state.session || {};
  const db = s.db_backend === "neon_postgres" ? "Neon PostgreSQL" : s.db_backend === "sqlite" ? "SQLite (local file)" : s.db_backend || "Unknown";
  const engineName = String(s.media_engine || "Unknown").replace(/\s+Copyright.*$/i, "");
  const specs = [
    ["Hashing", "SHA-256 for every source, artifact, viewing copy and audit record"],
    ["Source checks", "Source hash re-verified before and after every analysis"],
    ["Inputs", ".img .dd .raw .mp4 .avi .h264 .264 .dav .jpg .jpeg .mkv .ts .dat .hevc"],
    ["E01 images", "Convert with ewfexport; the Heimvision public corpus streams through Dissect"],
    ["Browser upload", "Up to 8 GiB — local path ingestion has no browser limit"],
    ["Raw inspection", "1–4,096 bytes per read, from the verified copy"],
    ["Carving bounds", "256 MiB per fragment · 2,000 candidates per scan"],
    ["Processing", "One worker per instance · up to four pending jobs per case"],
    ["Enhancement", "Deterministic FFmpeg filters · no generative AI bundled"],
    ["Frontend", "Native HTML, CSS and JavaScript modules · no build step"],
  ];
  return `<section class="s-section s-local" id="sec-local" aria-labelledby="loc-h">
    <div class="s-split s-split--top">
      <div class="s-copy" data-reveal>
        <p class="s-kicker">Local by design</p>
        <h2 class="s-title" id="loc-h">Evidence never leaves<br>this workstation.</h2>
        <p class="s-lede">Trace serves itself on 127.0.0.1. Every mutation needs a per-process session token, cross-origin requests are refused, and a strict Content-Security-Policy blocks third-party scripts, fonts and connections.</p>
        <ul class="s-list" role="list">
          <li>${icon("lock", { size: 16 })}Loopback-only host check</li>
          <li>${icon("key", { size: 16 })}Rotating session token, kept in memory</li>
          <li>${icon("cloud-off", { size: 16 })}No CDN, no telemetry, no cloud account</li>
        </ul>
      </div>
      <aside class="session-card" data-reveal aria-label="Live session">
        <div class="session-card__head"><span class="live-dot" aria-hidden="true"></span><strong>Live from this session</strong></div>
        <dl class="session-card__rows">
          <div><dt>Mode</dt><dd>${esc(s.mode || "Unknown")}</dd></div>
          <div><dt>Version</dt><dd class="mono">v${esc(s.version || "—")}</dd></div>
          <div><dt>Case database</dt><dd>${esc(db)}</dd></div>
          <div><dt>Media engine</dt><dd class="mono truncate" title="${esc(s.media_engine || "")}">${esc(engineName)}</dd></div>
          <div><dt>Real-vendor validation</dt><dd>${s.real_vendor_validation ? toneBadge("green", "Passed", { icon: "check", size: "sm" }) : toneBadge("yellow", "Gate not passed", { icon: "warning", size: "sm" })}</dd></div>
          <div><dt>Cases on this workstation</dt><dd class="tabular">${number(state.cases.length)}</dd></div>
        </dl>
      </aside>
    </div>
    <div class="specs" data-reveal>
      <h3 class="specs__title">Tech specs</h3>
      <dl class="specs__grid">${specs.map(([k, v]) => `<div class="specs__row"><dt>${k}</dt><dd>${v}</dd></div>`).join("")}</dl>
    </div>
  </section>`;
}

function vocabulary() {
  const words = [
    ["EXACT_RECOVERED", "The identified byte range was recovered exactly and decoded. It does not claim the whole recording survived."],
    ["PARTIAL_RECOVERED", "Only part of the stream validates. Decodable portions are kept; missing ranges are reported as gaps."],
    ["INFERRED", "Derived from surviving evidence rather than read directly — always labelled as inference."],
    ["ENHANCED_COPY", "A transformed viewing copy with its own hash. Never the original evidence."],
    ["UNRECOVERABLE", "Candidate bytes exist, but no decoder could validate them. They stay listed with diagnostics."],
    ["VALIDATED", "Tested against a documented corpus — and only within the stated model and firmware scope."],
    ["EXPERIMENTAL", "Works on an observed corpus; model, firmware or completeness remain unverified."],
    ["UNSUPPORTED", "No validated parser. A labelled export does not validate a recorder’s storage layout."],
  ];
  return `<section class="s-section s-vocab" id="sec-vocabulary" aria-labelledby="voc-h">
    <div class="s-head" data-reveal><p class="s-kicker">Status vocabulary</p><h2 class="s-title" id="voc-h">Eight words, used exactly.</h2><p class="s-lede">Status codes are load-bearing. The interface shows them the same way everywhere — always with an icon and a label, never colour alone.</p></div>
    <dl class="vocab">${words.map(([code, text]) => `<div class="vocab__item" data-reveal><dt>${badge(code)}<code class="vocab__code">${code}</code></dt><dd>${text}</dd></div>`).join("")}</dl>
  </section>`;
}

function closing() {
  return `<section class="s-section s-cta" aria-labelledby="cta-h">
    <div class="s-cta__card" data-reveal>
      <div class="s-cta__art" aria-hidden="true">${platter({ className: "platter--cta" })}</div>
      <p class="s-kicker">Ready when the evidence is</p>
      <h2 class="s-title" id="cta-h">Start with the evidence.</h2>
      <p class="s-lede">Create a case, import a raw image or media export, and let Trace show you exactly what survives.</p>
      <div class="s-hero__cta">${cta("lg")}</div>
    </div>
  </section>`;
}

function footer() {
  const version = state.session?.version ? `v${state.session.version}` : "";
  return `<footer class="site-footer">
    <div class="site-footer__inner">
      <div class="site-footer__brand"><a class="brand brand--site" href="#home" aria-label="Trace — home"><span class="brand__mark" aria-hidden="true">t<span>·</span></span><span class="brand__name">trace</span></a><p>DVR &amp; NVR evidence recovery.<br>Local, read-only and traceable.</p></div>
      <nav class="site-footer__col" aria-label="Workspace"><h3>Workspace</h3><a href="#overview">Overview</a><a href="#sources">Evidence sources</a><a href="#evidence">Recovered evidence</a><a href="#reports">Reports &amp; exports</a><a href="#registry">Compatibility</a></nav>
      <nav class="site-footer__col" aria-label="Product"><h3>Product</h3>${SECTIONS.map(([id, label]) => `<a href="#home/${id}">${label}</a>`).join("")}</nav>
      <div class="site-footer__col"><h3>Project</h3><p>SIH26150 · Team RAWSEC</p><p>Team ID S047</p><p>Blockchain &amp; Cybersecurity</p>${version ? `<p class="mono">${esc(version)}</p>` : ""}</div>
    </div>
    <p class="site-footer__legal">The controlled demo is generated from FFmpeg test patterns, not real surveillance footage, and does not validate any recorder vendor. Trace is a local workstation tool; it is not an OS-level media sandbox or a multi-user network service.</p>
  </footer>`;
}

export function render() {
  return `<div class="site-page">${nav()}<main class="site-main" id="site-main" tabindex="-1">${hero()}${principles()}${engine()}${separation()}${custody()}${output()}${compatibility()}${local()}${vocabulary()}${closing()}</main>${footer()}</div>`;
}

// ------------------------------------------------------------ behaviour ----
function scrollToSection(root, section, smooth = true) {
  const target = section ? root.querySelector(`#sec-${CSS.escape(section)}`) : null;
  if (target) target.scrollIntoView({ behavior: smooth && !prefersReducedMotion() ? "smooth" : "auto", block: "start" });
  else window.scrollTo({ top: 0, behavior: "auto" });
}

export function onSection(root, ctx) {
  scrollToSection(root, ctx.route.section);
  setMenu(root, false);
}

function setMenu(root, open) {
  const menu = $("#site-menu", root);
  const toggle = $(".site-nav__menu", root);
  if (!menu || !toggle) return;
  menu.hidden = !open;
  toggle.setAttribute("aria-expanded", String(open));
  toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
}

export function mount(root, ctx) {
  const cleanups = [];
  const reduce = prefersReducedMotion();
  const navEl = $("[data-site-nav]", root);

  // Hero entrance: headline lines rise out of a soft blur, then supporting copy.
  animate($$("[data-hero-line]", root), { opacity: [0, 1], y: [30, 0], filter: ["blur(8px)", "blur(0px)"] }, { duration: 0.9, delay: stagger(0.12), ease: [0.16, 1, 0.3, 1] });
  animate($$("[data-hero-fade]", root), { opacity: [0, 1], y: [14, 0] }, { duration: 0.7, delay: stagger(0.08, { startDelay: 0.25 }), ease: [0.16, 1, 0.3, 1] });
  animate($("[data-hero-intro]", root), { opacity: [0, 1], scale: [0.94, 1] }, { duration: 1.2, delay: 0.2, ease: [0.16, 1, 0.3, 1] });

  // Scroll-linked hero stage: gently recede as the page scrolls on.
  const stage = $("[data-hero-stage]", root);
  if (stage && !reduce) cleanups.push(scroll(animate(stage, { y: [0, 80], scale: [1, 0.92], opacity: [1, 0.35] }, { ease: "linear" }), { target: $(".s-hero", root), offset: ["start start", "end start"] }));

  // Reveal-on-scroll for every [data-reveal] block.
  const reveals = $$("[data-reveal]", root);
  if (!reduce) reveals.forEach((el) => { el.style.opacity = "0"; });
  cleanups.push(inView(reveals, (el) => {
    animate(el, { opacity: [0, 1], y: [26, 0] }, { duration: 0.75, ease: [0.16, 1, 0.3, 1] });
  }, { margin: "0px 0px -12% 0px" }));

  // Three tiers: the sticky visual follows whichever step is centred.
  const vis = $(".tier-vis", root);
  const tiers = $$(".tier", root);
  cleanups.push(inView(tiers, (el) => {
    tiers.forEach((t) => t.classList.toggle("is-active", t === el));
    if (vis) vis.dataset.step = el.dataset.tier;
    return () => {};
  }, { margin: "-45% 0px -45% 0px" }));

  // Chain of custody blocks draw in sequence.
  const chain = $("[data-chain]", root);
  if (chain) {
    const blocks = $$("[data-chain-block]", chain);
    if (!reduce) blocks.forEach((b) => { b.style.opacity = "0"; });
    cleanups.push(inView(chain, () => {
      chain.classList.add("is-drawn");
      animate(blocks, { opacity: [0, 1], y: [18, 0], scale: [0.96, 1] }, { duration: 0.6, delay: stagger(0.11), ease: [0.16, 1, 0.3, 1] });
    }, { margin: "0px 0px -15% 0px" }));
  }

  // Active section highlighting in the nav.
  const links = $$("[data-section-link]", root);
  const sections = SECTIONS.map(([id]) => root.querySelector(`#sec-${id}`)).filter(Boolean);
  cleanups.push(inView(sections, (el) => {
    const id = el.id.replace(/^sec-/, "");
    links.forEach((a) => a.classList.toggle("is-current", a.dataset.sectionLink === id));
    return () => links.forEach((a) => { if (a.dataset.sectionLink === id) a.classList.remove("is-current"); });
  }, { margin: "-40% 0px -55% 0px" }));

  // Glass nav gains a hairline once the page scrolls.
  const onScroll = () => navEl?.classList.toggle("is-scrolled", window.scrollY > 8);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  cleanups.push(() => window.removeEventListener("scroll", onScroll));

  const onKey = (event) => { if (event.key === "Escape") setMenu(root, false); };
  document.addEventListener("keydown", onKey);
  cleanups.push(() => document.removeEventListener("keydown", onKey));

  if (ctx.route.section) requestAnimationFrame(() => scrollToSection(root, ctx.route.section, false));
  else window.scrollTo({ top: 0, behavior: "auto" });

  return () => cleanups.forEach((fn) => { try { typeof fn === "function" && fn(); } catch { /* ignore */ } });
}

defineActions({
  "site-menu": ({ element }) => {
    const root = element.closest(".site-page");
    const menu = $("#site-menu", root);
    setMenu(root, menu.hidden);
  },
});

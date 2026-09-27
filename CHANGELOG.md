# Changelog — Trace Frontend Rebuild

All notable changes to the Trace DVR/NVR Forensic Workspace frontend are documented in this file.

## [2.0.0] - 2026-09-27

### Summary
Complete frontend rebuild of the Trace DVR/NVR Forensic Recovery Workspace from a light, monolithic UI into a polished, dark, SOC/EDR-grade forensic dashboard and Apple-style product website, strictly obeying the zero-build, no-CDN, self-hosted architectural constraints.

---

### Key Additions & Enhancements

#### 1. Architecture & Design System (Zero-Build, Self-Hosted ES Modules)
- **Design Tokens (`web/styles/tokens.css`)**: Dark-only palette (`#0A0B0F` canvas, `#16171E` surface, `#1C1D26` raised, warm amber accent `#D6853D` and status tones). Every color token meets WCAG AA contrast standards.
- **Self-Hosted Typography**: Inter Variable font (`Inter-Variable.woff2`) self-hosted locally under `web/assets/fonts/`. System monospace stack used for cryptographic hashes, offsets, and JSON.
- **Vendored Motion Library**: Standalone Motion library vendored locally at `web/assets/vendor/motion/motion.js` without any external network dependency. Fully respects `prefers-reduced-motion`.
- **Modular Stylesheet Hierarchy**: Split into `tokens.css`, `base.css`, `layout.css`, `components.css`, `pages.css`, and `site.css`. `web/styles.css` maintained as a master bundle.
- **Componentized JavaScript**: Modularized into 48 clean ES modules under `web/js/components/`, `web/js/modals/`, and `web/js/pages/`. `web/app.js` preserved as an entry shim passing `node --check`.

#### 2. Apple-Grade Product Landing Website (`#home`)
- **Interactive Storytelling**: Comprehensive product story explaining the problem statement (SIH26150), Three-Tier Recovery Engine, Evidence vs. Derivative separation, and Section 63 BSA / Section 65B IEA courtroom deliverables.
- **Live Workstation Telemetry**: Dynamic session card pulling live facts (FFmpeg version, SQLite/Neon backend, real vendor validation gate status, case count) and compatibility registry counts.
- **Interactive Tier Visualization**: SVG sector map demonstrating deterministic structural recovery, verified fragment reconstruction seams, and explicit gap reporting.
- **Seamless Transition**: One-click jump to `#overview` to access the active forensic workspace.

#### 3. Command Palette (`Ctrl+K` / `⌘+K`)
- **Spotlight Navigation**: Global quick-switcher modal allowing instant jumping across all 8 routes (`#overview`, `#sources`, `#evidence`, `#timeline`, `#recovery`, `#integrity`, `#reports`, `#registry`), switching active cases, and triggering rapid actions (New case, Import, USB Ingest, Run demo).

#### 4. Forensic Evidence & Provenance Rigor
- **Strict Evidence vs. Derivative Separation**: Any artifact with `kind === "DERIVATIVE"` or `status === "ENHANCED_COPY"` renders with a dashed violet border, a persistent `✨ Derivative` tag, and a mandatory viewing copy banner.
- **Exact Vocabulary Mapping**: All 18 domain statuses and decisions mapped through `web/js/statusMap.js` ensuring consistent badge tone, icon, and label everywhere.
- **No Fabricated Data**: If fields are absent, explicit empty or unassessed states are shown. Metrics are computed client-side from actual verified records.

#### 5. Page-by-Page Workspace Upgrades
- **Overview (`#overview`)**: Dynamic hero banner, 4 KPI cards with trend pills, SVG line chart for cumulative recovery progress over time, and status/quality outcome distribution bar chart.
- **Evidence Sources (`#sources`)**: Multi-column source cards with partition tables, bad sector notices, copyable SHA-256 hashes, hex inspector modal, and parent E01 segmented image lineage.
- **Recovered Evidence (`#evidence`)**: Responsive card grid with FQI meter bars, multi-channel and status filters, multi-select join workflow, and full-featured Artifact Viewer modal with video playback, container repair, and enhancement copy triggers.
- **Timeline & Notes (`#timeline`)**: Multi-lane per-channel timeline with substream dashed clips and secondary gap coverage notice. Examiner notes feed with composer.
- **Recovery Engine (`#recovery`)**: Real-time job queue with animated progress bars, cancellable jobs, fragment adjacency edge decisions table, and plain-language redundancy findings.
- **Chain of Custody (`#integrity`)**: On-demand SHA-256 hash re-verification, audit log event ledger with expandable JSON payloads, and residual proof bundle verification.
- **Reports & Exports (`#reports`)**: 6 live metric pills, 3-tab dossier viewer (Forensic Case Report, Sec. 63 BSA Certificate, Structured JSON with jump chips), deliverables builder, and paginated recording index browser.
- **Compatibility (`#registry`)**: Radical honesty regarding tested scope for Dahua, Heimvision, Hikvision, and MP4/AVI generic containers, with known limitations and "Run controlled demo" trigger.

---

### Verification & Quality Gates
- **100% Passing Automated Tests**: `python -m pytest -q` passed 55/55 backend tests.
- **Zero JS Syntax Errors**: `node --check` passed across all 48 JavaScript files.
- **Zero CSP Violations**: Strict `default-src 'self'` Content Security Policy confirmed with zero violations in headless Chrome DevTools Protocol logs.
- **Air-Gap Validated**: 100% of network requests confirmed to be same-origin or data/blob URIs. Zero external network calls.
- **Responsive Across Breakpoints**: Verified at 375px (mobile), 768px (tablet), 1024px (laptop), 1440px (desktop), and 1920px (wide).

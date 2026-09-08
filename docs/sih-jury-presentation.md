# Trace · SIH Jury Demonstration Battle Script
**Problem Statement SIH26150 (NTRO — DVR/NVR Forensic Recovery Platform)**

---

## 1. Executive Summary for Judges (30 Seconds)

> *"Good afternoon, respected members of the Jury. Modern CCTV and DVR recovery fails because conventional forensic tools rely on standard video containers (`.mp4`, `.avi`), while surveillance systems use raw, proprietary, or unfinalized multiplexed streams. When power fails, filesystems corrupt, or drives get damaged, commercial tools fail or invent missing pixels with generative AI—which is inadmissible in an Indian court of law.*
>
> *We built **Trace**: a vendor-agnostic DVR/NVR forensic recovery platform engineered directly from the NTRO Master Plan. It operates from the physical storage layer up, maintains strict cryptographic chain of custody, correlates surviving sub-streams without hallucinating pixels, and automatically generates legal certificates under **Section 63 of the Bharatiya Sakshya Adhiniyam (BSA), 2023**."*

---

## 2. Live Demo Script (4 Minutes)

### Minute 1: Real 150 GB E01 Forensic Image Ingestion & 806-File Index
1. Open **Evidence Sources**:
   - Point out the **HeimVision K9604-W** forensic disk image.
   - Show that Trace reads the segmented E01 (`HeimVision K9604-W.E01` to `.E03`) **directly through Dissect without expanding 150 GB of raw disk**.
   - Show the **Logical Verification Badge**:
     - MD5: `4895ea6d10b08c29fb1bb03591adc7b2` (**Exact match** with NIST CFReDS ground truth).
     - SHA-1: `06f48890961187979ed4142ceab8a7144bd4dfea` (**Exact match**).
     - Full 150,039,945,216 bytes verified.
   - Click **"Browse 806 Surveillance Files on E01 Disk"**:
     - Show the continuous **24.04-hour surveillance timeline** (2021-08-04 02:40 UTC to 2021-08-05 02:43 UTC).
     - Filter files in real-time and demonstrate **one-click on-demand extraction** of any DAT file from the E01 image via Dissect.

### Minute 2: Multi-Vendor Demuxing, Frame Decoding & Audio Companion Recovery
1. Navigate to **Recovered Evidence**:
   - Show the 12 extracted camera streams across **all 4 cameras**.
   - Show that **13,186 real H.265 frames** were decoded at 1080p.
   - Click **Review Provenance** on a clip:
     - Show the exact byte ranges on disk where each NALU was carved.
     - Play the **Synchronized 16-bit 8000Hz PCM Audio Companion** demultiplexed from the proprietary DAT container.
     - Click **"Download Audio (WAV)"** to show court-ready audio artifact delivery.
   - Show the second vendor adapter: **Dahua DHAV** (`0xfd` keyframes, `0xfc` P-frames, packed 32-bit BCD UTC timestamps).

### Minute 3: Multi-Representation Correlation & Forensic Quality Scoring (The Game Changers)
1. Open **Timeline & Notes**:
   - Scroll to **Multi-Representation Sub-Stream Correlation**:
   - Point out the **Gap Coverage Analysis**:
     - *"When primary 1080p footage has a sector drop or power-loss gap (e.g. 5.0 seconds missing), Trace searches the evidence for secondary representations. It proves that the 480p substream covers that exact interval."*
     - **The Evidentiary Punchline**: *"Unlike competitors who claim to upscale or hallucinate missing 1080p pixels, Trace explicitly logs: 'Surviving substream provides visual timeline context; high-resolution pixels are not synthesized.' This protects evidence admissibility."*
2. In **Recovered Evidence**:
   - Show the **Forensic Quality Index (FQI)** badge (`PRIME 83.5`) calculated via Laplacian blur variance, contrast dynamic range, and DCT blockiness.
   - Select **"Sort: Visual Quality (FQI)"** to demonstrate how an investigator can immediately pull the sharpest keyframes for suspect facial recognition or vehicle license plate identification.

### Minute 4: Courtroom Admissibility & In-App Dossier Center (Section 63 BSA / 65B IEA)
1. Open **Reports & Exports**:
   - Show the **Interactive Courtroom Document Dossier Center**:
     - Metric Strip: 150 GB Verified, 13,186 Frames, 12 Audio Streams, 100% PRIME FQI, Valid Audit Chain.
     - **Tab 1: Forensic Case Report (ISO/IEC 27037)**: Live printable digital laboratory examination report with disk extent tables, FQI scoring, and chain-of-custody audit logs.
     - **Tab 2: Courtroom Certificate (Sec. 63 BSA / 65B IEA)**: Statutory legal admissibility certificate with official declaration clauses, cryptographic hash manifest, and examiner signature block. Click **"Print Certificate"** for instant court filing.
     - **Tab 3: Structured Evidence Record (JSON)**: Court-ready RFC 8259 hierarchical JSON rendered in an in-app dark terminal viewer with syntax highlighting (emerald keys, amber strings, blue numbers), quick-jump section badges (`#storage_lineage`, `#video_evidence`, `#audit_ledger`), and one-click copy to clipboard.
   - Click **"Download JSON"** / **"Save .json"** for automated ingestion into police/court forensics databases (ICJS / CCTNS compliant).
2. Click **"Verify all hashes"** in Chain of Custody:
   - Live recalculation of all SHA-256 hashes verifying zero file tampering.

---

## 3. Defense Against Tough Jury Questions

| Jury Question | Winning Answer |
|---|---|
| **"Why not use AI super-resolution to make blurry CCTV clear?"** | *"Under Section 63 BSA and international ISO/IEC 27037 standards, generative AI creates synthetic pixels that do not exist in the physical scene. A defense attorney can easily get AI-hallucinated footage dismissed as fabrication. Trace provides deterministic enhancement (CLAHE, unsharp masking, de-noising) labeled strictly as `ENHANCED_COPY` with full transformation provenance."* |
| **"How does Trace handle bad sectors and disk read errors?"** | *"Trace enforces a strict read-only boundary with verified-prefix resume. It maps unallocated regions and bounded partition extents, isolates corrupted frame boundaries with automatic resync markers, and reports partial artifacts rather than silently dropping evidence or substituting fake zero bytes."* |
| **"Can't someone just modify the SQLite database?"** | *"Trace uses a forward SHA-256 hash-chained audit log where every event includes the cryptographic digest of the preceding event. Any row modification or deletion breaks the hash chain, triggering an immediate audit failure warning in the UI and report."* |

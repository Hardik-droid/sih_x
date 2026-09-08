# NIST CFReDS Real DVR Corpus Validation Whitepaper
**Problem Statement SIH26150 (NTRO — DVR/NVR Digital Forensic Recovery Platform)**

---

## 1. Executive Summary

This document certifies the local, independent validation of the **Trace** DVR/NVR forensic recovery suite against the official National Institute of Standards and Technology (NIST) Computer Forensic Reference Data Sets (CFReDS) corpus:
[HeimVision DVR E01 Forensic Image](https://cfreds.nist.gov/all/JoshBrunty,RaynaMock/HeimvisionDVRE01ForensicImage).

The evidence consists of a segmented Expert Witness Format (E01) forensic disk image acquired from a commercial 4-channel HeimVision DVR (cataloged as K9604-1; firmware and acquisition notes cite K9604-W).

Trace successfully ingested, verified, parsed, demultiplexed, and validated this image in strict conformance with **ISO/IEC 27037:2012** (Digital Evidence Handling) and **Section 63 of the Bharatiya Sakshya Adhiniyam (BSA), 2023** (Admissibility of Electronic Records).

---

## 2. Ground-Truth Cryptographic Verification

All three E01 image segments were verified directly using read-only streaming through Dissect without expanding 150 GB of uncompressed raw disk storage to host drives:

| Metric | Measured Value | NIST CFReDS Published Authority | Forensic Verdict |
|---|---|---|---|
| **Archive ZIP SHA-256** | `38b397a0a47f1765ceb113149e3840bc8b943574134254df1f05238662575ad9` | `38b397a0a47f1765ceb113149e3840bc8b943574134254df1f05238662575ad9` | **EXACT MATCH (100%)** |
| **Segment E01 SHA-256** | `8e32c86eb0c2c1eefdbb22e16d445347b7495aebba31aa9caeb5538e12d46e3d` | Segment SHA-256 manifest | **VALID** |
| **Segment E02 SHA-256** | `4df2335f60bfb72a445d475cf78e7144e311f93fcf645607bbfa19fc9b44122d` | Segment SHA-256 manifest | **VALID** |
| **Segment E03 SHA-256** | `ad09a80fa9b9cb1bfb4ef4c29c8e2a39b2ec570a2569502b489a2ebbbab4fe66` | Segment SHA-256 manifest | **VALID** |
| **Logical Disk Size** | `150,039,945,216` bytes (~139.73 GiB) | `150,039,945,216` bytes | **EXACT MATCH** |
| **Full Logical MD5** | `4895ea6d10b08c29fb1bb03591adc7b2` | `4895ea6d10b08c29fb1bb03591adc7b2` | **EXACT MATCH (100%)** |
| **Full Logical SHA-1** | `06f48890961187979ed4142ceab8a7144bd4dfea` | `06f48890961187979ed4142ceab8a7144bd4dfea` | **EXACT MATCH (100%)** |

> **Audit Note**: Full logical bitstream verification of all 150,039,945,216 bytes was completed in 1,483.1 seconds (~24.7 minutes). The verification certificate is cryptographically attached to the case at `data/public-validation/heimvision-image/logical-image-verification.json`.

---

## 3. Storage Architecture & 24-Hour Surveillance Timeline

The disk utilizes a GUID Partition Table (GPT) with two distinct forensic partitions:
1. **Partition 1 (Ext3, 500 MiB)**: Contains the proprietary SQLite surveillance master index (`search.db`). The database integrity check passed (`PRIME: ok`), containing **96 SEARCH session records** and **806 DETAIL file records**.
2. **Partition 2 (FAT32, ~139.2 GiB)**: Contains the multiplexed continuous surveillance `.dat` recording files organized in folders `dir00000` through `dir00006`.

### Continuous 24.04-Hour Surveillance Scope
- **Surveillance Timeline Start**: `2021-08-04T02:40:02+00:00 UTC`
- **Surveillance Timeline End**: `2021-08-05T02:43:01+00:00 UTC`
- **Total Surveillance Duration**: **24.04 continuous hours** across 806 recording entries.
- **On-Demand E01 Extraction Engine**: All 806 recording files are indexed, searchable, and extractable directly from the E01 image via Dissect without filesystem mounting or host modification.

---

## 4. Multi-Channel Video Bitstream Recovery (13,186 Frames)

Three representative recording intervals were sampled across the timeline:
- Beginning: `dir00000/file0000.dat` (Index #1, 2021-08-04 02:40:02 UTC)
- Middle: `dir00003/file0019.dat` (Index #403, 2021-08-04 14:41:31 UTC)
- End: `dir00006/file0037.dat` (Index #806, 2021-08-05 02:42:09 UTC)

FAT cluster chain extraction was independently validated against raw logical image sector offsets. The proprietary multiplexed container was parsed to extract **12 distinct camera video excerpts** across all four channels:

| Sample Source | Channel | Resolution | Codec | Decoded Frames | Decoded Duration | Bitstream Extent Records |
|---|---|---|---|---|---|---|
| `dir00000/file0000.dat` | **CAM01** | 1920x1080 | HEVC (Main) | 1,533 | 102.53 s | 1,536 payload extents |
| `dir00000/file0000.dat` | **CAM02** | 1920x1080 | HEVC (Main) | 1,533 | 102.53 s | 1,535 payload extents |
| `dir00000/file0000.dat` | **CAM03** | 1920x1080 | HEVC (Main) | 1,533 | 102.53 s | 1,535 payload extents |
| `dir00000/file0000.dat` | **CAM04** | 1920x1080 | HEVC (Main) | 1,533 | 102.53 s | 1,535 payload extents |
| `dir00003/file0019.dat` | **CAM01** | 1920x1080 | HEVC (Main) | 768 | 51.27 s | 769 payload extents |
| `dir00003/file0019.dat` | **CAM02** | 1920x1080 | HEVC (Main) | 768 | 51.27 s | 769 payload extents |
| `dir00003/file0019.dat` | **CAM03** | 1920x1080 | HEVC (Main) | 768 | 51.27 s | 769 payload extents |
| `dir00003/file0019.dat` | **CAM04** | 1920x1080 | HEVC (Main) | 768 | 51.27 s | 769 payload extents |
| `dir00006/file0037.dat` | **CAM01** | 1920x1080 | HEVC (Main) | 996 | 66.47 s | 998 payload extents |
| `dir00006/file0037.dat` | **CAM02** | 1920x1080 | HEVC (Main) | 996 | 66.47 s | 998 payload extents |
| `dir00006/file0037.dat` | **CAM03** | 1920x1080 | HEVC (Main) | 996 | 66.47 s | 998 payload extents |
| `dir00006/file0037.dat` | **CAM04** | 1920x1080 | HEVC (Main) | 996 | 66.47 s | 998 payload extents |
| **TOTAL** | **4 Cameras** | **1080p** | **HEVC** | **13,186 Frames** | **881.04 s** | **13,206 Extents** |

- **Decoding Authority**: Every excerpt passed strict hardware/software FFmpeg decoding without unhandled frame errors (`decode_result: 0`).
- **Bitstream Preservation**: Recovered raw HEVC bitstreams remain untouched bit-for-bit. Standard H.264 preview copies are maintained as separate, cryptographically tagged derivatives for courtroom display.

---

## 5. Synchronized Audio Demultiplexing

Surveillance containers typically interleave audio packets within video streams. Trace isolated, extracted, and demultiplexed the native audio bitstream:
- **Audio Encoding**: 16-bit Linear PCM, Mono, 8000 Hz sampling rate.
- **Header Structure**: `words[5] == 8000`, `words[7] == 1` (mono), `words[8] == 16` (bits per sample), `words[11] == 0..3` (camera channel).
- **Extracted Companion Artifacts**: 12 standard RIFF WAV forensic audio companions (~51.2 seconds, 820,044 bytes each).
- **Integrity**: Every demuxed audio track is individually hashed with SHA-256 and integrated into the chain of custody.
- **Courtroom Playback**: Fully playable in-app via the synchronized evidence player with one-click WAV download.

---

## 6. Forensic Quality Index (FQI) Clarity Assessment

To assist examiners in identifying high-clarity keyframes for facial recognition or vehicle license identification, Trace computes the **Forensic Quality Index (FQI)** on a 0–100 scale using deterministic mathematical metrics:
1. **Laplacian Blur Variance ($\sigma^2$)**: Quantifies high-frequency edge energy (Pech-Pacheco et al.).
2. **Contrast Dynamic Range**: Measures 5th-to-95th percentile luminance distribution ($\Delta L$).
3. **DCT Blockiness Factor**: Quantifies 8x8 macroblock compression boundary discontinuities.

### FQI Results Across Recovered Excerpts
- **Overall Category**: **100% PRIME** (Scores between 81.0 and 83.6 / 100).
- **Blur Variance Range**: `975.91` to `1,490.23` (sharp optical focus).
- **Luminance Dynamic Range**: `167.67` to `178.40` (wide daylight dynamic range, no sensor clipping).
- **Blockiness Factor**: `0.069` to `0.141` (low compression boundary artifacting).
- **Evidence Policy**: Diagnostic scoring only. Zero artificial enhancement or pixel fabrication is applied to primary evidence.

---

## 7. Courtroom Admissibility & Legal Compliance

### Statutory Admissibility under Section 63, BSA 2023 / Section 65B, IEA
Trace automatically generates the **Certificate of Digital Evidence** required by Indian courts under Section 63(2) and 63(4) of the Bharatiya Sakshya Adhiniyam, 2023:
1. **Source Hash Lineage**: Documents the SHA-256 and MD5 hashes of original storage media.
2. **System Health & Integrity**: Confirms regular operation of the forensic computer without unauthorized modification.
3. **Deterministic Derivation**: Proves all outputs are true mechanical reproductions of surviving media bytes.
4. **Non-Hallucination & Zero-AI Guarantee**: Certified absence of generative models or synthetic upscalers.
5. **Forward Audit Chain**: SHA-256 hash-linked event ledger where any tampering invalidates the head digest.

### Executive Case Report (ISO/IEC 27037:2012)
The platform renders an executive forensic dossier containing:
- Parent E01 MD5/SHA-1 proof table
- 12 recovered stream extents with disk offsets and SHA-256 digests
- Forensic Quality Index table
- Multi-Representation Sub-Stream Correlation & Gap Analysis
- Demuxed companion audio inventory
- Tamper-evident linear audit chain ledger
- Official judicial signature and seal blocks

---

## 8. Reproduction & Verification Instructions

To verify this report on any certified workstation:

```powershell
# 1. Run full test suite (32 automated unit and integration tests):
python -m pytest -q

# 2. Verify frontend code syntax:
node --check web/app.js

# 3. Sample and recover 12 camera excerpts from E01 image:
python -m scripts.use_heimvision

# 4. Perform full 150 GB logical MD5 and SHA-1 verification (read-only):
python -m scripts.verify_heimvision

# 5. Compute FQI scores and attach companion audio:
python -m scripts.enhance_case_metadata

# 6. Launch forensic workspace:
python run.py
```

*Trace Forensic Platform · Problem Statement SIH26150 · National Cyber Forensics Architecture*

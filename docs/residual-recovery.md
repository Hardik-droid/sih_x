# Residual recovery: deletion evidence, overwrite analysis and verifiable proof bundles

Implements the DVR/NVR **deleted & residual-video recovery** prompt as an extension of
Trace's existing acquisition, discovery, validation, hashing, ledger and reporting
architecture. Nothing already working was changed: all behavior is additive.

## Research foundation (verified citations)

- Jinhee Yoon, Sungjae Hwang. *Forensic analysis of video data deletion and recovery in
  Honeywell surveillance file system.* DFRWS USA 2026 (accepted). arXiv:2605.07430,
  DOI 10.48550/arXiv.2605.07430. Analyzes an undocumented proprietary DVR file system and
  three deletion mechanisms (formatting-based deletion, data expiration, overwrite),
  demonstrating when video remains recoverable after each. **This is the previously
  identified 2026 DVR/NVR research**, re-verified against arXiv before citing; the device
  family used for circular-retention labeling is drawn from it.
- Leila Rzayeva et al. *Forensic Video Recovery from Multi-Channel Analog DVR Systems:
  Channel Demultiplexing and Temporal Reconstruction from Interleaved DHAV Streams.*
  Information 17(5):493, 2026 (MDPI). Basis for the existing DHAV adapter's approach
  (channel demultiplexing and temporal reconstruction from interleaved streams).
- Simson L. Garfinkel. *Carving contiguous and fragmented files with fast object
  validation.* Digital Investigation 4(S):S2–S12, 2007. Foundational basis for signature
  carving and its limits; carving alone cannot establish deletion.

Distinctions (per the prompt): Yoon & Hwang and Rzayeva et al. are peer-reviewed/accepted
conference and journal research; the DHAV container layout is additionally documented in
vendor community documentation, which is treated as vendor documentation, not peer review.
**No other bibliographic details are claimed.** The SIH master plan referenced a 2026
DVR/NVR paper without bibliographic details; this implementation verified the candidate
against arXiv and only cites it with checked metadata.

## Architecture

```text
            ┌────────────────────────────────────────────────────────────┐
            │                     Evidence image (read-only)             │
            └───────────────┬────────────────────────────────────────────┘
                            │ acquisition + SHA-256 (unchanged)
            ┌───────────────▼───────────────┐
            │  discovery (unchanged)        │  MP4/AVI/JPEG/H.264 carving,
            │  core/recovery.discover       │  TRACEIDX1 index, DHAV, HeimVision
            └───────────────┬───────────────┘
                            │ candidate fragments + findings
            ┌───────────────▼───────────────────────────────────────┐
            │  residual layer (new, core/residual.py)               │
            │                                                       │
            │  derive_fs_states      surviving validated index?    │
            │                        └─ ORPHANED marking only      │
            │  deletion_evidence     six conservative levels       │
            │  analyze_overwrite     mechanism label + per-region  │
            │                        recovered/missing/overwritten │
            │  analyze_gaps          timeline gaps, never filled   │
            │  build_case_proof_…    SHA-256-bound JSON bundle     │
            └───────────────┬───────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────────────┐
        ▼                   ▼                           ▼
  store("residual")   source record fields      /api/cases/{id}/residual
  (audited ledger)    (deletion_evidence,       /api/cases/{id}/proof-bundle
                       overwrite_analysis)       /api/sources/{id}/proof-bundle/verify
                                                 scripts/residual_cli.py
```

The residual layer is a **classifier over adapter inputs**. Filesystem/device adapters
(synthetic index today; real DVR filesystems remain experimental) attach
`metadata_marks`, `deleted`, `recording_identifier`, `recording_extent`,
`overwritten_ranges` and `allocation_state` to candidate fragments. The classifier never
invents any of these and never mutates evidence.

## Deletion-evidence engine

Per the prompt, separate levels are implemented and no level is ever inferred from
carved location alone:

| Level | Requires |
|---|---|
| `DELETION_CONFIRMED_BY_METADATA` | Surviving metadata explicitly marks the recording deleted/unallocated (e.g. index `deleted` flag). |
| `DELETION_CORROBORATED` | A structurally intact, validated recording index survives, references at least one recording, and does not reference the recovered range. |
| `RESIDUAL_CONTENT_RECOVERED` | Video decoded; missing/overwritten regions present; deletion state not establishable. |
| `CONTENT_RECOVERED_ONLY` | Video decoded; no deletion or overwrite evidence either way. |
| `DELETION_UNSUPPORTED` | An examiner-supplied deletion claim exists but no metadata substantiates it. |
| `UNRECOVERABLE` | No frame decoded. |

Precedence: metadata confirmation > explicit claim testing (unsupported) > corroboration >
residual > content-only. The carved-only fallacy — "found in unallocated space, therefore
deleted" — is structurally impossible: location never enters the classification.

## Overwrite and gap analysis

- Mechanism labels: `FILE_DELETION` (validated recording index survives),
  `CIRCULAR_RECORDING` (device family documented in Yoon & Hwang, DFRWS USA 2026 —
  labeled with an explicit basis string, never claimed as a per-image fact),
  `UNKNOWN` otherwise.
- Per region: physical offsets and extents, allocation state (only when an adapter
  reports it), overwritten/partially overwritten ranges, recovered byte ranges, missing
  byte ranges (computed only when the recording extent is proven by surviving index
  metadata), missing/overlapped-by relationships, reconstruction confidence
  (HIGH/MEDIUM/LOW with rationale), SHA-256 of recovered artifacts.
- Timeline gaps per channel are reported (`TIMELINE_GAP_NOT_FILLED`); no bytes or frames
  are ever invented to fill them.

## Machine-verifiable proof bundle

`TRACE-RESIDUAL-PROOF-BUNDLE-V1` binds the analysis to evidence:

- source identity: name, SHA-256, capacity, vendor/model/firmware;
- artifact hashes (SHA-256) and every recovered byte range;
- deletion-evidence classifications with metadata bases;
- overwrite mechanism (with basis) and per-region state;
- a `payload_sha256` over the canonical JSON of the whole bundle (verify recomputes it).

Independent verification (`verify_proof_bundle`): recompute the payload hash; re-hash the
original image; re-read every claimed byte range from it; re-hash recovered artifact
files. A third party can therefore verify all claims from the original disk image alone.
Per-source bundles are aggregated in a case bundle (`TRACE-RESIDUAL-CASE-BUNDLE-V1`).

## Validation matrix (synthetic fixtures, CI)

`python -m scripts.corpus --residual` generates `residual_*.img` fixtures with embedded
ground truth; `tests/test_residual.py` covers each prompt scenario:

| Fixture | Scenario | Expected classification |
|---|---|---|
| `residual_deleted_confirmed.img` | normal deletion (flagged) + continued recording | flagged recording → CONFIRMED_BY_METADATA; live recording → CONTENT_RECOVERED_ONLY |
| `residual_continued_recording.img` | deletion then continued recording, intact live index | older unreferenced bytes → CORROBORATED |
| `residual_partial_overwrite.img` | last 40% rewritten with zeros | RESIDUAL_CONTENT_RECOVERED, MEDIUM confidence, missing ranges reported |
| `residual_heavy_overwrite.img` | only first 20% original | RESIDUAL_CONTENT_RECOVERED, LOW confidence |
| `residual_fragmented_recording.img` | two chunks + interior hole, extent declared | grouped recording, hole reported as MISSING_OR_OVERWRITTEN |
| `residual_corrupted_index.img` | index CRC destroyed | carving recovers content → CONTENT_RECOVERED_ONLY; INVALID finding reported |
| `residual_fs_metadata_removed.img` | index region zeroed | CONTENT_RECOVERED_ONLY; mechanism UNKNOWN |
| `residual_circular_reuse.img` | newer recording overwrites flagged-deleted tail | CIRCULAR_RECORDING label; overlap reported |

Bundle tampering (any payload edit), wrong-image verification and claim-without-metadata
paths are all covered by tests that must fail closed.

## Real-DVR validation procedure (gate, not yet executed)

1. Obtain a controlled recorder image with known ground truth **and** the exact
   model/firmware (the `real_dvr_gate` stays `BLOCKED` until then).
2. Acquire read-only (hardware write blocker), record the image SHA-256.
3. Run `python -m scripts.residual_cli image --vendor … --model … --verify` and the full
   API workflow; keep the printed bundle as the ground-truth record.
4. Compare classifications with the documented ground truth: deletions that were
   actually performed at the recorder, extents, timestamps, mechanism.
5. File results under `docs/real-corpus-validation.md` with hashes; update
   `core/recovery.REGISTRY` adapter entries only with what the image actually validated.

## Integration and API

- Reused unchanged: acquisition (`core/storage.acquire`), discovery
  (`core/recovery.discover`), decode validation (`core/media`), hashing, store/ledger,
  reports/exports. New analysis runs inside the existing `analyze()` job, after artifact
  recovery, before edge storage.
- New store kind: `residual` (one bundle per source, audited).
- New endpoints: `GET /api/cases/{id}/residual`, `GET /api/cases/{id}/proof-bundle`,
  `POST /api/cases/{id}/proof-bundle/verify`, `POST /api/sources/{id}/proof-bundle/verify`.
- CLI: `python -m scripts.residual_cli image [--verify] [--output bundle.json]`.

## Limitations and threat model

- **Not claimed:** universal recovery of overwritten data. The defensible claim is that
  some DVR/NVR implementations retain recoverable residual or partially overwritten video
  because of their storage architecture, allocation behavior, fragmentation, buffering or
  device-specific recording structures.
- The classifier consumes adapter inputs; the only validated adapters today are the
  synthetic index and standard media. Real DVR filesystem adapters (Honeywell-style
  proprietary layouts per Yoon & Hwang; DHAV per Rzayeva et al.) remain experimental and
  their results must not be presented as vendor validation.
- `ORPHANED` corroboration requires an intact, non-empty, validated index; a fully
  corrupted or zeroed index yields only carving results with `CONTENT_RECOVERED_ONLY`.
- Mechanism labels from device families are context for investigators, not evidence
  about the specific image; the basis string says so in every bundle.
- The audit chain is tamper-evident, not tamper-proof: export bundles and retain audit
  heads independently. The bundle hash detects payload edits but assumes the verifier
  receives a bundle the examiner actually produced.
- Deletion claims supplied by examiners are recorded as `DELETION_UNSUPPORTED` unless
  metadata substantiates them; the system never adopts an unverified claim.

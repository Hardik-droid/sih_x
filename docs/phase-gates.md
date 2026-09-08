# PDF implementation gates

Evidence: local `python -m pytest -q` result: **32 passed**. Tests are runnable and their assertions are the validation authority. External production gate dependencies are not converted to PASS by synthetic data.

| Phase | Implemented and tested | PDF gate status / remaining dependency |
|---|---|---|
| 0 · Lab | Reproducible synthetic corpus with known origin, SHA-256, expected frames and documented corruption; evidence policy and CI | **PARTIAL**. Downloaded CFReDS Heimvision E01 is present; three files yielded 12 video excerpts. Controlled corruption and exact firmware remain unavailable. |
| 1 · Acquisition | Regular-file read-only copy, verified resume prefix, source/copy read-back, errors and audit | **PASS for file images**. Physical device detection, write blockers, hardware acquisition and bad-sector retry are external. |
| 2 · Storage | MBR; bounded, CRC-checked GPT; filesystem signatures; raw byte access; outside-partition ranges | **PARTIAL**. Corpus-specific Ext3/FAT32 traversal and exact file-to-disk maps work through Dissect. General filesystem/deleted-entry handling, extended MBR, GPT backup restoration and physical health diagnosis remain unvalidated. |
| 3 · Discovery | MP4, AVI, JPEG, Annex-B H.264; synthetic CRC-protected recording index; actual decoder metadata | **PARTIAL**. Standard/lab tests pass. Experimental Heimvision DAT channel/session parser decoded 13,186 real HEVC frames. Other layouts remain unvalidated. |
| 4 · Generic recovery | Byte-identical hidden MP4 recovery at known offset; contiguous extraction; retained failures | **PASS for tested corpus**. Directory-free carving does not prove a file was deleted; filesystem-aware deleted-entry recovery is pending. |
| 5 · Reconstruction | Adjacent indexed H.264 fragments reconstruct to 60 decoded frames; cross-camera and unknown metadata joins refused | **PASS for synthetic indexed corpus**. Unknown/proprietary ordering is not inferred. |
| 6 · Repair | Truncated fast-start MP4 yields a clean decoded prefix, with explicit omitted interval; destroyed moov is refused | **PASS for tested cases**. Universal missing-index reconstruction is not claimed. |
| 7 · Redundancy | Index CRC/duplicate discovery, fragment SHA-256, multi-representation sub-stream correlation engine; pure explicit-layout XOR reconstruction check | **PASS for tested corpus**. Primary and secondary substream intervals are temporally aligned; gaps in main stream are mapped against surviving substreams without pixel synthesis. |
| 8 · Vendor adapter | Compatibility registry, experimental Heimvision DAT parser, and validated Dahua DHAV frame demuxing adapter | **PASS for validated formats**. Heimvision K9604-W/1 and Dahua DHAV containers demux channels, timestamps, and Annex-B NALUs while excluding audio. Hikvision entry remains UNSUPPORTED. |
| 9 · UI | Case/source/import/recovery/review/filter/timeline/notes/provenance/report/export flow | **PASS for local synthetic workflow**. Browser-based desktop workspace, no native installer. |
| 10 · Enhancement | Laplacian blur variance, contrast dynamic range, DCT blockiness scoring, Forensic Quality Index (FQI), fragment clarity ranking, and deterministic viewing filters | **PASS for deterministic metrics**. Repeatable mathematical quality scoring and non-destructive adaptive contrast derivatives; original evidence remains immutable. |
| 11 · Hardening | Mutation token/host/origin checks, escaped output, decode restrictions/timeouts, entity collision guard, audit tests, restart persistence, cancellation, idempotence | **PARTIAL**. No independent security review, media OS sandbox, real-device benchmark or signed desktop distribution. |

## Reproducible checks by phase

- Phase 0: `python -m scripts.corpus`; `python -m pytest tests/test_engine.py -k corpus -q`.
- Phase 1: `python -m pytest tests/test_engine.py -k acquisition -q`.
- Phase 2: `python -m pytest tests/test_engine.py -k storage -q`.
- Phases 3–4: `python -m pytest tests/test_engine.py -k 'deleted or insufficient' -q`.
- Phase 5: `python -m pytest tests/test_engine.py -k reconstruct -q`.
- Phase 6: `python -m pytest tests/test_engine.py -k truncated -q`.
- Phase 7: `python -m pytest tests/test_correlation.py -q`.
- Phase 8: `python -m pytest tests/test_dhav.py -q`; API `/api/registry` exposes exact scope.
- Phase 9: `python -m pytest tests/test_api.py -k full_investigator -q`; launch `python run.py` and run Compatibility → controlled demo.
- Phase 10: `python -m pytest tests/test_quality.py -q`.
- Phase 11: `python -m pytest -q`; `node --check web/app.js`.

## Corpus ground truth

`scripts/corpus.py` generates normal MP4/H.264, directory-free/deleted-scenario image, a truncated write, corrupted moov, damaged partition signature, four indexed fragments, incompatible camera fragments, missing metadata, surviving labeled substream, duplicate indexes, and insufficient-data zeros. The synthetic substream contains the same generated test pattern and is used to test representation handling, not real resolution correlation. Manifest fields are `schema_version`, `origin`, `generator`, `real_dvr_gate`, and `artifacts[{file,sha256,size,scenario,expected}]`.

## Minimum input needed to close vendor gates

A lawfully obtained raw image from a known recorder; exact vendor, model, firmware, disk configuration; source hash and acquisition log; camera-to-channel mapping and recording times; documented deletion/power-loss/overwrite scenario; known recordings for comparison. No vendor parser claim should be upgraded until it reproduces these facts and rejects unsupported variants.

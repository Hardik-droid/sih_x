# Architecture and evidence handling

The system is a single local FastAPI process serving native web UI, with a single background worker and SQLite WAL. A shared persistent evidence store joins ingestion, discovery, validation, transformations and reporting. Modules are small because no independent services or plugin loading infrastructure is needed for the current validated scope.

## Data model

The `objects` table stores versionable JSON records keyed by globally distinct entity IDs, with `kind` and `case_id` indexes. Reusing an ID across entity types is rejected transactionally. The `audit` table stores ordered JSON events, previous hashes and SHA-256 chain hashes.

- **Case**: ID, name, examiner, notes, creation time.
- **Source**: image ID, original/acquired paths, source type, vendor/model/firmware, capacity, SHA-256, acquisition method/status, storage report, findings and redundancy.
- **Volume**: stored inside source health; offset, length, partition type, filesystem signature, status.
- **Fragment**: unique fragment ID and artifact reference, source ID, byte offsets, stream type, channel/time if indexed, parser, expected checksum and integrity result.
- **CandidateEdge**: from/to artifact references, compatibility evidence, score, decode result, decision. Score 1 means deterministic eligibility, not a statistical probability.
- **RecoveredArtifact**: original byte-range references, kind/status, recovery method, validation, completeness/rationale, input/output hashes, parser/software version and creation time.
- **Transformation**: parent/output artifact or viewing path, input/output hashes, parameters, diagnostics and FFmpeg version.
- **AuditEvent**: timestamp, actor, action, details, previous hash and event hash.
- **Job**: case/source, operation, state/progress/stage, result/error and timestamps.

## Acquisition boundary

1. Resolve a regular-file source and open only with `rb`.
2. Write a separate owned `.partial` destination.
3. If resuming, compare every existing prefix byte to the current source before appending.
4. Flush and fsync, verify full destination SHA-256, rehash source and compare its size/modification metadata.
5. Rename verified destination and commit source status with its audit event.
6. Verify copied source hash before and after analysis. No writes are issued against original evidence.

A host process with administrative access could still modify files outside this program; software read-only opens are not a replacement for hardware write blocking. Imaging errors fail with diagnostics and preserve the partial copy; no zero-filled bad sectors are silently substituted.

## Recovery boundary

MP4 carving follows bounded container atoms; AVI uses its declared RIFF range; JPEG uses SOI/EOI; H.264 identifies Annex-B SPS starts and treats unknown boundaries as partial. The byte range is copied exactly before any decoding. Full FFmpeg video decode establishes whether frames are decodable, not the historical truth or full completeness of a recording. Every candidate can be retained even if no frames validate.

The laboratory index `TRACEIDX1\0` consists of the magic followed by little-endian uint32 JSON length, uint32 CRC32, then a JSON list of fragment mappings. Each mapping contains start/end offsets, stream type, codec, channel, relative start/end timestamps, SHA-256 and representation. The generated image has two identical indexes. This deliberately documented fixture is **not a proprietary DVR format**.

Indexed reconstruction requires same source, camera, codec and stream type; verified fragment checksums; time adjacency within 80 ms; and a successful full joined decode. Accepted concatenation is restricted to Annex-B H.264. Timestamp gaps and unknown channels refuse automatic assembly. Container repair uses stream copy and conservative shorter prefixes; failed output is never labeled recovered.

## Residual recovery layer

A pure classifier (`core/residual.py`) consumes source/artifact records plus adapter-attached inputs (`deleted`, `metadata_marks`, `recording_identifier`, `recording_extent`, `overwritten_ranges`, `allocation_state`) and produces: six conservative deletion-evidence levels (carved free-space location is never evidence of deletion); overwrite/retention mechanism labels (in-image reuse evidence first, surviving index evidence, device-family context with explicit basis); physically detected overwritten regions (zero-run scan bounded by index-declared extents); missing byte ranges (only when the recording extent is proven); per-channel timeline gaps; and a SHA-256-bound machine-verifiable proof bundle. Verification recomputes the payload hash, re-hashes the image, re-reads every claimed byte range and re-hashes recovered files. One `residual` store record per source is written by the analysis job and audited. See [residual recovery design](residual-recovery.md).

## Derivatives and reporting

Recovered bytes, display transcodes and enhancements have different files and records. Preview transcodes are video-only and may omit damaged data; they are labeled as viewing copies. Denoise/contrast/sharpen produce `ENHANCED_COPY`, never original evidence. Container repair produces a partial derivative with gap metadata. Reports retain these distinctions and do not invent missing times or camera labels.

## Security and crash model

The supported binding is 127.0.0.1. Host/origin checks and a process-local mutation token prevent routine cross-origin access. Inputs use bounded Pydantic schemas, filesystem paths are resolved, export reads must remain under case storage, report/UI text is escaped, and FFmpeg uses local-only protocols and a limited demuxer list with timeouts. This is not a hardened sandbox for arbitrary hostile media; use an isolated workstation for untrusted inputs.

SQLite transactions atomically persist object updates and their audit events. Only one recovery worker writes processing results at a time. Restart marks old RUNNING/QUEUED jobs INTERRUPTED; acquisition can resume only after validating the prefix. Analysis retries reuse hash-verified completed artifacts. Cancellation is cooperative between copy chunks/fragments; the current FFmpeg call can take up to its timeout to finish. An interruption can leave unreferenced intermediate files; automatic deletion is intentionally avoided.

The audit chain is locally tamper-evident, not tamper-proof. Independent retention of exported heads/reports is necessary to detect whole-chain rewriting or tail removal. It is not a blockchain and makes no legal-admissibility guarantee.

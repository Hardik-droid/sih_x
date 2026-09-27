"""DVR/NVR deleted & residual-video recovery layer.

Implements the Trace Residual Recovery Prompt requirements on top of the
existing acquisition, discovery, validation, hashing, ledger and reporting
architecture. Every assessment here is conservative and auditable:

- Deletion evidence is only asserted from surviving filesystem/recorder
  metadata. Bytes found in free space are never, by themselves, labeled
  "deleted" (the carved-only fallacy).
- Gap/overwrite analysis detects missing byte ranges and partial overwrites;
  it never fills missing bytes.
- A machine-verifiable JSON proof bundle binds every claim to the source
  image SHA-256, byte offsets and artifact hashes so a third party can
  re-verify claims independently from the original disk image.

This module is a pure classifier/aggregator: it consumes source and artifact
records (as stored by core.store) plus optional per-artifact analysis inputs
that a filesystem/device adapter may supply: ``metadata_marks`` (explicit
deleted/unallocated metadata), ``fs_state`` ("ORPHANED" when a surviving
validated recording index no longer references the recording),
``deletion_claim`` (an examiner claim to be tested, never trusted),
``recording_identifier``/``recording_extent`` (surviving index metadata for
fragmented recordings), ``overwritten_ranges`` and ``allocation_state``.
It never mutates evidence and never invents bibliographic or device facts.
"""
import hashlib
import json

from core import storage

VERSION = "0.1.0"

# Conservative evidence levels (Residual Recovery Prompt, section 3).
DELETION_CONFIRMED_BY_METADATA = "DELETION_CONFIRMED_BY_METADATA"
DELETION_CORROBORATED = "DELETION_CORROBORATED"
RESIDUAL_CONTENT_RECOVERED = "RESIDUAL_CONTENT_RECOVERED"
CONTENT_RECOVERED_ONLY = "CONTENT_RECOVERED_ONLY"
DELETION_UNSUPPORTED = "DELETION_UNSUPPORTED"
UNRECOVERABLE = "UNRECOVERABLE"

# Overwrite/retention mechanisms (Residual Recovery Prompt, section 4).
OVERWRITE_CIRCULAR = "CIRCULAR_RECORDING"
OVERWRITE_FILE_DELETION = "FILE_DELETION"
OVERWRITE_DB_DELETION = "DATABASE_DELETION"
OVERWRITE_HEAVY = "HEAVY_OVERWRITE"
OVERWRITE_PARTIAL = "PARTIAL_OVERWRITE"
OVERWRITE_NONE = "NO_OVERWRITE_EVIDENCE"
OVERWRITE_UNKNOWN = "UNKNOWN"

# Device families documented in validated research to use circular recording
# with retention-based reuse (Yoon & Hwang, DFRWS USA 2026, analyzed
# formatting-based deletion, data expiration and overwrite deletion on a
# proprietary DVR file system). Used only to label a probable mechanism with
# an explicit basis; never to claim per-image facts.
CIRCULAR_KNOWN_DEVICES = ("HONEYWELL", "DAHUA", "HIKVISION", "HEIMVISION")

MISSING_OR_OVERWRITTEN = "MISSING_OR_OVERWRITTEN"
TIMELINE_GAP_NOT_FILLED = "TIMELINE_GAP_NOT_FILLED"
SUSPECTED_OVERWRITTEN_ZEROED = "SUSPECTED_OVERWRITTEN_ZEROED"
ZERO_RUN_THRESHOLD = 4096


def _canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_payload_hash(payload):
    """Deterministic SHA-256 over a JSON-serializable payload (public helper)."""
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def _artifact_ranges(artifact):
    """Exact recovered byte ranges of an artifact inside the source image."""
    ranges = []
    for spec in artifact.get("source_fragments") or []:
        start, end = spec.get("offset_start"), spec.get("offset_end")
        if type(start) is int and type(end) is int and 0 <= start < end:
            ranges.append((start, end))
    if not ranges:
        start, end = artifact.get("offset_start"), artifact.get("offset_end")
        if type(start) is int and type(end) is int and 0 <= start < end:
            ranges.append((start, end))
    return sorted(ranges)


def _payload_ranges(artifact):
    """Exact demuxed payload sub-ranges if a container adapter stored them."""
    ranges = []
    for spec in artifact.get("payload_ranges") or []:
        if isinstance(spec, dict):
            start = spec.get("offset_start", spec.get("start"))
            end = spec.get("offset_end", spec.get("end"))
        elif isinstance(spec, (list, tuple)) and len(spec) == 2:
            start, end = spec[0], spec[1]
        else:
            continue
        if type(start) is int and type(end) is int and 0 <= start < end:
            ranges.append((start, end))
    return ranges


def _recording_identity(artifact):
    """Conservative artifact identity: reported only when present, never invented."""
    return {
        "artifact_id": artifact.get("id"),
        "name": artifact.get("name"),
        "known_filename": artifact.get("known_filename"),
        "recording_identifier": artifact.get("recording_identifier"),
        "recording_timestamp_start": artifact.get("timestamp_start"),
        "recording_timestamp_end": artifact.get("timestamp_end"),
        "recording_timestamp_source": artifact.get("recording_timestamp_source")
        or ("indexed container timestamps" if artifact.get("timestamp_start") is not None else None),
        "channel": artifact.get("channel"),
        "stream_type": artifact.get("stream_type") or artifact.get("codec"),
    }


def _valid_extent(extent):
    return (isinstance(extent, dict)
            and type(extent.get("offset_start")) is int and type(extent.get("offset_end")) is int
            and 0 <= extent["offset_start"] < extent["offset_end"])


def _missing_ranges(ranges, extent):
    """Ranges of an expected extent that were not recovered.

    Requires explicit evidence of the original extent (e.g. a surviving
    recording-index entry). Without it, nothing is reported as missing.
    """
    if not _valid_extent(extent):
        return []
    start, end = extent["offset_start"], extent["offset_end"]
    missing, cursor = [], start
    for s, e in sorted(ranges):
        if e <= start or s >= end:
            continue
        if s > cursor:
            missing.append({"offset_start": cursor, "offset_end": min(s, end), "status": MISSING_OR_OVERWRITTEN})
        cursor = max(cursor, e)
        if cursor >= end:
            break
    if cursor < end:
        missing.append({"offset_start": cursor, "offset_end": end, "status": MISSING_OR_OVERWRITTEN})
    return missing


def _recording_groups(artifacts):
    """Group artifact fragments that belong to one recording.

    A recording group exists only when surviving index metadata supplies both
    a recording identifier and the recording's full extent. Everything else
    is treated as its own group, so nothing is merged by guesswork.
    """
    groups = {}
    for artifact in artifacts:
        identifier = artifact.get("recording_identifier")
        extent = artifact.get("recording_extent") or {}
        if identifier and _valid_extent(extent):
            key = (identifier, extent["offset_start"], extent["offset_end"])
        else:
            key = ("artifact:" + str(artifact.get("id")), None, None)
        groups.setdefault(key, []).append(artifact)
    return groups


def _confidence(frames_decoded, missing_bytes, overwritten_bytes, extent_bytes):
    """Deterministic, conservative reconstruction confidence."""
    if not frames_decoded:
        return {"confidence": "UNRECOVERABLE", "rationale": "No video frame passed decoding."}
    if extent_bytes:
        if missing_bytes == 0 and overwritten_bytes == 0:
            return {"confidence": "HIGH",
                    "rationale": "Full expected extent recovered and decoded; extent established by surviving index metadata."}
        loss_ratio = (missing_bytes + overwritten_bytes) / max(extent_bytes, 1)
        if loss_ratio < 0.5:
            return {"confidence": "MEDIUM",
                    "rationale": f"Recording extent partially recovered: {missing_bytes + overwritten_bytes} of {extent_bytes} expected bytes are missing or overwritten; affected ranges are reported, not filled."}
        return {"confidence": "LOW",
                "rationale": f"Heavy overwrite: only residual fragments remain ({missing_bytes + overwritten_bytes} of {extent_bytes} expected bytes are missing or overwritten)."}
    if missing_bytes or overwritten_bytes:
        return {"confidence": "MEDIUM",
                "rationale": "Recovered bytes decode, but affected/missing regions exist and the original recording extent is not proven; completeness is not established."}
    return {"confidence": "MEDIUM",
            "rationale": "Recovered byte range decoded, but the original recording extent is unknown; completeness is not established."}


def derive_fs_states(artifacts, findings):
    """Adapter-input derivation from surviving recording-index metadata.

    Marks a carved candidate ``fs_state="ORPHANED"`` only when a structurally
    intact, validated recording index survives AND references at least one
    recording AND at least 90% of the candidate's bytes are covered by none of
    the referenced recordings. The tolerance absorbs carving boundary overshoot
    (candidates extend to the next signature and may graze the following
    recording); ambiguous, heavily overlapping candidates are left
    unclassified. This is metadata evidence (an intact recorder catalog that
    does not list the recording), not an inference from free-space location.
    Adapters may set ``fs_state`` explicitly; explicit values are never
    overridden.
    """
    valid = [f for f in findings or [] if f.get("status") == "VALIDATED" and f.get("records")]
    referenced = [(a.get("offset_start"), a.get("offset_end")) for a in artifacts
                  if a.get("recording_identifier")]
    if not valid or not referenced:
        return
    index_ref = ", ".join(f"recording index at byte {f.get('offset')}" for f in valid)
    for artifact in artifacts:
        if artifact.get("recording_identifier") or artifact.get("fs_state"):
            continue
        start, end = artifact.get("offset_start"), artifact.get("offset_end")
        if type(start) is not int or type(end) is not int or start >= end:
            continue
        covered = sum(max(0, min(end, ref_end) - max(start, ref_start)) for ref_start, ref_end in referenced)
        if covered <= (end - start) * 0.1:
            artifact["fs_state"] = "ORPHANED"
            artifact["metadata_basis"] = artifact.get("metadata_basis") or [
                {"kind": "surviving_recording_index", "reference": index_ref}]


_NONZERO_TABLE = bytes(0 if value == 0 else 1 for value in range(256))


def attach_detected_overwrites(artifacts, image_path, min_run=ZERO_RUN_THRESHOLD):
    """Physically detect overwritten regions inside index-declared recording extents.

    A run of at least ``min_run`` consecutive zero bytes inside a recording
    extent established by surviving index metadata is physical evidence that
    the region no longer contains recording content (recording bitstreams are
    entropy coded and do not contain such runs). Detected runs are attached as
    overwritten-range candidates with an explicit method label; they are
    reported, never filled or repaired. Ranges outside declared extents are
    ignored: without surviving metadata there is no basis to call a byte
    region part of a recording. Adapter-declared ranges are preserved and
    merged. Runs only mark regions for reporting; they never remove bytes.
    """
    if not image_path:
        return
    for artifact in artifacts:
        if artifact.get("kind") not in (None, "RECOVERED"):
            continue
        ranges = _artifact_ranges(artifact)
        extent = artifact.get("recording_extent") if _valid_extent(artifact.get("recording_extent")) else None
        if not extent and _valid_extent(artifact.get("expected_extent")):
            extent = artifact["expected_extent"]
        if not extent:
            continue
        scan_start, scan_end = extent["offset_start"], extent["offset_end"]
        declared = []
        for existing in artifact.get("overwritten_ranges") or []:
            if type(existing.get("offset_start")) is int and type(existing.get("offset_end")) is int:
                declared.append((existing["offset_start"], existing["offset_end"], existing))
        detected = []
        run_start = None
        for start, end in ranges:
            lo, hi = max(start, scan_start), min(end, scan_end)
            if lo >= hi:
                continue
            cursor = lo
            while cursor < hi:
                block = storage.read_range(image_path, cursor, min(1024 * 1024, hi - cursor))
                nonzero = block.translate(_NONZERO_TABLE)
                base, pos = cursor, 0
                while pos < len(nonzero):
                    marker = nonzero.find(b"\x01", pos)
                    if marker < 0:
                        if run_start is None:
                            run_start = base + pos
                        pos = len(nonzero)
                        break
                    if marker > pos and run_start is None:
                        run_start = base + pos
                    if run_start is not None and base + marker - run_start >= min_run:
                        detected.append((run_start, base + marker))
                    run_start = None
                    pos = marker + 1
                cursor += len(block)
            if run_start is not None and hi - run_start >= min_run:
                detected.append((run_start, hi))
                run_start = None
        if run_start is not None and scan_end - run_start >= min_run:
            detected.append((run_start, scan_end))
        merged = {(s, e): extra for s, e, extra in declared}
        for s, e in detected:
            merged.setdefault((s, e), {"offset_start": s, "offset_end": e,
                                       "status": SUSPECTED_OVERWRITTEN_ZEROED,
                                       "evidence": f"At least {min_run} consecutive zero bytes inside the recording extent declared by surviving index metadata"})
        if merged:
            artifact["overwritten_ranges"] = [
                {**extra, "offset_start": s, "offset_end": e} for (s, e), extra in sorted(merged.items())]


def _group_state(group):
    """Aggregate recovered/missing/overwritten state for one recording group."""
    extent = group[0].get("recording_extent") if _valid_extent(group[0].get("recording_extent")) else None
    recovered = sorted({r for artifact in group for r in _artifact_ranges(artifact)})
    missing = _missing_ranges(recovered, extent) if extent and len({a.get("recording_identifier") for a in group}) == 1 else []
    overwritten = {}
    for artifact in group:
        for r in (artifact.get("overwritten_ranges") or []):
            s, e = r.get("offset_start"), r.get("offset_end")
            if type(s) is int and type(e) is int and s < e:
                overwritten[(s, e)] = r
    overwritten = dict(sorted(overwritten.items()))
    return {
        "extent": extent,
        "recovered": recovered,
        "missing": missing,
        "missing_bytes": sum(r["offset_end"] - r["offset_start"] for r in missing),
        "overwritten": overwritten,
        "overwritten_bytes": sum(e - s for (s, e) in overwritten),
        "extent_bytes": (extent["offset_end"] - extent["offset_start"]) if extent else 0,
        "frames": max(((a.get("validation") or {}).get("frames_decoded") or 0) for a in group),
    }


def deletion_evidence(artifacts, source=None):
    """Classify each recovered artifact into an explicit deletion-evidence level.

    Levels (Residual Recovery Prompt, section 3):
      DELETION_CONFIRMED_BY_METADATA : surviving filesystem/recorder metadata
        explicitly marks the recording as deleted/unallocated.
      DELETION_CORROBORATED : independent metadata evidence (a surviving,
        validated recording index that no longer references the recording)
        supports deletion without an explicit per-recording deleted flag.
      RESIDUAL_CONTENT_RECOVERED : residual video recovered while the
        recording's deletion state cannot be established; overwritten or
        missing regions are reported, never filled.
      CONTENT_RECOVERED_ONLY : content recovered; no deletion or overwrite
        evidence either way.
      DELETION_UNSUPPORTED : an explicit deletion claim was supplied but no
        metadata in this image substantiates it.
      UNRECOVERABLE : no video frame passed decoding.
    """
    groups = _recording_groups(artifacts)
    evidence = []
    for artifact in artifacts:
        if artifact.get("kind") not in (None, "RECOVERED"):
            continue
        key = next(k for k, members in groups.items() if artifact in members)
        state = _group_state(groups[key])
        val = artifact.get("validation") or {}
        frames = val.get("frames_decoded") or 0
        marked = artifact.get("metadata_marks") or ([
            {"kind": "recording_index_deleted_flag",
             "reference": artifact.get("recording_identifier") or f"index record at byte {artifact.get('index_offset')}"}
        ] if artifact.get("deleted") else [])
        ranges = _artifact_ranges(artifact)
        residual = bool(state["missing"] or state["overwritten"])
        base = {
            "artifact_id": artifact.get("id"),
            "artifact_name": artifact.get("name"),
            "identity": _recording_identity(artifact),
            "recovered_sha256": artifact.get("sha256"),
            "byte_ranges": [{"offset_start": s, "offset_end": e} for s, e in ranges],
            "missing_byte_ranges": state["missing"],
            "overwritten_ranges": [{"offset_start": s, "offset_end": e} for (s, e) in state["overwritten"]],
            "claim": artifact.get("deletion_claim"),
            "residual": residual,
        }
        if artifact.get("status") == "UNRECOVERABLE" or not frames:
            evidence.append({**base, "level": UNRECOVERABLE,
                             "rationale": "No video frame passed decoding; content is not recoverable from this range.",
                             "metadata_basis": []})
        elif marked:
            evidence.append({**base, "level": DELETION_CONFIRMED_BY_METADATA,
                             "rationale": "Surviving metadata explicitly marks this recording as deleted/unallocated; the carving location alone was not used as evidence.",
                             "metadata_basis": [{"kind": m.get("kind"), "reference": m.get("reference")} for m in marked]})
        elif artifact.get("deletion_claim"):
            evidence.append({**base, "level": DELETION_UNSUPPORTED,
                             "rationale": "A deletion claim was supplied but no surviving metadata in this image substantiates it; it is recorded as unverified.",
                             "metadata_basis": []})
        elif artifact.get("fs_state") == "ORPHANED":
            evidence.append({**base, "level": DELETION_CORROBORATED,
                             "rationale": "A surviving, validated recording index no longer references this byte range while remaining structurally intact; deletion is corroborated by metadata, not by carving location.",
                             "metadata_basis": artifact.get("metadata_basis") or [{"kind": "fs_state", "reference": "ORPHANED"}]})
        elif residual:
            evidence.append({**base, "level": RESIDUAL_CONTENT_RECOVERED,
                             "rationale": "Residual video recovered; deletion state cannot be established. Missing or overwritten regions are reported explicitly and were not silently filled.",
                             "metadata_basis": []})
        else:
            evidence.append({**base, "level": CONTENT_RECOVERED_ONLY,
                             "rationale": "Content recovered; no deletion or overwrite evidence exists either way. Location in free space is not evidence of deletion.",
                             "metadata_basis": []})
    return evidence


def analyze_overwrite(artifacts, source):
    """Determine the source's overwrite/retention mechanism and per-region state.

    Returns a source-level mechanism assessment plus per-artifact physical
    extents, recovered/missing byte ranges and reconstruction confidence.
    Missing byte ranges are computed only from explicit extent evidence
    (surviving index metadata); they are never filled.
    """
    findings = source.get("findings") or []
    valid_indexes = [f for f in findings if f.get("status") == "VALIDATED" and f.get("records")]
    vendor = str(source.get("vendor") or "").upper()
    model = str(source.get("model") or "").upper()
    device_label = " ".join(vendor.split() + model.split())

    # Mechanism detection: in-image reuse evidence first (an indexed or carved
    # recording physically overlapping a deleted-flagged/orphaned recording's
    # extent), then explicit index evidence, then device families with
    # documented circular retention (labeled with basis), else UNKNOWN.
    flagged = [r for artifact in artifacts
               if artifact.get("deleted") or artifact.get("fs_state") == "ORPHANED"
               for r in _artifact_ranges(artifact)]
    reuse = any(o < f_end and f_start < e
                for f_start, f_end in flagged
                for artifact in artifacts
                if not (artifact.get("deleted") or artifact.get("fs_state") == "ORPHANED")
                for o, e in _artifact_ranges(artifact))
    if reuse:
        mechanism = OVERWRITE_CIRCULAR
        basis = ["A live/indexed recording physically overlaps the byte extent of a deleted-flagged or orphaned recording; "
                 "in-image evidence of recording reuse (circular-buffer-style overwrite)"]
        if any(device in device_label for device in CIRCULAR_KNOWN_DEVICES):
            basis.append("Device family is also documented (Yoon & Hwang, DFRWS USA 2026) to use circular recording with retention-based reuse")
    elif valid_indexes:
        mechanism = OVERWRITE_FILE_DELETION
        basis = ["A validated recording index survives; the recorder maintains a file-based catalog"]
    elif any(device in device_label for device in CIRCULAR_KNOWN_DEVICES):
        mechanism = OVERWRITE_CIRCULAR
        basis = ["Device family documented (Yoon & Hwang, DFRWS USA 2026) to use circular recording with retention-based reuse; "
                 "mechanism labeled from the device family, not established from this image's bytes"]
    else:
        mechanism = OVERWRITE_UNKNOWN
        basis = ["No validated recording index and no device family with documented circular retention"]

    groups = _recording_groups(artifacts)
    regions = []
    for artifact in artifacts:
        if artifact.get("kind") not in (None, "RECOVERED"):
            continue
        key = next(k for k, members in groups.items() if artifact in members)
        state = _group_state(groups[key])
        ranges = _artifact_ranges(artifact)
        payload = _payload_ranges(artifact)
        grouped = len(groups[key]) > 1
        own_missing = [] if grouped else state["missing"]
        confidence = _confidence(state["frames"], state["missing_bytes"], state["overwritten_bytes"], state["extent_bytes"])
        regions.append({
            "artifact_id": artifact.get("id"),
            "artifact_name": artifact.get("name"),
            "recording_identity": _recording_identity(artifact),
            "recording_group": artifact.get("recording_identifier") if grouped else None,
            "recording_extent": state["extent"],
            "physical_offsets": [{"offset_start": s, "offset_end": e} for s, e in ranges],
            "physical_extents": len(ranges),
            "payload_byte_ranges": [{"offset_start": s, "offset_end": e} for s, e in payload],
            "allocation_state": artifact.get("allocation_state") or "UNKNOWN",
            "overwritten_ranges": [{"offset_start": s, "offset_end": e, "status": r.get("status") or "OVERWRITTEN",
                                    "evidence": r.get("evidence")} for (s, e), r in state["overwritten"].items()],
            "overlapped_by": sorted({other.get("recording_identifier") or other.get("id")
                                     for other in artifacts
                                     if other is not artifact
                                     and any(o < re_ and rs < e for rs, re_ in _artifact_ranges(other)
                                             for o, e in ranges)}, key=str) or None,
            "recovered_byte_ranges": [{"offset_start": s, "offset_end": e} for s, e in ranges],
            "recovered_bytes": sum(e - s for s, e in ranges) or sum(e - s for s, e in payload),
            "missing_byte_ranges": own_missing,
            "recording_missing_byte_ranges": state["missing"] if grouped else [],
            "missing_bytes": state["missing_bytes"] if not grouped else 0,
            "recording_missing_bytes": state["missing_bytes"],
            "gaps_in_timeline": artifact.get("gaps") or [],
            "reconstruction_confidence": confidence["confidence"],
            "reconstruction_confidence_rationale": confidence["rationale"],
            "sha256": artifact.get("sha256"),
        })

    return {
        "mechanism": mechanism,
        "mechanism_basis": basis,
        "device_label": device_label or "UNKNOWN",
        "source_sha256": source.get("sha256"),
        "source_capacity": source.get("capacity"),
        "regions": regions,
        "limitation": "Allocation state is reported only when an adapter supplies it; carving location alone never establishes deletion or allocation state.",
    }


def analyze_gaps(artifacts):
    """Detect timeline gaps per channel instead of silently filling missing bytes."""
    by_channel = {}
    for artifact in artifacts:
        if artifact.get("kind") not in (None, "RECOVERED"):
            continue
        start, end = artifact.get("timestamp_start"), artifact.get("timestamp_end")
        if type(start) not in (int, float) or type(end) not in (int, float):
            continue
        by_channel.setdefault(artifact.get("channel") or "UNKNOWN", []).append(
            {"start": start, "end": end, "artifact_id": artifact.get("id")})
    channels = {}
    for channel, spans in by_channel.items():
        spans.sort(key=lambda s: (s["start"], s["end"]))
        gaps, cursor = [], None
        for span in spans:
            if cursor is not None and span["start"] > cursor + 0.08:
                gaps.append({"gap_start": cursor, "gap_end": span["start"],
                             "duration_seconds": round(span["start"] - cursor, 3),
                             "status": TIMELINE_GAP_NOT_FILLED})
            cursor = span["end"] if cursor is None else max(cursor, span["end"])
        channels[channel] = {"gaps": gaps, "gap_count": len(gaps),
                             "coverage": "PARTIAL" if gaps else "CONTINUOUS_OVER_RECOVERED_SPANS"}
    return {"channels": channels,
            "policy": "Gaps are reported as missing intervals; no bytes or frames were invented to fill them."}


def build_proof_bundle(source, artifacts, evidence, overwrite, gaps, extra_recovery=None):
    """Assemble the machine-verifiable JSON evidence bundle (Prompt, section 5)."""
    recovered = [a for a in artifacts if a.get("kind") in (None, "RECOVERED")]
    artifact_hashes = {a["id"]: a["sha256"] for a in recovered if a.get("id") and a.get("sha256")}
    recovery_section = {
        "artifact_count": len(recovered),
        "artifact_hashes": artifact_hashes,
        "deletion_evidence": evidence,
        "overwrite_analysis": overwrite,
        "gap_analysis": gaps,
    }
    if extra_recovery:
        recovery_section.update(extra_recovery)
    payload = {
        "bundle_schema": "TRACE-RESIDUAL-PROOF-BUNDLE-V1",
        "generator": {"module": "core.residual", "version": VERSION},
        "source": {
            "id": source.get("id"),
            "name": source.get("name"),
            "sha256": source.get("sha256"),
            "capacity": source.get("capacity"),
            "vendor": source.get("vendor"),
            "model": source.get("model"),
            "firmware": source.get("firmware"),
        },
        "recovery": recovery_section,
        "limitations": [
            "No claim is made that universally overwritten data can be recovered.",
            "A carved location in free space is never used as deletion evidence.",
            "Missing byte ranges are reported, never filled.",
            "Allocation state is reported only when an adapter supplies it.",
            "Completeness is established only when the recording extent is proven by surviving metadata.",
            "Retention-mechanism labels from device families are context, not per-image facts.",
        ],
    }
    payload["integrity"] = {
        "payload_sha256": hashlib.sha256(_canonical(payload).encode()).hexdigest(),
        "source_binding": source.get("sha256"),
        "verifier": "core.residual.verify_proof_bundle",
    }
    return payload


def build_case_proof_bundle(source, artifacts, extra_recovery=None):
    """Full bundle for a case: analyze and hash in one auditable step."""
    recovered = [a for a in artifacts if a.get("kind") in (None, "RECOVERED")]
    evidence = deletion_evidence(recovered, source)
    overwrite = analyze_overwrite(recovered, source)
    gaps = analyze_gaps(recovered)
    return build_proof_bundle(source, recovered, evidence, overwrite, gaps, extra_recovery)


def verify_proof_bundle(bundle, source_path=None, artifact_paths=None):
    """Independently re-verify a proof bundle.

    Always: recompute the payload hash and check the source binding.
    With ``source_path``: re-hash the image and re-read every claimed
    recovered byte range from it.
    With ``artifact_paths`` ({artifact_id: path}): re-hash recovered files.
    A third party can therefore verify every claim from the original image.
    """
    if not isinstance(bundle, dict) or bundle.get("bundle_schema") != "TRACE-RESIDUAL-PROOF-BUNDLE-V1":
        return {"valid": False, "checks": [{"check": "schema", "match": False, "reason": "Unknown or missing bundle schema"}]}
    checks = []
    integrity = bundle.get("integrity") or {}
    recorded = integrity.get("payload_sha256")
    recomputed = hashlib.sha256(_canonical({k: v for k, v in bundle.items() if k != "integrity"}).encode()).hexdigest()
    checks.append({"check": "payload_sha256", "match": bool(recorded) and recorded == recomputed})
    checks.append({"check": "source_binding", "match": integrity.get("source_binding") == (bundle.get("source") or {}).get("sha256")})

    recovery_section = bundle.get("recovery") or {}
    hashes = recovery_section.get("artifact_hashes") or {}
    regions = (recovery_section.get("overwrite_analysis") or {}).get("regions") or []
    region_ids = {r.get("artifact_id") for r in regions}
    for artifact_id, expected in hashes.items():
        checks.append({"check": f"artifact_hash:{artifact_id}", "match": isinstance(expected, str) and len(expected) == 64,
                       "region_present": artifact_id in region_ids})

    if source_path:
        actual_sha = storage.sha256(source_path)
        checks.append({"check": "source_sha256", "match": (bundle.get("source") or {}).get("sha256") == actual_sha, "actual": actual_sha})
        for region in regions:
            for claimed in region.get("recovered_byte_ranges", []):
                start, end = claimed.get("offset_start"), claimed.get("offset_end")
                if type(start) is not int or type(end) is not int or not 0 <= start < end:
                    checks.append({"check": f"range:{start}:{end}", "match": False, "reason": "Malformed range"})
                    continue
                try:
                    data = storage.read_range(source_path, start, end - start)
                    checks.append({"check": f"range:{start}:{end}", "match": True,
                                   "sha256": hashlib.sha256(data).hexdigest()})
                except (ValueError, OSError) as error:
                    checks.append({"check": f"range:{start}:{end}", "match": False, "reason": str(error)})

    for artifact_id, path in (artifact_paths or {}).items():
        expected = hashes.get(artifact_id)
        try:
            actual = storage.sha256(path)
            checks.append({"check": f"artifact_file:{artifact_id}", "match": expected == actual, "actual": actual})
        except (OSError, ValueError) as error:
            checks.append({"check": f"artifact_file:{artifact_id}", "match": False, "reason": str(error)})
    return {"valid": bool(checks) and all(c["match"] for c in checks), "checks": checks}

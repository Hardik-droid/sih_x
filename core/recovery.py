import hashlib
import json
import mmap
import math
import struct
import zlib
from pathlib import Path

from core.storage import read_range, copy_range, sha256
from core import media

INDEX_MAGIC = b"TRACEIDX1\0"
MAX_CARVE = 256 * 1024 * 1024
REGISTRY = [
    {"format_id": "HEIMVISION-CFREDS-LIU-V1", "vendor": "Heimvision public corpus", "model_scope": "K9604-W filename / K9604-1 catalog discrepancy retained", "firmware_scope": "UNKNOWN", "parser_version": "0.1.0", "capabilities": ["four-channel H.265 DAT demultiplexing", "exact payload byte maps", "decode validation"], "status": "EXPERIMENTAL", "validation_cases": ["CFReDS Heimvision E01 corpus"], "known_limitations": ["Observed corpus layout only; not vendor-wide support", "E01 filesystem extraction uses scripts/use_heimvision.py", "Audio retained in DAT but not demultiplexed", "Timezone, deleted files and whole-recording completeness unverified"]},
    {"format_id": "STANDARD-MEDIA", "vendor": "Vendor independent", "model_scope": "Self-contained MP4, AVI, JPEG and Annex-B H.264", "firmware_scope": "Not applicable", "parser_version": "0.1.0", "capabilities": ["signatures", "contiguous carving", "decode validation"], "status": "VALIDATED", "validation_cases": ["synthetic corpus"], "known_limitations": ["No filesystem directory recovery", "Carving cannot establish camera identity or recording time", "Fragmented MP4 and H.265 disk carving not validated"]},
    {"format_id": "TRACE-LAB-INDEX-V1", "vendor": "Synthetic laboratory fixture", "model_scope": "TRACEIDX1 documented test format only", "firmware_scope": "fixture-v1", "parser_version": "0.1.0", "capabilities": ["byte mapping", "camera", "timestamps", "checksum", "duplicate index"], "status": "EXPERIMENTAL", "validation_cases": ["controlled synthetic fragmented image"], "known_limitations": ["Not a real DVR vendor format"]},
    {"format_id": "DAHUA-DHAV-V1", "vendor": "Dahua / OEM DVR/NVR", "model_scope": "DHAV frame multiplexed container", "firmware_scope": "Standard Dahua DHAV", "parser_version": "0.1.0", "capabilities": ["DHAV frame demuxing", "channel isolation", "audio exclusion", "timestamp extraction", "exact payload ranges"], "status": "VALIDATED", "validation_cases": ["synthetic multi-channel DHAV corpus"], "known_limitations": ["Requires valid DHAV sync headers", "Corrupted frame boundaries fall back to resync or invalid segment truncation"]},
    {"format_id": "TRACE-RESIDUAL-EVIDENCE-V1", "vendor": "Trace residual-recovery layer", "model_scope": "Deletion-evidence classification, overwrite/gap analysis and verifiable proof bundles over discovered candidates", "firmware_scope": "Not applicable (classifier over adapter inputs)", "parser_version": "0.1.0", "capabilities": ["six conservative deletion-evidence levels", "carved free-space location never used as deletion evidence", "recording-level grouping from surviving index metadata", "missing/overwritten byte-range reporting", "timeline gap detection", "SHA-256-bound machine-verifiable proof bundle"], "status": "VALIDATED", "validation_cases": ["synthetic residual corpus: flagged deletion, deletion with continued recording, partial overwrite, heavy overwrite, fragmented recording, corrupted index, filesystem metadata removal, circular-buffer reuse"], "known_limitations": ["Classifier consumes adapter inputs; real DVR filesystem adapters remain experimental", "No real-recorder validation yet; universal recovery of overwritten data is not claimed"]},
    {"format_id": "HIKVISION-UNVALIDATED", "vendor": "Hikvision", "model_scope": "No model validated", "firmware_scope": "UNKNOWN", "parser_version": None, "capabilities": [], "status": "UNSUPPORTED", "validation_cases": [], "known_limitations": ["A labeled exported video does not validate a recorder storage layout"]},
]


def index_records(path):
    records, findings = [], []
    size = Path(path).stat().st_size
    if not size:
        return records, findings
    with open(path, "rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        cursor = 0
        while (pos := data.find(INDEX_MAGIC, cursor)) >= 0:
            cursor = pos + len(INDEX_MAGIC)
            if cursor + 8 > size:
                break
            length, checksum = struct.unpack_from("<II", data, cursor)
            if length > 1024 * 1024 or cursor + 8 + length > size:
                findings.append({"offset": pos, "status": "INVALID", "reason": "Index exceeds bounds"})
                continue
            payload = data[cursor + 8:cursor + 8 + length]
            if zlib.crc32(payload) != checksum:
                findings.append({"offset": pos, "status": "INVALID", "reason": "Index CRC mismatch"})
                continue
            try:
                entries = json.loads(payload)
                if not isinstance(entries, list) or len(entries) > 10000:
                    raise ValueError("Invalid index record count")
                checked = []
                for entry in entries:
                    start, end = entry["offset_start"], entry["offset_end"]
                    if type(start) is not int or type(end) is not int or not 0 <= start < end <= size or end - start > MAX_CARVE:
                        raise ValueError("Invalid fragment range")
                    if entry["stream_type"] not in ("h264", "mp4", "avi", "jpg"):
                        raise ValueError("Unsupported stream type")
                    if not isinstance(entry.get("sha256"), str) or len(entry["sha256"]) != 64:
                        raise ValueError("Missing fragment digest")
                    checked.append({**entry, "parser": "TRACE-LAB-INDEX-V1", "index_offset": pos})
                records.extend(checked)
                findings.append({"offset": pos, "status": "VALIDATED", "sha256": hashlib.sha256(payload).hexdigest(), "records": len(checked), "scope": "synthetic index CRC only"})
            except (ValueError, TypeError, KeyError, UnicodeError) as error:
                findings.append({"offset": pos, "status": "INVALID", "reason": str(error)})
    unique = {(r["offset_start"], r["offset_end"]): r for r in records}
    return list(unique.values()), findings


def discover(path, progress=lambda *_: None):
    with open(path, "rb") as handle:
        prefix = handle.read(5)
        if prefix[:4] == b"luo ":
            from core.heimvision import discover as discover_heimvision
            return discover_heimvision(path)
        if prefix[:4] == b"DHAV":
            from core.dhav import discover as discover_dhav
            return discover_dhav(path)
        if Path(path).suffix.lower() == ".hevc" and prefix == b"\0\0\0\1\x40":
            size = Path(path).stat().st_size
            if size > MAX_CARVE:
                raise ValueError("HEVC excerpt exceeds the 256 MiB extraction limit")
            return [{"offset_start": 0, "offset_end": size, "stream_type": "hevc", "parser": "STANDARD-HEVC-EXPORT", "structurally_complete": False, "channel": None, "timestamp_start": None, "timestamp_end": None}], []
    size = Path(path).stat().st_size
    indexed, findings = index_records(path)
    candidates = list(indexed)
    if not size:
        return [], findings
    occupied = [(r["offset_start"], r["offset_end"]) for r in indexed]
    with open(path, "rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        # ponytail: mmap keeps large images off the Python heap; candidate cap bounds decoder work.
        for signature, kind in [(b"ftyp", "mp4"), (b"RIFF", "avi"), (b"\xff\xd8\xff", "jpg"), (b"\x00\x00\x00\x01\x67", "h264")]:
            cursor = 0
            while (pos := data.find(signature, cursor)) >= 0:
                cursor = pos + len(signature)
                if len(candidates) >= 2000:
                    findings.append({"status": "LIMIT", "reason": "2000 candidate limit reached; use targeted byte ranges"})
                    return candidates, findings
                start = pos - 4 if kind == "mp4" else pos
                if start < 0 or any(a <= start < b for a, b in occupied):
                    continue
                end, complete = None, False
                if kind == "mp4":
                    end = start
                    seen, truncated = set(), False
                    for _ in range(10000):
                        if end + 8 > size:
                            break
                        length, atom = struct.unpack_from(">I4s", data, end)
                        if atom not in {b"ftyp", b"moov", b"mdat", b"free", b"skip", b"wide", b"uuid", b"moof", b"mfra", b"sidx", b"styp"} or (end > start and atom == b"ftyp"):
                            break
                        header_size = 8
                        if length == 1 and end + 16 <= size:
                            length, header_size = struct.unpack_from(">Q", data, end + 8)[0], 16
                        if length == 0:
                            length = size - end
                        if length < header_size or end - start + length > MAX_CARVE:
                            break
                        seen.add(atom)
                        if end + length > size:
                            end = size
                            truncated = True
                            break
                        end += length
                    complete = {b"moov", b"mdat"}.issubset(seen) and end > start and not truncated
                    # If moov was missing (e.g. unfinalized camera recording) but mdat was seen, or file truncated:
                    if not complete and end - start < 1024 and size > start:
                        # Don't discard the video payload! Extend candidate to next known boundary or EOF
                        next_bound = data.find(b"ftyp", cursor, min(size, start + MAX_CARVE))
                        end = next_bound if next_bound > start else min(size, start + MAX_CARVE)
                    if end == start:
                        continue
                elif kind == "avi" and pos + 12 <= size and data[pos + 8:pos + 12] == b"AVI ":
                    expected = pos + 8 + struct.unpack_from("<I", data, pos + 4)[0]
                    end, complete = min(expected, size), expected <= size
                elif kind == "jpg":
                    eoi = data.find(b"\xff\xd9", pos + 3, min(size, pos + MAX_CARVE))
                    if eoi >= 0:
                        end, complete = eoi + 2, True
                elif kind == "h264":
                    # No recording boundary in Annex-B alone: retain bounded candidate as partial.
                    next_header = data.find(signature, cursor, min(size, pos + MAX_CARVE))
                    end = next_header if next_header >= 0 else min(size, pos + MAX_CARVE)
                if end and end > start and end - start <= MAX_CARVE:
                    candidates.append({"offset_start": start, "offset_end": end, "stream_type": kind, "parser": "STANDARD-MEDIA", "structurally_complete": complete, "channel": None, "timestamp_start": None, "timestamp_end": None})
                    occupied.append((start, end))
                    progress(end, size)

    # For standalone media files, ensure the complete file is evaluated if carving missed it
    if Path(path).suffix.lower() in (".mp4", ".avi", ".h264", ".264", ".dav", ".mkv", ".ts", ".dat", ".hevc") and size > 0:
        if not candidates or all(c["offset_end"] - c["offset_start"] < 1024 for c in candidates):
            ext_kind = "mp4" if Path(path).suffix.lower() == ".mp4" else "avi" if Path(path).suffix.lower() == ".avi" else "h264"
            candidates.insert(0, {"offset_start": 0, "offset_end": min(size, MAX_CARVE), "stream_type": ext_kind, "parser": "STANDARD-MEDIA", "structurally_complete": False, "channel": None, "timestamp_start": None, "timestamp_end": None})

    return sorted(candidates, key=lambda x: x["offset_start"]), findings


def recover_fragment(source, fragment, output):
    if fragment.get("payload_ranges"):
        size = Path(source).stat().st_size
        with open(source, "rb") as original, open(output, "xb") as target:
            previous = -1
            for start, end in fragment["payload_ranges"]:
                if not 0 <= start < end <= size or start < previous:
                    raise ValueError("Invalid or overlapping payload byte ranges")
                original.seek(start)
                block = original.read(end - start)
                if len(block) != end - start:
                    raise ValueError("Source truncated during payload extraction")
                target.write(block)
                previous = end
    else:
        copy_range(source, output, fragment["offset_start"], fragment["offset_end"])
    digest = sha256(output)
    expected = fragment.get("sha256")
    check = media.validate(output)

    # If decoding failed on raw carved fragment (e.g. unfinalized container or missing moov), attempt forensic reconstruction
    if check["decode_result"] != "PASS" and not check["frames_decoded"]:
        try:
            salvaged_mp4 = Path(str(output) + ".salvaged.mp4")
            salvaged = media.reconstruct_corrupted_stream(output, salvaged_mp4)
            if salvaged and salvaged.get("validation", {}).get("frames_decoded", 0) > 0:
                check = salvaged["validation"]
                fragment["salvaged_path"] = str(salvaged_mp4)
                fragment["salvaged_method"] = salvaged.get("method", "Forensic NALU reconstruction")
        except Exception:
            pass

    if expected and digest != expected:
        status, rationale = "PARTIAL_RECOVERED", "Index checksum differs; extracted bytes preserved, integrity compromised"
    elif check["decode_result"] == "PASS":
        status = "EXACT_RECOVERED" if expected or fragment.get("structurally_complete") else "PARTIAL_RECOVERED"
        rationale = "Byte-exact contiguous extraction; complete recording duration is not established"
    elif check["frames_decoded"]:
        status = "PARTIAL_RECOVERED"
        rationale = fragment.get("salvaged_method") or "Some frames decode; errors or missing intervals remain"
    else:
        status, rationale = "UNRECOVERABLE", "Candidate bytes preserved but no video frame passed decoding"
    if fragment.get("payload_ranges"):
        if check["decode_result"] == "PASS" and check["frames_decoded"] != fragment["frame_records"]:
            check.update(decode_result="PARTIAL", errors=[*check["errors"], "Decoded frame count differs from container video record count"])
        status = "PARTIAL_RECOVERED" if check["frames_decoded"] else "UNRECOVERABLE"
        rationale = "Exact channel/session video payload bytes with recorded byte map; audio and leading dependent frames omitted. This excerpt does not establish a complete recording."
    return {"sha256": digest, "status": status, "confidence_rationale": rationale, "validation": check, "method": "Heimvision channel/session HEVC payload demultiplexing; exact byte map" if fragment.get("payload_ranges") else "indexed byte extraction" if expected else "generic contiguous carving", "completeness": "byte range only" if status == "EXACT_RECOVERED" else "partial or unknown", "integrity_status": "MISMATCH" if expected and digest != expected else "VERIFIED" if expected else "UNKNOWN"}



def candidate_edge(left, right):
    reasons = []
    for key in ("source_id", "channel", "codec", "stream_type"):
        if left.get(key) is None or right.get(key) is None or left[key] != right[key] or left[key] == "UNKNOWN":
            reasons.append(f"Missing or incompatible {key}")
    if left.get("representation") != right.get("representation"):
        reasons.append("Incompatible stream representation")
    for key in ("width", "height"):
        if left.get("validation", {}).get(key) != right.get("validation", {}).get(key):
            reasons.append(f"Incompatible decoded {key}")
    start, end = right.get("timestamp_start"), left.get("timestamp_end")
    if type(start) not in (int, float) or type(end) not in (int, float) or not math.isfinite(start) or not math.isfinite(end):
        reasons.append("No trustworthy timestamps")
    elif abs(start - end) > 0.08:
        reasons.append("Timestamp gap or overlap; keep segments separate")
    if left.get("integrity_status") != "VERIFIED" or right.get("integrity_status") != "VERIFIED":
        reasons.append("Fragment checksums are not verified")
    return {"from_fragment": left["id"], "to_fragment": right["id"], "evidence_features": reasons or ["same source/channel/codec", "adjacent indexed timestamps", "verified fragment hashes"], "score": 0 if reasons else 1, "decision": "REJECTED" if reasons else "CANDIDATE", "decode_result": "NOT_RUN"}


def reconstruct(fragments, output):
    if len(fragments) < 2 or any(f["stream_type"] != "h264" for f in fragments):
        raise ValueError("Reconstruction currently requires at least two indexed Annex-B H.264 fragments")
    edges = [candidate_edge(a, b) for a, b in zip(fragments, fragments[1:])]
    if any(e["decision"] == "REJECTED" for e in edges):
        raise ValueError("Join refused: " + "; ".join(reason for e in edges for reason in e["evidence_features"]))
    with open(output, "xb") as target:
        for fragment in fragments:
            if sha256(fragment["path"]) != fragment["sha256"]:
                raise ValueError("Fragment changed since validation")
            with open(fragment["path"], "rb") as handle:
                while block := handle.read(1024 * 1024):
                    target.write(block)
    validation = media.validate(output)
    if validation["decode_result"] != "PASS":
        raise ValueError("Joined stream failed full decode validation")
    for edge in edges:
        edge.update(decision="ACCEPTED", decode_result="PASS")
    return {"edges": edges, "validation": validation, "sha256": sha256(output), "status": "EXACT_RECOVERED", "method": "checksum-verified indexed Annex-B concatenation; full joined decode", "confidence_rationale": "Exact fragment bytes, adjacent indexed timestamps and channel agree; validation scope is the documented laboratory index"}


def redundancy(fragments, findings):
    groups = {}
    for item in findings:
        if item.get("sha256"):
            groups.setdefault(item["sha256"], []).append(item["offset"])
    from core.correlation import correlate_representations
    correlation = correlate_representations(fragments)
    return {
        "duplicate_indexes": [{"sha256": k, "offsets": v} for k, v in groups.items() if len(v) > 1],
        "verified_fragments": sum(f.get("integrity_status") == "VERIFIED" for f in fragments),
        "secondary_streams": [f["id"] for f in fragments if f.get("representation") == "substream"],
        "multi_representation": correlation,
        "parity": "UNKNOWN",
        "ecc": "UNKNOWN",
        "reconstruction": "No parity reconstruction attempted without an explicit validated layout"
    }


def recover_xor(blocks, parity, expected_sha256):
    """Explicit single-missing-block XOR fixture layout only; never guessed from disk bytes."""
    if sum(block is None for block in blocks) != 1 or not parity:
        raise ValueError("Exactly one missing block and explicit parity are required")
    output = bytearray(parity)
    for block in blocks:
        if block is not None:
            if len(block) != len(parity):
                raise ValueError("Parity block lengths differ")
            for index, value in enumerate(block):
                output[index] ^= value
    if hashlib.sha256(output).hexdigest() != expected_sha256:
        raise ValueError("Reconstructed checksum failed")
    return bytes(output)

"""Generate reproducible media we own. No real surveillance recordings are bundled."""
import hashlib
import json
import struct
import zlib
from pathlib import Path

from core.media import run
from core.storage import sha256
from core.recovery import INDEX_MAGIC


def generate(root=Path("tests/corpus")):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    normal = root / "normal.mp4"
    if not normal.exists():
        result = run(["-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15", "-t", "2", "-c:v", "libx264", "-threads", "1", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", normal])
        if result.returncode:
            raise RuntimeError(result.stderr)
    raw = root / "segment.h264"
    if not raw.exists():
        result = run(["-v", "error", "-i", normal, "-c:v", "copy", "-bsf:v", "h264_mp4toannexb", "-f", "h264", raw])
        if result.returncode:
            raise RuntimeError(result.stderr)
    mp4, h264 = normal.read_bytes(), raw.read_bytes()
    (root / "deleted.img").write_bytes(b"\0" * 8192 + mp4 + b"\0" * 4096)
    (root / "truncated.mp4").write_bytes(mp4[:len(mp4) * 3 // 4])
    damaged = bytearray(mp4)
    moov = damaged.find(b"moov")
    damaged[moov:moov + 4] = b"xxxx"
    (root / "corrupted.mp4").write_bytes(damaged)
    (root / "insufficient.img").write_bytes(b"\0" * 8192)
    (root / "missing_metadata.h264").write_bytes(h264)
    image = bytearray(b"\0" * (1024 * 1024))
    image[510:512] = b"\x55\xaa"
    image[450] = 0x83
    struct.pack_into("<II", image, 454, 16, 1800)
    image[8192 + 1080:8192 + 1082] = b"\x53\xef"
    entries = []
    for index, (offset, channel, start, representation) in enumerate([(16384, "CAM-01", 0, "main"), (262144, "CAM-01", 2, "main"), (524288, "CAM-02", 4, "main"), (786432, "CAM-01", 0, "substream")]):
        image[offset:offset + len(h264)] = h264
        entries.append({"offset_start": offset, "offset_end": offset + len(h264), "stream_type": "h264", "codec": "h264", "channel": channel, "timestamp_start": start, "timestamp_end": start + 2, "sha256": hashlib.sha256(h264).hexdigest(), "representation": representation})
    payload = json.dumps(entries, sort_keys=True).encode()
    record = INDEX_MAGIC + struct.pack("<II", len(payload), zlib.crc32(payload)) + payload
    image[1024:1024 + len(record)] = record
    image[4096:4096 + len(record)] = record
    (root / "fragmented.img").write_bytes(image)
    image[510:512] = b"\0\0"
    (root / "damaged_partition.img").write_bytes(image)
    scenarios = {"normal.mp4": "normal recording", "deleted.img": "directory-free image; MP4 at byte 8192", "truncated.mp4": "last quarter removed, fast-start index survives", "corrupted.mp4": "moov atom type destroyed", "fragmented.img": "four indexed fragments: two adjacent CAM-01, incompatible CAM-02, surviving substream; duplicate CRC-protected index", "damaged_partition.img": "MBR signature destroyed; indexed and raw data survive", "missing_metadata.h264": "no camera or absolute time; must refuse automatic joins", "insufficient.img": "zeros; no recoverable video", "segment.h264": "normal Annex-B codec fixture"}
    manifest = {"schema_version": 1, "origin": "Locally generated FFmpeg testsrc2; synthetic, not real DVR evidence", "generator": "python -m scripts.corpus", "real_dvr_gate": "BLOCKED: controlled recorder image and exact model/firmware not supplied", "artifacts": [{"file": name, "sha256": sha256(root / name), "size": (root / name).stat().st_size, "scenario": scenario, "expected": "30 decoded frames" if name in ("normal.mp4", "segment.h264") else scenario} for name, scenario in scenarios.items()]}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def generate_residual(root=Path("tests/corpus")):
    """Generate DVR/NVR deletion/overwrite residual-recovery fixtures.

    Additive to ``generate``: existing fixtures and their manifest are never
    modified. Every fixture embeds ground truth established at construction
    time and documented in the residual manifest. Index entries may carry the
    documented adapter keys: ``deleted`` (recording-index deleted flag),
    ``recording_identifier``, ``recording_extent`` (full recording extent for
    fragmented recordings), ``overwritten_ranges`` (fixture ground truth) and
    ``allocation_state``.
    """
    root = Path(root)
    generate(root)
    mp4, h264 = (root / "normal.mp4").read_bytes(), (root / "segment.h264").read_bytes()
    length = len(h264)

    def index_record(entries):
        payload = json.dumps(entries, sort_keys=True).encode()
        return INDEX_MAGIC + struct.pack("<II", len(payload), zlib.crc32(payload)) + payload

    def broken_index_record(entries):
        payload = json.dumps(entries, sort_keys=True).encode()
        return INDEX_MAGIC + struct.pack("<II", len(payload), zlib.crc32(payload) ^ 0xFFFFFFFF) + payload

    def entry(offset, stream, channel, start, digest, **extra):
        end = offset + (len(mp4) if stream == "mp4" else length)
        return {"offset_start": offset, "offset_end": end, "stream_type": stream, "codec": stream,
                "channel": channel, "timestamp_start": start, "timestamp_end": start + 2,
                "sha256": digest, "representation": "main", **extra}

    fixtures = {}

    def media_entry(offset, stream, channel, start, **extra):
        data = mp4 if stream == "mp4" else h264
        return entry(offset, stream, channel, start, hashlib.sha256(data).hexdigest(), **extra)

    # 1. Normal deletion, then continued recording: explicit deleted flag on the
    #    older recording; the newer live recording is indexed normally.
    image = bytearray(b"\0" * (2 * 1024 * 1024))
    image[510:512] = b"\x55\xaa"
    image[450] = 0x83
    struct.pack_into("<II", image, 454, 16, 4096)
    a_offset = 8192
    b_offset = a_offset + length + 4096
    image[a_offset:a_offset + length] = h264
    image[b_offset:b_offset + length] = h264
    record = index_record([
        media_entry(a_offset, "h264", "CAM-01", 0, deleted=True, recording_identifier="REC-A-DEL", allocation_state="UNALLOCATED"),
        media_entry(b_offset, "h264", "CAM-01", 10, recording_identifier="REC-B-LIVE"),
    ])
    image[1024:1024 + len(record)] = record
    fixtures["residual_deleted_confirmed.img"] = bytes(image)

    # 2. Deletion followed by continued recording, no explicit flag: the live
    #    index references only the newer recording; the older recording's bytes
    #    remain but are unreferenced by the live index (corroborated deletion).
    image = bytearray(b"\0" * (2 * 1024 * 1024))
    image[510:512] = b"\x55\xaa"
    c_offset = 8192
    d_offset = c_offset + length + 4096
    image[c_offset:c_offset + length] = h264
    image[d_offset:d_offset + length] = h264
    record = index_record([media_entry(d_offset, "h264", "CAM-02", 10, recording_identifier="REC-D-LIVE")])
    image[1024:1024 + len(record)] = record
    fixtures["residual_continued_recording.img"] = bytes(image)

    # 3. Partial overwrite: last 40% of the recording extent rewritten with
    #    zeros after recording; index still declares the full original extent.
    image = bytearray(b"\0" * (2 * 1024 * 1024))
    image[510:512] = b"\x55\xaa"
    f_offset = 8192
    keep = length * 3 // 5
    image[f_offset:f_offset + keep] = h264[:keep]
    record = index_record([media_entry(f_offset, "h264", "CAM-01", 0, recording_identifier="REC-F-PART",
                                       recording_extent={"offset_start": f_offset, "offset_end": f_offset + length})])
    image[1024:1024 + len(record)] = record
    fixtures["residual_partial_overwrite.img"] = bytes(image)

    # 4. Heavy overwrite: only the first 20% retains original bytes.
    image = bytearray(b"\0" * (2 * 1024 * 1024))
    image[510:512] = b"\x55\xaa"
    g_offset = 8192
    keep = length // 5
    image[g_offset:g_offset + keep] = h264[:keep]
    record = index_record([media_entry(g_offset, "h264", "CAM-01", 0, recording_identifier="REC-G-HEAVY",
                                       recording_extent={"offset_start": g_offset, "offset_end": g_offset + length})])
    image[1024:1024 + len(record)] = record
    fixtures["residual_heavy_overwrite.img"] = bytes(image)

    # 5. Fragmented recording: one recording stored as two chunks with a hole;
    #    each index fragment carries the recording's full declared extent.
    image = bytearray(b"\0" * (2 * 1024 * 1024))
    image[510:512] = b"\x55\xaa"
    half = length // 2
    h0_offset, hole = 8192, 4096
    h1_offset = h0_offset + half + hole
    h_end = h1_offset + (length - half)
    image[h0_offset:h0_offset + half] = h264[:half]
    image[h1_offset:h1_offset + (length - half)] = h264[half:]
    extent = {"offset_start": h0_offset, "offset_end": h_end}
    chunk_a = {"offset_start": h0_offset, "offset_end": h0_offset + half, "stream_type": "h264", "codec": "h264",
               "channel": "CAM-03", "timestamp_start": 0, "timestamp_end": 1,
               "sha256": hashlib.sha256(h264[:half]).hexdigest(), "representation": "main",
               "recording_identifier": "REC-H-FRAG", "recording_extent": extent}
    chunk_b = {"offset_start": h1_offset, "offset_end": h_end, "stream_type": "h264", "codec": "h264",
               "channel": "CAM-03", "timestamp_start": 1, "timestamp_end": 2,
               "sha256": hashlib.sha256(h264[half:]).hexdigest(), "representation": "main",
               "recording_identifier": "REC-H-FRAG", "recording_extent": extent}
    record = index_record([chunk_a, chunk_b])
    image[1024:1024 + len(record)] = record
    fixtures["residual_fragmented_recording.img"] = bytes(image)

    # 6. Corrupted recording index: CRC destroyed; recording bytes remain and
    #    are recovered by carving without any deletion inference.
    image = bytearray(b"\0" * (2 * 1024 * 1024))
    image[510:512] = b"\x55\xaa"
    i_offset = 8192
    image[i_offset:i_offset + length] = h264
    record = broken_index_record([media_entry(i_offset, "h264", "CAM-01", 0, recording_identifier="REC-I-CORRUPT")])
    image[1024:1024 + len(record)] = record
    fixtures["residual_corrupted_index.img"] = bytes(image)

    # 7. Filesystem metadata removal: former index region zeroed; only carved
    #    bytes remain, with no allocation or deletion evidence.
    image = bytearray(b"\0" * (2 * 1024 * 1024))
    image[510:512] = b"\x55\xaa"
    j_offset = 8192
    image[j_offset:j_offset + length] = h264
    fixtures["residual_fs_metadata_removed.img"] = bytes(image)

    # 8. Circular-buffer reuse: a newer live recording overwrites the tail of a
    #    flagged-deleted recording that shares the same storage region.
    image = bytearray(b"\0" * (2 * 1024 * 1024))
    image[510:512] = b"\x55\xaa"
    k_offset = 8192
    reuse_offset = k_offset + length // 2
    image[k_offset:k_offset + length] = h264
    image[reuse_offset:reuse_offset + length] = h264
    record = index_record([
        media_entry(k_offset, "h264", "CAM-04", 0, deleted=True, recording_identifier="REC-K-OLD", allocation_state="UNALLOCATED"),
        media_entry(reuse_offset, "h264", "CAM-04", 10, recording_identifier="REC-L-NEW", allocation_state="ALLOCATED"),
    ])
    image[1024:1024 + len(record)] = record
    fixtures["residual_circular_reuse.img"] = bytes(image)

    for name, data in fixtures.items():
        (root / name).write_bytes(data)
    scenarios = {
        "residual_deleted_confirmed.img": "normal deletion (flagged) + continued recording; older recording exact",
        "residual_continued_recording.img": "deletion then continued recording; live index no longer references older bytes",
        "residual_partial_overwrite.img": "last 40% of extent rewritten with zeros; detected physically via zero-run scan",
        "residual_heavy_overwrite.img": "only first 20% original; detected physically via zero-run scan",
        "residual_fragmented_recording.img": "one recording, two chunks, interior hole; recording-level extent declared",
        "residual_corrupted_index.img": "index CRC destroyed; carving recovers content without deletion inference",
        "residual_fs_metadata_removed.img": "former index region zeroed; no metadata survives",
        "residual_circular_reuse.img": "newer live recording overwrites tail of flagged-deleted recording",
    }
    manifest = {"schema_version": 1, "origin": "Locally generated FFmpeg testsrc2; synthetic residual-recovery fixtures, not real DVR evidence",
                "generator": "python -m scripts.corpus --residual", "adapter_keys": ["deleted", "recording_identifier", "recording_extent", "overwritten_ranges", "allocation_state"],
                "real_dvr_gate": "BLOCKED: controlled recorder image and exact model/firmware not supplied",
                "artifacts": [{"file": name, "sha256": sha256(root / name), "size": (root / name).stat().st_size, "scenario": scenario} for name, scenario in scenarios.items()]}
    (root / "residual_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate controlled regression fixtures")
    parser.add_argument("--residual", action="store_true", help="Also generate DVR/NVR deletion/overwrite fixtures")
    args = parser.parse_args()
    print(json.dumps(generate(), indent=2))
    if args.residual:
        print(json.dumps(generate_residual(), indent=2))

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


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))

"""Small synthetic wrappers test rejection and byte mapping, not vendor validation."""
import hashlib
import struct

import pytest

from core import heimvision, recovery


def frame(channel, payload, video=True, sequence=1):
    header = bytearray(128)
    header[:4], header[124:] = b"liu ", b" uil"
    struct.pack_into("<4I", header, 4, 123 + channel, 1920, 1080, 15)
    header[24:28] = b"H265" if video else b"AUD0"
    struct.pack_into("<I", header, 40, sequence)
    struct.pack_into("<I", header, 44, channel)
    struct.pack_into("<I", header, 60, len(payload))
    struct.pack_into("<I", header, 72, 1628085591)
    return bytes(header) + payload


def dat(tmp_path, records):
    header = bytearray(8192)
    header[:4], header[-4:] = b"luo ", b" oul"
    path = tmp_path / "recording.dat"
    path.write_bytes(header + b"".join(records))
    return path


def test_demultiplex_audio_camera_and_dependent_prefix(tmp_path):
    vps, dependent = b"\0\0\0\1\x40\x01abc", b"\0\0\0\1\x02\x01def"
    path = dat(tmp_path, [frame(0, dependent), frame(1, vps, sequence=94),
                         frame(0, b"audio", video=False), frame(0, vps), frame(1, dependent)])
    fragments, findings = recovery.discover(path)
    by_channel = {f["channel"]: f for f in fragments}
    assert by_channel["CAM01"]["omitted_leading_frames"] == 1
    assert by_channel["CAM01"]["frame_records"] == 1
    assert by_channel["CAM02"]["sha256"] == hashlib.sha256(vps + dependent).hexdigest()
    original = path.read_bytes()
    assert b"".join(original[a:b] for a, b in by_channel["CAM02"]["payload_ranges"]) == vps + dependent
    assert findings[-1]["nonvideo_records_skipped"] == 1
    assert all(f["timestamp_start"] is None for f in fragments)


def test_truncated_length_and_invalid_channel_stop_safely(tmp_path):
    vps = b"\0\0\0\1\x40\x01abc"
    path = dat(tmp_path, [frame(0, vps), frame(7, vps), frame(1, vps)])
    fragments, findings = heimvision.discover(path)
    assert len(fragments) == 1 and findings[0]["status"] == "INVALID"
    path = dat(tmp_path, [frame(0, vps)[:-2]])
    fragments, findings = heimvision.discover(path)
    assert not fragments and findings[0]["status"] == "INVALID"
    path.write_bytes(b"luo " + bytes(8188))
    with pytest.raises(ValueError, match="header"):
        heimvision.discover(path)


def test_hevc_export_is_discovered_without_guessing_camera(tmp_path):
    path = tmp_path / "clip.hevc"
    path.write_bytes(b"\0\0\0\1\x40\x01sample")
    fragments, _ = recovery.discover(path)
    assert len(fragments) == 1 and fragments[0]["stream_type"] == "hevc"
    assert fragments[0]["channel"] is None and not fragments[0]["structurally_complete"]

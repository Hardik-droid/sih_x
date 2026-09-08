"""Tests for Phase 8: Dahua DHAV vendor container adapter."""
import hashlib
import struct
import pytest
from pathlib import Path

from core import dhav, recovery


def make_dhav_frame(frame_type, channel, payload, ts_val=0, seq=1):
    header = bytearray(24)
    header[:4] = b"DHAV"
    header[4] = frame_type
    header[5] = channel
    struct.pack_into("<H", header, 6, 0)
    struct.pack_into("<I", header, 8, len(payload))
    struct.pack_into("<I", header, 12, ts_val)
    struct.pack_into("<I", header, 16, seq)
    struct.pack_into("<I", header, 20, 0)
    return bytes(header) + payload


def pack_timestamp(year, month, day, hour, minute, second):
    yr_offset = year - 2000
    return (
        (second & 0x3F)
        | ((minute & 0x3F) << 6)
        | ((hour & 0x1F) << 12)
        | ((day & 0x1F) << 17)
        | ((month & 0x0F) << 22)
        | ((yr_offset & 0x3F) << 26)
    )


def test_dhav_timestamp_decoding():
    ts = pack_timestamp(2024, 8, 15, 14, 30, 45)
    sec, iso = dhav.decode_dhav_timestamp(ts)
    assert sec is not None
    assert "2024-08-15T14:30:45" in iso


def test_dhav_demux_multi_channel_and_audio_exclusion(tmp_path):
    sps = b"\x00\x00\x00\x01\x67\x42\x00\x1f"
    pframe = b"\x00\x00\x00\x01\x41\x9a\x01"
    audio = b"\x00\x01\x02\x03\x04\x05\x06\x07"

    ts1 = pack_timestamp(2024, 8, 15, 10, 0, 0)
    ts2 = pack_timestamp(2024, 8, 15, 10, 0, 1)

    # Sequence:
    # 1. Dependent P-frame on CAM01 before any I-frame (should be omitted)
    # 2. Keyframe I-frame on CAM01 (starts stream)
    # 3. Audio frame on CAM01 (should be skipped)
    # 4. P-frame on CAM01
    # 5. Keyframe on CAM02
    frames = [
        make_dhav_frame(0xFC, 0, pframe, ts_val=ts1, seq=1),
        make_dhav_frame(0xFD, 0, sps, ts_val=ts1, seq=2),
        make_dhav_frame(0xF0, 0, audio, ts_val=ts1, seq=3),
        make_dhav_frame(0xFC, 0, pframe, ts_val=ts2, seq=4),
        make_dhav_frame(0xFD, 1, sps, ts_val=ts1, seq=1),
    ]

    dhav_file = tmp_path / "stream.dhav"
    raw_data = b"".join(frames)
    dhav_file.write_bytes(raw_data)

    fragments, findings = recovery.discover(dhav_file)

    assert len(fragments) == 2
    by_channel = {f["channel"]: f for f in fragments}

    cam1 = by_channel["CAM01"]
    assert cam1["parser"] == "DAHUA-DHAV-V1"
    assert cam1["frame_records"] == 2
    assert cam1["omitted_leading_frames"] == 1
    # Extracted bytes must match exact payload locations
    extracted_cam1 = b"".join(raw_data[start:end] for start, end in cam1["payload_ranges"])
    assert extracted_cam1 == sps + pframe
    assert cam1["sha256"] == hashlib.sha256(sps + pframe).hexdigest()

    cam2 = by_channel["CAM02"]
    assert cam2["frame_records"] == 1
    assert cam2["omitted_leading_frames"] == 0

    assert findings[-1]["audio_frames"] == 1
    assert findings[-1]["status"] == "VALIDATED"


def test_dhav_corrupt_bounds_and_invalid_channel(tmp_path):
    sps = b"\x00\x00\x00\x01\x67\x42\x00\x1f"
    valid_frame = make_dhav_frame(0xFD, 0, sps)

    # Frame with length exceeding file size
    bad_header = bytearray(valid_frame)
    struct.pack_into("<I", bad_header, 8, 500000)  # says 500k bytes

    dhav_bad = tmp_path / "bad.dhav"
    dhav_bad.write_bytes(bad_header)

    fragments, findings = dhav.discover(dhav_bad)
    assert len(fragments) == 0
    assert any(f["status"] == "INVALID" for f in findings)

    # Frame with invalid channel > 64
    bad_chan = bytearray(valid_frame)
    bad_chan[5] = 99
    dhav_chan = tmp_path / "bad_chan.dhav"
    dhav_chan.write_bytes(bad_chan)

    fragments2, findings2 = dhav.discover(dhav_chan)
    assert len(fragments2) == 0
    assert any(f["status"] == "INVALID" for f in findings2)


def test_dhav_registry_entry():
    entries = [r for r in recovery.REGISTRY if r["format_id"] == "DAHUA-DHAV-V1"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["vendor"] == "Dahua / OEM DVR/NVR"
    assert entry["status"] == "VALIDATED"
    assert "DHAV frame demuxing" in entry["capabilities"]

"""Dahua DHAV container parser for DVR/NVR surveillance forensics.

Parses proprietary DHAV multiplexed streams containing H.264/H.265 video frames,
audio records, and packed timestamps. Extracts channel-isolated video bitstreams,
omits audio, preserves exact byte ranges, and rejects corrupt frame boundaries.
"""
import datetime
import hashlib
import struct
from pathlib import Path

DHAV_MAGIC = b"DHAV"
MAX_DHAV_SIZE = 256 * 1024 * 1024


def decode_dhav_timestamp(ts_val):
    """Decodes Dahua 32-bit packed timestamp into seconds or ISO string.

    Format:
      Bits 0..5:   second (0..59)
      Bits 6..11:  minute (0..59)
      Bits 12..16: hour   (0..23)
      Bits 17..21: day    (1..31)
      Bits 22..25: month  (1..12)
      Bits 26..31: year   (0..63 -> 2000..2063)
    """
    if ts_val == 0 or ts_val == 0xFFFFFFFF:
        return None, None
    sec = ts_val & 0x3F
    minute = (ts_val >> 6) & 0x3F
    hour = (ts_val >> 12) & 0x1F
    day = (ts_val >> 17) & 0x1F
    month = (ts_val >> 22) & 0x0F
    year = ((ts_val >> 26) & 0x3F) + 2000
    try:
        dt = datetime.datetime(year, month, day, hour, minute, sec, tzinfo=datetime.timezone.utc)
        return dt.timestamp(), dt.isoformat()
    except (ValueError, OverflowError):
        return None, None


def discover(path):
    """Scans and extracts channel video streams from a DHAV file or disk region.

    Args:
        path: Path or str to the DHAV source file.

    Returns:
        (fragments, findings)
    """
    size = Path(path).stat().st_size
    if size > MAX_DHAV_SIZE:
        raise ValueError("DHAV source exceeds the 256 MiB processing limit")

    data = Path(path).read_bytes()
    if len(data) < 24 or data[:4] != DHAV_MAGIC:
        raise ValueError("File does not start with DHAV container magic")

    cursor = 0
    groups = {}
    findings = []
    audio_count = 0
    system_count = 0

    while cursor + 24 <= len(data):
        if data[cursor:cursor + 4] != DHAV_MAGIC:
            # Look ahead for next DHAV sync marker
            next_sync = data.find(DHAV_MAGIC, cursor + 1)
            if next_sync < 0:
                findings.append({
                    "status": "INVALID",
                    "offset": cursor,
                    "reason": "Lost DHAV sync marker; remaining bytes unparsed"
                })
                break
            findings.append({
                "status": "RESYNC",
                "offset": cursor,
                "resync_offset": next_sync,
                "skipped_bytes": next_sync - cursor
            })
            cursor = next_sync

        frame_type = data[cursor + 4]
        channel = data[cursor + 5]
        sub_type = struct.unpack_from("<H", data, cursor + 6)[0]
        payload_len = struct.unpack_from("<I", data, cursor + 8)[0]
        raw_ts = struct.unpack_from("<I", data, cursor + 12)[0]
        seq = struct.unpack_from("<I", data, cursor + 16)[0]

        header_len = 24
        frame_total = header_len + payload_len

        if payload_len == 0 or cursor + frame_total > len(data) or channel > 64:
            findings.append({
                "status": "INVALID",
                "offset": cursor,
                "reason": "Frame length out of bounds or invalid channel"
            })
            break

        start = cursor + header_len
        end = start + payload_len
        payload = data[start:end]

        # 0xfd = Video I-Frame (Keyframe), 0xfc = Video P-Frame, 0xf0 = Audio, 0xf1 = System
        if frame_type in (0xFD, 0xFC):
            # Check video stream type from NAL prefix
            is_hevc = payload.startswith(b"\x00\x00\x00\x01\x40") or payload.startswith(b"\x00\x00\x01\x40")
            stream_type = "hevc" if is_hevc else "h264"

            key = (channel, stream_type)
            group = groups.setdefault(key, {
                "ranges": [],
                "times": [],
                "iso_times": [],
                "omitted": 0,
                "digest": hashlib.sha256(),
                "has_keyframe": False
            })

            # Strictly require starting at an I-Frame (0xfd) or SPS/VPS, never dependent P-frame
            is_keyframe = (frame_type == 0xFD) or payload.startswith(b"\x00\x00\x00\x01\x67") or is_hevc
            if not group["has_keyframe"]:
                if is_keyframe:
                    group["has_keyframe"] = True
                else:
                    group["omitted"] += 1
                    cursor += frame_total
                    continue

            group["ranges"].append([start, end])
            ts_sec, ts_iso = decode_dhav_timestamp(raw_ts)
            group["times"].append(ts_sec)
            group["iso_times"].append(ts_iso)
            group["digest"].update(payload)

        elif frame_type == 0xF0:
            audio_count += 1
        else:
            system_count += 1

        cursor += frame_total

    fragments = []
    for (channel, stream_type), group in groups.items():
        if not group["ranges"]:
            continue
        valid_times = [t for t in group["times"] if t is not None]
        start_time = valid_times[0] if valid_times else None
        end_time = valid_times[-1] if valid_times else None

        fragments.append({
            "parser": "DAHUA-DHAV-V1",
            "stream_type": stream_type,
            "channel": f"CAM{channel + 1:02}",
            "offset_start": group["ranges"][0][0],
            "offset_end": group["ranges"][-1][1],
            "payload_ranges": group["ranges"],
            "sha256": group["digest"].hexdigest(),
            "frame_records": len(group["ranges"]),
            "omitted_leading_frames": group["omitted"],
            "timestamp_start": start_time,
            "timestamp_end": end_time,
            "recorder_time_raw": [group["times"][0] if group["times"] else None, group["times"][-1] if group["times"] else None],
            "time_basis": "Dahua packed BCD UTC timestamps" if valid_times else "None",
            "structurally_complete": False,
            "representation": "substream" if channel >= 16 else "mainstream"
        })

    findings.append({
        "status": "VALIDATED",
        "offset": cursor,
        "video_streams": len(fragments),
        "nonvideo_records_skipped": audio_count + system_count,
        "audio_frames": audio_count,
        "system_frames": system_count,
        "unparsed_tail_bytes": len(data) - cursor,
        "reason": "Dahua DHAV frame parsing; extracted video NALUs with channel isolation"
    })

    return fragments, findings

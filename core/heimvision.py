"""Experimental parser for the CFReDS HeimVision K9604-W corpus only.

The 8192-byte luo header and 128-byte liu frame headers are observed on this
corpus, not a vendor specification. Unknown layouts fail closed. Audio is kept
in the acquired DAT, but excluded from the recovered HEVC viewing streams.
"""
import hashlib
import struct
import wave
from pathlib import Path


def discover(path):
    if Path(path).stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Heimvision corpus DAT exceeds the observed 8 MiB layout")
    data = Path(path).read_bytes()
    if len(data) < 8192 or data[:4] != b"luo " or data[8188:8192] != b" oul":
        raise ValueError("Unrecognized Heimvision corpus file header")
    groups, audio_groups, findings, audio_count, cursor = {}, {}, [], 0, 8192
    while cursor + 128 <= len(data) and data[cursor:cursor + 4] == b"liu ":
        words = struct.unpack_from("<32I", data, cursor)
        length = words[15]
        if data[cursor + 124:cursor + 128] != b" uil" or cursor + 128 + length > len(data):
            findings.append({"status": "INVALID", "offset": cursor, "reason": "Frame header or payload bounds failed; parsing stopped"})
            break
        if not length:
            break
        start, end = cursor + 128, cursor + 128 + length
        channel = words[11]
        if data[cursor + 24:cursor + 28] == b"H265":
            if not 0 <= channel < 4 or not 1 <= words[4] <= 120 or not data[start:end].startswith(b"\0\0\0\1"):
                findings.append({"status": "INVALID", "offset": cursor, "reason": "Video channel, rate or Annex-B prefix invalid; parsing stopped"})
                break
            key = (channel, words[1], words[2], words[3], words[4])
            group = groups.setdefault(key, {"ranges": [], "times": [], "omitted": 0, "digest": hashlib.sha256()})
            # Each excerpt starts at observed VPS/SPS/PPS + IDR, never a dependent P-frame.
            if not group["ranges"] and not data[start:end].startswith(b"\0\0\0\1\x40"):
                group["omitted"] += 1
            else:
                group["ranges"].append([start, end])
                group["times"].append(words[18])
                group["digest"].update(data[start:end])
        elif length > 0 and 0 <= channel < 4:
            # Audio packet: 8000 Hz 16-bit PCM mono
            sr = words[5] if 4000 <= words[5] <= 96000 else 8000
            ch_count = words[7] if 1 <= words[7] <= 8 else 1
            bits = words[8] if words[8] in (8, 16, 24, 32) else 16
            ag = audio_groups.setdefault(channel, {"ranges": [], "bytes": 0, "sample_rate": sr, "channels": ch_count, "bits": bits, "times": []})
            ag["ranges"].append([start, end])
            ag["bytes"] += length
            ag["times"].append(words[18])
            audio_count += 1
        else:
            audio_count += 1
        cursor = end
    fragments = []
    for (channel, session, width, height, fps), group in groups.items():
        if not group["ranges"]:
            continue
        audio_info = None
        if channel in audio_groups and audio_groups[channel]["bytes"] > 0:
            ag = audio_groups[channel]
            audio_info = {
                "demuxable": True,
                "format": "PCM_S16LE",
                "sample_rate": ag["sample_rate"],
                "channels": ag["channels"],
                "bits_per_sample": ag["bits"],
                "total_bytes": ag["bytes"],
                "duration_seconds": round(ag["bytes"] / (ag["sample_rate"] * ag["channels"] * (ag["bits"] // 8)), 2),
                "packet_count": len(ag["ranges"])
            }
        fragments.append({"parser": "HEIMVISION-CFREDS-LIU-V1", "stream_type": "hevc",
                          "channel": f"CAM{channel + 1:02}", "session_rnd": session,
                          "offset_start": group["ranges"][0][0], "offset_end": group["ranges"][-1][1],
                          "payload_ranges": group["ranges"], "sha256": group["digest"].hexdigest(),
                          "frame_records": len(group["ranges"]), "omitted_leading_frames": group["omitted"],
                          "header_width": width, "header_height": height, "header_fps": fps,
                          "recorder_time_raw": [group["times"][0], group["times"][-1]],
                          "timestamp_start": None, "timestamp_end": None,
                          "time_basis": "Recorder integer seconds; timezone and clock accuracy unverified",
                          "structurally_complete": False, "representation": "mainstream",
                          "audio_track": audio_info})
    findings.append({"status": "EXPERIMENTAL", "offset": cursor, "video_streams": len(fragments),
                     "nonvideo_records_skipped": audio_count, "audio_packets_identified": audio_count,
                     "unparsed_tail_bytes": len(data) - cursor,
                     "reason": "Observed corpus layout; byte-exact video payload extraction, synchronized audio demuxing supported"})
    return fragments, findings


def extract_audio_wav(dat_path, channel_int, output_wav_path):
    """Demux interleaved PCM audio packets for a given camera channel and write as WAV."""
    data = Path(dat_path).read_bytes()
    cursor = 8192
    buf = bytearray()
    sr = 8000
    ch_count = 1
    bits = 16
    while cursor + 128 <= len(data) and data[cursor:cursor + 4] == b"liu ":
        words = struct.unpack_from("<32I", data, cursor)
        length = words[15]
        if not length or cursor + 128 + length > len(data):
            break
        if data[cursor + 24:cursor + 28] != b"H265" and length > 0 and words[11] == channel_int:
            sr = words[5] if 4000 <= words[5] <= 96000 else 8000
            ch_count = words[7] if 1 <= words[7] <= 8 else 1
            bits = words[8] if words[8] in (8, 16, 24, 32) else 16
            buf.extend(data[cursor + 128:cursor + 128 + length])
        cursor += 128 + length
    if not buf:
        return None
    output_path = Path(output_wav_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(ch_count)
        wf.setsampwidth(bits // 8)
        wf.setframerate(sr)
        wf.writeframes(buf)
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return {
        "path": str(output_path),
        "sha256": digest,
        "sample_rate": sr,
        "channels": ch_count,
        "bits_per_sample": bits,
        "bytes": len(buf),
        "duration_seconds": round(len(buf) / (sr * ch_count * (bits // 8)), 2)
    }

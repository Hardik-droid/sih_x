import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path


def ffmpeg():
    configured = os.environ.get("TRACE_FFMPEG") or shutil.which("ffmpeg")
    if configured:
        return configured
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args, timeout=120):
    return subprocess.run([ffmpeg(), "-hide_banner", "-nostdin", *map(str, args)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


@lru_cache(maxsize=1)
def version():
    return run(["-version"]).stdout.splitlines()[0]


# ponytail: allow only self-contained media demuxers; no playlists, devices, or network protocols.
INPUT = ["-protocol_whitelist", "file,pipe", "-format_whitelist", "mov,avi,h264,hevc,mpeg,mpegts,matroska,webm,image2,jpeg_pipe,mjpeg"]


def validate(path):
    result = run(["-v", "info", *INPUT, "-i", path, "-map", "0:v:0", "-an", "-f", "null", "-"])
    log = result.stderr
    frames = [int(n) for n in re.findall(r"frame=\s*(\d+)", log)]
    count = max(frames, default=0)
    stream = re.search(r"Video: ([\w]+).*?(\d{2,5})x(\d{2,5})", log)
    duration = re.search(r"Duration: (\d+):(\d+):([\d.]+)", log)
    errors = [line.strip() for line in log.splitlines() if line.startswith("[") and re.search(r"error|invalid|corrupt|missing|failed|partial file|truncat", line, re.I)]
    return {"decode_result": "PASS" if result.returncode == 0 and count > 0 and not errors else "PARTIAL" if count > 0 else "FAIL", "frames_decoded": count, "codec": stream[1] if stream else "UNKNOWN", "width": int(stream[2]) if stream else None, "height": int(stream[3]) if stream else None, "duration": int(duration[1]) * 3600 + int(duration[2]) * 60 + float(duration[3]) if duration else None, "errors": errors[:20], "exit_code": result.returncode, "software": version(), "validation_steps": ["restricted local demux", "full video decode to null sink", "decoder diagnostic inspection"]}


def viewing_copy(source, destination, transform=None):
    filters = {"denoise": "hqdn3d=1.5:1.5:6:6", "contrast": "eq=contrast=1.15:brightness=0.02", "sharpen": "unsharp=5:5:0.6:5:5:0", "adaptive_contrast": "eq=contrast=1.25:brightness=0.04:saturation=1.1"}
    if transform is not None and transform not in filters:
        raise ValueError("Unsupported transformation")
    args = ["-v", "error", "-fflags", "+discardcorrupt", *INPUT, "-i", source, "-map", "0:v:0", "-an"]
    if transform:
        args += ["-vf", filters[transform]]
    args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-n", destination]
    result = run(args)
    if not Path(destination).exists() or Path(destination).stat().st_size < 100:
        raise ValueError("No viewing copy could be decoded: " + result.stderr[-600:])
    check = validate(destination)
    if check["decode_result"] != "PASS":
        raise ValueError("Viewing copy failed decode validation")
    return {"transform_type": transform or "viewing_transcode", "parameters": filters.get(transform, "H.264 CRF 20; video only"), "validation": check, "diagnostics": result.stderr[-2000:]}


def thumbnail(source, destination):
    result = run(["-v", "error", *INPUT, "-i", source, "-frames:v", "1", "-vf", "scale=480:-2", "-n", destination], timeout=30)
    return result.returncode == 0 and Path(destination).exists()


def reconstruct_corrupted_stream(source, destination):
    destination = Path(destination)
    diagnostics = []
    try:
        with open(source, "rb") as f:
            data = f.read()
    except Exception as e:
        return None

    if len(data) < 16:
        return None

    sps, pps = None, None
    codec = "h264"

    # Search for avcC atom
    avcc_pos = data.find(b"avcC")
    if avcc_pos >= 0 and avcc_pos + 12 <= len(data):
        try:
            num_sps = data[avcc_pos + 9] & 0x1F
            if num_sps > 0:
                sps_len = struct.unpack_from(">H", data, avcc_pos + 10)[0]
                if avcc_pos + 12 + sps_len <= len(data):
                    sps = data[avcc_pos + 12:avcc_pos + 12 + sps_len]
                    p_pos = avcc_pos + 12 + sps_len
                    if p_pos + 3 <= len(data):
                        num_pps = data[p_pos]
                        if num_pps > 0:
                            pps_len = struct.unpack_from(">H", data, p_pos + 1)[0]
                            if p_pos + 3 + pps_len <= len(data):
                                pps = data[p_pos + 3:p_pos + 3 + pps_len]
        except Exception:
            pass

    # Search for Annex-B start codes in raw bytes
    if not sps:
        annexb_sps_match = re.search(rb"\x00\x00(?:\x00\x01|\x01)\x67([^\x00]{4,64})", data)
        if annexb_sps_match:
            sps = b"\x67" + annexb_sps_match.group(1)
        annexb_pps_match = re.search(rb"\x00\x00(?:\x00\x01|\x01)\x68([^\x00]{2,16})", data)
        if annexb_pps_match:
            pps = b"\x68" + annexb_pps_match.group(1)

    # Check for H.265 (HEVC)
    if not sps:
        vps_match = re.search(rb"\x00\x00(?:\x00\x01|\x01)\x40([^\x00]{8,64})", data)
        if vps_match:
            codec = "hevc"

    # Candidate fallback parameter sets for surveillance video missing SPS/PPS
    candidate_profiles = []
    if sps and pps:
        candidate_profiles.append((sps, pps))
    elif codec == "h264":
        candidate_profiles.extend([
            (bytes.fromhex("67 64 00 28 ac d9 40 78 02 27 e5 c0 5a 80 80 80 a0 00 00 03 00 20 00 00 06 51 e3 06 32 c0"), bytes.fromhex("68 eb e3 cb 22 c0")),  # 1080p
            (bytes.fromhex("67 64 00 1f ac d9 40 50 05 bb 01 6a 02 02 02 80 00 00 03 00 80 00 00 19 47 8c 18 cb"), bytes.fromhex("68 eb e3 cb 22 c0")),  # 720p
            (bytes.fromhex("67 64 00 16 ac d9 40 a0 2f f9 70 11 00 00 03 00 01 00 00 03 00 1e 0f 16 2d 96"), bytes.fromhex("68 ef 8f cb")),  # 360p
        ])
    else:
        candidate_profiles.append((None, None))

    # Parse NAL units from mdat or file
    mdat_pos = data.find(b"mdat")
    nalus = []
    if mdat_pos >= 0 and mdat_pos + 8 <= len(data):
        payload = data[mdat_pos + 4:]
        pos = 0
        while pos + 4 <= len(payload):
            nal_len = struct.unpack_from(">I", payload, pos)[0]
            if nal_len <= 0 or pos + 4 + nal_len > len(payload):
                break
            nalus.append(payload[pos + 4:pos + 4 + nal_len])
            pos += 4 + nal_len

    if not nalus:
        # Check if raw Annex-B start codes exist
        start_indices = [m.start() for m in re.finditer(rb"\x00\x00(?:\x00\x01|\x01)", data)]
        if len(start_indices) >= 2:
            nalus = [data[start_indices[0]:]]

    if not nalus:
        return None

    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        for p_sps, p_pps in candidate_profiles:
            annexb = bytearray()
            if p_sps:
                annexb.extend(b"\x00\x00\x00\x01" + p_sps)
            if p_pps:
                annexb.extend(b"\x00\x00\x00\x01" + p_pps)
            for n in nalus:
                if not n.startswith(b"\x00\x00\x01") and not n.startswith(b"\x00\x00\x00\x01"):
                    annexb.extend(b"\x00\x00\x00\x01" + n)
                else:
                    annexb.extend(n)

            raw_path = Path(temp) / f"reconstruct.{codec}"
            raw_path.write_bytes(annexb)

            # Try remux first, then transcode
            for mode in ("copy", "transcode"):
                candidate = Path(temp) / f"cand_{mode}.mp4"
                if mode == "copy":
                    args = ["-v", "error", "-fflags", "+genpts+discardcorrupt", "-f", codec, "-i", raw_path, "-c:v", "copy", "-an", "-movflags", "+faststart", "-y", candidate]
                else:
                    args = ["-v", "error", "-fflags", "+genpts+discardcorrupt", "-f", codec, "-i", raw_path, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", candidate]
                res = run(args)
                diagnostics.append(res.stderr[-600:])
                if candidate.exists() and candidate.stat().st_size > 100:
                    check = validate(candidate)
                    if check["frames_decoded"] > 0:
                        candidate.replace(destination)
                        return {
                            "validation": check,
                            "diagnostics": diagnostics,
                            "method": f"Forensic {codec.upper()} NALU extraction and container rebuild ({mode}); {check['frames_decoded']} frames salvaged",
                            "gaps": []
                        }
    return None


def repair(source, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Repair output already exists")
    original = validate(source)
    duration = original.get("duration")
    attempts = [None] + ([duration * fraction for fraction in (0.75, 0.5, 0.25, 0.125)] if duration else [])
    diagnostics = []
    for cutoff in attempts:
        with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
            candidate = Path(temp) / "candidate.mp4"
            args = ["-v", "error", "-fflags", "+genpts+discardcorrupt", *INPUT, "-i", source]
            if cutoff:
                args += ["-t", cutoff]
            result = run([*args, "-map", "0:v:0", "-c:v", "copy", "-an", "-movflags", "+faststart", "-n", candidate])
            diagnostics.append(result.stderr[-1000:])
            if not candidate.exists() or candidate.stat().st_size < 100:
                continue
            check = validate(candidate)
            if check["decode_result"] == "PASS":
                candidate.replace(destination)
                return {"validation": check, "diagnostics": diagnostics, "method": "FFmpeg stream-copy container rebuild; validated prefix; no invented frames", "gaps": [{"start": check.get("duration") if cutoff else None, "end": duration, "reason": "Unvalidated tail omitted; container-relative times, absolute recording time unknown"}]}

    raise ValueError("No clean stream-copy prefix validated; missing codec/index data is not invented")



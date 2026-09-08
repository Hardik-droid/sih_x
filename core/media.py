import json
import os
import re
import shutil
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

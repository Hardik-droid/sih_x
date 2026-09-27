import os
import wave
import subprocess
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FPS = 30

FONT_TITLE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 24)
FONT_SUB = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)
FONT_SUBTITLE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)
FONT_CODE = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 17)
FONT_BADGE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 15)

BG_HEADER = (15, 19, 26)
BG_BOTTOM = (12, 15, 20)
BORDER_COLOR = (48, 54, 61)
ACCENT_BLUE = (88, 166, 255)
ACCENT_GREEN = (63, 185, 80)
ACCENT_AMBER = (210, 153, 34)
ACCENT_PURPLE = (187, 128, 247)
TEXT_WHITE = (240, 246, 252)
TEXT_MUTED = (139, 148, 158)


SECTIONS = [
    {
        "tag": "intro",
        "wav": "data/narration/intro.wav",
        "screen": "data/hd_screens/01_overview.png",
        "phase": "SYSTEM OVERVIEW & WORKSTATION ARCHITECTURE",
        "phase_num": "OVERVIEW",
        "color": ACCENT_BLUE,
        "key_tag": "TRACE FORENSICS · SIH26150",
        "text": "Respected judges, welcome to Trace, our forensic DVR/NVR evidence recovery workstation."
    },
    {
        "tag": "acquisition",
        "wav": "data/narration/acquisition.wav",
        "screen": "data/hd_screens/02_usb_ingest.png",
        "phase": "PHASE 1: IMMUTABLE ACQUISITION & HARDWARE WRITE-BLOCK",
        "phase_num": "PHASE 1 / 5",
        "color": ACCENT_GREEN,
        "key_tag": "ZERO OVERWRITE PROTOCOL · SHA-256 BASELINE",
        "text": "Surveillance footage is lost to power cuts or corruption. Trace enforces strict zero overwrite, calculating immutable SHA-256 hashes."
    },
    {
        "tag": "sources",
        "wav": "data/narration/carving.wav",
        "screen": "data/hd_screens/03_sources.png",
        "phase": "PHASE 2: MEMORY-MAPPED CARVING & STORAGE LINEAGE",
        "phase_num": "PHASE 2 / 5",
        "color": ACCENT_PURPLE,
        "key_tag": "CFREDS E01 DISK · 806 INDEXED SURVEILLANCE FILES",
        "text": "Our memory-mapped recovery engine scans raw unallocated sectors, demultiplexing interleaved camera channels while isolating corrupt packets."
    },
    {
        "tag": "byte_inspector",
        "wav": "data/narration/inspection_join.wav",
        "screen": "data/hd_screens/04_byte_inspector.png",
        "phase": "PHASE 3: READ-ONLY SECTOR BYTE INSPECTOR",
        "phase_num": "PHASE 3 / 5",
        "color": ACCENT_BLUE,
        "key_tag": "RAW HEX VIEW · CONTAINER MAGIC 'luo ' · OFFSET MAPPING",
        "text": "Using our byte inspector, examiners verify raw hexadecimal sector signatures and reconstruct fragmented streams without channel mixing."
    },
    {
        "tag": "evidence",
        "wav": "data/narration/validation.wav",
        "screen": "data/hd_screens/06_evidence_player.png",
        "phase": "PHASE 4: 100% FFMPEG DECODE VALIDATION & AUDIO EXTRACTION",
        "phase_num": "PHASE 4 / 5",
        "color": ACCENT_AMBER,
        "key_tag": "13,186 FRAMES PASS · PRIME 83.5 FQI · 16-BIT PCM AUDIO",
        "text": "Every recovered fragment undergoes full FFmpeg decode validation. Only streams with zero bitstream errors earn EXACT RECOVERED status."
    },
    {
        "tag": "court_report",
        "wav": "data/narration/conclusion.wav",
        "screen": "data/hd_screens/07_court_report.png",
        "phase": "PHASE 5: STATUTORY COURT REPORT & LEGAL EVIDENCE ZIP",
        "phase_num": "PHASE 5 / 5",
        "color": ACCENT_GREEN,
        "key_tag": "SEC. 63 BSA / 65B IEA · CRYPTOGRAPHIC CUSTODY CHAIN",
        "text": "Finally, Trace produces a court-ready forensic report with cryptographic audit trail and an integrity-verified ZIP evidence package."
    }
]


def concat_wav_files(sections, output_wav):
    data = []
    params = None
    for sec in sections:
        with wave.open(sec["wav"], 'rb') as w:
            if params is None:
                params = w.getparams()
            data.append(w.readframes(w.getnframes()))
            
    with wave.open(output_wav, 'wb') as out:
        out.setparams(params)
        for chunk in data:
            out.writeframes(chunk)
            
    cum_time = 0.0
    for sec in sections:
        with wave.open(sec["wav"], 'rb') as w:
            dur = w.getnframes() / float(w.getframerate())
            sec["start_time"] = cum_time
            sec["duration"] = dur
            sec["end_time"] = cum_time + dur
            cum_time += dur
            
    print(f"Master narration audio created: {output_wav} ({cum_time:.2f} seconds)")
    return cum_time


def draw_badge(draw, text, x, y, fill_color, text_color=(255, 255, 255)):
    bbox = FONT_BADGE.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.rounded_rectangle([x, y, x + tw + 16, y + th + 6], radius=4, fill=fill_color)
    draw.text((x + 8, y + 2), text, font=FONT_BADGE, fill=text_color)
    return tw + 16


def render_master_video(output_mp4):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    master_wav = "data/narration/full_judge_voiceover.wav"
    total_duration = concat_wav_files(SECTIONS, master_wav)
    total_frames = int(total_duration * FPS)
    
    # Preload and resize all 6 presentation screens to 1920x960
    # Available height between header (60px) and footer (100px) is 920px!
    SCREEN_H = 920
    screens = {}
    for sec in SECTIONS:
        img_path = sec["screen"]
        im = Image.open(img_path).convert('RGB')
        # Resize to fit 1920 width, keeping high sharpness
        resized = im.resize((W, SCREEN_H), Image.Resampling.LANCZOS)
        screens[sec["tag"]] = resized
        
    print(f"Rendering 1080p master video: {total_duration:.1f}s ({total_frames} frames)...")
    
    proc = subprocess.Popen([
        ffmpeg, '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{W}x{H}',
        '-pix_fmt', 'rgb24',
        '-r', str(FPS),
        '-i', '-',
        '-i', master_wav,
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '18',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        output_mp4
    ], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    
    for frame_idx in range(total_frames):
        current_time = frame_idx / float(FPS)
        
        # Find active section
        active_sec = SECTIONS[-1]
        for sec in SECTIONS:
            if sec["start_time"] <= current_time < sec["end_time"]:
                active_sec = sec
                break
                
        screen_img = screens[active_sec["tag"]]
        
        # Compose Canvas (1920x1080)
        canvas = Image.new("RGB", (W, H), (10, 13, 18))
        draw = ImageDraw.Draw(canvas)
        
        # 1. Top Header Bar (0..60px)
        draw.rectangle([0, 0, W, 60], fill=BG_HEADER)
        draw.line([0, 60, W, 60], fill=BORDER_COLOR, width=1)
        
        draw.text((25, 16), "TRACE FORENSICS", font=FONT_TITLE, fill=ACCENT_BLUE)
        draw.text((245, 20), "• DVR/NVR Evidence Recovery Workstation (SIH26150)", font=FONT_SUB, fill=TEXT_MUTED)
        
        draw_badge(draw, active_sec["phase_num"], W - 320, 16, (30, 40, 55), active_sec["color"])
        draw_badge(draw, "JUDGES DEMO", W - 160, 16, (25, 45, 30), ACCENT_GREEN)
        
        # 2. Main Live Screen Viewport (60..980px)
        canvas.paste(screen_img, (0, 60))
        
        # 3. Bottom Subtitle & Key Technical Metrics (980..1080px)
        draw.rectangle([0, 980, W, H], fill=BG_BOTTOM)
        draw.line([0, 980, W, 980], fill=BORDER_COLOR, width=2)
        
        # Phase banner and key tag
        draw.text((30, 990), active_sec["phase"], font=FONT_SUB, fill=active_sec["color"])
        draw.text((600, 990), f"[{active_sec['key_tag']}]", font=FONT_CODE, fill=TEXT_WHITE)
        
        # Large clear subtitles
        draw.text((30, 1022), active_sec["text"], font=FONT_SUBTITLE, fill=TEXT_WHITE)
        
        # Animated bottom progress bar
        progress = (frame_idx + 1) / float(total_frames)
        bar_w = int(W * progress)
        draw.rectangle([0, H - 5, W, H], fill=(25, 30, 40))
        draw.rectangle([0, H - 5, bar_w, H], fill=active_sec["color"])
        
        proc.stdin.write(canvas.tobytes())
        
        if (frame_idx + 1) % (FPS * 10) == 0 or frame_idx == total_frames - 1:
            print(f"Rendered {frame_idx + 1} / {total_frames} frames ({current_time:.1f}s / {total_duration:.1f}s)")
            
    proc.stdin.close()
    proc.wait()
    print(f"Master video finished: {output_mp4} (Exit: {proc.returncode})")
    
    # Run full decode check to verify zero bitstream errors
    val = subprocess.run([ffmpeg, '-v', 'error', '-i', output_mp4, '-f', 'null', '-'], capture_output=True, text=True)
    if val.returncode == 0 and not val.stderr.strip():
        print("VERIFICATION PASS: Output video has 0 bitstream errors and passes full decode!")
    else:
        print("VERIFICATION WARNING:", val.stderr)
        
    art_path = "C:/Users/Asus/.gemini/antigravity-ide/brain/f4617ed3-4916-4352-b81a-fda68855b0f9/trace_judge_presentation.mp4"
    import shutil
    shutil.copyfile(output_mp4, art_path)
    print(f"Copied to artifacts: {art_path}")


if __name__ == "__main__":
    out = "c:/Users/Asus/Desktop/sih/trace_judge_presentation.mp4"
    render_master_video(out)

import os
import wave
import subprocess
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageSequence

W, H = 1920, 1080
FPS = 30

FONT_TITLE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 26)
FONT_SUB = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 18)
FONT_SUBTITLE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)
FONT_CODE = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 18)
FONT_BADGE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)

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
        "phase": "JUDGE DEMONSTRATION · SYSTEM OVERVIEW",
        "phase_num": "OVERVIEW",
        "color": ACCENT_BLUE,
        "key_tag": "TRACE DVR FORENSICS · SIH26150",
        "text": "Respected judges, welcome to the demonstration of Trace, our comprehensive forensic DVR and NVR evidence recovery workstation."
    },
    {
        "tag": "acquisition",
        "wav": "data/narration/acquisition.wav",
        "phase": "PHASE 1: IMMUTABLE ACQUISITION & WRITE-BLOCK",
        "phase_num": "PHASE 1 / 5",
        "color": ACCENT_GREEN,
        "key_tag": "ZERO OVERWRITE PROTOCOL · SHA-256 BASELINE HASH",
        "text": "Surveillance footage is easily lost due to power cuts, corrupted file systems, or proprietary formats. Trace operates on read-only handles with zero overwrite, calculating an immutable SHA-256 hash."
    },
    {
        "tag": "carving",
        "wav": "data/narration/carving.wav",
        "phase": "PHASE 2: MEMORY-MAPPED CARVING & MULTI-CHANNEL DEMUXING",
        "phase_num": "PHASE 2 / 5",
        "color": ACCENT_PURPLE,
        "key_tag": "DAHUA DHAV & HEIMVISION DEMUXERS · CHANNEL ISOLATION",
        "text": "Our memory-mapped recovery engine executes deep carving across unallocated disk sectors. It automatically identifies proprietary Dahua DHAV and HeimVision containers, demultiplexing interleaved camera feeds."
    },
    {
        "tag": "validation",
        "wav": "data/narration/validation.wav",
        "phase": "PHASE 3: FRAME-BY-FRAME FFMPEG DECODE VALIDATION",
        "phase_num": "PHASE 3 / 5",
        "color": ACCENT_AMBER,
        "key_tag": "EXACT_RECOVERED · ZERO BITSTREAM ERRORS · EXACT OFFSETS",
        "text": "Every recovered fragment undergoes full FFmpeg decode validation. Only fragments with zero bitstream errors earn EXACT RECOVERED status. Examiners inspect exact source offsets, resolutions, and frame counts."
    },
    {
        "tag": "inspection_join",
        "wav": "data/narration/inspection_join.wav",
        "phase": "PHASE 4: BYTE INSPECTOR & STREAM RECONSTRUCTION",
        "phase_num": "PHASE 4 / 5",
        "color": ACCENT_BLUE,
        "key_tag": "CANDIDATE ADJACENCY GRAPH · 60/60 FRAMES RECONSTRUCTED",
        "text": "Using our byte inspector, examiners verify raw hexadecimal sector signatures. Then, our candidate edge graph evaluates timestamps and resolution, reconstructing fragmented camera streams without mixing channels."
    },
    {
        "tag": "conclusion",
        "wav": "data/narration/conclusion.wav",
        "phase": "PHASE 5: COURT-READY FORENSIC REPORT & ZIP EXPORT",
        "phase_num": "PHASE 5 / 5",
        "color": ACCENT_GREEN,
        "key_tag": "TAMPER-EVIDENT AUDIT CHAIN · COURT LEGAL DEFENSE",
        "text": "Finally, Trace produces a court-ready forensic examination report with a cryptographic audit trail and an integrity-verified ZIP evidence package, ensuring an unbroken chain of custody for legal proceedings."
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
            
    # Calculate exact start and end time of each section
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
    draw.rounded_rectangle([x, y, x + tw + 18, y + th + 8], radius=4, fill=fill_color)
    draw.text((x + 9, y + 3), text, font=FONT_BADGE, fill=text_color)
    return tw + 18


def build_judge_video(webp_path, output_mp4):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    master_wav = "data/narration/full_judge_voiceover.wav"
    total_duration = concat_wav_files(SECTIONS, master_wav)
    total_frames = int(total_duration * FPS)
    
    print(f"Loading browser recording from: {webp_path}")
    im_webp = Image.open(webp_path)
    print("Pre-loading browser frames into memory...")
    browser_frames = []
    for frame in ImageSequence.Iterator(im_webp):
        # Resize browser frame to fit 1920x880 nicely
        resized = frame.convert('RGB').resize((1920, 880), Image.Resampling.BILINEAR)
        browser_frames.append(resized)
    
    n_browser_frames = len(browser_frames)
    print(f"Loaded {n_browser_frames} browser frames. Mapping to {total_frames} video frames...")
    
    # Start FFmpeg process piping rawvideo and muxing audio
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
        
        # Determine active section
        active_sec = SECTIONS[-1]
        for sec in SECTIONS:
            if sec["start_time"] <= current_time < sec["end_time"]:
                active_sec = sec
                break
                
        # Map time proportionally to browser frames
        b_idx = min(int((frame_idx / float(total_frames)) * n_browser_frames), n_browser_frames - 1)
        b_frame = browser_frames[b_idx]
        
        # Create full 1920x1080 canvas
        canvas = Image.new("RGB", (W, H), (10, 13, 18))
        draw = ImageDraw.Draw(canvas)
        
        # 1. Top Header Bar (0..65px)
        draw.rectangle([0, 0, W, 65], fill=BG_HEADER)
        draw.line([0, 65, W, 65], fill=BORDER_COLOR, width=1)
        
        draw.text((30, 18), "TRACE FORENSICS", font=FONT_TITLE, fill=ACCENT_BLUE)
        draw.text((270, 23), "• DVR/NVR Forensic Evidence Recovery Workstation", font=FONT_SUB, fill=TEXT_MUTED)
        
        draw_badge(draw, active_sec["phase_num"], W - 320, 18, (30, 40, 55), active_sec["color"])
        draw_badge(draw, "JUDGES DEMO", W - 160, 18, (25, 45, 30), ACCENT_GREEN)
        
        # 2. Main Browser Area (65..945px)
        canvas.paste(b_frame, (0, 65))
        
        # 3. Bottom Subtitle & Forensic Status Bar (945..1080px)
        draw.rectangle([0, 945, W, H], fill=BG_BOTTOM)
        draw.line([0, 945, W, 945], fill=BORDER_COLOR, width=2)
        
        # Phase Banner
        draw.text((40, 955), active_sec["phase"], font=FONT_SUB, fill=active_sec["color"])
        draw.text((650, 957), f"[{active_sec['key_tag']}]", font=FONT_CODE, fill=TEXT_WHITE)
        
        # Spoken narration subtitle
        draw.text((40, 995), active_sec["text"], font=FONT_SUBTITLE, fill=TEXT_WHITE)
        
        # Global Progress Bar at very bottom
        progress = (frame_idx + 1) / float(total_frames)
        bar_w = int(W * progress)
        draw.rectangle([0, H - 5, W, H], fill=(25, 30, 40))
        draw.rectangle([0, H - 5, bar_w, H], fill=active_sec["color"])
        
        proc.stdin.write(canvas.tobytes())
        
        if (frame_idx + 1) % (FPS * 5) == 0 or frame_idx == total_frames - 1:
            print(f"Rendered {frame_idx + 1} / {total_frames} frames ({current_time:.1f}s / {total_duration:.1f}s)")
            
    proc.stdin.close()
    proc.wait()
    print(f"Video with narration generated successfully at: {output_mp4} (Exit code: {proc.returncode})")


if __name__ == "__main__":
    src_webp = "C:/Users/Asus/.gemini/antigravity-ide/brain/f4617ed3-4916-4352-b81a-fda68855b0f9/recovery_demo_walkthrough_1789178620504.webp"
    dst1 = "c:/Users/Asus/Desktop/sih/trace_judge_presentation.mp4"
    dst2 = "C:/Users/Asus/.gemini/antigravity-ide/brain/f4617ed3-4916-4352-b81a-fda68855b0f9/trace_judge_presentation.mp4"
    
    build_judge_video(src_webp, dst1)
    
    import shutil
    shutil.copyfile(dst1, dst2)
    print(f"Copied to artifacts directory: {dst2}")

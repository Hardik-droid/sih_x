import os
import wave
import subprocess
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageSequence

W, H = 1280, 720
FPS = 30

FONT_TITLE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 20)
FONT_SUB = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 15)
FONT_SUBTITLE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 18)
FONT_CODE = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 14)
FONT_BADGE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 13)

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
        "phase": "SYSTEM OVERVIEW & PURPOSE",
        "phase_num": "OVERVIEW",
        "color": ACCENT_BLUE,
        "key_tag": "TRACE DVR FORENSICS · SIH26150",
        "text": "Respected judges, welcome to the demonstration of Trace, our forensic DVR/NVR evidence recovery workstation."
    },
    {
        "tag": "acquisition",
        "wav": "data/narration/acquisition.wav",
        "phase": "PHASE 1: IMMUTABLE ACQUISITION & WRITE-BLOCK",
        "phase_num": "PHASE 1 / 5",
        "color": ACCENT_GREEN,
        "key_tag": "ZERO OVERWRITE · SHA-256 BASELINE",
        "text": "Surveillance footage is lost to power cuts or disk damage. Trace operates on read-only handles with zero overwrite, calculating an immutable SHA-256 hash."
    },
    {
        "tag": "carving",
        "wav": "data/narration/carving.wav",
        "phase": "PHASE 2: CARVING & CHANNEL DEMUXING",
        "phase_num": "PHASE 2 / 5",
        "color": ACCENT_PURPLE,
        "key_tag": "DAHUA DHAV & HEIMVISION DEMUXERS",
        "text": "Our memory-mapped engine executes deep carving across unallocated sectors, identifying Dahua DHAV and HeimVision containers and isolating channels."
    },
    {
        "tag": "validation",
        "wav": "data/narration/validation.wav",
        "phase": "PHASE 3: FRAME DECODE VALIDATION",
        "phase_num": "PHASE 3 / 5",
        "color": ACCENT_AMBER,
        "key_tag": "EXACT_RECOVERED · ZERO BITSTREAM ERRORS",
        "text": "Every fragment undergoes FFmpeg decode validation. Only fragments with zero bitstream errors earn EXACT RECOVERED status with exact byte offsets."
    },
    {
        "tag": "inspection_join",
        "wav": "data/narration/inspection_join.wav",
        "phase": "PHASE 4: BYTE INSPECTOR & RECONSTRUCTION",
        "phase_num": "PHASE 4 / 5",
        "color": ACCENT_BLUE,
        "key_tag": "CANDIDATE ADJACENCY GRAPH · 60/60 FRAMES",
        "text": "Examiners verify raw sector headers in the byte inspector. Then, our candidate edge graph reconstructs fragmented camera streams without mixing channels."
    },
    {
        "tag": "conclusion",
        "wav": "data/narration/conclusion.wav",
        "phase": "PHASE 5: COURT-READY FORENSIC REPORT",
        "phase_num": "PHASE 5 / 5",
        "color": ACCENT_GREEN,
        "key_tag": "TAMPER-EVIDENT AUDIT CHAIN · EVIDENCE ZIP",
        "text": "Finally, Trace produces a court-ready forensic report with cryptographic audit trail and an integrity-verified ZIP evidence package for legal proceedings."
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
    draw.rounded_rectangle([x, y, x + tw + 14, y + th + 6], radius=4, fill=fill_color)
    draw.text((x + 7, y + 2), text, font=FONT_BADGE, fill=text_color)
    return tw + 14


def run_stream():
    master_wav = "data/narration/full_judge_voiceover.wav"
    total_duration = concat_wav_files(SECTIONS, master_wav)
    total_frames = int(total_duration * FPS)
    
    webp_path = "C:/Users/Asus/.gemini/antigravity-ide/brain/f4617ed3-4916-4352-b81a-fda68855b0f9/recovery_demo_walkthrough_1789178620504.webp"
    output_mp4 = "c:/Users/Asus/Desktop/sih/trace_judge_presentation.mp4"
    
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    
    im_webp = Image.open(webp_path)
    n_webp_frames = getattr(im_webp, 'n_frames', 1023)
    print(f"Streaming {n_webp_frames} browser frames over {total_frames} video frames ({total_duration:.1f}s)...")
    
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
        '-preset', 'veryfast',
        '-crf', '19',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        output_mp4
    ], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    
    # Calculate how many video frames each webp frame gets
    frames_written = 0
    
    for webp_idx, frame in enumerate(ImageSequence.Iterator(im_webp)):
        # Calculate target video frame index for this webp frame
        target_video_frame = int((webp_idx + 1) / float(n_webp_frames) * total_frames)
        repeats = max(1, target_video_frame - frames_written)
        
        # Resize browser frame to 1280x560
        browser_img = frame.convert('RGB').resize((1280, 560), Image.Resampling.BILINEAR)
        
        for _ in range(repeats):
            if frames_written >= total_frames:
                break
                
            current_time = frames_written / float(FPS)
            
            # Find active narration section
            active_sec = SECTIONS[-1]
            for sec in SECTIONS:
                if sec["start_time"] <= current_time < sec["end_time"]:
                    active_sec = sec
                    break
                    
            # Composite frame
            canvas = Image.new("RGB", (W, H), (10, 13, 18))
            draw = ImageDraw.Draw(canvas)
            
            # 1. Top Header Bar (0..50px)
            draw.rectangle([0, 0, W, 50], fill=BG_HEADER)
            draw.line([0, 50, W, 50], fill=BORDER_COLOR, width=1)
            
            draw.text((20, 14), "TRACE FORENSICS", font=FONT_TITLE, fill=ACCENT_BLUE)
            draw.text((200, 18), "• DVR/NVR Evidence Recovery Workstation", font=FONT_SUB, fill=TEXT_MUTED)
            
            draw_badge(draw, active_sec["phase_num"], W - 240, 13, (30, 40, 55), active_sec["color"])
            draw_badge(draw, "JUDGES DEMO", W - 120, 13, (25, 45, 30), ACCENT_GREEN)
            
            # 2. Main Browser Area (50..610px)
            canvas.paste(browser_img, (0, 50))
            
            # 3. Bottom Subtitle & Forensic Status Bar (610..720px)
            draw.rectangle([0, 610, W, H], fill=BG_BOTTOM)
            draw.line([0, 610, W, 610], fill=BORDER_COLOR, width=2)
            
            # Phase banner
            draw.text((25, 620), active_sec["phase"], font=FONT_SUB, fill=active_sec["color"])
            draw.text((450, 621), f"[{active_sec['key_tag']}]", font=FONT_CODE, fill=TEXT_WHITE)
            
            # Spoken subtitle
            draw.text((25, 650), active_sec["text"], font=FONT_SUBTITLE, fill=TEXT_WHITE)
            
            # Progress bar
            progress = (frames_written + 1) / float(total_frames)
            bar_w = int(W * progress)
            draw.rectangle([0, H - 4, W, H], fill=(25, 30, 40))
            draw.rectangle([0, H - 4, bar_w, H], fill=active_sec["color"])
            
            proc.stdin.write(canvas.tobytes())
            frames_written += 1
            
        if webp_idx % 100 == 0 or webp_idx == n_webp_frames - 1:
            print(f"Processed WebP frame {webp_idx + 1} / {n_webp_frames} (Video: {frames_written} / {total_frames} frames)")
            
    # Pad any remaining frames if necessary
    while frames_written < total_frames:
        proc.stdin.write(canvas.tobytes())
        frames_written += 1
        
    proc.stdin.close()
    proc.wait()
    print(f"Presentation video with narration finished: {output_mp4} (Exit: {proc.returncode})")
    
    art_path = "C:/Users/Asus/.gemini/antigravity-ide/brain/f4617ed3-4916-4352-b81a-fda68855b0f9/trace_judge_presentation.mp4"
    import shutil
    shutil.copyfile(output_mp4, art_path)
    print(f"Copied to artifacts: {art_path}")


if __name__ == "__main__":
    run_stream()

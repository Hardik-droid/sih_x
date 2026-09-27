import os
import subprocess
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FONT_TITLE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 44)
FONT_HEADING = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 32)
FONT_SUB = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)
FONT_BODY = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 19)
FONT_CODE = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 17)
FONT_BADGE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 15)

W, H = 1280, 720
FPS = 30

BG_DARK = (13, 17, 23)
PANEL_BG = (22, 27, 34)
BORDER_COLOR = (48, 54, 61)
ACCENT_BLUE = (88, 166, 255)
ACCENT_GREEN = (63, 185, 80)
ACCENT_AMBER = (210, 153, 34)
ACCENT_PURPLE = (187, 128, 247)
TEXT_WHITE = (240, 246, 252)
TEXT_MUTED = (139, 148, 158)
TEXT_DIM = (110, 118, 129)


def draw_card(draw, x, y, w, h, bg=PANEL_BG, border=BORDER_COLOR, radius=8):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=bg, outline=border, width=2)


def draw_badge(draw, text, x, y, fill_color, text_color=(255, 255, 255)):
    bbox = FONT_BADGE.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.rounded_rectangle([x, y, x + tw + 18, y + th + 10], radius=4, fill=fill_color)
    draw.text((x + 9, y + 4), text, font=FONT_BADGE, fill=text_color)
    return tw + 18


def draw_header(draw, title, subtitle, phase_num, total_phases=7):
    # Top navbar
    draw.rectangle([0, 0, W, 70], fill=(18, 22, 28))
    draw.line([0, 70, W, 70], fill=BORDER_COLOR, width=1)
    
    draw.text((30, 20), "TRACE FORENSICS", font=FONT_SUB, fill=ACCENT_BLUE)
    draw.text((220, 22), "•  DVR/NVR Forensic Evidence Recovery Engine", font=FONT_BODY, fill=TEXT_MUTED)
    
    phase_str = f"STEP {phase_num} / {total_phases}"
    draw_badge(draw, phase_str, W - 140, 20, (35, 45, 60), ACCENT_BLUE)
    
    # Section title
    draw.text((50, 95), title, font=FONT_HEADING, fill=TEXT_WHITE)
    draw.text((50, 140), subtitle, font=FONT_BODY, fill=TEXT_MUTED)
    draw.line([50, 175, W - 50, 175], fill=BORDER_COLOR, width=1)


def make_scene_1(t, dur):
    # Title Slide
    im = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(im)
    
    # Subtle grid lines
    for x in range(0, W, 80):
        d.line([x, 0, x, H], fill=(18, 22, 30), width=1)
    for y in range(0, H, 80):
        d.line([0, y, W, y], fill=(18, 22, 30), width=1)
        
    draw_badge(d, "CRIME SCENE FORENSICS · SIH26150", 450, 140, (26, 40, 60), ACCENT_BLUE)
    
    d.text((150, 210), "DVR/NVR FORENSIC RECOVERY ENGINE", font=FONT_TITLE, fill=TEXT_WHITE)
    d.text((250, 275), "HOW IT WORKS & COMPLETE ARCHITECTURAL DEEP DIVE", font=FONT_HEADING, fill=ACCENT_GREEN)
    
    # 4 Pillar Boxes
    pillars = [
        ("1. Zero Overwrite", "Hardware write-block & immutable SHA-256 baseline", ACCENT_BLUE),
        ("2. Multi-Vendor Carving", "DHAV / HeimVision / MP4 / H.264 & H.265 bitstreams", ACCENT_PURPLE),
        ("3. Frame Validation", "Bitstream verification with FFmpeg decode check", ACCENT_AMBER),
        ("4. Stream Graph", "Candidate edge stitching & cryptographic custody", ACCENT_GREEN)
    ]
    
    for i, (p_title, p_desc, color) in enumerate(pillars):
        bx = 70 + i * 285
        by = 380
        draw_card(d, bx, by, 270, 180, PANEL_BG, BORDER_COLOR)
        d.rectangle([bx, by, bx + 270, by + 6], fill=color)
        d.text((bx + 16, by + 25), p_title, font=FONT_SUB, fill=color)
        
        # Word wrap desc
        words = p_desc.split(" ")
        line1 = " ".join(words[:4])
        line2 = " ".join(words[4:])
        d.text((bx + 16, by + 75), line1, font=FONT_BODY, fill=TEXT_WHITE)
        d.text((bx + 16, by + 105), line2, font=FONT_BODY, fill=TEXT_MUTED)
        
    # Footer
    d.text((50, 660), "Local Station Engine · Zero Cloud Dependency · Python 3.13 + FastAPI + SQLite / Neon", font=FONT_BODY, fill=TEXT_DIM)
    return im


def make_scene_2(t, dur):
    # Storage & Acquisition
    im = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(im)
    draw_header(d, "Phase 1: Storage Layer & Immutable Evidence Acquisition",
                "core/storage.py — Enforcing write-blocked zero-overwrite protocol before analysis", 1)
    
    # Left Card: Flow diagram
    draw_card(d, 50, 200, 560, 470)
    d.text((75, 220), "FORENSIC ACQUISITION WORKFLOW", font=FONT_SUB, fill=ACCENT_BLUE)
    
    steps = [
        ("Target Physical / Image Source", "E:\\, \\\\.\\PhysicalDrive1, .dd, .img, .raw, .E01"),
        ("Strict Read-Only Access", "O_RDONLY handles; Windows filesystem bypass"),
        ("Dual SHA-256 Checksum", "Calculated on live stream & verified local replica"),
        ("Partition Table Inspection", "Scans MBR & CRC32-validated GPT boundary tables"),
        ("Unallocated Sector Mapping", "Identifies raw unpartitioned space for bitstream scan")
    ]
    for i, (title, sub) in enumerate(steps):
        sy = 270 + i * 75
        d.ellipse([75, sy + 4, 95, sy + 24], fill=(30, 45, 65), outline=ACCENT_BLUE, width=2)
        d.text((82, sy + 4), str(i + 1), font=FONT_BADGE, fill=ACCENT_BLUE)
        d.text((115, sy), title, font=FONT_BODY, fill=TEXT_WHITE)
        d.text((115, sy + 25), sub, font=FONT_CODE, fill=TEXT_MUTED)
        if i < 4:
            d.line([85, sy + 26, 85, sy + 73], fill=BORDER_COLOR, width=2)
            
    # Right Card: Code Focus
    draw_card(d, 640, 200, 590, 470)
    d.text((665, 220), "KEY FUNCTION: storage.py", font=FONT_SUB, fill=ACCENT_GREEN)
    
    code_lines = [
        "# Read range directly without loading file to RAM",
        "def read_range(path, start, end):",
        "    with open(path, 'rb') as f:",
        "        f.seek(start)",
        "        return f.read(end - start)",
        "",
        "# Cryptographic proof of immutable custody",
        "def sha256(path):",
        "    h = hashlib.sha256()",
        "    with open(path, 'rb') as f:",
        "        while chunk := f.read(1024 * 1024):",
        "            h.update(chunk)",
        "    return h.hexdigest()",
        "",
        "# GPT & MBR partition parsing validates structure",
        "def inspect_storage(path): ...",
    ]
    for i, line in enumerate(code_lines):
        color = ACCENT_AMBER if line.startswith("def") else TEXT_MUTED if line.startswith("#") else TEXT_WHITE
        d.text((665, 260 + i * 26), line, font=FONT_CODE, fill=color)
        
    return im


def make_scene_3(t, dur):
    # Discovery & Carving Engine
    im = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(im)
    draw_header(d, "Phase 2: Byte Stream Discovery & Multi-Vendor Carving",
                "core/recovery.py (discover) — Memory-mapped signature carving & proprietary headers", 2)
    
    draw_card(d, 50, 200, 560, 470)
    d.text((75, 220), "DETECTION SIGNATURES & ADAPTERS", font=FONT_SUB, fill=ACCENT_PURPLE)
    
    sigs = [
        ("Dahua DHAV Container", "Magic: b'DHAV' (32-bit packed timestamp + channel)", "core/dhav.py"),
        ("HeimVision DAT Excerpt", "Magic: b'luo ' header (8192B) + b'liu ' frames (128B)", "core/heimvision.py"),
        ("Standard Annex-B H.264", "NALU Prefix: 00 00 00 01 67 (SPS Header)", "STANDARD-MEDIA"),
        ("Standard Annex-B H.265", "NALU Prefix: 00 00 00 01 40 (VPS Header)", "STANDARD-MEDIA"),
        ("MP4 / MOV Containers", "Atoms: ftyp, moov, mdat, moof (Truncation aware)", "STANDARD-MEDIA"),
        ("Synthetic Lab Index", "Magic: b'TRACEIDX1\\0' + CRC32 checksum payload", "TRACE-LAB-INDEX")
    ]
    for i, (fmt, sig, mod) in enumerate(sigs):
        sy = 270 + i * 65
        draw_card(d, 75, sy, 510, 55, (16, 20, 26), BORDER_COLOR)
        d.text((90, sy + 8), fmt, font=FONT_BODY, fill=TEXT_WHITE)
        d.text((90, sy + 30), sig, font=FONT_CODE, fill=TEXT_MUTED)
        draw_badge(d, mod, 440, sy + 15, (25, 35, 50), ACCENT_BLUE)
        
    # Right: Memory Mapped Optimization Card
    draw_card(d, 640, 200, 590, 470)
    d.text((665, 220), "MEMORY-MAPPED DISK SCANNING", font=FONT_SUB, fill=ACCENT_BLUE)
    
    d.text((665, 260), "Why mmap? Large surveillance drives exceed available RAM.", font=FONT_BODY, fill=TEXT_WHITE)
    d.text((665, 290), "mmap pages disk sectors on-demand without memory explosion.", font=FONT_BODY, fill=TEXT_MUTED)
    
    code_lines = [
        "with open(path, 'rb') as handle,",
        "     mmap.mmap(handle.fileno(), 0, access=ACCESS_READ) as data:",
        "    cursor = 0",
        "    # Rapid search across gigabytes of sectors",
        "    while (pos := data.find(signature, cursor)) >= 0:",
        "        cursor = pos + len(signature)",
        "        # Verify container boundaries (e.g. atoms / NALUs)",
        "        start, end = extract_bounds(data, pos, kind)",
        "        candidates.append({",
        "            'offset_start': start,",
        "            'offset_end': end,",
        "            'stream_type': kind",
        "        })",
    ]
    for i, line in enumerate(code_lines):
        color = ACCENT_AMBER if "while" in line or "with" in line else TEXT_MUTED if line.strip().startswith("#") else TEXT_WHITE
        d.text((665, 340 + i * 26), line, font=FONT_CODE, fill=color)
        
    return im


def make_scene_4(t, dur):
    # Specialized CCTV Demuxers
    im = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(im)
    draw_header(d, "Phase 3: Specialized CCTV Multiplex Demuxers",
                "core/dhav.py & core/heimvision.py — Separating channels, stripping corrupt frames", 3)
    
    draw_card(d, 50, 200, 560, 470)
    d.text((75, 220), "DAHUA DHAV DEMULTIPLEXING", font=FONT_SUB, fill=ACCENT_BLUE)
    
    dhav_info = [
        "• Container Problem: Dahua packs multiple camera channels,",
        "  audio packets, and system records into a single .dav stream.",
        "",
        "• DHAV Frame Header Structure (24 Bytes):",
        "  - [0..3]   'DHAV' sync marker",
        "  - [4]      Channel Index (0..15)",
        "  - [5]      Frame Type (Video I-frame, P-frame, Audio)",
        "  - [8..11]  32-bit packed timestamp (Year, Mo, Day, Hr, Min, Sec)",
        "  - [16..19] Length of payload bytes",
        "",
        "• Forensic Channel Isolation:",
        "  Extracts exact byte slices for Camera 1, isolates Camera 2,",
        "  and safely drops audio packets to prevent playback stutter."
    ]
    for i, line in enumerate(dhav_info):
        color = ACCENT_AMBER if "Header" in line or "DHAV" in line else TEXT_WHITE if line.startswith("•") else TEXT_MUTED
        d.text((75, 260 + i * 24), line, font=FONT_CODE if "[" in line else FONT_BODY, fill=color)
        
    draw_card(d, 640, 200, 590, 470)
    d.text((665, 220), "HEIMVISION K9604-W CORPUS DEMUXER", font=FONT_SUB, fill=ACCENT_GREEN)
    
    heim_info = [
        "• Header Layout: 8192-byte 'luo ' file header + ' oul' trailer.",
        "",
        "• Liu Frame Header (128 Bytes):",
        "  - [0..3]    'liu ' sync marker",
        "  - [124..127]' uil' closing marker",
        "  - Channel:  words[11] (Cameras 0..3)",
        "  - Codec:    'H265' Annex-B NALUs",
        "  - Audio:    8000 Hz 16-bit PCM Mono audio packets",
        "",
        "• Exact Payload Byte Maps (payload_ranges):",
        "  Stores discrete [[start1, end1], [start2, end2]] slices.",
        "  Carves keyframe VPS/SPS/PPS excerpts without modifying",
        "  original files."
    ]
    for i, line in enumerate(heim_info):
        color = ACCENT_AMBER if "Header" in line or "Liu" in line else TEXT_WHITE if line.startswith("•") else TEXT_MUTED
        d.text((665, 260 + i * 24), line, font=FONT_CODE if "[" in line or "Channel" in line else FONT_BODY, fill=color)
        
    return im


def make_scene_5(t, dur):
    # Fragment Extraction & FFmpeg Frame Decode Validation
    im = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(im)
    draw_header(d, "Phase 4: Fragment Extraction & FFmpeg Frame Validation",
                "core/recovery.py (recover_fragment) & core/media.py — Zero false positives", 4)
    
    draw_card(d, 50, 200, 560, 470)
    d.text((75, 220), "STRICT DECODE VALIDATION GATES", font=FONT_SUB, fill=ACCENT_AMBER)
    
    d.text((75, 260), "Carving bytes is not enough: bytes must produce actual video.", font=FONT_BODY, fill=TEXT_WHITE)
    d.text((75, 290), "Every extracted fragment undergoes full FFmpeg decode check:", font=FONT_BODY, fill=TEXT_MUTED)
    
    checks = [
        ("EXACT_RECOVERED", "100% of frames decode with zero bitstream errors; SHA matches index", ACCENT_GREEN),
        ("PARTIAL_RECOVERED", "Valid frames recovered, but file truncated or some packets dropped", ACCENT_AMBER),
        ("UNRECOVERABLE", "Candidate bytes preserved for forensic integrity, but 0 frames decoded", (248, 81, 73))
    ]
    for i, (status, desc, col) in enumerate(checks):
        sy = 340 + i * 100
        draw_card(d, 75, sy, 510, 85, (18, 22, 28), col)
        draw_badge(d, status, 90, sy + 15, col)
        d.text((90, sy + 50), desc, font=FONT_BODY, fill=TEXT_WHITE)
        
    draw_card(d, 640, 200, 590, 470)
    d.text((665, 220), "MEDIA ENGINE VALIDATION: media.py", font=FONT_SUB, fill=ACCENT_BLUE)
    
    code_lines = [
        "# Invokes FFmpeg with strict protocol & demuxer limits",
        "def validate(path):",
        "    cmd = [",
        "        ffmpeg, '-v', 'error',",
        "        '-protocols_whitelist', 'file',",
        "        '-i', path,",
        "        '-f', 'null', '-c:v', 'rawvideo', '-'",
        "    ]",
        "    # Parse stderr for corrupt NALUs, macroblock errors",
        "    # Count decoded frames and inspect PTS monotonicity",
        "    return {",
        "        'decode_result': 'PASS' if frames > 0 else 'FAIL',",
        "        'frames_decoded': frames,",
        "        'codec': stream_codec,",
        "        'errors': stderr_errors",
        "    }"
    ]
    for i, line in enumerate(code_lines):
        color = ACCENT_AMBER if line.strip().startswith("def") else TEXT_MUTED if line.strip().startswith("#") else TEXT_WHITE
        d.text((665, 265 + i * 26), line, font=FONT_CODE, fill=color)
        
    return im


def make_scene_6(t, dur):
    # Candidate Edge Graph & Reconstruction
    im = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(im)
    draw_header(d, "Phase 5: Candidate Graph & Safe Stream Reassembly",
                "core/recovery.py (candidate_edge, reconstruct) — Joining CCTV fragments without corruption", 5)
    
    draw_card(d, 50, 200, 560, 470)
    d.text((75, 220), "FRAGMENT ADJACENCY DECISION MATRIX", font=FONT_SUB, fill=ACCENT_GREEN)
    
    d.text((75, 260), "A camera recording split across clusters cannot be naively joined.", font=FONT_BODY, fill=TEXT_WHITE)
    d.text((75, 290), "Edges are rejected unless all forensic criteria match:", font=FONT_BODY, fill=TEXT_MUTED)
    
    rules = [
        ("Source ID & Drive Match", "Must originate from identical physical evidence source"),
        ("Channel Isolation", "CAM-01 must NEVER be stitched with CAM-02"),
        ("Codec & Parameter Sets", "H.264 vs H.265, SPS, PPS, resolution & aspect ratio"),
        ("Timestamp Continuity", "Gaps or overlaps > 80ms are rejected to avoid tearing"),
        ("Verified Fragment Hashes", "Only verified integrity fragments qualify for stitching")
    ]
    for i, (rule, exp) in enumerate(rules):
        sy = 330 + i * 65
        d.text((75, sy), f"✔ {rule}", font=FONT_BODY, fill=ACCENT_GREEN)
        d.text((95, sy + 25), exp, font=FONT_CODE, fill=TEXT_MUTED)
        
    draw_card(d, 640, 200, 590, 470)
    d.text((665, 220), "RECONSTRUCTION PIPELINE: reconstruct()", font=FONT_SUB, fill=ACCENT_BLUE)
    
    recon_steps = [
        ("1. Evaluate Graph Edges", "candidate_edge(left, right) checks compatibility"),
        ("2. Binary Annex-B Concatenation", "Streams byte blocks directly, preserving NALUs"),
        ("3. Full Joined Decode Verification", "Joined stream must decode all frames via FFmpeg"),
        ("4. Cryptographic Provenance Record", "Parent fragments, source offsets, & joined SHA-256 recorded")
    ]
    for i, (step, desc) in enumerate(recon_steps):
        sy = 270 + i * 85
        draw_card(d, 665, sy, 540, 70, (18, 22, 28), BORDER_COLOR)
        d.text((680, sy + 12), step, font=FONT_SUB, fill=ACCENT_BLUE)
        d.text((680, sy + 38), desc, font=FONT_BODY, fill=TEXT_WHITE)
        
    return im


def make_scene_7(t, dur):
    # Forensic Audit & Court Reporting
    im = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(im)
    draw_header(d, "Phase 6: Forensic Chain of Custody & Court-Ready Reporting",
                "core/store.py & core/report.py — Tamper-evident hash-linked ledger & export packages", 6)
    
    draw_card(d, 50, 200, 560, 470)
    d.text((75, 220), "TAMPER-EVIDENT AUDIT CHAIN", font=FONT_SUB, fill=ACCENT_PURPLE)
    
    d.text((75, 260), "Every forensic event is recorded in a hash-linked cryptographic chain:", font=FONT_BODY, fill=TEXT_MUTED)
    
    chain_events = [
        ("Case Creation", "Examiner credentials, case UID, system environment"),
        ("Drive Ingestion", "Read-only image hash, capacity, device serial"),
        ("Fragment Recovery", "Exact source byte offsets, fragment SHA-256, frames"),
        ("Visual Derivatives", "Denoise / Contrast / Sharpen parameters & hashes"),
        ("Reconstruction", "Parent fragment links, joined stream validation status")
    ]
    for i, (ev, det) in enumerate(chain_events):
        sy = 300 + i * 70
        draw_card(d, 75, sy, 510, 58, (16, 20, 26), BORDER_COLOR)
        d.text((90, sy + 8), ev, font=FONT_BODY, fill=TEXT_WHITE)
        d.text((90, sy + 30), det, font=FONT_CODE, fill=TEXT_MUTED)
        
    draw_card(d, 640, 200, 590, 470)
    d.text((665, 220), "OFFICIAL EVIDENCE EXPORT PACKAGES", font=FONT_SUB, fill=ACCENT_GREEN)
    
    d.text((665, 260), "Standard deliverables for legal proceedings & court testimony:", font=FONT_BODY, fill=TEXT_WHITE)
    
    features = [
        "• Printable Forensic Examination Report (HTML / PDF):",
        "  Executive summary, hardware specs, complete fragment table,",
        "  timeline analysis, examiner notes, and official sign-off.",
        "",
        "• Machine-Readable Forensic JSON Manifest:",
        "  Every recovered artifact, byte range, decoder log, and",
        "  hash is structured for automated external verification.",
        "",
        "• Integrity-Verified ZIP Evidence Package:",
        "  Bundles original recovered video bitstreams, viewing derivatives,",
        "  manifest, and audit head verification."
    ]
    for i, line in enumerate(features):
        color = ACCENT_AMBER if line.startswith("•") else TEXT_WHITE if line.startswith("  -") else TEXT_MUTED
        d.text((665, 295 + i * 23), line, font=FONT_BODY, fill=color)
        
    return im


def make_scene_8(t, dur):
    # Summary & Operational Guide
    im = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(im)
    draw_header(d, "System Summary: Complete Forensic Engine Operation",
                "SIH26150 Master Plan Implementation · Production Verification", 7)
    
    # 3 Summary Column Cards
    col_data = [
        ("Core Engine Modules", [
            ("core/recovery.py", "Carving, discover, recover, join"),
            ("core/storage.py", "Hardware acquire, read-only hash"),
            ("core/dhav.py", "Dahua multi-channel demux"),
            ("core/heimvision.py", "HeimVision luo/liu parser"),
            ("core/media.py", "FFmpeg decode & viewing copies"),
            ("core/store.py", "SQLite / Neon audit store")
        ], ACCENT_BLUE),
        ("Forensic Standards Met", [
            ("Zero Overwrite", "Physical source remains unmodified"),
            ("Channel Purity", "Never joins mismatched cameras"),
            ("Exact Bytes", "All extractions have exact offsets"),
            ("Bitstream Valid", "Zero tolerance for corrupt NALUs"),
            ("Cryptographic", "End-to-end SHA-256 chain of custody"),
            ("Reproducible", "Deterministic FFmpeg filters")
        ], ACCENT_GREEN),
        ("Execution Commands", [
            ("Launch Web App", "python run.py"),
            ("Automated Tests", "python -m pytest -q"),
            ("Build Test Corpus", "python -m scripts.corpus"),
            ("E01 Extraction", "python -m scripts.use_heimvision"),
            ("DB Migration", "python -m scripts.migrate_to_neon"),
            ("Web UI Port", "http://127.0.0.1:8000")
        ], ACCENT_AMBER)
    ]
    
    for c_idx, (col_title, items, color) in enumerate(col_data):
        cx = 50 + c_idx * 395
        draw_card(d, cx, 200, 380, 470)
        d.rectangle([cx, 200, cx + 380, 206], fill=color)
        d.text((cx + 20, 225), col_title, font=FONT_SUB, fill=color)
        
        for i, (term, desc) in enumerate(items):
            iy = 275 + i * 62
            d.text((cx + 20, iy), term, font=FONT_BODY, fill=TEXT_WHITE)
            d.text((cx + 20, iy + 24), desc, font=FONT_CODE, fill=TEXT_MUTED)
            
    return im


def generate_video(output_path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    
    scenes = [
        (make_scene_1, 5),   # Title (5s)
        (make_scene_2, 6),   # Storage / Acquisition (6s)
        (make_scene_3, 6),   # Byte Carving & Discovery (6s)
        (make_scene_4, 6),   # CCTV Demuxers (6s)
        (make_scene_5, 6),   # Frame Validation & FFmpeg (6s)
        (make_scene_6, 6),   # Graph Reconstruction (6s)
        (make_scene_7, 6),   # Chain of Custody & Reporting (6s)
        (make_scene_8, 6),   # Complete Summary (6s)
    ]
    
    total_duration = sum(dur for _, dur in scenes)
    total_frames = total_duration * FPS
    
    print(f"Generating video: {total_duration}s ({total_frames} frames) at {W}x{H} {FPS}fps...")
    
    proc = subprocess.Popen([
        ffmpeg, '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{W}x{H}',
        '-pix_fmt', 'rgb24',
        '-r', str(FPS),
        '-i', '-',
        '-an',
        '-vcodec', 'libx264',
        '-preset', 'fast',
        '-crf', '18',
        '-pix_fmt', 'yuv420p',
        output_path
    ], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    
    frame_count = 0
    for scene_idx, (scene_func, dur) in enumerate(scenes):
        scene_frames = dur * FPS
        # Pre-render scene base
        base_im = scene_func(0, dur)
        
        for sf in range(scene_frames):
            # Render frame with active progress bar
            im = base_im.copy()
            d = ImageDraw.Draw(im)
            
            # Bottom global video progress bar
            progress = (frame_count + 1) / total_frames
            bar_w = int(W * progress)
            d.rectangle([0, H - 6, W, H], fill=(22, 27, 34))
            d.rectangle([0, H - 6, bar_w, H], fill=ACCENT_BLUE)
            
            # Write frame to ffmpeg stdin
            proc.stdin.write(im.tobytes())
            frame_count += 1
            
        print(f"Scene {scene_idx + 1}/{len(scenes)} rendered ({dur}s)")
        
    proc.stdin.close()
    proc.wait()
    print(f"Video created successfully at: {output_path} (Exit code: {proc.returncode})")


if __name__ == "__main__":
    out1 = "c:/Users/Asus/Desktop/sih/forensic_recovery_explainer.mp4"
    out2 = "C:/Users/Asus/.gemini/antigravity-ide/brain/f4617ed3-4916-4352-b81a-fda68855b0f9/forensic_recovery_explainer.mp4"
    generate_video(out1)
    
    import shutil
    shutil.copyfile(out1, out2)
    print(f"Copied to artifact directory: {out2}")

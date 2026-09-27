import os
import subprocess
import imageio_ffmpeg

narration_segments = [
    ("intro", "Respected judges, welcome to the demonstration of Trace, our high-fidelity forensic DVR and NVR evidence recovery workstation."),
    ("acquisition", "In digital investigations, surveillance footage is easily lost due to power cuts, corrupted file systems, or proprietary formats. Trace operates strictly on read-only handles with a zero-overwrite protocol, calculating an immutable SHA-256 baseline hash."),
    ("carving", "Here, our memory-mapped recovery engine executes deep carving across unallocated disk sectors. It automatically identifies proprietary Dahua DHAV and HeimVision containers, demultiplexing interleaved camera channels while isolating corrupted packets."),
    ("validation", "Notice that every recovered fragment undergoes full FFmpeg frame-by-frame decode validation. Only fragments with zero bitstream errors earn the EXACT RECOVERED forensic status. Examiners can inspect exact source byte offsets, resolutions, and frame counts."),
    ("inspection_join", "Using our built-in byte inspector, examiners verify raw hexadecimal sector signatures. Then, our candidate edge graph evaluates temporal adjacency and codec compatibility, reconstructing fragmented camera streams without mixing channels."),
    ("conclusion", "Finally, Trace produces a court-ready forensic examination report with a cryptographic audit trail and an integrity-verified ZIP evidence package, ensuring an unbroken chain of custody for legal proceedings.")
]

def generate_voiceover(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    audio_files = []
    
    ps_lines = [
        "Add-Type -AssemblyName System.Speech",
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer",
        "$synth.Rate = 0"
    ]
    
    for tag, text in narration_segments:
        wav_path = os.path.join(output_dir, f"{tag}.wav").replace("\\", "/")
        ps_lines.append(f"$synth.SetOutputToWaveFile('{wav_path}')")
        # escape single quotes
        safe_text = text.replace("'", "''")
        ps_lines.append(f"$synth.Speak('{safe_text}')")
        audio_files.append((tag, wav_path))
        
    ps_lines.append("$synth.Dispose()")
    ps_lines.append("Write-Host 'ALL_VOICEOVERS_GENERATED'")
    
    ps_script_path = os.path.join(output_dir, "gen_tts.ps1")
    with open(ps_script_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ps_lines))
        
    print("Running PowerShell Speech Synthesizer...")
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_script_path], capture_output=True, text=True)
    print("TTS output:", res.stdout.strip())
    if "ALL_VOICEOVERS_GENERATED" not in res.stdout:
        print("TTS Error:", res.stderr)
        raise RuntimeError("Failed to generate voiceover audio")
        
    return audio_files

if __name__ == "__main__":
    files = generate_voiceover("data/narration")
    print("Generated files:")
    for tag, path in files:
        size = os.path.getsize(path)
        print(f"  {tag}: {path} ({size} bytes)")

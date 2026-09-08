# Trace · DVR/NVR forensic workspace

A working local forensic image recovery application built from `SIH26150_DVR_NVR_Forensic_Recovery_Master_Plan_v2 (1).pdf`.

## Run

```powershell
python -m pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8000**. `run.py` opens the browser automatically. Alternatively, run `./start.ps1` to create a project virtual environment and launch. Use `python run.py --port 8001` if port 8000 is occupied. Stop the foreground server with Ctrl+C.

Python 3.13 is tested. The `imageio-ffmpeg` wheel supplies FFmpeg on supported platforms; a system FFmpeg or `TRACE_FFMPEG` overrides it. No Node build, cloud account, remote database, or AI key is required. The UI is native HTML/CSS/JavaScript served by FastAPI. It runs in a browser on the local workstation; an Electron/Tauri installer is not included.

## Try the controlled regression demo

1. Open **Compatibility → Run controlled demo**.
2. Wait for **Recovery engine → Completed**.
3. Open **Recovered evidence** and review the four recovered fragments, source offsets and actual decoder results.
4. Select the first two CAM-01 main-stream fragments and choose **Join selected**. The resulting stream must decode all 60 frames. CAM-02 must not be joined to CAM-01.
5. Add an examiner note, inspect source bytes, verify all hashes, and build an evidence ZIP under Reports & exports.

The demo is generated from FFmpeg test patterns, not real surveillance footage. It exercises a documented synthetic index and must not be presented as validation of any recorder vendor.

For your own data, create a case and import a local RAW/IMG/DD image or media file. A verified copy is created under the case folder before analysis. Browser upload is limited to 8 GiB; local path ingestion avoids that limit. Physical devices are deliberately not opened: acquire them using an established imaging tool and a hardware write blocker. For the downloaded Heimvision segmented E01 corpus, use `python -m scripts.use_heimvision` with the app stopped. It streams E01 through Dissect, reads Ext3/FAT32 and imports three indexed DAT samples without a 150 GB raw expansion. Other E01 workflows still require external conversion.

## Implemented behavior

- SQLite case management, source metadata, notes and persistent background jobs.
- Read-only file acquisition, verified-prefix resume, SHA-256 of source and copied image, acquisition diagnostics.
- MBR and CRC-checked GPT inspection, filesystem signature identification, bounded raw reads, outside-partition range map.
- MP4/AVI/JPEG and Annex-B H.264 signature discovery; contiguous byte extraction; exact source offsets and hashes.
- Full FFmpeg video decode validation, separate video-only viewing copies and thumbnails. Original recovered bytes remain downloadable.
- Documented synthetic DVR-like index with CRC and fragment hashes; duplicate-index discovery and substream labels.
- Conservative candidate graph and indexed H.264 reconstruction requiring source/channel/codec/time/checksum compatibility and full joined decoding.
- Stream-copy repair with validated-prefix fallback; explicit gaps and refusal when required index/codec data is missing.
- Separate, labeled denoise/contrast/sharpen viewing derivatives with transformation history. These are deterministic FFmpeg filters, not generative AI.
- Timeline, camera/status/search filters, provenance viewer, source health, byte inspector, audit and printable/JSON reports.
- Integrity-checked ZIP export containing recovered artifacts and a hash manifest; cancellation, interrupted-job status, idempotent rescan.
- Local host and origin checks, mutation session tokens, restricted media protocols/demuxers, subprocess timeouts, escaped report/UI text.

`EXACT_RECOVERED` means the identified byte range was recovered exactly and decoded successfully. It **does not** assert that the entire original event or recording was recovered. Generic carving does not establish deletion state, camera identity, absolute recording time, or filesystem allocation.

## Validation and remaining gates

```powershell
python -m pytest -q
node --check web/app.js
python -m scripts.corpus
```

18 automated tests passed locally on Windows, covering engine and complete API workflow. Tests generate their own corpus in temporary folders. `python -m scripts.corpus` creates a reusable corpus and its origin/hash/scenario manifest under `tests/corpus/`.

This is a functional local implementation, **not completion of all research/production gates in the PDF**. The downloaded Heimvision public E01 yielded 12 four-camera HEVC excerpts and 13,186 decoded frames from three sampled files. Its corpus parser is experimental: the model labels disagree and firmware is unknown. Physical acquisition, hardware bad-sector diagnosis, general/deleted-entry filesystem recovery, other E01 layouts, real RAID/ECC, AI models and a desktop installer remain outside the validated implementation. See [real corpus results and critique fixes](docs/real-corpus-validation.md). See [phase gates](docs/phase-gates.md) for the precise scope.

## Storage and architecture

```text
app.py                 Local FastAPI API, background jobs, report/export workflow
run.py / start.ps1     Local launch
core/storage.py       Acquisition, hashing, partitions and raw reads
core/recovery.py      Discovery, synthetic adapter, graph, reconstruction, redundancy
core/media.py         FFmpeg validation, previews, repair and derivatives
core/store.py         SQLite evidence records and hash-linked audit
web/                  Responsive workstation interface; no frontend build step
scripts/corpus.py     Controlled regression fixture generator
tests/                Engine and end-to-end API tests
docs/                 Architecture, evidence policy and phase gate results
data/                 Local case database, acquired images, artifacts and exports
```

Set `TRACE_DATA` to choose a different data directory before starting the app. Back up that whole directory while the app is stopped; it includes source copies, recovered artifacts and the case database. There is no automatic deletion of evidence.

Processing is intentionally one worker per local instance. Do not run several server instances against the same data directory. Scans use a read-only memory map, cap candidate extraction at 256 MiB per fragment and 2,000 candidates, and report the cap when hit. FFmpeg operations have time limits; very large/long recordings may need a later configurable batch pipeline. Hash verification performs full reads and may take significant time on large images.

Audit hashes detect internal edits. They cannot prevent a local administrator from rewriting the whole database or deleting its tail. Retain exported reports and audit-head hashes independently. The process is not an OS-level media sandbox or a multi-user network service.

Technical references: [FFmpeg protocol restrictions](https://ffmpeg.org/ffmpeg-protocols.html), [FFmpeg command documentation](https://ffmpeg.org/ffmpeg.html), [public camera/DVR sample archive](https://samples.ffmpeg.org/camera-dvr/hikvision/). Four archive samples were acquired and checksum-verified, but their proprietary exports produced no decodable frames. Their vendor labels do not establish exact hardware/firmware compatibility.

"""Reproduce validation against the four downloaded FFmpeg camera/DVR samples.

This reports observed compatibility, not a successful vendor validation gate.
Downloads are explicit and bounded; original public sample bytes stay unchanged.
"""
import hashlib
import json
import time
from pathlib import Path
from urllib.request import urlopen

from fastapi.testclient import TestClient

from app import create_app
from core import media, recovery, storage
from core.store import now

SAMPLES = [
    ("hikvision/120MB.mp4", "9fffa5624469fa048932a7bb2932fd1d"),
    ("hikvision/ch01_20090329170509.mp4", "ec4b080211afb57b0c6bfbed6f50d395"),
    ("hikvision/test000.mp4", "a4f073699dfecd46859c19e09c18f242"),
    ("nc_sample.avi", "482d9469461e002372df70a96d2f34a4"),
]


def main():
    root = Path("data/public-validation").resolve()
    root.mkdir(parents=True, exist_ok=True)
    results = []
    for relative, expected_md5 in SAMPLES:
        url = "https://samples.ffmpeg.org/camera-dvr/" + relative
        path = root / Path(relative).name
        if not path.exists():
            with urlopen(url, timeout=30) as response:
                data = response.read(10 * 1024 * 1024 + 1)
            if len(data) > 10 * 1024 * 1024:
                raise ValueError("Public sample exceeds 10 MiB download bound")
            path.write_bytes(data)
        content = path.read_bytes()
        if hashlib.md5(content).hexdigest() != expected_md5:
            raise ValueError("Publisher MD5 mismatch: " + path.name)
        fragments, findings = recovery.discover(path)
        validation = media.validate(path)
        results.append({"file": path.name, "path": str(path), "url": url,
                        "bytes": len(content), "sha256": storage.sha256(path),
                        "publisher_md5": expected_md5, "publisher_md5_match": True,
                        "signature_ascii": repr(content[:4]), "validation": validation,
                        "discovered_fragments": len(fragments), "findings": findings,
                        "model": "UNKNOWN", "firmware": "UNKNOWN"})
        print(f"{path.name}: checksum OK; decode {validation['decode_result']}; "
              f"frames {validation['frames_decoded']}; candidates {len(fragments)}", flush=True)

    # Use the same persistent store, with a separate named case; run with server stopped.
    with TestClient(create_app("data")) as client:
        client.headers["x-trace-token"] = client.get("/api/session").json()["token"]
        case = client.post("/api/cases", json={
            "name": "Public DVR sample validation · FFmpeg archive",
            "examiner": "Public corpus verification",
            "notes": "Real public camera/DVR exports, not synthetic footage or full disk images. "
                     "Published archive MD5 checked; local SHA-256 recorded. Exact model/firmware unknown. "
                     "A completed processing job is not evidence that a recording was recovered."
        }).json()
        for result in results:
            response = client.post(f"/api/cases/{case['id']}/sources", json={
                "path": result["path"], "vendor": "Hikvision archive label" if "/hikvision/" in result["url"] else "NC cameras archive label",
                "model": "UNKNOWN", "firmware": "UNKNOWN"})
            response.raise_for_status()
            result["job_id"] = response.json()["id"]
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            detail = client.get(f"/api/cases/{case['id']}").json()
            if all(job["status"] not in ("QUEUED", "RUNNING") for job in detail["jobs"]):
                break
            time.sleep(0.1)
        else:
            raise TimeoutError("Public sample ingestion did not finish")
        for result in results:
            job = next(job for job in detail["jobs"] if job["id"] == result["job_id"])
            result["pipeline_status"] = job["status"]
            result["pipeline_result"] = job.get("result")
            result["source_unchanged"] = storage.sha256(result["path"]) == result["sha256"]
            client.post(f"/api/cases/{case['id']}/notes", json={"text": json.dumps(result, indent=2)})
        integrity = client.get(f"/api/cases/{case['id']}/integrity").json()
        report = {"checked_at": now(), "case_id": case["id"], "media_engine": media.version(),
                  "samples": results, "acquisition_integrity": integrity,
                  "real_vendor_gate": "NOT_PASSED", "full_disk_image_tested": False}
        output = root / "validation-results.json"
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Saved case {case['id']} and {output}", flush=True)
        print(f"Acquisition integrity: {integrity['valid']}; recovered artifacts: {len(detail['artifacts'])}", flush=True)


if __name__ == "__main__":
    main()

"""Read the downloaded segmented E01 and recover three indexed time samples.

Run: python -m scripts.use_heimvision
No raw 150 GB expansion, mounting, source writes, or synthetic footage.
"""
import json
import sqlite3
import struct
import time
import zlib
from pathlib import Path

from dissect.evidence.ewf import EWF, find_files
from dissect.extfs import ExtFS
from dissect.fat import FATFS
from dissect.util.stream import RangeStream
from fastapi.testclient import TestClient

from app import create_app
from core import heimvision, storage
from core.store import Store, now

ROOT = Path("data/public-validation/heimvision-image").resolve()


def partitions(stream, size):
    stream.seek(512)
    header = bytearray(stream.read(512))
    if header[:8] != b"EFI PART":
        raise ValueError("Expected GPT")
    header_size, checksum = struct.unpack_from("<II", header, 12)
    if not 92 <= header_size <= 512:
        raise ValueError("GPT header size invalid")
    header[16:20] = bytes(4)
    if zlib.crc32(header[:header_size]) != checksum:
        raise ValueError("GPT header CRC failed")
    lba, count, entry_size, checksum = struct.unpack_from("<QIII", header, 72)
    if count > 4096 or not 128 <= entry_size <= 4096 or lba * 512 + count * entry_size > size:
        raise ValueError("GPT entries out of bounds")
    stream.seek(lba * 512)
    table = stream.read(count * entry_size)
    if zlib.crc32(table) != checksum:
        raise ValueError("GPT table CRC failed")
    result = []
    for i in range(count):
        entry = table[i * entry_size:(i + 1) * entry_size]
        if entry[:16] == bytes(16):
            continue
        first, last = struct.unpack_from("<QQ", entry, 32)
        if not 0 < first <= last or (last + 1) * 512 > size:
            raise ValueError("Partition out of bounds")
        result.append({"offset": first * 512, "length": (last - first + 1) * 512})
    if len(result) != 2:
        raise ValueError("Expected the two-partition CFReDS corpus layout")
    return result


def main():
    checkpoint = ROOT / "recovery-case.json"
    previous_case = json.loads(checkpoint.read_text())["case_id"] if checkpoint.exists() else None
    manifest = json.loads((ROOT / "extraction-manifest.json").read_text())
    segments = [{**m, "path": str(ROOT / m["file"])} for m in manifest if Path(m["file"]).suffix.lower() in (".e01", ".e02", ".e03")]
    for entry in segments:
        if storage.sha256(entry["path"]) != entry["sha256"]:
            raise ValueError("Extracted E01 segment changed")
    image = EWF(find_files(ROOT / "HeimVision K9604-W.E01"))
    stream = image.open()
    volumes = partitions(stream, image.size)
    ext = ExtFS(RangeStream(stream, **{"offset": volumes[0]["offset"], "size": volumes[0]["length"]}))
    index_path = ROOT / "search.db"
    index_path.write_bytes(ext.get("/search.db").open().read())
    with sqlite3.connect(index_path.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Recorder SQLite index is corrupt")
        detail = [dict(r) for r in db.execute("SELECT * FROM DETAIL ORDER BY id")]
        search = [dict(r) for r in db.execute("SELECT * FROM SEARCH ORDER BY id")]
    inventory = {"detail": detail, "search": search, "index_sha256": storage.sha256(index_path)}
    inventory_path = ROOT / "recording-index.json"
    inventory_path.write_text(json.dumps(inventory, indent=2))
    fat = FATFS(RangeStream(stream, volumes[1]["offset"], volumes[1]["length"]))
    selected, extracted = [0, len(detail) // 2, len(detail) - 1], []
    for ordinal in selected:
        record = detail[ordinal]
        relative = f"dir{record['folder']:05}/file{record['file']:04}.dat"
        entry = fat.get(relative)
        if entry.size != 8 * 1024 * 1024:
            raise ValueError("Unexpected corpus recording file size")
        target = ROOT / relative.replace("/", "-")
        target.write_bytes(entry.open().read())
        extents, file_offset = [], 0
        for cluster, count in entry.dataruns():
            length = min(count * fat.cluster_size, entry.size - file_offset)
            offset = volumes[1]["offset"] + fat.first_data_sector * fat.sector_size + cluster * fat.cluster_size
            if extents and extents[-1]["image_offset"] + extents[-1]["length"] == offset:
                extents[-1]["length"] += length
            else:
                extents.append({"file_offset": file_offset, "image_offset": offset, "length": length})
            file_offset += length
        # Independently replay physical image extents and compare with filesystem output.
        replay = bytearray()
        for extent in extents:
            stream.seek(extent["image_offset"])
            replay.extend(stream.read(extent["length"]))
        if bytes(replay) != target.read_bytes():
            raise ValueError("Filesystem extraction and logical image byte map disagree")
        fragments, findings = heimvision.discover(target)
        for fragment in fragments:
            ch = int(fragment["channel"][-2:]) - 1
            if not any(r["channel"] == ch and r["session_rnd"] == fragment["session_rnd"] for r in search):
                raise ValueError("Frame session/channel does not match recorder SQLite index")
        extracted.append({"path": str(target), "sha256": storage.sha256(target), "filesystem_path": relative,
                          "detail_record": record, "logical_image_extents": extents, "byte_map_verified": True,
                          "session_channel_index_match": True, "findings": findings})
        print(f"Extracted {relative}: {len(fragments)} camera streams; byte map and index agree", flush=True)
    store = Store("data")
    with TestClient(create_app("data")) as client:
        client.headers["x-trace-token"] = client.get("/api/session").json()["token"]
        response = client.get(f"/api/cases/{previous_case}") if previous_case else client.post("/api/cases", json={"name": "Heimvision E01 · real four-camera recovery", "examiner": "Public corpus verification", "notes": "Downloaded CFReDS Heimvision DVR disk. Three indexed files sampled across beginning, middle and end. Four-camera H.265 video payloads preserved; viewing copies are transcoded. Model label discrepancy K9604-W / K9604-1 retained; firmware and timezone unknown. This is sample validation, not complete recovery of all recordings."})
        response.raise_for_status()
        case = response.json()["case"] if previous_case else response.json()
        parent = {"name": "CFReDS Heimvision segmented E01", "url": "https://cfreds.nist.gov/all/JoshBrunty,RaynaMock/HeimvisionDVRE01ForensicImage", "logical_size": image.size, "segments": segments, "volumes": volumes, "gpt_crc_verified": True, "index_entries": len(detail), "search_entries": len(search), "index_path": str(inventory_path), "index_sha256": storage.sha256(inventory_path), "logical_verification": "RUNNING; see verification-progress.json"}
        store.put("case", {**case, "parent_evidence": parent}, "parent_image_registered")
        checkpoint.write_text(json.dumps({"case_id": case["id"], "selected_index_ordinals": selected}, indent=2))
        for item in extracted:
            prior = next((s for s in store.list("source", case["id"]) if s["original_path"] == item["path"]), None)
            response = client.post(f"/api/sources/{prior['id']}/analyze") if prior else client.post(f"/api/cases/{case['id']}/sources", json={"path": item["path"], "vendor": "Heimvision", "model": "K9604-W (filename; catalog K9604-1)", "firmware": "UNKNOWN"})
            response.raise_for_status()
            item["job_id"] = response.json()["id"]
        while True:
            result = client.get(f"/api/cases/{case['id']}").json()
            active = [j for j in result["jobs"] if j["status"] in ("QUEUED", "RUNNING")]
            if not active:
                break
            print([(j["status"], j["stage"]) for j in active], flush=True)
            time.sleep(15)
        for source in result["sources"]:
            provenance = next(e for e in extracted if Path(e["path"]).name == source["name"])
            store.put("source", {**source, "parent_image_provenance": provenance}, "image_byte_map_recorded")
        current_job_ids = {item["job_id"] for item in extracted}
        if any(j["status"] != "COMPLETED" for j in result["jobs"] if j["id"] in current_job_ids):
            raise ValueError("A recovery job failed: " + str(result["jobs"]))
        report = {"checked_at": now(), "case_id": case["id"], "parent_evidence": parent,
                  "extracted_files": extracted, "artifacts": [{k: a.get(k) for k in ("id", "channel", "name", "sha256", "validation", "frame_records", "omitted_leading_frames", "preview_path", "preview_error")} for a in result["artifacts"]]}
        (ROOT / "recovery-results.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({"case_id": case["id"], "artifacts": len(result["artifacts"]), "frames": sum(a["validation"]["frames_decoded"] for a in result["artifacts"])}), flush=True)


if __name__ == "__main__":
    main()

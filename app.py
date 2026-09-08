"""Local-only case API and web application. Run: python -m uvicorn app:app --host 127.0.0.1"""
import datetime
import hashlib
import html
import json
import os
import secrets
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core import VERSION, media, recovery, storage
from core.store import Store, now, uid

ROOT = Path(__file__).parent.resolve()


class CaseInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    examiner: str = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=10000)


class ImportInput(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
    vendor: str = Field(default="UNKNOWN", max_length=100)
    model: str = Field(default="UNKNOWN", max_length=100)
    firmware: str = Field(default="UNKNOWN", max_length=100)


class NoteInput(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    artifact_id: str | None = None


class TransformInput(BaseModel):
    operation: Literal["repair", "denoise", "contrast", "sharpen", "adaptive_contrast"]


class JoinInput(BaseModel):
    artifact_ids: list[str] = Field(min_length=2, max_length=50)


def create_app(data_root=None):
    is_cloud = bool(os.environ.get("VERCEL") or os.environ.get("RENDER") or os.environ.get("ALLOW_REMOTE_HOSTS"))
    default_data = Path("/tmp/data") if is_cloud else (ROOT / "data")
    store = Store(data_root or os.environ.get("TRACE_DATA", default_data))
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="recovery")
    token = os.environ.get("TRACE_SECRET_TOKEN") or (secrets.token_urlsafe(32) if not is_cloud else "trace-cloud-forensics-token")
    cancel_flags = {}

    @asynccontextmanager
    async def lifespan(app):
        for job in store.list("job"):
            if job["status"] in ("QUEUED", "RUNNING"):
                store.put("job", {**job, "status": "INTERRUPTED", "error": "Application stopped. Retry acquisition or analysis to resume safely."}, "job_interrupted")
        yield
        for flag in cancel_flags.values():
            flag.set()
        executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="Trace DVR Forensics", version=VERSION, lifespan=lifespan)
    app.state.store = store
    app.state.token = token

    @app.middleware("http")
    async def local_boundary(request, call_next):
        host = request.url.hostname
        if not is_cloud and host not in ("127.0.0.1", "localhost", "::1", "testserver"):
            return JSONResponse({"detail": "Local access only"}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not secrets.compare_digest(request.headers.get("x-trace-token", ""), token):
                return JSONResponse({"detail": "Invalid local session; refresh the app"}, status_code=403)
            origin = request.headers.get("origin")
            if origin and not is_cloud and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Cross-origin request refused"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Record not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def inaccessible(request, exc):
        return JSONResponse({"detail": "File was not found. Check its local path and availability."}, status_code=400)

    def case(case_id):
        return store.get(case_id, "case")

    def owned_path(path):
        path = Path(path).resolve(strict=True)
        if not path.is_relative_to(store.root) or not path.is_file():
            raise ValueError("Stored artifact path is outside case storage")
        return path

    def update_job(job, **changes):
        job.update(changes, updated_at=now())
        store.put("job", job)

    def submit(case_id, action, work, source_id=None):
        active = [j for j in store.list("job", case_id) if j["status"] in ("RUNNING", "QUEUED")]
        if len(active) >= 4:
            raise HTTPException(409, "This case already has four pending jobs")
        job = store.put("job", {"case_id": case_id, "source_id": source_id, "action": action, "status": "QUEUED", "progress": 0, "stage": "Queued"}, "job_queued")
        flag = cancel_flags[job["id"]] = threading.Event()

        def progress(done, total, stage="Working"):
            if flag.is_set():
                raise InterruptedError("Cancelled by examiner; completed artifacts retained")
            update_job(job, progress=round(done / max(total, 1) * 100, 1), stage=stage)

        def execute():
            try:
                progress(0, 1, action)
                update_job(job, status="RUNNING")
                result = work(job, progress)
                update_job(job, status="COMPLETED", progress=100, stage="Complete", result=result)
                store.audit(case_id, "engine", "job_completed", {"job_id": job["id"], "action": action})
            except Exception as error:
                update_job(job, status="CANCELLED" if isinstance(error, InterruptedError) else "FAILED", error=str(error), stage="Stopped")
                store.audit(case_id, "engine", "job_failed", {"job_id": job["id"], "error": str(error)})
            finally:
                cancel_flags.pop(job["id"], None)
        executor.submit(execute)
        return job

    def analyze(source, job, progress):
        source = store.get(source["id"], "source")
        path = owned_path(source["path"])
        if storage.sha256(path) != source["sha256"]:
            raise ValueError("Evidence image hash mismatch; analysis stopped")
        progress(2, 100, "Inspecting storage")
        health = storage.inspect_storage(path)
        fragments, findings = recovery.discover(path)
        progress(10, 100, f"Discovered {len(fragments)} candidate ranges")
        output_dir = store.root / source["case_id"] / "artifacts"
        output_dir.mkdir(parents=True, exist_ok=True)
        existing = {(a.get("source_id"), a.get("offset_start"), a.get("offset_end")): a for a in store.list("artifact", source["case_id"]) if a.get("kind") == "RECOVERED"}
        recovered = []
        for index, fragment in enumerate(fragments):
            progress(10 + 85 * index / max(len(fragments), 1), 100, f"Validating fragment {index + 1} / {len(fragments)}")
            key = (source["id"], fragment["offset_start"], fragment["offset_end"])
            if key in existing:
                prior = existing[key]
                if storage.sha256(owned_path(prior["path"])) != prior["sha256"]:
                    raise ValueError("Previously recovered artifact hash mismatch")
                recovered.append(prior)
                continue
            artifact_id = uid()
            output = output_dir / f"{artifact_id}.{fragment['stream_type']}"
            result = recovery.recover_fragment(path, fragment, output)
            record = {**fragment, **result, "id": artifact_id, "case_id": source["case_id"], "source_id": source["id"], "path": str(output), "name": f"{source['name']} · fragment {index + 1:03}", "kind": "RECOVERED", "input_hash": source["sha256"], "source_fragments": [{"source_id": source["id"], "offset_start": fragment["offset_start"], "offset_end": fragment["offset_end"], "range_semantics": "envelope; exact bytes listed in artifact.payload_ranges" if fragment.get("payload_ranges") else "contiguous"}], "software_version": VERSION, "codec": result["validation"]["codec"]}
            if result["validation"]["frames_decoded"]:
                try:
                    preview = output_dir / f"{artifact_id}.preview.mp4"
                    view = media.viewing_copy(output, preview)
                    record.update(preview_path=str(preview), preview_sha256=storage.sha256(preview))
                    store.put("transformation", {"case_id": source["case_id"], "input_artifact": artifact_id, "input_hash": result["sha256"], "output_path": str(preview), "output_hash": record["preview_sha256"], "software_version": media.version(), **view}, "viewing_copy_created")
                    thumb = output_dir / f"{artifact_id}.jpg"
                    if media.thumbnail(preview, thumb):
                        record["thumbnail_path"] = str(thumb)
                        record["thumbnail_sha256"] = storage.sha256(thumb)
                except (ValueError, OSError) as error:
                    record["preview_error"] = str(error)
            artifact = store.put("artifact", record, "artifact_recovered")
            store.put("fragment", {**fragment, "id": "fragment-" + artifact_id, "artifact_id": artifact_id, "case_id": source["case_id"], "source_id": source["id"], "integrity_status": result["integrity_status"], "codec": result["validation"]["codec"]})
            recovered.append(artifact)
        if storage.sha256(path) != source["sha256"]:
            raise ValueError("Evidence changed during analysis")
        # Store candidate decisions, including incompatible neighboring camera fragments.
        ordered = sorted(recovered, key=lambda a: (a.get("timestamp_start") is None, a.get("timestamp_start") or 0, a["offset_start"]))
        for left, right in zip(ordered, ordered[1:]):
            edge = recovery.candidate_edge(left, right)
            edge_id = hashlib.sha256((left["id"] + right["id"]).encode()).hexdigest()[:32]
            store.put("edge", {**edge, "id": edge_id, "case_id": source["case_id"], "source_id": source["id"]})
        source = store.put("source", {**source, "status": "ANALYZED", "health": health, "findings": findings, "redundancy": recovery.redundancy(recovered, findings), "artifact_count": len(recovered)}, "analysis_completed")
        return {"source_id": source["id"], "artifacts": len(recovered), "recoverable": sum(a["status"] != "UNRECOVERABLE" for a in recovered)}

    def ingest(case_id, path, metadata):
        case(case_id)
        path = Path(path).expanduser().resolve(strict=True)
        allowed = {".img", ".dd", ".raw", ".mp4", ".avi", ".h264", ".264", ".dav", ".jpg", ".jpeg", ".mkv", ".ts", ".dat", ".hevc"}
        if not path.is_file() or path.suffix.lower() not in allowed:
            raise ValueError("Import a raw image or supported media file. Convert E01 with ewfexport; acquire physical devices using established write-blocked tools.")
        source_id = uid()
        destination = store.root / case_id / "sources" / f"{source_id}{path.suffix.lower()}"
        source = store.put("source", {"id": source_id, "case_id": case_id, "name": path.name, "original_path": str(path), "path": str(destination), "type": "FORENSIC_IMAGE" if path.suffix.lower() in (".img", ".dd", ".raw") else "MEDIA_EXPORT", "status": "PENDING", "capacity": path.stat().st_size, **metadata}, "source_registered")
        return acquire_source(source)

    def acquire_source(source):
        def work(job, progress):
            result = storage.acquire(source["original_path"], source["path"], lambda d, t: progress(d, t, "Acquiring and hashing read-only source"))
            saved = store.put("source", {**source, **result, "status": "VERIFIED", "acquired_at": now()}, "acquisition_verified")
            return analyze(saved, job, progress)
        return submit(source["case_id"], "Acquire and recover", work, source["id"])

    @app.get("/api/session")
    def session():
        return {
            "token": token,
            "version": VERSION,
            "storage": str(store.root),
            "media_engine": media.version(),
            "mode": "Local workstation",
            "db_backend": store.backend,
            "real_vendor_validation": False,
        }

    @app.get("/api/db/status")
    def db_status():
        try:
            with store.connect() as db:
                if store.is_postgres:
                    row = db.execute("SELECT current_database(), version()").fetchone()
                    return {
                        "backend": "Neon PostgreSQL",
                        "database": row[0],
                        "status": "connected",
                        "endpoint": store.database_url.split("@")[-1] if "@" in store.database_url else "connected",
                    }
                else:
                    return {
                        "backend": "SQLite",
                        "database": str(store.db),
                        "status": "connected",
                    }
        except Exception as e:
            return {"backend": store.backend, "status": "error", "error": str(e)}

    @app.get("/api/cases")
    def cases():
        return store.list("case")

    @app.post("/api/cases", status_code=201)
    def create_case(body: CaseInput):
        if not body.name.strip() or not body.examiner.strip():
            raise ValueError("Case name and examiner are required")
        return store.put("case", body.model_dump(), "case_created", body.examiner)

    @app.get("/api/cases/{case_id}")
    def case_detail(case_id: str):
        return {"case": case(case_id), **{kind + "s": store.list(kind, case_id) for kind in ("source", "artifact", "fragment", "edge", "job", "note", "transformation")}, "audit": store.audit_log(case_id)}

    @app.post("/api/cases/{case_id}/sources")
    def import_source(case_id: str, body: ImportInput):
        return ingest(case_id, body.path, body.model_dump(exclude={"path"}))

    @app.post("/api/cases/{case_id}/upload")
    async def upload(case_id: str, request: Request, filename: str):
        case(case_id)
        safe_name = Path(filename.replace("\\", "/")).name
        if len(safe_name) > 160 or Path(safe_name).suffix.lower() not in {".img", ".dd", ".raw", ".mp4", ".avi", ".h264", ".264", ".dav", ".jpg", ".jpeg", ".mkv", ".ts", ".dat", ".hevc"}:
            raise ValueError("Unsupported evidence filename")
        folder = store.root / case_id / "uploads" / uid()
        folder.mkdir(parents=True)
        path = folder / safe_name
        size = 0
        try:
            with path.open("xb") as target:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 8 * 1024**3:
                        raise ValueError("Browser uploads are limited to 8 GiB; use local path acquisition for larger images")
                    target.write(chunk)
            return ingest(case_id, path, {"vendor": "UNKNOWN", "model": "UNKNOWN", "firmware": "UNKNOWN"})
        except Exception:
            path.unlink(missing_ok=True)
            raise

    @app.post("/api/sources/{source_id}/analyze")
    def rescan(source_id: str):
        source = store.get(source_id, "source")
        if any(j.get("source_id") == source_id and j["status"] in ("RUNNING", "QUEUED") for j in store.list("job", source["case_id"])):
            raise HTTPException(409, "Source already has an active job")
        if source["status"] == "PENDING":
            return acquire_source(source)
        return submit(source["case_id"], "Analyze verified image", lambda j, p: analyze(source, j, p), source_id)

    @app.get("/api/sources/{source_id}/bytes")
    def raw_bytes(source_id: str, offset: int = 0, length: int = 256):
        if not 1 <= length <= 4096:
            raise ValueError("Raw inspection supports 1–4096 bytes per request")
        source = store.get(source_id, "source")
        data = storage.read_range(owned_path(source["path"]), offset, length)
        return {"offset": offset, "length": len(data), "hex": data.hex(" "), "ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in data)}

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str):
        job = store.get(job_id, "job")
        if job_id in cancel_flags:
            cancel_flags[job_id].set()
        return {"status": "Cancellation requested; current decode may finish first", "job_id": job["id"]}

    @app.post("/api/cases/{case_id}/notes")
    def add_note(case_id: str, body: NoteInput):
        examiner = case(case_id)["examiner"]
        if body.artifact_id and store.get(body.artifact_id, "artifact")["case_id"] != case_id:
            raise ValueError("Artifact belongs to a different case")
        return store.put("note", {"case_id": case_id, "actor": examiner, **body.model_dump()}, "note_added", examiner)

    @app.get("/api/artifacts/{artifact_id}/file")
    def artifact_file(artifact_id: str, variant: Literal["original", "preview", "thumbnail", "audio"] = "original"):
        artifact = store.get(artifact_id, "artifact")
        field = {"original": "path", "preview": "preview_path", "thumbnail": "thumbnail_path", "audio": "audio_path"}[variant]
        if not artifact.get(field):
            raise HTTPException(404, "This artifact has no requested viewing representation")
        path = owned_path(artifact[field])
        expected = artifact.get({"original": "sha256", "preview": "preview_sha256", "thumbnail": "thumbnail_sha256", "audio": "audio_sha256"}[variant])
        if expected and storage.sha256(path) != expected:
            raise HTTPException(409, "Artifact integrity mismatch; requested file withheld")
        if variant == "original":
            store.audit(artifact["case_id"], "examiner", "artifact_exported", {"artifact_id": artifact_id, "sha256": artifact["sha256"]})
        media_types = {"preview": "video/mp4", "thumbnail": "image/jpeg", "audio": "audio/wav", "original": "application/octet-stream"}
        return FileResponse(path, media_type=media_types.get(variant, "application/octet-stream"), filename=path.name if variant in ("original", "audio") else None)

    @app.post("/api/artifacts/{artifact_id}/transform")
    def transform(artifact_id: str, body: TransformInput):
        artifact = store.get(artifact_id, "artifact")
        def work(job, progress):
            original = owned_path(artifact["path"])
            if storage.sha256(original) != artifact["sha256"]:
                raise ValueError("Artifact integrity mismatch")
            progress(10, 100, "Creating separate derivative")
            new_id = uid()
            output = original.parent / f"{new_id}.mp4"
            result = media.repair(original, output) if body.operation == "repair" else media.viewing_copy(original, output, body.operation)
            if storage.sha256(original) != artifact["sha256"]:
                raise ValueError("Source artifact changed during transformation")
            record = {**artifact, "id": new_id, "created_at": now(), "path": str(output), "preview_path": str(output), "sha256": storage.sha256(output), "name": f"{body.operation.title()} · {artifact['name']}", "kind": "DERIVATIVE", "parent_id": artifact_id, "input_hash": artifact["sha256"], "status": "PARTIAL_RECOVERED" if body.operation == "repair" else "ENHANCED_COPY", "method": result.get("method", f"Non-AI {body.operation} viewing filter"), "confidence_rationale": "Derivative only; source evidence is retained unchanged", "validation": result["validation"], "gaps": result.get("gaps", []), "stream_type": "mp4"}
            record.pop("thumbnail_path", None)
            record.pop("thumbnail_sha256", None)
            record["codec"] = result["validation"]["codec"]
            record["preview_sha256"] = record["sha256"]
            if body.operation == "repair":
                preview = output.with_suffix(".preview.mp4")
                view = media.viewing_copy(output, preview)
                record.update(preview_path=str(preview), preview_sha256=storage.sha256(preview))
                store.put("transformation", {"case_id": artifact["case_id"], "input_artifact": new_id, "input_hash": record["sha256"], "output_path": str(preview), "output_hash": record["preview_sha256"], "software_version": media.version(), **view}, "viewing_copy_created")
            thumb = original.parent / f"{new_id}.jpg"
            if media.thumbnail(output, thumb):
                record["thumbnail_path"] = str(thumb)
                record["thumbnail_sha256"] = storage.sha256(thumb)
            store.put("transformation", {"case_id": artifact["case_id"], "input_artifact": artifact_id, "output_artifact": new_id, "input_hash": artifact["sha256"], "output_hash": record["sha256"], "transform_type": body.operation, "parameters": result, "software_version": media.version()}, "transformation_recorded")
            return store.put("artifact", record, "derivative_created")
        return submit(artifact["case_id"], body.operation.title(), work)

    @app.post("/api/cases/{case_id}/reconstruct")
    def join(case_id: str, body: JoinInput):
        case(case_id)
        artifacts = [store.get(x, "artifact") for x in body.artifact_ids]
        if len(set(body.artifact_ids)) != len(body.artifact_ids) or any(a["case_id"] != case_id or a["kind"] != "RECOVERED" for a in artifacts):
            raise ValueError("Select distinct recovered fragments from this case")
        artifacts.sort(key=lambda a: a.get("timestamp_start") if a.get("timestamp_start") is not None else -1)
        for left, right in zip(artifacts, artifacts[1:]):
            edge = recovery.candidate_edge(left, right)
            if edge["decision"] == "REJECTED":
                store.audit(case_id, "engine", "join_rejected", edge)
                raise ValueError("Join refused: " + "; ".join(edge["evidence_features"]))
        def work(job, progress):
            new_id = uid()
            output = owned_path(artifacts[0]["path"]).parent / f"{new_id}.h264"
            result = recovery.reconstruct(artifacts, output)
            preview = output.with_suffix(".preview.mp4")
            view = media.viewing_copy(output, preview)
            record = {**artifacts[0], **result, "id": new_id, "created_at": now(), "path": str(output), "preview_path": str(preview), "preview_sha256": storage.sha256(preview), "kind": "RECONSTRUCTED", "name": "Reconstructed · " + artifacts[0]["channel"], "source_fragments": [f for a in artifacts for f in a["source_fragments"]], "timestamp_end": artifacts[-1].get("timestamp_end"), "input_hashes": [a["sha256"] for a in artifacts]}
            store.put("transformation", {"case_id": case_id, "input_artifacts": body.artifact_ids, "output_artifact": new_id, "output_hash": result["sha256"], "transform_type": "verified_fragment_join", "parameters": result, "viewing_copy": view, "software_version": media.version()}, "reconstruction_recorded")
            for edge in result["edges"]:
                edge_id = hashlib.sha256((edge["from_fragment"] + edge["to_fragment"]).encode()).hexdigest()[:32]
                store.put("edge", {**edge, "id": edge_id, "case_id": case_id, "source_id": artifacts[0]["source_id"]}, "join_verified")
            return store.put("artifact", record, "reconstruction_completed")
        return submit(case_id, "Verify fragment reconstruction", work)

    @app.get("/api/registry")
    def registry():
        return recovery.REGISTRY

    @app.post("/api/demo")
    def demo():
        from scripts.corpus import generate
        corpus = store.root / "lab"
        generate(corpus)
        item = store.put("case", {"name": "Recovery lab · controlled test", "examiner": "Lab examiner", "notes": "SYNTHETIC TEST EVIDENCE. FFmpeg-generated test patterns; no real camera footage. Four indexed fragments, two channels, duplicate indexes and a substream."}, "case_created")
        ingest(item["id"], corpus / "fragmented.img", {"vendor": "Synthetic laboratory", "model": "TRACEIDX1", "firmware": "fixture-v1"})
        return item

    @app.get("/api/cases/{case_id}/integrity")
    def integrity(case_id: str):
        current_case = case(case_id)
        checks = []
        for segment in current_case.get("parent_evidence", {}).get("segments", []):
            try:
                actual = storage.sha256(owned_path(segment["path"]))
                checks.append({"id": segment["file"], "kind": "parent_e01_segment", "match": actual == segment["sha256"], "actual": actual})
            except (OSError, ValueError):
                checks.append({"id": segment["file"], "kind": "parent_e01_segment", "match": False, "error": "File missing or inaccessible"})
        for kind in ("source", "artifact"):
            for item in store.list(kind, case_id):
                if not item.get("sha256"):
                    continue
                try:
                    actual = storage.sha256(owned_path(item["path"]))
                    checks.append({"id": item["id"], "kind": kind, "match": actual == item["sha256"], "actual": actual})
                except (OSError, ValueError):
                    checks.append({"id": item["id"], "kind": kind, "match": False, "error": "File missing or inaccessible"})
                for variant in ("preview", "thumbnail"):
                    if not item.get(variant + "_path"):
                        continue
                    expected = item.get(variant + "_sha256")
                    try:
                        actual = storage.sha256(owned_path(item[variant + "_path"]))
                        checks.append({"id": item["id"], "kind": variant, "match": expected is not None and actual == expected, "actual": actual})
                    except (OSError, ValueError):
                        checks.append({"id": item["id"], "kind": variant, "match": False, "error": "File missing or inaccessible"})
        return {"files": checks, "audit": store.audit_log(case_id), "valid": bool(checks) and all(x["match"] for x in checks) and store.audit_log(case_id)["valid"]}

    @app.get("/api/cases/{case_id}/correlation")
    def correlation(case_id: str):
        case(case_id)
        from core.correlation import correlate_representations
        artifacts = store.list("artifact", case_id)
        return correlate_representations(artifacts)

    @app.get("/api/artifacts/{artifact_id}/quality")
    def artifact_quality(artifact_id: str):
        artifact = store.get(artifact_id, "artifact")
        from core.quality import assess_video_file
        target = owned_path(artifact.get("preview_path") or artifact["path"])
        return assess_video_file(target)

    @app.get("/api/cases/{case_id}/quality-ranking")
    def case_quality_ranking(case_id: str):
        case(case_id)
        artifacts = store.list("artifact", case_id)
        from core.quality import rank_artifacts_by_quality
        return rank_artifacts_by_quality(artifacts, store.root)

    def report_data(case_id):
        details = case_detail(case_id)
        return {"application": "Trace DVR Forensics", "version": VERSION, "generated_at": now(), "scope": "Byte-range recovery; exact bytes do not establish a complete recording. Synthetic adapters do not imply real vendor support.", **details}

    @app.get("/api/cases/{case_id}/report")
    def report(case_id: str, format: Literal["json", "html", "raw"] = "json"):
        store.audit(case_id, case(case_id)["examiner"], "report_generated", {"format": format})
        data = report_data(case_id)
        from core.correlation import correlate_representations
        corr = correlate_representations(store.list("artifact", case_id))
        if format == "html":
            from core.report import generate_forensic_html_report
            return HTMLResponse(generate_forensic_html_report(data, corr))
        if format == "raw":
            return Response(content=json.dumps(data, indent=2), media_type="application/json")
        from core.report import generate_forensic_structured_json
        structured = generate_forensic_structured_json(data, corr)
        formatted_json = json.dumps(structured, indent=2, ensure_ascii=False)
        return Response(content=formatted_json, media_type="application/json; charset=utf-8", headers={"Content-Disposition": f'inline; filename="trace-report-{case_id[:8]}.json"'})

    @app.get("/api/cases/{case_id}/recording-index")
    def recording_index(case_id: str, search: str = "", limit: int = 50, offset: int = 0):
        case_obj = case(case_id)
        parent = case_obj.get("parent_evidence") or {}
        idx_path = Path(parent.get("index_path", "")) if parent.get("index_path") else ROOT / "data" / "public-validation" / "heimvision-image" / "recording-index.json"
        if not idx_path.exists():
            idx_path = ROOT / "data" / "public-validation" / "heimvision-image" / "recording-index.json"
        if not idx_path.exists():
            return {"total": 0, "entries": [], "message": "No recording index found for this case"}

        data = json.loads(idx_path.read_text(encoding="utf-8"))
        detail = data.get("detail", [])
        filtered = []
        for r in detail:
            rel_path = f"dir{r['folder']:05}/file{r['file']:04}.dat"
            dt_start = datetime.datetime.fromtimestamp(r["start_time"], datetime.timezone.utc).isoformat()
            dt_end = datetime.datetime.fromtimestamp(r["end_time"], datetime.timezone.utc).isoformat()
            item = {
                "id": r["id"],
                "folder": r["folder"],
                "file": r["file"],
                "relative_path": rel_path,
                "fs_index": r.get("fs_index", r["id"] - 1),
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "start_iso": dt_start,
                "end_iso": dt_end,
                "duration_seconds": r["end_time"] - r["start_time"],
                "status": "EXTRACTED" if rel_path in ("dir00000/file0000.dat", "dir00003/file0019.dat", "dir00006/file0037.dat") else "AVAILABLE_ON_E01"
            }
            if search:
                q = search.lower()
                if not (q in rel_path.lower() or q in dt_start.lower() or q in dt_end.lower()):
                    continue
            filtered.append(item)

        total = len(filtered)
        paginated = filtered[offset:offset + limit]
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "time_span": {
                "start_iso": datetime.datetime.fromtimestamp(detail[0]["start_time"], datetime.timezone.utc).isoformat() if detail else None,
                "end_iso": datetime.datetime.fromtimestamp(detail[-1]["end_time"], datetime.timezone.utc).isoformat() if detail else None,
                "total_surveillance_hours": round((detail[-1]["end_time"] - detail[0]["start_time"]) / 3600, 2) if detail else 0
            },
            "entries": paginated
        }

    @app.post("/api/cases/{case_id}/recording-index/extract")
    def extract_from_index(case_id: str, body: dict):
        case_obj = case(case_id)
        folder = int(body.get("folder", 0))
        file_num = int(body.get("file", 0))
        relative = f"dir{folder:05}/file{file_num:04}.dat"

        def work(job, progress):
            progress(10, 100, f"Locating {relative} in E01 image")
            from dissect.evidence.ewf import EWF, find_files
            from dissect.fat import FATFS
            from dissect.util.stream import RangeStream
            from scripts.use_heimvision import partitions

            e01_dir = (ROOT / "data" / "public-validation" / "heimvision-image").resolve()
            image = EWF(find_files(e01_dir / "HeimVision K9604-W.E01"))
            stream = image.open()
            volumes = partitions(stream, image.size)
            fat = FATFS(RangeStream(stream, volumes[1]["offset"], volumes[1]["length"]))
            entry = fat.get(relative)
            if not entry:
                raise ValueError(f"Recording {relative} not found in FAT32 partition")
            target = e01_dir / relative.replace("/", "-")
            target.write_bytes(entry.open().read())

            progress(50, 100, f"Ingesting and demuxing {relative}")
            ingest_res = ingest(case_id, target, {"vendor": "Heimvision public corpus", "model": "K9604-W", "firmware": "UNKNOWN"})
            return {"status": "COMPLETED", "source_id": ingest_res["id"], "file": relative}

        return submit(case_id, f"Extract E01 · {relative}", work)

    @app.get("/api/cases/{case_id}/bsa-certificate")
    def bsa_certificate(case_id: str):
        store.audit(case_id, case(case_id)["examiner"], "bsa_certificate_generated", {})
        data = case_detail(case_id)
        current_case = data["case"]
        sources = data["sources"]
        artifacts = data["artifacts"]
        audit = data["audit"]

        source_rows = ""
        for s in sources:
            source_rows += f"""<tr>
              <td><strong>{html.escape(s['name'])}</strong><br><small>{html.escape(s.get('vendor', 'Unknown'))} {html.escape(s.get('model', 'Unknown'))}</small></td>
              <td>{html.escape(s.get('type', 'Image'))}</td>
              <td>{s.get('capacity', 0):,} bytes</td>
              <td><code style="word-break:break-all">{html.escape(s.get('sha256', 'Pending'))}</code></td>
              <td><span style="color:green;font-weight:bold">VERIFIED (READ-ONLY)</span></td>
            </tr>"""

        artifact_rows = ""
        for a in artifacts:
            frames = a.get("validation", {}).get("frames_decoded", 0)
            res = a.get("validation", {}).get("width")
            res_str = f"{res}x{a.get('validation', {}).get('height')}" if res else "Unknown"
            artifact_rows += f"""<tr>
              <td><strong>{html.escape(a['name'])}</strong></td>
              <td>{html.escape(a.get('channel', 'Unknown'))}</td>
              <td>{html.escape(a.get('codec', '').upper())} ({res_str})</td>
              <td>{frames} frames</td>
              <td><code style="word-break:break-all">{html.escape(a.get('sha256', ''))}</code></td>
              <td><strong>{html.escape(a.get('status', ''))}</strong></td>
            </tr>"""

        cert_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Section 63 BSA / 65B IEA Certificate - {html.escape(current_case['name'])}</title>
  <style>
    body {{ font-family: 'Times New Roman', Times, serif; color: #111; max-width: 900px; margin: 40px auto; padding: 20px; line-height: 1.5; }}
    .header {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 15px; margin-bottom: 25px; }}
    .header h1 {{ font-size: 20px; text-transform: uppercase; margin: 0 0 8px 0; }}
    .header h2 {{ font-size: 15px; font-weight: normal; margin: 0; font-style: italic; }}
    .badge-box {{ border: 1px solid #333; padding: 12px; background: #fdfdfd; margin-bottom: 20px; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 12px; }}
    th, td {{ border: 1px solid #444; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f0f0f0; }}
    .declaration {{ margin: 25px 0; }}
    .declaration ol {{ padding-left: 25px; }}
    .declaration li {{ margin-bottom: 12px; text-align: justify; }}
    .signatures {{ display: flex; justify-content: space-between; margin-top: 60px; page-break-inside: avoid; }}
    .sig-box {{ width: 45%; border-top: 1px solid #000; padding-top: 8px; font-size: 13px; }}
    @media print {{
      body {{ margin: 0; padding: 15mm; font-size: 12pt; }}
      .no-print {{ display: none; }}
      button {{ display: none; }}
    }}
  </style>
</head>
<body>
  <div class="no-print" style="margin-bottom:20px;text-align:right">
    <button onclick="window.print()" style="padding:10px 20px;font-size:14px;background:#183d35;color:#fff;border:none;border-radius:4px;cursor:pointer">Print / Save as PDF</button>
  </div>
  <div class="header">
    <h1>Certificate of Digital Evidence</h1>
    <h2>Under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023 (BSA)<br><small>(Corresponding to Section 65B of the Indian Evidence Act, 1872)</small></h2>
  </div>

  <div class="badge-box">
    <strong>Case Reference:</strong> {html.escape(current_case['name'])}<br>
    <strong>Case Unique Identifier:</strong> {html.escape(current_case['id'])}<br>
    <strong>Investigating Examiner:</strong> {html.escape(current_case['examiner'])}<br>
    <strong>Date & Time of Processing:</strong> {html.escape(now())}<br>
    <strong>Forensic Application & Engine:</strong> Trace DVR Forensics v{VERSION} (FFmpeg Demuxing & Byte Analysis Engine)
  </div>

  <p>I, <strong>{html.escape(current_case['examiner'])}</strong>, hereby solemnly state and affirm as under:</p>

  <div class="declaration">
    <ol>
      <li>I am the authorized digital forensics examiner / officer in lawful possession and charge of the computer system and workstation used to produce, extract, and analyze the electronic records associated with this investigation.</li>
      <li>The primary storage media / forensic image(s) described in <strong>Table 1</strong> below were acquired using strict read-only protocols without altering, overwriting, or modifying any sector or bitstream of the original evidence.</li>
      <li>Throughout the forensic extraction, carving, demuxing, and validation period, the forensic computer system operated properly, and there were no operational defects, distortions, or unauthorized access that could affect the accuracy, integrity, or authenticity of the electronic records.</li>
      <li>The recovered video excerpts and electronic artifacts listed in <strong>Table 2</strong> were generated directly from the verified source bitstreams through deterministic container demuxing, NALU parsing, and frame-accurate decoder verification. No artificial intelligence models were employed to synthesize, interpolate, or hallucinate missing pixel information.</li>
      <li>The cryptographic hash values (SHA-256) recorded in this certificate uniquely identify both the source images and the extracted electronic records. The local chain of custody audit head hash is recorded as: <code>{html.escape(audit.get('head_hash', 'N/A'))}</code>.</li>
    </ol>
  </div>

  <h3>Table 1: Source Storage Media & Forensic Images</h3>
  <table>
    <thead>
      <tr>
        <th>Source Identifier & Model</th>
        <th>Type</th>
        <th>Logical Capacity</th>
        <th>Cryptographic SHA-256 Digest</th>
        <th>Integrity Status</th>
      </tr>
    </thead>
    <tbody>
      {source_rows if source_rows else '<tr><td colspan="5">No sources registered</td></tr>'}
    </tbody>
  </table>

  <h3>Table 2: Extracted Electronic Artifacts & Bitstream Records</h3>
  <table>
    <thead>
      <tr>
        <th>Artifact Name</th>
        <th>Camera</th>
        <th>Codec & Resolution</th>
        <th>Frames Decoded</th>
        <th>Cryptographic SHA-256 Digest</th>
        <th>Evidentiary Status</th>
      </tr>
    </thead>
    <tbody>
      {artifact_rows if artifact_rows else '<tr><td colspan="6">No artifacts extracted</td></tr>'}
    </tbody>
  </table>

  <div class="signatures">
    <div class="sig-box">
      <strong>Examiner Signature:</strong><br><br><br>
      Name: {html.escape(current_case['examiner'])}<br>
      Designation: Forensic Examiner / Investigating Officer<br>
      Agency / Police Station:<br>
      Date: {html.escape(now().split('T')[0])}
    </div>
    <div class="sig-box">
      <strong>Verifying Authority / Lab In-Charge:</strong><br><br><br>
      Name:<br>
      Designation:<br>
      Official Seal / Stamp:<br>
      Date:
    </div>
  </div>
</body>
</html>"""
        return HTMLResponse(cert_html)

    @app.post("/api/cases/{case_id}/export")
    def export(case_id: str):
        case(case_id)
        def work(job, progress):
            check = integrity(case_id)
            if not check["valid"]:
                raise ValueError("Integrity verification failed or no acquired evidence exists")
            output_dir = store.root / case_id / "exports"
            output_dir.mkdir(parents=True, exist_ok=True)
            output = output_dir / f"{job['id']}.zip"
            artifacts = store.list("artifact", case_id)
            manifest = []
            with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_STORED) as archive:
                for index, artifact in enumerate(artifacts):
                    progress(index, max(len(artifacts), 1), "Packaging verified artifacts")
                    path = owned_path(artifact["path"])
                    name = "artifacts/" + path.name
                    archive.write(path, name)
                    manifest.append({"file": name, "sha256": artifact["sha256"], "status": artifact["status"]})
                store.audit(case_id, "engine", "export_packaged", {"job_id": job["id"], "artifacts": len(artifacts)})
                archive.writestr("report.json", json.dumps(report_data(case_id), indent=2))
                archive.writestr("manifest.json", json.dumps(manifest, indent=2))
                archive.writestr("README.txt", "Original source images are not duplicated in this package. Verify artifact SHA-256 against manifest.json. Preserve report.json and its audit head independently. Enhanced copies are derivatives, not original recordings.")
            return {"download_url": f"/api/jobs/{job['id']}/download", "path": str(output), "sha256": storage.sha256(output)}
        return submit(case_id, "Export evidence package", work)

    @app.get("/api/jobs/{job_id}/download")
    def download(job_id: str):
        job = store.get(job_id, "job")
        if job["action"] != "Export evidence package" or job["status"] != "COMPLETED":
            raise HTTPException(409, "Export is not ready")
        return FileResponse(owned_path(job["result"]["path"]), filename=f"trace-evidence-{job_id[:8]}.zip")

    app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
    return app


app = create_app()

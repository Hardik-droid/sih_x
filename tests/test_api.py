import io
import json
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import create_app
from core import storage


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        client.headers["x-trace-token"] = client.get("/api/session").json()["token"]
        yield client


def wait_job(client, case_id):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = client.get(f"/api/cases/{case_id}").json()
        if all(j["status"] not in ("QUEUED", "RUNNING") for j in result["jobs"]):
            return result
        time.sleep(0.1)
    pytest.fail("Background job did not finish in 60 seconds")


def test_full_investigator_workflow(client):
    case = client.post("/api/demo").json()
    detail = wait_job(client, case["id"])
    assert detail["jobs"][0]["status"] == "COMPLETED", detail["jobs"]
    assert len(detail["artifacts"]) == 4
    assert detail["sources"][0]["verified"]
    source_id = detail["sources"][0]["id"]
    raw = client.get(f"/api/sources/{source_id}/bytes?offset=510&length=2").json()
    assert raw["hex"] == "55 aa"
    assert client.get(f"/api/sources/{source_id}/bytes?offset=-1").status_code == 400
    assert client.post(f"/api/cases/{case['id']}/notes", json={"text": "Observed indexed fragments"}).status_code == 200
    fragments = detail["artifacts"]
    join = client.post(f"/api/cases/{case['id']}/reconstruct", json={"artifact_ids": [a["id"] for a in fragments[:2]]})
    assert join.status_code == 200, join.text
    detail = wait_job(client, case["id"])
    assert detail["jobs"][-1]["status"] == "COMPLETED", detail["jobs"][-1]
    assert detail["artifacts"][-1]["validation"]["frames_decoded"] == 60
    rejected = client.post(f"/api/cases/{case['id']}/reconstruct", json={"artifact_ids": [a["id"] for a in fragments[1:3]]})
    assert rejected.status_code == 400
    transform = client.post(f"/api/artifacts/{fragments[0]['id']}/transform", json={"operation": "denoise"})
    assert transform.status_code == 200
    detail = wait_job(client, case["id"])
    assert detail["jobs"][-1]["status"] == "COMPLETED", detail["jobs"][-1]
    assert detail["artifacts"][-1]["status"] == "ENHANCED_COPY"
    derivative = detail["artifacts"][-1]
    assert derivative["codec"] == derivative["validation"]["codec"]
    assert derivative["preview_sha256"] == storage.sha256(derivative["preview_path"])
    preview = client.get(f"/api/artifacts/{fragments[0]['id']}/file?variant=preview", headers={"Range": "bytes=0-99"})
    assert preview.status_code == 206 and len(preview.content) == 100
    verified = client.get(f"/api/cases/{case['id']}/integrity").json()
    assert verified["valid"]
    response = client.post(f"/api/cases/{case['id']}/export")
    assert response.status_code == 200
    detail = wait_job(client, case["id"])
    job = detail["jobs"][-1]
    assert job["status"] == "COMPLETED", job
    package = client.get(job["result"]["download_url"])
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        report = json.loads(archive.read("report.json"))
        assert report["audit"]["valid"]
        assert len(json.loads(archive.read("manifest.json"))) == 6
    assert client.get(f"/api/cases/{case['id']}/report?format=html").status_code == 200
    # Rescan is idempotent, preserving artifacts and notes.
    assert client.post(f"/api/sources/{source_id}/analyze").status_code == 200
    detail = wait_job(client, case["id"])
    assert len(detail["artifacts"]) == 6 and len(detail["notes"]) == 1
    # A changed viewing copy must not pass custody checks or be served for review.
    preview_path = Path(fragments[0]["preview_path"])
    preview_path.write_bytes(b"tampered preview")
    assert client.get(f"/api/artifacts/{fragments[0]['id']}/file?variant=preview").status_code == 409
    verified = client.get(f"/api/cases/{case['id']}/integrity").json()
    assert not verified["valid"]
    assert any(f["kind"] == "preview" and not f["match"] for f in verified["files"])


def test_security_and_case_validation(client):
    assert client.post("/api/cases", headers={"x-trace-token": ""}, json={"name": "x", "examiner": "x"}).status_code == 403
    assert client.post("/api/cases", headers={"Origin": "https://evil.example"}, json={"name": "x", "examiner": "x"}).status_code == 403
    assert client.get("/api/cases", headers={"Host": "evil.example"}).status_code == 403
    assert client.post("/api/cases", json={"name": " ", "examiner": "x"}).status_code == 400
    assert client.get("/api/cases/missing").status_code == 404
    item = client.post("/api/cases", json={"name": "<script>alert(1)</script>", "examiner": "Examiner"}).json()
    report = client.get(f"/api/cases/{item['id']}/report?format=html").text
    assert "<script>alert(1)</script>" not in report
    assert client.post(f"/api/cases/{item['id']}/upload?filename=test.exe", content=b"bad").status_code == 400


def test_upload_unknown_media_is_reported(client):
    item = client.post("/api/cases", json={"name": "Unknown image", "examiner": "Examiner"}).json()
    response = client.post(f"/api/cases/{item['id']}/upload?filename=zero.img", content=b"\0" * 8192)
    assert response.status_code == 200
    detail = wait_job(client, item["id"])
    assert detail["jobs"][0]["status"] == "COMPLETED"
    assert detail["artifacts"] == []
    assert detail["sources"][0]["health"]["scheme"] == "RAW"


def test_persistence_and_interrupted_job_recovery(tmp_path):
    root = tmp_path / "persist"
    first = create_app(root)
    with TestClient(first) as client:
        client.headers["x-trace-token"] = client.get("/api/session").json()["token"]
        case = client.post("/api/cases", json={"name": "Persistent", "examiner": "Examiner"}).json()
        first.state.store.put("job", {"case_id": case["id"], "status": "RUNNING", "action": "test", "progress": 20})
    with TestClient(create_app(root)) as client:
        detail = client.get(f"/api/cases/{case['id']}").json()
        assert detail["case"]["name"] == "Persistent"
        assert detail["jobs"][0]["status"] == "INTERRUPTED"


def test_bsa_certificate_generation(client):
    case = client.post("/api/cases", json={"name": "Courtroom Case", "examiner": "Insp. Sharma"}).json()
    resp = client.get(f"/api/cases/{case['id']}/bsa-certificate")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    text = resp.text
    assert "Bharatiya Sakshya Adhiniyam, 2023" in text
    assert "Section 65B of the Indian Evidence Act" in text
    assert "Insp. Sharma" in text
    assert "Courtroom Case" in text
    assert "Examiner Signature:" in text


def test_forensic_structured_json_and_recording_index(client):
    case = client.post("/api/cases", json={"name": "Forensic JSON Case", "examiner": "Insp. Rao"}).json()
    resp = client.get(f"/api/cases/{case['id']}/report")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    data = resp.json()
    assert "$schema" in data
    assert "report_metadata" in data
    assert data["report_metadata"]["statutory_classification"] == "CONFIDENTIAL // OFFICIAL DIGITAL EVIDENCE"
    assert data["case_identification"]["case_id"] == case["id"]
    assert "executive_summary" in data
    assert "parent_storage_lineage" in data
    assert "recovered_video_evidence" in data
    assert "chain_of_custody_audit_ledger" in data
    assert "statutory_declaration" in data

    rec_resp = client.get(f"/api/cases/{case['id']}/recording-index")
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert "total" in rec_data
    assert "entries" in rec_data



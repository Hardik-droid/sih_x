"""Tests for Phase 7: Multi-Representation and Secondary-Stream Correlation Engine."""
import pytest
from core.correlation import correlate_representations
from core import recovery


def test_multi_representation_detects_gap_covered_by_substream():
    fragments = [
        {
            "id": "frag-main-1",
            "channel": "CAM-01",
            "representation": "main",
            "timestamp_start": 0.0,
            "timestamp_end": 10.0,
        },
        {
            "id": "frag-main-2",
            "channel": "CAM-01",
            "representation": "main",
            "timestamp_start": 15.0,
            "timestamp_end": 25.0,
        },
        {
            "id": "frag-sub-1",
            "channel": "CAM-01",
            "representation": "substream",
            "timestamp_start": 8.0,
            "timestamp_end": 18.0,
        },
    ]

    result = correlate_representations(fragments)

    assert result["status"] == "MULTI_REPRESENTATION_CORRELATED"
    assert result["total_primary_gaps"] == 1
    assert result["gaps_covered_by_substreams"] == 1
    assert result["forensic_policy"]["pixel_synthesis"] == "REFUSED"

    cam1 = result["channels"]["CAM-01"]
    assert cam1["status"] == "CORRELATED_WITH_GAPS_COVERED"
    assert len(cam1["gaps_in_primary"]) == 1
    gap = cam1["gaps_in_primary"][0]
    assert gap["gap_start"] == 10.0
    assert gap["gap_end"] == 15.0
    assert gap["duration_seconds"] == 5.0
    assert gap["covered_by_substream"] is True
    assert len(gap["covering_substreams"]) == 1
    assert gap["covering_substreams"][0]["substream_id"] == "frag-sub-1"


def test_cross_camera_substream_does_not_cover_other_camera_gap():
    fragments = [
        {
            "id": "cam1-main-1",
            "channel": "CAM-01",
            "representation": "main",
            "timestamp_start": 0.0,
            "timestamp_end": 10.0,
        },
        {
            "id": "cam1-main-2",
            "channel": "CAM-01",
            "representation": "main",
            "timestamp_start": 15.0,
            "timestamp_end": 25.0,
        },
        {
            "id": "cam2-sub-1",
            "channel": "CAM-02",
            "representation": "substream",
            "timestamp_start": 5.0,
            "timestamp_end": 20.0,
        },
    ]

    result = correlate_representations(fragments)

    cam1 = result["channels"]["CAM-01"]
    assert cam1["status"] == "PRIMARY_ONLY"
    assert cam1["gaps_in_primary"][0]["covered_by_substream"] is False

    cam2 = result["channels"]["CAM-02"]
    assert cam2["status"] == "CORRELATED_CONCURRENT"
    assert len(cam2["gaps_in_primary"]) == 0

    assert result["total_primary_gaps"] == 1
    assert result["gaps_covered_by_substreams"] == 0


def test_redundancy_integration_includes_correlation():
    fragments = [
        {
            "id": "frag-1",
            "channel": "CAM-01",
            "representation": "main",
            "timestamp_start": 0.0,
            "timestamp_end": 2.0,
            "integrity_status": "VERIFIED",
        },
        {
            "id": "frag-2",
            "channel": "CAM-01",
            "representation": "substream",
            "timestamp_start": 0.0,
            "timestamp_end": 2.0,
            "integrity_status": "VERIFIED",
        },
    ]
    findings = [{"offset": 100, "sha256": "abc"}]

    red = recovery.redundancy(fragments, findings)

    assert "multi_representation" in red
    assert red["multi_representation"]["status"] == "MULTI_REPRESENTATION_CORRELATED"
    assert "secondary_streams" in red
    assert "frag-2" in red["secondary_streams"]


def test_correlation_api_endpoint(tmp_path):
    from fastapi.testclient import TestClient
    from app import create_app
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        token = client.get("/api/session").json()["token"]
        client.headers["x-trace-token"] = token
        case = client.post("/api/cases", json={"name": "Correlation Case", "examiner": "Examiner 1"}).json()
        resp = client.get(f"/api/cases/{case['id']}/correlation")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "forensic_policy" in data
        assert data["forensic_policy"]["pixel_synthesis"] == "REFUSED"

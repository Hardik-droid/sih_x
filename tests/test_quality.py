"""Tests for Phase 10: AI / Forensic Quality Assessment & Ranking Engine."""
import numpy as np
import pytest
from pathlib import Path
from PIL import Image

from core import quality, media
from app import create_app
from fastapi.testclient import TestClient


def test_laplacian_sharpness_differentiates_sharp_vs_blurred():
    # Create sharp checkerboard image (64x64)
    sharp = np.zeros((64, 64), dtype=np.float64)
    sharp[::8, :] = 255.0
    sharp[:, ::8] = 255.0

    # Create blurred version by averaging
    blurred = np.full((64, 64), 128.0, dtype=np.float64)
    # slight gradient
    for y in range(64):
        blurred[y, :] += (y - 32) * 0.5

    var_sharp = quality.compute_laplacian_variance(sharp)
    var_blurred = quality.compute_laplacian_variance(blurred)

    assert var_sharp > var_blurred * 10
    assert var_sharp > 500


def test_contrast_and_dynamic_range_metrics():
    high_contrast = np.linspace(0, 255, 64 * 64).reshape((64, 64))
    low_contrast = np.linspace(120, 135, 64 * 64).reshape((64, 64))

    hc_metrics = quality.compute_contrast_metrics(high_contrast)
    lc_metrics = quality.compute_contrast_metrics(low_contrast)

    assert hc_metrics["contrast_std"] > lc_metrics["contrast_std"] * 5
    assert hc_metrics["dynamic_range"] > 200
    assert lc_metrics["dynamic_range"] < 20


def test_assess_frame_fqi_and_immutability_policy(tmp_path):
    img_arr = np.zeros((100, 100, 3), dtype=np.uint8)
    img_arr[::4, :, :] = 255
    img_path = tmp_path / "test_frame.jpg"
    Image.fromarray(img_arr).save(img_path)

    assessment = quality.assess_frame(img_path)

    assert 0 <= assessment["forensic_quality_index"] <= 100
    assert assessment["category"] in ("PRIME", "STANDARD", "DEGRADED", "SEVERE_BLUR_OR_LOW_CONTRAST")
    assert "blur_variance" in assessment
    assert "contrast" in assessment
    assert "blockiness" in assessment
    assert "Diagnostic quality scoring only" in assessment["evidence_policy"]


def test_assess_video_file_and_ranking(tmp_path):
    # Test video assessment with existing sample or synthetic pattern
    video_path = Path("repair-debug.mp4")
    if not video_path.exists():
        pytest.skip("repair-debug.mp4 not found in workspace")

    result = quality.assess_video_file(video_path, num_samples=2)
    assert "forensic_quality_index" in result
    assert result["frames_sampled"] > 0
    assert result["category"] in ("PRIME", "STANDARD", "DEGRADED", "SEVERE_BLUR_OR_LOW_CONTRAST")

    # Test ranking
    artifacts = [
        {"id": "art-1", "name": "CAM01-1", "channel": "CAM01", "path": str(video_path)},
        {"id": "art-2", "name": "CAM01-2", "channel": "CAM01", "path": str(tmp_path / "missing.mp4")}
    ]
    ranked = quality.rank_artifacts_by_quality(artifacts)
    assert len(ranked) == 2
    assert ranked[0]["artifact_id"] == "art-1"
    assert ranked[0]["quality"]["forensic_quality_index"] > ranked[1]["quality"]["forensic_quality_index"]


def test_quality_and_ranking_api_endpoints(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        token = client.get("/api/session").json()["token"]
        client.headers["x-trace-token"] = token
        case = client.post("/api/cases", json={"name": "Quality Case", "examiner": "Examiner Q"}).json()

        # Check ranking on empty case returns empty list
        resp = client.get(f"/api/cases/{case['id']}/quality-ranking")
        assert resp.status_code == 200
        assert resp.json() == []

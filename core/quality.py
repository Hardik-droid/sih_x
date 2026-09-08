"""Forensic video and frame quality assessment engine.

Provides deterministic, mathematically repeatable quality metrics:
1. Laplacian variance blur metric (Pech-Pacheco et al.)
2. Luminance standard deviation and dynamic range contrast metric
3. Blockiness / compression discontinuity estimation
4. Forensic Quality Index (FQI) on a 0-100 scale

Non-destructive: operates only on viewing frames and derivative copies;
original evidence remains immutable.
"""
import math
import subprocess
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image

from core import media


def compute_laplacian_variance(gray_array):
    """Computes the variance of the discrete 3x3 Laplacian on a 2D float array.

    Higher values indicate sharp edges and high frequency detail;
    lower values indicate blur or out-of-focus capture.
    """
    # 3x3 discrete Laplacian kernel:
    #  0  1  0
    #  1 -4  1
    #  0  1  0
    padded = np.pad(gray_array, 1, mode="edge")
    laplacian = (
        padded[:-2, 1:-1]
        + padded[2:, 1:-1]
        + padded[1:-1, :-2]
        + padded[1:-1, 2:]
        - 4 * padded[1:-1, 1:-1]
    )
    return float(np.var(laplacian))


def compute_contrast_metrics(gray_array):
    """Computes luminance standard deviation and dynamic range metrics."""
    std_dev = float(np.std(gray_array))
    p5 = float(np.percentile(gray_array, 5))
    p95 = float(np.percentile(gray_array, 95))
    dynamic_range = max(0.0, p95 - p5)
    # Check for underexposure (mean < 30) or overexposure (mean > 225)
    mean_val = float(np.mean(gray_array))
    is_clipped = p5 < 5 and p95 > 250
    return {
        "contrast_std": round(std_dev, 2),
        "dynamic_range": round(dynamic_range, 2),
        "luminance_mean": round(mean_val, 2),
        "is_clipped": is_clipped
    }


def compute_blockiness_metric(gray_array):
    """Estimates DCT blockiness typical of heavy CCTV compression.

    Compares differences across 8-pixel macroblock boundaries vs intra-block differences.
    """
    h, w = gray_array.shape
    if h < 16 or w < 16:
        return 0.0

    # Horizontal boundary differences across columns 8, 16, 24...
    cols = np.arange(8, w - 1, 8)
    if len(cols) == 0:
        return 0.0
    boundary_diffs = np.abs(gray_array[:, cols] - gray_array[:, cols - 1])
    intra_diffs = np.abs(gray_array[:, cols - 1] - gray_array[:, cols - 2])

    b_mean = float(np.mean(boundary_diffs))
    i_mean = float(np.mean(intra_diffs)) + 1e-5
    ratio = b_mean / i_mean
    # Normalize ratio to a 0.0 - 1.0 compression artifact factor
    return round(float(min(1.0, max(0.0, (ratio - 1.0) / 2.0))), 3)


def assess_frame(image_path_or_array):
    """Evaluates a single frame and returns forensic quality metrics."""
    if isinstance(image_path_or_array, (str, Path)):
        img = Image.open(image_path_or_array).convert("L")
        arr = np.array(img, dtype=np.float64)
    elif isinstance(image_path_or_array, np.ndarray):
        if image_path_or_array.ndim == 3:
            # Convert RGB to Luminance
            arr = np.dot(image_path_or_array[..., :3], [0.299, 0.587, 0.114])
        else:
            arr = image_path_or_array.astype(np.float64)
    else:
        raise ValueError("Unsupported input format for frame assessment")

    blur_var = compute_laplacian_variance(arr)
    contrast = compute_contrast_metrics(arr)
    blockiness = compute_blockiness_metric(arr)

    # Forensic Quality Index (FQI) calculation (0 - 100):
    # Sharpness contribution (log-scaled, capped around var=500): up to 50 pts
    sharpness_score = min(50.0, math.log(max(1.0, blur_var), 10) * 18.5)
    # Contrast contribution (std_dev target 50): up to 35 pts
    contrast_score = min(35.0, (contrast["contrast_std"] / 50.0) * 35.0)
    # Blockiness penalty: up to -15 pts
    blockiness_penalty = blockiness * 15.0

    fqi = round(max(0.0, min(100.0, sharpness_score + contrast_score - blockiness_penalty)), 1)

    if fqi >= 75:
        category = "PRIME"
    elif fqi >= 50:
        category = "STANDARD"
    elif fqi >= 25:
        category = "DEGRADED"
    else:
        category = "SEVERE_BLUR_OR_LOW_CONTRAST"

    return {
        "forensic_quality_index": fqi,
        "category": category,
        "blur_variance": round(blur_var, 2),
        "contrast": contrast,
        "blockiness": blockiness,
        "assessment_method": "Pech-Pacheco Laplacian variance + luminance dynamic range + DCT block boundary discontinuity",
        "evidence_policy": "Diagnostic quality scoring only; original evidence is not modified"
    }


def assess_video_file(video_path, num_samples=3):
    """Samples frames from a video file and produces aggregate forensic quality metrics."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        pattern = str(temp_path / "sample_%02d.jpg")
        # Extract sample frames using FFmpeg
        result = media.run([
            "-v", "error",
            "-i", str(video_path),
            "-vf", f"thumbnail=30,scale=640:-2",
            "-frames:v", str(num_samples),
            "-n", pattern
        ], timeout=45)

        frames = sorted(temp_path.glob("sample_*.jpg"))
        if not frames:
            # Fallback: extract single frame at 0
            single = temp_path / "first.jpg"
            if media.thumbnail(str(video_path), str(single)):
                frames = [single]

        if not frames:
            return {
                "forensic_quality_index": 0.0,
                "category": "UNINSPECTABLE",
                "blur_variance": 0.0,
                "contrast": {"contrast_std": 0.0, "dynamic_range": 0.0, "luminance_mean": 0.0, "is_clipped": False},
                "blockiness": 0.0,
                "frames_sampled": 0,
                "error": "No frames could be extracted for visual quality assessment"
            }

        assessments = [assess_frame(f) for f in frames]
        avg_fqi = round(sum(a["forensic_quality_index"] for a in assessments) / len(assessments), 1)
        avg_blur = round(sum(a["blur_variance"] for a in assessments) / len(assessments), 2)
        avg_contrast = round(sum(a["contrast"]["contrast_std"] for a in assessments) / len(assessments), 2)
        avg_blockiness = round(sum(a["blockiness"] for a in assessments) / len(assessments), 3)

        if avg_fqi >= 75:
            cat = "PRIME"
        elif avg_fqi >= 50:
            cat = "STANDARD"
        elif avg_fqi >= 25:
            cat = "DEGRADED"
        else:
            cat = "SEVERE_BLUR_OR_LOW_CONTRAST"

        return {
            "forensic_quality_index": avg_fqi,
            "category": cat,
            "blur_variance": avg_blur,
            "contrast": {
                "contrast_std": avg_contrast,
                "dynamic_range": round(sum(a["contrast"]["dynamic_range"] for a in assessments) / len(assessments), 2),
                "luminance_mean": round(sum(a["contrast"]["luminance_mean"] for a in assessments) / len(assessments), 2),
                "is_clipped": any(a["contrast"]["is_clipped"] for a in assessments)
            },
            "blockiness": avg_blockiness,
            "frames_sampled": len(frames),
            "assessment_method": "Multi-sample frame Laplacian variance + dynamic range aggregation",
            "evidence_policy": "Diagnostic quality scoring only; original evidence is not modified"
        }


def rank_artifacts_by_quality(artifacts, data_root=None):
    """Sorts recovered artifacts by forensic quality index descending."""
    ranked = []
    for artifact in artifacts:
        # Prefer preview_path or path if preview is available
        target_path = artifact.get("preview_path") or artifact.get("path")
        if target_path and Path(target_path).exists():
            score_data = assess_video_file(target_path)
            ranked.append({
                "artifact_id": artifact["id"],
                "name": artifact.get("name"),
                "channel": artifact.get("channel"),
                "stream_type": artifact.get("stream_type"),
                "quality": score_data
            })
        else:
            ranked.append({
                "artifact_id": artifact["id"],
                "name": artifact.get("name"),
                "channel": artifact.get("channel"),
                "stream_type": artifact.get("stream_type"),
                "quality": {"forensic_quality_index": 0.0, "category": "UNAVAILABLE"}
            })

    ranked.sort(key=lambda x: x["quality"]["forensic_quality_index"], reverse=True)
    return ranked

"""Residual-recovery engine and API tests.

Covers the validation matrix of the DVR/NVR Residual Recovery Prompt:
normal deletion, deletion + continued recording, partial overwrite, heavy
overwrite, fragmented recordings, corrupted recording indexes, filesystem
metadata removal, circular-buffer reuse, plus deletion-evidence levels,
timeline gap detection and machine-verifiable proof bundles.
"""
import json
import time

import pytest
from fastapi.testclient import TestClient

from core import recovery, residual, storage
from scripts.corpus import generate_residual


@pytest.fixture(scope="module")
def residual_corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("residual_corpus")
    generate_residual(root)
    return root


@pytest.fixture
def client(tmp_path):
    from app import create_app
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


def analyze_fixture(residual_corpus, tmp_path, name):
    """Full pipeline over one fixture: discover, recover, classify, bundle."""
    image = residual_corpus / name
    fragments, findings = recovery.discover(image)
    artifacts = []
    for index, fragment in enumerate(fragments):
        output = tmp_path / f"{name}-{index}.{fragment['stream_type']}"
        result = recovery.recover_fragment(image, fragment, output)
        artifacts.append({**fragment, **result, "id": f"{name}-{index}", "kind": "RECOVERED",
                          "source_fragments": [{"offset_start": fragment["offset_start"], "offset_end": fragment["offset_end"]}]})
    residual.derive_fs_states(artifacts, findings)
    residual.attach_detected_overwrites(artifacts, image)
    source = {"id": "src-" + name, "case_id": "case", "name": name, "sha256": storage.sha256(image),
              "capacity": image.stat().st_size, "vendor": "Synthetic lab", "model": "TRACEIDX1",
              "findings": findings}
    return source, artifacts, residual.build_case_proof_bundle(source, artifacts)


def test_corpus_residual_ground_truth(residual_corpus):
    manifest = json.loads((residual_corpus / "residual_manifest.json").read_text())
    assert len(manifest["artifacts"]) == 8
    assert all(storage.sha256(residual_corpus / a["file"]) == a["sha256"] for a in manifest["artifacts"])


def test_normal_deletion_confirmed_by_metadata(residual_corpus, tmp_path):
    source, artifacts, bundle = analyze_fixture(residual_corpus, tmp_path, "residual_deleted_confirmed.img")
    levels = {e["artifact_id"]: e["level"] for e in bundle["recovery"]["deletion_evidence"]}
    assert set(levels.values()) <= {residual.DELETION_CONFIRMED_BY_METADATA, residual.CONTENT_RECOVERED_ONLY}
    assert residual.DELETION_CONFIRMED_BY_METADATA in levels.values()
    # The flagged (older) recording must be the confirmed one; the live one must not.
    for entry in bundle["recovery"]["deletion_evidence"]:
        if entry["identity"]["recording_identifier"] == "REC-A-DEL":
            assert entry["level"] == residual.DELETION_CONFIRMED_BY_METADATA
        if entry["identity"]["recording_identifier"] == "REC-B-LIVE":
            assert entry["level"] == residual.CONTENT_RECOVERED_ONLY
    assert bundle["recovery"]["overwrite_analysis"]["mechanism"] == residual.OVERWRITE_FILE_DELETION


def test_continued_recording_corroborates_deletion(residual_corpus, tmp_path):
    source, artifacts, bundle = analyze_fixture(residual_corpus, tmp_path, "residual_continued_recording.img")
    by_level = {}
    for entry in bundle["recovery"]["deletion_evidence"]:
        by_level.setdefault(entry["level"], []).append(entry)
    assert residual.DELETION_CORROBORATED in by_level
    for entry in by_level[residual.DELETION_CORROBORATED]:
        assert entry["identity"]["recording_identifier"] is None  # orphaned bytes carry no identifier
        assert entry["metadata_basis"][0]["kind"] == "surviving_recording_index"


def test_partial_overwrite_reports_missing_ranges(residual_corpus, tmp_path):
    source, artifacts, bundle = analyze_fixture(residual_corpus, tmp_path, "residual_partial_overwrite.img")
    entry = bundle["recovery"]["deletion_evidence"][0]
    assert entry["level"] == residual.RESIDUAL_CONTENT_RECOVERED
    region = bundle["recovery"]["overwrite_analysis"]["regions"][0]
    assert region["overwritten_ranges"], "physically detected overwrite must be reported"
    assert region["overwritten_ranges"][0]["status"] == "SUSPECTED_OVERWRITTEN_ZEROED"
    assert region["missing_bytes"] == 0  # envelope includes zeroed region; extent proven
    assert region["reconstruction_confidence"] == "MEDIUM"
    assert region["recovered_bytes"] > 0


def test_heavy_overwrite_is_low_confidence_residual(residual_corpus, tmp_path):
    source, artifacts, bundle = analyze_fixture(residual_corpus, tmp_path, "residual_heavy_overwrite.img")
    entry = bundle["recovery"]["deletion_evidence"][0]
    assert entry["level"] == residual.RESIDUAL_CONTENT_RECOVERED
    region = bundle["recovery"]["overwrite_analysis"]["regions"][0]
    assert region["reconstruction_confidence"] == "LOW"
    overwritten = region["overwritten_ranges"]
    assert overwritten and overwritten[0]["status"] == "SUSPECTED_OVERWRITTEN_ZEROED"
    run_len = overwritten[0]["offset_end"] - overwritten[0]["offset_start"]
    extent_len = region["physical_offsets"][0]["offset_end"] - region["physical_offsets"][0]["offset_start"]
    assert run_len > extent_len * 0.5


def test_fragmented_recording_groups_and_hole(residual_corpus, tmp_path):
    source, artifacts, bundle = analyze_fixture(residual_corpus, tmp_path, "residual_fragmented_recording.img")
    assert len(artifacts) == 2
    regions = bundle["recovery"]["overwrite_analysis"]["regions"]
    assert all(r["recording_group"] == "REC-H-FRAG" for r in regions)
    hole = regions[0]["recording_missing_byte_ranges"]
    assert hole and hole[0]["offset_start"] == 8192 + len((residual_corpus / "segment.h264").read_bytes()) // 2
    assert hole[0]["status"] == "MISSING_OR_OVERWRITTEN"
    assert all(r["reconstruction_confidence"] == "MEDIUM" for r in regions)


def test_corrupted_index_never_infers_deletion(residual_corpus, tmp_path):
    source, artifacts, bundle = analyze_fixture(residual_corpus, tmp_path, "residual_corrupted_index.img")
    entry = bundle["recovery"]["deletion_evidence"][0]
    assert entry["level"] == residual.CONTENT_RECOVERED_ONLY
    assert "not evidence of deletion" in entry["rationale"]
    # The broken index must be reported as an invalid finding, not silently dropped.
    assert any(f.get("status") == "INVALID" for f in source["findings"])


def test_fs_metadata_removed_is_content_only(residual_corpus, tmp_path):
    source, artifacts, bundle = analyze_fixture(residual_corpus, tmp_path, "residual_fs_metadata_removed.img")
    assert bundle["recovery"]["deletion_evidence"][0]["level"] == residual.CONTENT_RECOVERED_ONLY
    assert bundle["recovery"]["overwrite_analysis"]["mechanism"] == residual.OVERWRITE_UNKNOWN


def test_circular_reuse_labels_mechanism_and_overlap(residual_corpus, tmp_path):
    source, artifacts, bundle = analyze_fixture(residual_corpus, tmp_path, "residual_circular_reuse.img")
    analysis = bundle["recovery"]["overwrite_analysis"]
    assert analysis["mechanism"] == residual.OVERWRITE_CIRCULAR
    assert any("overlap" in b.lower() for b in analysis["mechanism_basis"])
    deleted = [r for r in analysis["regions"] if (r["recording_identity"] or {}).get("recording_identifier") == "REC-K-OLD"]
    assert deleted and deleted[0]["allocation_state"] == "UNALLOCATED"
    reuse = [r for r in analysis["regions"] if (r["recording_identity"] or {}).get("recording_identifier") == "REC-L-NEW"]
    assert reuse and reuse[0]["allocation_state"] == "ALLOCATED"
    assert "REC-K-OLD" in (reuse[0]["overlapped_by"] or [])


def test_device_family_labeling_is_explicit_not_implied():
    source = {"id": "s", "case_id": "c", "name": "disk.img", "sha256": "0" * 64, "capacity": 1024,
              "vendor": "Honeywell", "model": "MAXPRO NVR", "findings": []}
    bundle = residual.build_case_proof_bundle(source, [])
    analysis = bundle["recovery"]["overwrite_analysis"]
    assert analysis["mechanism"] == residual.OVERWRITE_CIRCULAR
    assert any("dfrws usa 2026" in b.lower() for b in analysis["mechanism_basis"])
    assert any("not established from this image" in b.lower() for b in analysis["mechanism_basis"])


def test_deletion_claim_without_metadata_is_unsupported(residual_corpus, tmp_path):
    image = residual_corpus / "residual_fs_metadata_removed.img"
    fragments, findings = recovery.discover(image)
    artifacts = []
    for index, fragment in enumerate(fragments):
        output = tmp_path / f"claim-{index}.{fragment['stream_type']}"
        result = recovery.recover_fragment(image, fragment, output)
        artifacts.append({**fragment, **result, "id": f"claim-{index}", "kind": "RECOVERED",
                          "deletion_claim": "examiner believes this recording was deleted",
                          "source_fragments": [{"offset_start": fragment["offset_start"], "offset_end": fragment["offset_end"]}]})
    residual.derive_fs_states(artifacts, findings)
    source = {"id": "claim-src", "case_id": "case", "name": "claim.img", "sha256": "0" * 64,
              "capacity": image.stat().st_size, "vendor": "Synthetic lab", "model": "TRACEIDX1", "findings": findings}
    bundle = residual.build_case_proof_bundle(source, artifacts)
    assert bundle["recovery"]["deletion_evidence"][0]["level"] == residual.DELETION_UNSUPPORTED


def test_gap_analysis_reports_never_fills():
    artifacts = [
        {"kind": "RECOVERED", "channel": "CAM-01", "timestamp_start": 0.0, "timestamp_end": 10.0, "id": "a"},
        {"kind": "RECOVERED", "channel": "CAM-01", "timestamp_start": 25.0, "timestamp_end": 30.0, "id": "b"},
    ]
    gaps = residual.analyze_gaps(artifacts)
    channel = gaps["channels"]["CAM-01"]
    assert channel["gap_count"] == 1
    assert channel["gaps"][0] == {"gap_start": 10.0, "gap_end": 25.0, "duration_seconds": 15.0,
                                  "status": "TIMELINE_GAP_NOT_FILLED"}
    assert channel["coverage"] == "PARTIAL"


def test_bundle_verifies_and_detects_tampering(residual_corpus, tmp_path):
    source, artifacts, bundle = analyze_fixture(residual_corpus, tmp_path, "residual_partial_overwrite.img")
    image = residual_corpus / "residual_partial_overwrite.img"
    report = residual.verify_proof_bundle(bundle, source_path=image)
    assert report["valid"], report["checks"]

    tampered = json.loads(json.dumps(bundle))
    tampered["recovery"]["deletion_evidence"][0]["level"] = residual.DELETION_CONFIRMED_BY_METADATA
    assert not residual.verify_proof_bundle(tampered)["valid"]

    wrong_image = residual_corpus / "residual_heavy_overwrite.img"
    assert not residual.verify_proof_bundle(bundle, source_path=wrong_image)["valid"]


def test_orphan_rule_requires_intact_nonempty_index():
    findings = [{"status": "VALIDATED", "records": 1, "offset": 1024}]
    artifacts = [
        {"id": "live", "kind": "RECOVERED", "recording_identifier": "REC-1", "offset_start": 100, "offset_end": 200},
        {"id": "orphan", "kind": "RECOVERED", "offset_start": 500, "offset_end": 600},
    ]
    residual.derive_fs_states(artifacts, findings)
    assert artifacts[1]["fs_state"] == "ORPHANED"
    # Empty validated index: no reference base, nothing may be marked orphaned.
    artifacts2 = [{"id": "c", "kind": "RECOVERED", "offset_start": 0, "offset_end": 10}]
    residual.derive_fs_states(artifacts2, [{"status": "VALIDATED", "records": 0, "offset": 1024}])
    assert "fs_state" not in artifacts2[0]
    # No validated index at all.
    residual.derive_fs_states(artifacts2, [{"status": "INVALID", "offset": 1024}])
    assert "fs_state" not in artifacts2[0]


def test_api_residual_and_proof_bundle_endpoints(client):
    case = client.post("/api/demo").json()
    detail = wait_job(client, case["id"])
    assert detail["jobs"][0]["status"] == "COMPLETED"

    residual_payload = client.get(f"/api/cases/{case['id']}/residual").json()
    assert residual_payload["bundle_schema"] == "TRACE-RESIDUAL-CASE-BUNDLE-V1"
    assert residual_payload["policy"]["carved_only_is_not_deletion_evidence"] is True
    source_bundle = residual_payload["sources"][0]["bundle"]
    assert source_bundle["bundle_schema"] == "TRACE-RESIDUAL-PROOF-BUNDLE-V1"
    levels = {e["level"] for e in source_bundle["recovery"]["deletion_evidence"]}
    assert levels == {residual.CONTENT_RECOVERED_ONLY}

    verified = client.post(f"/api/cases/{case['id']}/proof-bundle/verify").json()
    assert verified["verification"]["valid"] is True

    source_id = detail["sources"][0]["id"]
    deep = client.post(f"/api/sources/{source_id}/proof-bundle/verify").json()
    assert deep["valid"] is True
    assert any(c["check"] == "source_sha256" and c["match"] for c in deep["checks"])
    assert any(c["check"].startswith("range:") and c["match"] for c in deep["checks"])

    audit = client.get(f"/api/cases/{case['id']}").json()["audit"]["events"]
    assert any(e["action"] == "proof_bundle_verified" for e in audit)


def test_registry_documents_residual_layer():
    registry = {entry["format_id"]: entry for entry in recovery.REGISTRY}
    entry = registry["TRACE-RESIDUAL-EVIDENCE-V1"]
    assert entry["status"] == "VALIDATED"
    assert any("never" in limit or "not claimed" in limit for limit in entry["known_limitations"])

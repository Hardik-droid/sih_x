import hashlib
import json
import struct
from pathlib import Path

import pytest

from core import media, recovery, storage
from core.store import Store
from scripts.corpus import generate


@pytest.fixture(scope="session")
def corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("corpus")
    generate(root)
    return root


def test_corpus_ground_truth(corpus):
    manifest = json.loads((corpus / "manifest.json").read_text())
    assert all(storage.sha256(corpus / x["file"]) == x["sha256"] for x in manifest["artifacts"])
    assert media.validate(corpus / "normal.mp4")["frames_decoded"] == 30


def test_acquisition_resume_and_immutable(corpus, tmp_path):
    source, target = corpus / "normal.mp4", tmp_path / "copy.img"
    original = source.read_bytes()
    target.with_suffix(".img.partial").write_bytes(original[:1234])
    result = storage.acquire(source, target)
    assert result["verified"] and source.read_bytes() == original == target.read_bytes()
    with pytest.raises(ValueError):
        storage.acquire(source, source)
    bad = tmp_path / "bad.img"
    bad.with_suffix(".img.partial").write_bytes(b"bad")
    with pytest.raises(ValueError, match="prefix"):
        storage.acquire(source, bad)
    alias_source = tmp_path / "alias.img.partial"
    alias_source.write_bytes(original)
    with pytest.raises(ValueError, match="separate"):
        storage.acquire(alias_source, tmp_path / "alias.img")
    assert alias_source.read_bytes() == original


def test_storage_and_bounds(corpus):
    report = storage.inspect_storage(corpus / "fragmented.img")
    assert report["scheme"] == "MBR"
    assert report["volumes"][0]["filesystem"] == "ext family"
    assert storage.inspect_storage(corpus / "damaged_partition.img")["scheme"] == "RAW"
    with pytest.raises(ValueError):
        storage.read_range(corpus / "normal.mp4", -1, 3)
    with pytest.raises(ValueError):
        storage.read_range(corpus / "normal.mp4", 0, 10**12)


def test_deleted_clip_exact_hash(corpus, tmp_path):
    fragments, _ = recovery.discover(corpus / "deleted.img")
    fragment = next(f for f in fragments if f["stream_type"] == "mp4")
    assert fragment["offset_start"] == 8192
    result = recovery.recover_fragment(corpus / "deleted.img", fragment, tmp_path / "recovered.mp4")
    assert result["sha256"] == storage.sha256(corpus / "normal.mp4")
    assert result["status"] == "EXACT_RECOVERED"


def indexed_fragments(corpus, tmp_path):
    fragments, findings = recovery.discover(corpus / "fragmented.img")
    output = []
    for i, fragment in enumerate(fragments):
        path = tmp_path / f"fragment-{i}.h264"
        result = recovery.recover_fragment(corpus / "fragmented.img", fragment, path)
        output.append({**fragment, **result, "id": str(i), "source_id": "source", "path": str(path)})
    return output, findings


def test_reconstruct_and_reject_cross_camera(corpus, tmp_path):
    fragments, findings = indexed_fragments(corpus, tmp_path)
    result = recovery.reconstruct(fragments[:2], tmp_path / "joined.h264")
    assert result["validation"]["frames_decoded"] == 60
    assert all(edge["decision"] == "ACCEPTED" for edge in result["edges"])
    with pytest.raises(ValueError, match="channel"):
        recovery.reconstruct(fragments[1:3], tmp_path / "bad.h264")
    assert recovery.redundancy(fragments, findings)["duplicate_indexes"]
    assert recovery.redundancy(fragments, findings)["secondary_streams"]
    unknown = {**fragments[1], "channel": None}
    assert recovery.candidate_edge(fragments[0], unknown)["decision"] == "REJECTED"
    substream = {**fragments[1], "representation": "substream"}
    assert recovery.candidate_edge(fragments[0], substream)["decision"] == "REJECTED"
    invalid_time = {**fragments[1], "timestamp_start": float("nan")}
    assert recovery.candidate_edge(fragments[0], invalid_time)["decision"] == "REJECTED"


def test_truncated_repair_and_no_invented_index(corpus, tmp_path):
    truncated = media.validate(corpus / "truncated.mp4")
    assert 0 < truncated["frames_decoded"] < 30
    repaired = media.repair(corpus / "truncated.mp4", tmp_path / "repaired.mp4")
    assert repaired["validation"]["decode_result"] == "PASS"
    assert repaired["gaps"]
    with pytest.raises(ValueError):
        media.repair(corpus / "corrupted.mp4", tmp_path / "impossible.mp4")


def test_redundancy_only_with_verified_layout():
    a, b = b"abcd", b"wxyz"
    parity = bytes(x ^ y for x, y in zip(a, b))
    assert recovery.recover_xor([a, None], parity, hashlib.sha256(b).hexdigest()) == b
    with pytest.raises(ValueError):
        recovery.recover_xor([None, None], parity, hashlib.sha256(b).hexdigest())
    with pytest.raises(ValueError):
        recovery.recover_xor([a, None], parity, "0" * 64)


def test_enhancement_preserves_original(corpus, tmp_path):
    source = corpus / "normal.mp4"
    before = storage.sha256(source)
    result = media.viewing_copy(source, tmp_path / "enhanced.mp4", "denoise")
    assert result["validation"]["decode_result"] == "PASS"
    assert storage.sha256(source) == before


def test_insufficient_and_bad_index(corpus, tmp_path):
    assert recovery.discover(corpus / "insufficient.img")[0] == []
    invalid = tmp_path / "invalid.img"
    invalid.write_bytes(recovery.INDEX_MAGIC + struct.pack("<II", 100, 0) + b"0" * 100)
    assert recovery.index_records(invalid)[1][0]["status"] == "INVALID"


def test_audit_chain_tampering(tmp_path):
    store = Store(tmp_path)
    case = store.put("case", {"name": "test"}, "case_created")
    store.audit(case["id"], "examiner", "note_added", {"note": "Observed"})
    assert store.audit_log(case["id"])["valid"]
    with store.connect() as db:
        db.execute("UPDATE audit SET payload='{}' WHERE seq=1")
    assert not store.audit_log(case["id"])["valid"]


def test_entity_ids_cannot_overwrite_artifacts(tmp_path):
    store = Store(tmp_path)
    artifact = store.put("artifact", {"path": "evidence.mp4"})
    with pytest.raises(ValueError, match="entity types"):
        store.put("fragment", {"id": artifact["id"], "offset_start": 0})
    assert store.get(artifact["id"], "artifact")["path"] == "evidence.mp4"

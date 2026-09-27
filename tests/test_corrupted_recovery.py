from pathlib import Path
from core import media, recovery


def test_corrupted_mp4_salvage_reconstruction(corpus, tmp_path):
    normal = corpus / "normal.mp4"
    data = normal.read_bytes()

    # Create unfinalized power-loss MP4: ftyp + mdat without moov box
    mdat_pos = data.find(b"mdat")
    assert mdat_pos > 0, "mdat atom must exist in normal.mp4"
    power_loss_mp4 = tmp_path / "power_loss.mp4"
    power_loss_mp4.write_bytes(data[:32] + data[mdat_pos - 4:])

    # Direct validation of the power-loss MP4 must fail because moov is missing
    val_before = media.validate(power_loss_mp4)
    assert val_before["decode_result"] == "FAIL"
    assert val_before["frames_decoded"] == 0

    # Forensic reconstruction must salvage the surviving frames
    salvaged_mp4 = tmp_path / "salvaged.mp4"
    salvaged = media.reconstruct_corrupted_stream(power_loss_mp4, salvaged_mp4)

    assert salvaged is not None, "Reconstruction must succeed"
    assert salvaged["validation"]["frames_decoded"] > 0, "Must recover surviving video frames"
    assert salvaged_mp4.exists()
    assert salvaged_mp4.stat().st_size > 100


def test_recovery_engine_recovers_unfinalized_fragment(corpus, tmp_path):
    normal = corpus / "normal.mp4"
    data = normal.read_bytes()
    mdat_pos = data.find(b"mdat")
    unfinalized_bytes = data[:32] + data[mdat_pos - 4:]
    power_loss_mp4 = tmp_path / "power_loss.mp4"
    power_loss_mp4.write_bytes(unfinalized_bytes)

    out = tmp_path / "recovered.mp4"
    frag = {
        "offset_start": 0,
        "offset_end": len(unfinalized_bytes),
        "stream_type": "mp4",
        "parser": "STANDARD-MEDIA",
        "structurally_complete": False,
        "channel": None,
        "timestamp_start": None,
        "timestamp_end": None,
    }
    result = recovery.recover_fragment(power_loss_mp4, frag, out)
    assert result["status"] == "PARTIAL_RECOVERED"
    assert result["validation"]["frames_decoded"] > 0

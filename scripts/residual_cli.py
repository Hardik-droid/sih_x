"""DVR/NVR deleted & residual-video recovery CLI.

Run against a raw image or media file without starting the web app:

    python -m scripts.residual_cli path/to/image.img
    python -m scripts.residual_cli path/to/image.img --verify
    python -m scripts.residual_cli path/to/image.img --output bundle.json
    python -m scripts.residual_cli path/to/image.img --vendor Honeywell --model "MAXPRO NVR"

The analysis is read-only and reuses Trace's acquisition, discovery and
media-validation architecture. The proof bundle it prints is machine
verifiable: re-run with ``--verify`` against the same image to recompute the
payload hash, re-read every claimed byte range and re-hash the image.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from core import recovery, residual, storage


def _artifact_records(fragments, image_path, tmp_dir):
    """Recover every discovered candidate and return artifact-style records."""
    records = []
    for index, fragment in enumerate(fragments):
        output = tmp_dir / f"candidate-{index:03}.{fragment['stream_type']}"
        try:
            result = recovery.recover_fragment(image_path, fragment, output)
        except (ValueError, OSError) as error:
            records.append({**fragment, "id": f"candidate-{index:03}", "status": "UNRECOVERABLE",
                            "validation": {"frames_decoded": 0}, "recovery_error": str(error),
                            "source_fragments": [{"offset_start": fragment["offset_start"], "offset_end": fragment["offset_end"]}]})
            output.unlink(missing_ok=True)
            continue
        records.append({**fragment, **result, "id": f"candidate-{index:03}",
                        "source_fragments": [{"offset_start": fragment["offset_start"], "offset_end": fragment["offset_end"]}]})
    return records


def analyze(image_path, vendor="UNKNOWN", model="UNKNOWN", firmware="UNKNOWN"):
    image_path = Path(image_path)
    size = image_path.stat().st_size
    source = {"id": "cli-source", "case_id": "cli", "name": image_path.name,
              "sha256": storage.sha256(image_path), "capacity": size,
              "vendor": vendor, "model": model, "firmware": firmware}
    fragments, findings = recovery.discover(image_path)
    import tempfile
    with tempfile.TemporaryDirectory(prefix="trace-residual-") as scratch:
        records = _artifact_records(fragments, image_path, Path(scratch))
    residual.derive_fs_states(records, findings)
    residual.attach_detected_overwrites(records, image_path)
    bundle = residual.build_case_proof_bundle(source, records, extra_recovery={"candidate_count": len(fragments)})
    return bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description="Trace residual-recovery analysis (read-only)")
    parser.add_argument("image", help="Path to a raw image (.img/.dd/.raw) or media file")
    parser.add_argument("--vendor", default="UNKNOWN")
    parser.add_argument("--model", default="UNKNOWN")
    parser.add_argument("--firmware", default="UNKNOWN")
    parser.add_argument("--verify", action="store_true", help="Re-verify the produced bundle against the image")
    parser.add_argument("--output", type=Path, help="Write the JSON bundle to this path")
    args = parser.parse_args(argv)

    image_path = Path(args.image)
    if not image_path.is_file():
        parser.error(f"No such file: {image_path}")
    bundle = analyze(image_path, args.vendor, args.model, args.firmware)

    text = json.dumps(bundle, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"Proof bundle written to {args.output}", file=sys.stderr)
    else:
        print(text)

    evidence = bundle["recovery"]["deletion_evidence"]
    overwrite = bundle["recovery"]["overwrite_analysis"]
    print(f"\nSource SHA-256 : {bundle['source']['sha256']}", file=sys.stderr)
    print(f"Candidates     : {bundle['recovery'].get('candidate_count', bundle['recovery']['artifact_count'])}", file=sys.stderr)
    print(f"Mechanism      : {overwrite['mechanism']}", file=sys.stderr)
    levels = {}
    for item in evidence:
        levels[item["level"]] = levels.get(item["level"], 0) + 1
    for level, count in sorted(levels.items()):
        print(f"{level:34} {count}", file=sys.stderr)

    if args.verify:
        report = residual.verify_proof_bundle(bundle, source_path=image_path)
        print(f"\nVerification   : {'VALID' if report['valid'] else 'FAILED'} ({len(report['checks'])} checks)", file=sys.stderr)
        if not report["valid"]:
            for check in report["checks"]:
                if not check["match"]:
                    print(f"  FAILED: {check}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

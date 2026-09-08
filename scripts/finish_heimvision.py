"""Attach completed logical E01 verification to the existing recovery case.

May run alongside the app; this only appends an audit event and updates case
metadata. It does not start another app instance or interrupt recovery jobs.
"""
import json
import time
from pathlib import Path

from core import storage
from core.store import Store


def main():
    root = Path("data/public-validation/heimvision-image")
    result_path = root / "logical-image-verification.json"
    deadline = time.monotonic() + 7200
    while time.monotonic() < deadline:
        try:
            result = json.loads(result_path.read_text())
            break
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(10)
    else:
        raise TimeoutError("Logical verification did not finish; case remains pending")
    store = Store("data")
    case_id = json.loads((root / "recovery-case.json").read_text())["case_id"]
    case = store.get(case_id, "case")
    parent = case["parent_evidence"]
    if not all(storage.sha256(s["path"]) == s["sha256"] for s in parent["segments"]):
        raise ValueError("E01 segment changed after recovery; logical verification not attached")
    parent["logical_verification"] = result
    store.put("case", {**case, "parent_evidence": parent}, "logical_image_verification_recorded")
    report_path = root / "recovery-results.json"
    report = json.loads(report_path.read_text())
    report["parent_evidence"] = parent
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps({"case_id": case_id, "logical_verification": result}, indent=2), flush=True)
    if not result["verified"]:
        raise ValueError("Logical image did not match the published hashes")


if __name__ == "__main__":
    main()

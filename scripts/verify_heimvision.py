"""Stream the complete published Heimvision E01 without creating a raw disk copy."""
import hashlib
import json
import time
from pathlib import Path

from dissect.evidence.ewf import EWF, find_files


def main():
    root = Path("data/public-validation/heimvision-image")
    image = EWF(find_files(root / "HeimVision K9604-W.E01"))
    digests = {name: hashlib.new(name) for name in ("md5", "sha1", "sha256")}
    expected = {"md5": "4895ea6d10b08c29fb1bb03591adc7b2", "sha1": "06f48890961187979ed4142ceab8a7144bd4dfea"}
    done, start, last = 0, time.monotonic(), 0
    with image.open() as stream:
        while block := stream.read(8 * 1024 * 1024):
            for digest in digests.values():
                digest.update(block)
            done += len(block)
            if time.monotonic() - last > 15:
                progress = {"bytes_read": done, "total": image.size, "percent": round(done / image.size * 100, 2), "elapsed_seconds": round(time.monotonic() - start, 1)}
                (root / "verification-progress.json").write_text(json.dumps(progress))
                print(json.dumps(progress), flush=True)
                last = time.monotonic()
    result = {"logical_size": image.size, "bytes_read": done, "hashes": {k: d.hexdigest() for k, d in digests.items()}, "published_hashes": expected, "elapsed_seconds": round(time.monotonic() - start, 1)}
    result["verified"] = done == image.size and all(result["hashes"][k] == v for k, v in expected.items())
    (root / "logical-image-verification.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)
    if not result["verified"]:
        raise ValueError("Logical E01 image does not match published hashes")


if __name__ == "__main__":
    main()

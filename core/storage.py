import hashlib
import json
import os
import struct
import zlib
from pathlib import Path

CHUNK = 4 * 1024 * 1024


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def acquire(source, destination, progress=lambda *_: None):
    """Resume only after verifying the existing prefix; never open source writable."""
    source, destination = Path(source).resolve(strict=True), Path(destination).resolve()
    if not source.is_file() or source == destination:
        raise ValueError("Select a regular forensic image; acquire hardware with a write blocker first.")
    if destination.exists():
        raise ValueError("Acquisition destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    if partial.is_symlink() or source == partial or (partial.exists() and source.samefile(partial)):
        raise ValueError("Acquisition partial target must be separate from the source")
    before = source.stat()
    done = partial.stat().st_size if partial.exists() else 0
    if done > before.st_size:
        raise ValueError("Resume image is larger than source")
    digest = hashlib.sha256()
    with source.open("rb") as incoming:
        if done:
            with partial.open("rb") as existing:
                remaining = done
                while remaining:
                    block = incoming.read(min(CHUNK, remaining))
                    if not block or block != existing.read(len(block)):
                        raise ValueError("Resume prefix differs from original source")
                    digest.update(block)
                    remaining -= len(block)
        with partial.open("ab") as outgoing:
            while block := incoming.read(CHUNK):
                outgoing.write(block)
                digest.update(block)
                done += len(block)
                progress(done, before.st_size)
            outgoing.flush()
            os.fsync(outgoing.fileno())
    after = source.stat()
    expected = digest.hexdigest()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Source changed during acquisition")
    if sha256(partial) != expected or sha256(source) != expected:
        raise ValueError("Acquisition verification failed")
    partial.replace(destination)
    return {"sha256": expected, "capacity": done, "method": "read-only file copy; full SHA-256 read-back", "read_errors": [], "verified": True}


def read_range(path, offset, length):
    size = Path(path).stat().st_size
    if offset < 0 or length < 0 or offset + length > size:
        raise ValueError("Byte range is outside the evidence image")
    with open(path, "rb") as handle:
        handle.seek(offset)
        data = handle.read(length)
    if len(data) != length:
        raise OSError("Short evidence read")
    return data


def copy_range(source, output, start, end):
    if start < 0 or end <= start or end > Path(source).stat().st_size:
        raise ValueError("Invalid extraction range")
    with open(source, "rb") as incoming, open(output, "xb") as outgoing:
        incoming.seek(start)
        remaining = end - start
        while remaining:
            block = incoming.read(min(CHUNK, remaining))
            if not block:
                raise OSError("Short evidence read")
            outgoing.write(block)
            remaining -= len(block)


def filesystem(data):
    if data[3:11] == b"NTFS    ":
        return "NTFS"
    if data[3:11] == b"EXFAT   ":
        return "exFAT"
    if data[54:62].startswith(b"FAT") or data[82:90].startswith(b"FAT"):
        return "FAT"
    if data[1080:1082] == b"\x53\xef":
        return "ext family"
    return "UNKNOWN"


def inspect_storage(path):
    size = Path(path).stat().st_size
    volumes, warnings = [], []
    header = read_range(path, 0, min(size, 4096))
    scheme = "RAW"
    if header[510:512] == b"\x55\xaa":
        scheme = "MBR"
        for index in range(4):
            entry = header[446 + index * 16:462 + index * 16]
            kind, start, sectors = entry[4], *struct.unpack_from("<II", entry, 8)
            if kind and sectors and kind != 0xEE:
                volumes.append({"offset": start * 512, "length": sectors * 512, "partition_type": f"MBR 0x{kind:02x}"})
    if header[512:520] == b"EFI PART":
        scheme, volumes = "GPT", []
        hsize = struct.unpack_from("<I", header, 524)[0]
        if not 92 <= hsize <= 512:
            warnings.append("Invalid GPT header length; partition mappings ignored")
        else:
            gpt = bytearray(header[512:512 + hsize])
            expected = struct.unpack_from("<I", gpt, 16)[0]
            gpt[16:20] = b"\0" * 4
            table_lba, count, entry_size, table_crc = struct.unpack_from("<QIII", header, 584)
            if zlib.crc32(gpt) != expected:
                warnings.append("GPT header checksum failed; mappings ignored")
            elif count > 4096 or not 128 <= entry_size <= 4096 or table_lba * 512 + count * entry_size > size:
                warnings.append("GPT partition table exceeds safety bounds")
            else:
                table = read_range(path, table_lba * 512, count * entry_size)
                if zlib.crc32(table) != table_crc:
                    warnings.append("GPT partition table checksum failed; mappings ignored")
                else:
                    for pos in range(0, len(table), entry_size):
                        entry = table[pos:pos + entry_size]
                        if entry[:16] != b"\0" * 16:
                            first, last = struct.unpack_from("<QQ", entry, 32)
                            volumes.append({"offset": first * 512, "length": (last - first + 1) * 512, "partition_type": "GPT", "name": entry[56:128].decode("utf-16-le", errors="replace").rstrip("\0")})
    valid = []
    for volume in volumes:
        start, length = volume["offset"], volume["length"]
        volume["status"] = "VALIDATED" if start >= 0 and length > 0 and start + length <= size else "INVALID"
        volume["filesystem"] = filesystem(read_range(path, start, min(length, 4096))) if volume["status"] == "VALIDATED" else "UNKNOWN"
        if volume["status"] == "VALIDATED":
            valid.append((start, start + length))
        else:
            warnings.append("Partition exceeds image bounds")
    regions, cursor = [], 0
    for start, end in sorted(valid):
        if start > cursor:
            regions.append({"offset": cursor, "length": start - cursor, "status": "OUTSIDE_KNOWN_PARTITIONS"})
        if start < cursor:
            warnings.append("Overlapping partition ranges")
        cursor = max(cursor, end)
    if cursor < size:
        regions.append({"offset": cursor, "length": size - cursor, "status": "OUTSIDE_KNOWN_PARTITIONS"})
    return {"scheme": scheme, "capacity": size, "volumes": volumes, "regions": regions, "filesystem": filesystem(header), "warnings": warnings, "bad_sectors": "UNKNOWN: image import does not establish physical device health", "allocation_note": "Outside-partition ranges are addressable; filesystem free-space allocation is not inferred."}

"""Evidence store: write-once files, atomic writes, disk-verified SHA-256.

Implements ARCHITECTURE §4 and the ``evidence-integrity`` skill:

* canonical name ``{account_id}-{seq:04d}.png`` always holds the PRIMARY image
  (the crop, or the viewport when ``crop_failed``);
* every file goes bytes → ``*.tmp`` → ``os.replace`` → read back → re-hash;
  a mismatch raises and the caller aborts the whole capture;
* nothing here ever overwrites, renames, or deletes committed evidence.
  :class:`WriteBatch` only removes files it created itself during a request that
  is being rolled back — those never became evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SIDECAR_SCHEMA_VERSION = 1


class IntegrityError(RuntimeError):
    """A write could not be verified. The capture must fail loudly (5xx)."""


class WriteOnceViolation(IntegrityError):
    """The target name already exists on disk; it is never overwritten."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_png(data: bytes) -> bool:
    return data[:8] == PNG_SIGNATURE


def _read_back(path: Path) -> bytes:
    # Separate function so the hash-mismatch path is testable (monkeypatch).
    with open(path, "rb") as handle:
        return handle.read()


def atomic_write_verified(path: Path, data: bytes) -> str:
    """Write ``data`` write-once and return its disk-verified SHA-256."""
    if path.exists():
        raise WriteOnceViolation(f"write-once violation: {path.name} already exists")
    expected = sha256_hex(data)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    got = sha256_hex(_read_back(path))
    if got != expected:
        raise IntegrityError(f"hash mismatch after write: {path.name} ({got} != {expected})")
    return expected


@dataclass
class WriteBatch:
    """Files created during one request; removed only if that request fails."""

    created: list[Path] = field(default_factory=list)

    def write(self, path: Path, data: bytes) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        try:
            digest = atomic_write_verified(path, data)
        except WriteOnceViolation:
            # The existing file belongs to someone else: never touch it.
            raise
        except (IntegrityError, OSError):
            self.created.extend([path, tmp])
            raise
        self.created.append(path)
        return digest

    def rollback(self) -> None:
        for path in self.created:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        self.created.clear()


def folder_for(evidence_dir: Path, phase: str, account_id: str) -> Path:
    return evidence_dir / f"{phase}-{account_id}"


def canonical_stem(account_id: str, seq: int) -> str:
    return f"{account_id}-{seq:04d}"


def relative(path: Path, data_dir: Path) -> str:
    """Stored paths are POSIX-relative to the data dir (portable backups)."""
    return path.relative_to(data_dir).as_posix()


def sidecar_bytes(payload: dict) -> bytes:
    body = {"schema_version": SIDECAR_SCHEMA_VERSION, **payload}
    return (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

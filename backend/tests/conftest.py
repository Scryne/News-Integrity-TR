"""Test fixtures: the real app against a temporary data dir.

Every test gets its own data dir (DB + evidence tree), migrated to head and
seeded from the real ``taxonomy.json`` by the app's own lifespan — the same
startup path production uses. The archive worker thread is off; worker tests
drive ``ArchiveWorker.tick`` directly with fake adapters.
"""

from __future__ import annotations

import json
import struct
import zlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

AUTHOR_ID = "1234567890123456789"  # > 2**53: must survive as text end to end
AUTHOR = "HaberSayfasi"


def make_png(width: int = 6, height: int = 4, rgb: tuple[int, int, int] = (200, 30, 30)) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path / "data", phase="VK1", archive_worker=False)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def meta(**overrides) -> dict:
    post_id = overrides.pop("post_id", "1811111111111111111")
    handle = overrides.pop("handle", AUTHOR)
    rest_id = overrides.pop("rest_id", AUTHOR_ID)
    body = {
        "post_url": f"https://x.com/{handle}/status/{post_id}",
        "post_id": post_id,
        "post_text": "Son dakika: deneme gönderisi",
        "posted_at": "2026-07-14T18:03:00.000Z",
        "author": {"rest_id": rest_id, "handle": handle, "follower_count": 48213},
        "category": "news",
        "codes": ["H2", "E1"],
        "note": "test",
        "crop_failed": False,
        "extraction": {"rest_id_method": "dom-anchor", "extractor_version": "1.0.0"},
    }
    body.update(overrides)
    return body


def capture(client: TestClient, body: dict | None = None, *, crop: bool = True, viewport: bytes | None = None):
    files = {"viewport": ("viewport.png", viewport or make_png(12, 9, (10, 10, 10)), "image/png")}
    if crop:
        files["crop"] = ("crop.png", make_png(), "image/png")
    return client.post("/api/captures", data={"meta": json.dumps(body or meta())}, files=files)

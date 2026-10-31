"""Phase 1: the evidence write path (PLAN.md Phase 1 test list)."""

from __future__ import annotations

import hashlib
import json

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import Settings
from app.main import create_app
from app.models import ArchiveJob, Evidence, EvidenceCode, HandleHistory
from app.services import evidence_store

from .conftest import AUTHOR, AUTHOR_ID, capture, make_png, meta


def _db(client: TestClient):
    return client.app.state.sessions()


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_happy_path_writes_files_sidecar_and_rows(client, settings):
    response = capture(client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["seq"] == 1 and body["merged"] is False and body["crop_failed"] is False

    folder = settings.data_dir / "evidence" / f"VK1-{AUTHOR_ID}"
    primary = folder / f"{AUTHOR_ID}-0001.png"
    viewport = folder / f"{AUTHOR_ID}-0001-viewport.png"
    sidecar = folder / f"{AUTHOR_ID}-0001.json"
    assert primary.read_bytes() == make_png()  # canonical name holds the crop
    with _db(client) as session:
        ev = session.get(Evidence, body["evidence_id"])
        assert ev.screenshot_sha256 == _sha(primary) == body["screenshot_sha256"]
        assert ev.viewport_sha256 == _sha(viewport) == body["viewport_sha256"]
        assert ev.sidecar_sha256 == _sha(sidecar)
        assert ev.account_id == AUTHOR_ID and isinstance(ev.account_id, str)
        assert ev.status == "complete" and ev.capture_source == "extension"
        assert ev.posted_at == "2026-07-14T18:03:00Z"
        codes = set(session.scalars(select(EvidenceCode.code).where(EvidenceCode.evidence_id == ev.id)))
        assert codes == {"H2", "E1"}
        jobs = session.scalars(select(ArchiveJob).where(ArchiveJob.evidence_id == ev.id)).all()
        assert sorted(j.service for j in jobs) == ["archive_today", "wayback"]
        assert {j.status for j in jobs} == {"pending"}

    side = json.loads(sidecar.read_text(encoding="utf-8"))
    assert side["schema_version"] == 1
    assert side["account_id"] == AUTHOR_ID
    assert side["files"]["primary"] == {"name": primary.name, "sha256": _sha(primary)}
    assert side["taxonomy_version"] == "1.1" and side["phase"] == "VK1"
    assert "archive" not in json.dumps(side).lower()  # archive links never in the sidecar
    assert not list(folder.glob("*.tmp"))


def test_second_capture_increments_seq(client):
    first = capture(client).json()
    second = capture(client, meta(post_id="1811111111111111112")).json()
    again = capture(client).json()  # same post again: temporal re-observation, new row
    assert (first["seq"], second["seq"], again["seq"]) == (1, 2, 3)
    assert again["evidence_id"] != first["evidence_id"]


def test_new_account_seeds_initial_handle(client):
    body = capture(client).json()
    with _db(client) as session:
        rows = session.scalars(select(HandleHistory).where(HandleHistory.account_id == AUTHOR_ID)).all()
        assert [(r.handle, r.evidence_id) for r in rows] == [(AUTHOR, body["evidence_id"])]


def test_handle_change_appends_history(client):
    capture(client)
    renamed = capture(client, meta(handle="YeniAd", post_id="1811111111111111199")).json()
    capture(client, meta(handle="yeniad", post_id="1811111111111111198"))  # case only: no row
    with _db(client) as session:
        rows = session.scalars(
            select(HandleHistory).where(HandleHistory.account_id == AUTHOR_ID).order_by(HandleHistory.id)
        ).all()
        assert [r.handle for r in rows] == [AUTHOR, "YeniAd"]
        assert rows[1].evidence_id == renamed["evidence_id"]
    account = client.get(f"/api/accounts/{AUTHOR_ID}").json()
    assert account["current_handle"] == "YeniAd"
    assert client.get("/api/accounts", params={"handle": AUTHOR}).json()[0]["account_id"] == AUTHOR_ID


def test_unknown_category_and_code_are_rejected(client):
    assert capture(client, meta(category="gossip")).status_code == 422
    response = capture(client, meta(codes=["H2", "Z9"]))
    assert response.status_code == 422 and "Z9" in response.text
    with _db(client) as session:
        assert session.scalar(select(func.count()).select_from(Evidence)) == 0


def test_client_cannot_supply_provenance(client):
    for field, value in (("phase", "VK2"), ("taxonomy_version", "9.9")):
        assert capture(client, meta(**{field: value})).status_code == 422


def test_rest_id_must_be_text(client):
    body = meta()
    body["author"]["rest_id"] = 1234567890123456789
    assert capture(client, body).status_code == 422


def test_phase_stamped_from_config(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path / "d", phase="VK2", archive_worker=False)
    with TestClient(create_app(settings)) as client:
        body = capture(client).json()
        assert body["phase"] == "VK2"
        assert (settings.data_dir / "evidence" / f"VK2-{AUTHOR_ID}" / f"{AUTHOR_ID}-0001.png").exists()


def test_hash_mismatch_fails_loudly_and_leaves_nothing(client, settings, monkeypatch):
    monkeypatch.setattr(evidence_store, "_read_back", lambda path: b"corrupted on disk")
    response = capture(client)
    assert response.status_code == 500 and "could not be verified" in response.text
    folder = settings.data_dir / "evidence" / f"VK1-{AUTHOR_ID}"
    assert not folder.exists() or not any(folder.iterdir())
    with _db(client) as session:
        assert session.scalar(select(func.count()).select_from(Evidence)) == 0
        assert session.scalar(select(func.count()).select_from(ArchiveJob)) == 0


def test_crop_failed_stores_viewport_under_canonical_name(client, settings):
    viewport = make_png(20, 10, (1, 2, 3))
    body = capture(client, meta(crop_failed=True), viewport=viewport).json()
    assert body["crop_failed"] is True and body["viewport_sha256"] is None
    folder = settings.data_dir / "evidence" / f"VK1-{AUTHOR_ID}"
    assert (folder / f"{AUTHOR_ID}-0001.png").read_bytes() == viewport
    assert not (folder / f"{AUTHOR_ID}-0001-viewport.png").exists()
    with _db(client) as session:
        ev = session.get(Evidence, body["evidence_id"])
        assert ev.crop_failed == 1 and ev.viewport_path is None


def test_missing_crop_upload_is_crop_failed(client):
    body = capture(client, crop=False).json()
    assert body["crop_failed"] is True


def test_write_once_never_overwrites_existing_file(client, settings):
    folder = settings.data_dir / "evidence" / f"VK1-{AUTHOR_ID}"
    folder.mkdir(parents=True)
    squatter = folder / f"{AUTHOR_ID}-0001.png"
    squatter.write_bytes(b"pre-existing")
    response = capture(client)
    assert response.status_code == 500
    assert squatter.read_bytes() == b"pre-existing"


def test_wrong_author_for_permalink_is_rejected(client):
    body = meta()
    body["author"]["handle"] = "BaskaHesap"
    response = capture(client, body)
    assert response.status_code == 422 and "permalink" in response.text


def test_non_png_is_rejected(client):
    response = capture(client, viewport=b"GIF89a not a png")
    assert response.status_code == 422


def test_taxonomy_payload(client):
    payload = client.get("/api/taxonomy").json()
    assert payload["version"] == "1.1"
    assert set(payload["groups"]) == {"H", "E", "I", "Y"}
    assert len(payload["codes"]) == 22
    assert [c["code"] for c in payload["codes"]][:3] == ["H1", "H2", "H3"]
    assert {c["key"] for c in payload["categories"]} >= {"news", "anonymous_news"}

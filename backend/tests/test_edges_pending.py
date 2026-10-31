"""Phase 3 edges + Phase 4 CLI/hybrid completion flow."""

from __future__ import annotations

import json

from sqlalchemy import func, select

from app.models import ArchiveJob, Edge, Evidence

from .conftest import AUTHOR, AUTHOR_ID, capture, meta


def _urls(n: int, handle: str = AUTHOR) -> list[str]:
    return [f"https://x.com/{handle}/status/18200000000000000{i:02d}" for i in range(n)]


def test_edge_with_unresolved_target_keeps_raw_handle(client):
    body = {
        "source": {"rest_id": AUTHOR_ID, "handle": AUTHOR},
        "target": {"handle": "kaynakhesap"},
        "edge_type": "reply",
        "post_url": f"https://twitter.com/{AUTHOR}/status/1811111111111111111?s=20",
    }
    response = client.post("/api/edges", json=body)
    assert response.status_code == 201 and response.json()["target_resolved"] is False
    with client.app.state.sessions() as session:
        edge = session.scalars(select(Edge)).one()
        assert edge.target_account_id is None and edge.target_handle_raw == "kaynakhesap"
        assert edge.phase == "VK1"
        assert edge.post_url == f"https://x.com/{AUTHOR}/status/1811111111111111111"


def test_edge_with_resolved_target_creates_account(client):
    body = {
        "source": {"rest_id": AUTHOR_ID, "handle": AUTHOR},
        "target": {"rest_id": "44196397", "handle": "kaynak"},
        "edge_type": "quote",
        "post_url": f"https://x.com/{AUTHOR}/status/1811111111111111111",
    }
    assert client.post("/api/edges", json=body).json()["target_resolved"] is True
    target = client.get("/api/accounts/44196397").json()
    assert target["current_handle"] == "kaynak"
    assert [h["handle"] for h in target["handle_history"]] == ["kaynak"]


def test_bulk_archive_creates_pending_rows_and_jobs(client):
    capture(client)  # makes the account known
    response = client.post(
        "/api/cli/bulk-archive", json={"account": {"handle": AUTHOR.lower()}, "urls": _urls(10)}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["created"]) == 10 and body["skipped"] == []
    assert [c["seq"] for c in body["created"]] == list(range(2, 12))
    with client.app.state.sessions() as session:
        rows = session.scalars(select(Evidence).where(Evidence.status == "pending_completion")).all()
        assert len(rows) == 10
        assert {r.phase for r in rows} == {"VK1"} and {r.capture_source for r in rows} == {"cli"}
        assert all(r.taxonomy_version is None and r.screenshot_path is None for r in rows)
        ids = [r.id for r in rows]
        jobs = session.scalar(
            select(func.count()).select_from(ArchiveJob).where(ArchiveJob.evidence_id.in_(ids))
        )
        assert jobs == 20


def test_bulk_archive_skips_with_reasons(client):
    capture(client)
    urls = [
        *_urls(1),
        _urls(1)[0],  # duplicate
        "https://x.com/BaskaHesap/status/1820000000000000077",  # other account
        "https://example.com/not-x",
        f"https://x.com/{AUTHOR}/status/1811111111111111111",  # already captured
    ]
    body = client.post("/api/cli/bulk-archive", json={"account": {"handle": AUTHOR}, "urls": urls}).json()
    assert len(body["created"]) == 1
    reasons = [s["reason"] for s in body["skipped"]]
    assert reasons[0] == "duplicate in this list"
    assert reasons[1].startswith("handle mismatch")
    assert "not an x.com" in reasons[2]
    assert reasons[3].startswith("already complete")


def test_bulk_archive_unknown_handle_needs_rest_id(client):
    response = client.post(
        "/api/cli/bulk-archive", json={"account": {"handle": "hicgorulmedi"}, "urls": _urls(1, "hicgorulmedi")}
    )
    assert response.status_code == 422
    with_id = client.post(
        "/api/cli/bulk-archive",
        json={"account": {"handle": "hicgorulmedi", "rest_id": "777"}, "urls": _urls(1, "hicgorulmedi")},
    )
    assert with_id.status_code == 201
    assert client.get("/api/accounts/777").json()["handle_history"][0]["handle"] == "hicgorulmedi"


def test_bulk_archive_rest_id_handle_conflict(client):
    capture(client)
    response = client.post(
        "/api/cli/bulk-archive",
        json={"account": {"handle": "baskaad", "rest_id": AUTHOR_ID}, "urls": _urls(1, "baskaad")},
    )
    assert response.status_code == 409


def test_completion_merge_preserves_identity(client, settings):
    capture(client, meta(post_id="1811111111111111100"))
    created = client.post(
        "/api/cli/bulk-archive", json={"account": {"handle": AUTHOR}, "urls": _urls(2)}
    ).json()["created"]
    target = created[0]
    post_id = target["post_url"].rsplit("/", 1)[1]
    with client.app.state.sessions() as session:
        before_jobs = sorted(
            session.scalars(select(ArchiveJob.id).where(ArchiveJob.evidence_id == target["evidence_id"]))
        )

    pending = client.get("/api/pending", params={"post_id": post_id}).json()
    assert [p["evidence_id"] for p in pending] == [target["evidence_id"]]

    result = capture(client, meta(post_id=post_id)).json()
    assert result["merged"] is True
    assert (result["evidence_id"], result["seq"]) == (target["evidence_id"], target["seq"])
    with client.app.state.sessions() as session:
        ev = session.get(Evidence, target["evidence_id"])
        assert ev.status == "complete" and ev.capture_source == "cli" and ev.phase == "VK1"
        assert ev.taxonomy_version == "1.1" and ev.screenshot_sha256
        after_jobs = sorted(
            session.scalars(select(ArchiveJob.id).where(ArchiveJob.evidence_id == ev.id))
        )
        assert after_jobs == before_jobs  # no new jobs on merge
    sidecar = settings.data_dir / ev.sidecar_path
    assert json.loads(sidecar.read_text(encoding="utf-8"))["capture_source"] == "cli"
    assert client.get("/api/pending", params={"post_id": post_id}).json() == []


def test_merge_refuses_a_different_author(client):
    client.post(
        "/api/cli/bulk-archive",
        json={"account": {"handle": AUTHOR, "rest_id": AUTHOR_ID}, "urls": _urls(1)},
    )
    post_id = _urls(1)[0].rsplit("/", 1)[1]
    response = capture(client, meta(post_id=post_id, rest_id="999"))
    assert response.status_code == 409


def test_archive_only_only_from_pending(client):
    client.post(
        "/api/cli/bulk-archive",
        json={"account": {"handle": AUTHOR, "rest_id": AUTHOR_ID}, "urls": _urls(1)},
    )
    pending_id = client.get("/api/pending").json()[0]["evidence_id"]
    degraded = client.post(f"/api/evidence/{pending_id}/archive-only", json={"note": "silinmiş"})
    assert degraded.status_code == 200 and degraded.json()["status"] == "archive_only"
    again = client.post(f"/api/evidence/{pending_id}/archive-only")
    assert again.status_code == 409
    complete_id = capture(client).json()["evidence_id"]
    assert client.post(f"/api/evidence/{complete_id}/archive-only").status_code == 409
    assert client.post("/api/evidence/9999/archive-only").status_code == 404

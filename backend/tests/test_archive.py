"""Phase 3: archive queue + worker (adapter fakes; no network)."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import func, select

from app.models import ArchiveJob
from app.services.archive_worker import (
    AdapterResult,
    ArchiveTodayAdapter,
    ArchiveWorker,
    WaybackAdapter,
)

from .conftest import AUTHOR, capture, meta


class FakeAdapter:
    def __init__(self, service: str, results: list[AdapterResult], route_result=None):
        self.service = service
        self.results = list(results)
        self.route_result = route_result
        self.calls: list[str] = []

    def route(self, url: str):
        return self.route_result

    def submit(self, url: str) -> AdapterResult:
        self.calls.append(url)
        return self.results.pop(0)


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _worker(client, settings, wayback, archive_today=None, clock=None):
    return ArchiveWorker(
        client.app.state.sessions,
        settings,
        adapters={
            "wayback": wayback,
            "archive_today": archive_today
            or FakeAdapter("archive_today", [], route_result=AdapterResult("manual", error="m")),
        },
        monotonic=clock or Clock(),
    )


def _jobs(client, service=None) -> list[ArchiveJob]:
    with client.app.state.sessions() as session:
        query = select(ArchiveJob).order_by(ArchiveJob.id)
        if service:
            query = query.where(ArchiveJob.service == service)
        return list(session.scalars(query))


def _make_due(client) -> None:
    with client.app.state.sessions() as session:
        for job in session.scalars(select(ArchiveJob).where(ArchiveJob.status == "pending")):
            job.next_attempt_at = "2000-01-01T00:00:00Z"
        session.commit()


def _drain(worker, n=20) -> None:
    for _ in range(n):
        if not worker.tick():
            break


def test_transient_failures_back_off_then_escalate(client, settings):
    capture(client)
    wayback = FakeAdapter("wayback", [AdapterResult("transient", error="HTTP 503")] * 5)
    clock = Clock()
    worker = _worker(client, settings, wayback, clock=clock)
    expected_attempts = [1, 2, 3, 4]
    for attempts in expected_attempts:
        _make_due(client)
        clock.t += 10_000
        _drain(worker)
        job = _jobs(client, "wayback")[0]
        assert job.status == "pending" and job.attempts == attempts
        assert job.next_attempt_at > "2026-01-01T00:00:00Z"
    _make_due(client)
    clock.t += 10_000
    _drain(worker)
    job = _jobs(client, "wayback")[0]
    assert job.status == "manual_pending" and job.attempts == 5
    assert "escalated after 5 attempts" in job.last_error
    assert len(wayback.calls) == 5


def test_backoff_schedule_is_1m_5m_30m_2h(client, settings, monkeypatch):
    from app.services import archive_worker

    delays: list[float] = []
    monkeypatch.setattr(archive_worker, "iso_after", lambda s: delays.append(s) or "2999-01-01T00:00:00Z")
    capture(client)
    wayback = FakeAdapter("wayback", [AdapterResult("transient", error="x")] * 4)
    clock = Clock()
    worker = _worker(client, settings, wayback, clock=clock)
    for _ in range(4):
        _make_due(client)
        clock.t += 10_000
        _drain(worker)
    assert delays == [60, 300, 1800, 7200]


def test_rate_limit_spacing_per_service(client, settings):
    capture(client)
    capture(client, meta(post_id="1811111111111111112"))
    wayback = FakeAdapter("wayback", [AdapterResult("done", archive_url="https://web.archive.org/web/1/a")] * 2)
    clock = Clock()
    worker = _worker(client, settings, wayback, clock=clock)
    _drain(worker)
    assert len(wayback.calls) == 1  # second job waits for the 60 s slot
    clock.t += settings.wayback_min_interval_s - 1
    _drain(worker)
    assert len(wayback.calls) == 1
    clock.t += 2
    _drain(worker)
    assert len(wayback.calls) == 2


def test_url_short_circuit_reuses_archive_without_call(client, settings):
    capture(client)
    url = "https://web.archive.org/web/20260719190822/https://x.com/a/status/1"
    wayback = FakeAdapter("wayback", [AdapterResult("done", archive_url=url)])
    worker = _worker(client, settings, wayback)
    _drain(worker)
    capture(client)  # same post captured again → new evidence, new jobs, same URL
    _drain(worker)
    jobs = _jobs(client, "wayback")
    assert [j.status for j in jobs] == ["done", "done"]
    assert jobs[1].archive_url == url and len(wayback.calls) == 1


def test_x_urls_route_to_manual_without_network(client, settings):
    capture(client)
    transport_calls: list[httpx.Request] = []
    http = httpx.Client(transport=httpx.MockTransport(lambda r: transport_calls.append(r) or httpx.Response(500)))
    worker = _worker(
        client, settings, WaybackAdapter("key", "secret", client=http), ArchiveTodayAdapter()
    )
    _drain(worker)
    jobs = _jobs(client)
    assert {j.status for j in jobs} == {"manual_pending"}
    assert "ADR-025" in jobs[0].last_error and "S2" in jobs[1].last_error
    assert transport_calls == []


def test_retry_and_manual_paste_back(client, settings):
    capture(client)
    worker = _worker(client, settings, WaybackAdapter("k", "s"), ArchiveTodayAdapter())
    _drain(worker)
    wayback_job, today_job = _jobs(client)

    bad = client.post(f"/api/archive/jobs/{today_job.id}/manual", json={"archive_url": "https://evil.example/abc"})
    assert bad.status_code == 422
    ok = client.post(f"/api/archive/jobs/{today_job.id}/manual", json={"archive_url": "https://archive.md/AbCd1"})
    assert ok.status_code == 200 and ok.json()["status"] == "manual_done"
    assert client.post(f"/api/archive/jobs/{today_job.id}/retry").status_code == 409

    retried = client.post(f"/api/archive/jobs/{wayback_job.id}/retry").json()
    assert retried["status"] == "pending" and retried["attempts"] == 0
    listed = client.get("/api/archive/jobs", params={"status": "manual_done"}).json()
    assert [j["id"] for j in listed] == [today_job.id]
    assert client.get("/api/archive/jobs", params={"status": "bogus"}).status_code == 422


def test_non_retryable_goes_failed_and_stays_visible(client, settings):
    capture(client)
    wayback = FakeAdapter("wayback", [AdapterResult("failed", error="SPN2 error:invalid-url-syntax")])
    _drain(_worker(client, settings, wayback))
    job = _jobs(client, "wayback")[0]
    assert job.status == "failed"
    assert client.get("/api/archive/jobs", params={"status": "failed"}).json()[0]["id"] == job.id
    pasted = client.post(
        f"/api/archive/jobs/{job.id}/manual",
        json={"archive_url": "https://web.archive.org/web/20260101000000/https://x.com/a/status/1"},
    )
    assert pasted.json()["status"] == "manual_done"


def test_restart_requeues_in_progress_and_never_deletes(client, settings):
    capture(client)
    with client.app.state.sessions() as session:
        job = session.scalars(select(ArchiveJob)).first()
        job.status = "in_progress"
        session.commit()
        total = session.scalar(select(func.count()).select_from(ArchiveJob))
    worker = _worker(client, settings, FakeAdapter("wayback", []))
    assert worker.recover() == 1
    with client.app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ArchiveJob)) == total
        assert {j.status for j in session.scalars(select(ArchiveJob))} == {"pending"}


def test_adapter_crash_does_not_strand_job(client, settings):
    capture(client)

    class Boom(FakeAdapter):
        def submit(self, url):
            raise RuntimeError("bug")

    _drain(_worker(client, settings, Boom("wayback", [])), n=1)
    job = _jobs(client, "wayback")[0]
    assert job.status == "pending" and job.attempts == 1 and "adapter error" in job.last_error


# --- the real SPN2 adapter against a mock transport ---------------------------
def _spn2(handler) -> WaybackAdapter:
    return WaybackAdapter(
        "key", "secret", client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
    )


def test_spn2_success_flow_builds_archive_url():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "LOW key:secret"
        if request.method == "POST":
            return httpx.Response(200, json={"url": "https://example.com/", "job_id": "spn2-abc"})
        return httpx.Response(
            200, json={"status": "success", "timestamp": "20260719190822", "original_url": "https://example.com/"}
        )

    result = _spn2(handler).submit("https://example.com/")
    assert result.kind == "done"
    assert result.archive_url == "https://web.archive.org/web/20260719190822/https://example.com/"


@pytest.mark.parametrize(
    ("response", "kind"),
    [
        (httpx.Response(200, json={"status": "error", "status_ext": "error:blocked-url"}), "manual"),
        (httpx.Response(200, json={"status": "error", "status_ext": "error:too-many-daily-captures"}), "transient"),
        (httpx.Response(200, json={"status": "error", "status_ext": "error:invalid-url-syntax"}), "failed"),
        (httpx.Response(401, json={"message": "You need to be logged in"}), "manual"),
        (httpx.Response(429), "transient"),
        (httpx.Response(502), "transient"),
    ],
)
def test_spn2_error_taxonomy(response, kind):
    assert _spn2(lambda request: response).submit("https://example.com/").kind == kind


def test_wayback_without_keys_is_manual():
    assert WaybackAdapter(None, None).route("https://example.com/").kind == "manual"
    assert WaybackAdapter("k", "s").route("https://example.com/") is None
    assert WaybackAdapter("k", "s").route(f"https://x.com/{AUTHOR}/status/1").kind == "manual"


@pytest.mark.parametrize(
    ("current", "target"),
    [("done", "pending"), ("manual_done", "pending"), ("pending", "done"), ("done", "manual_done"), ("pending", "manual_done")],
)
def test_transition_guard_rejects_illegal_moves(current, target):
    from app.services.archive_queue import IllegalTransition, transition

    job = ArchiveJob(status=current, service="wayback", target_url="u", evidence_id=1)
    with pytest.raises(IllegalTransition):
        transition(job, target, "2026-10-31T00:00:00Z")
    assert job.status == current

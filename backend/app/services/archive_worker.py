"""Archive worker: drains ``archive_jobs`` in the background (ARCHITECTURE §3.4).

One daemon thread, started in the FastAPI lifespan. It never blocks or is
awaited by a request handler (ADR-008). Per tick it takes due ``pending`` jobs
in order and, for each:

1. **URL short-circuit (ADR-022):** an existing ``done``/``manual_done`` job for
   the same ``(service, target_url)`` is copied locally — no external call;
2. **routing without network:** an adapter may decide a URL is manual-first
   before any request is fired — Wayback for x.com/twitter.com (ADR-025) or
   without SPN2 keys (ADR-024), and archive.today always (S2 / ADR-007);
3. otherwise, if the service's minimum interval has passed, it calls the adapter
   and records ``done`` / transient retry with backoff / escalation to
   ``manual_pending`` after max attempts / ``failed`` for non-retryable input.

Rows are never deleted. The network call happens outside any DB transaction.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import ArchiveJob
from app.services.archive_queue import transition
from app.services.x_urls import is_x_host
from app.timeutil import iso_after, now_iso

logger = logging.getLogger("news_integrity.archive")

# ARCHITECTURE §3.4: 1m → 5m → 30m → 2h; the last step repeats until max attempts.
BACKOFF_S = (60, 300, 1800, 7200)

Kind = Literal["done", "transient", "manual", "failed"]


@dataclass(frozen=True)
class AdapterResult:
    kind: Kind
    archive_url: str | None = None
    error: str | None = None


class Adapter(Protocol):
    service: str

    def route(self, url: str) -> AdapterResult | None:
        """Decide without network (manual-first rules). None = needs a submit."""

    def submit(self, url: str) -> AdapterResult: ...


class ArchiveTodayAdapter:
    """Manual-first: S2 saw 0/3 automated submits pass (429 + reCAPTCHA)."""

    service = "archive_today"

    def route(self, url: str) -> AdapterResult:
        return AdapterResult(
            "manual",
            error="manual-first (S2/ADR-007): archive.today answers automated submits with "
            "a CAPTCHA; open the submit page and paste the link back",
        )

    def submit(self, url: str) -> AdapterResult:  # pragma: no cover - never routed here
        return self.route(url)


# SPN2 status_ext values (S2 log + SPN2 docs). blocked-url is site-level and
# effectively permanent; the rest of the "too many" family is transient.
_SPN2_MANUAL = {"error:blocked-url", "error:blocked", "error:filesize-limit"}
_SPN2_FAILED = {"error:invalid-url-syntax", "error:invalid-host-resolution", "error:not-found"}


class WaybackAdapter:
    """Authenticated SPN2 (ADR-024); manual-first for X URLs (ADR-025)."""

    service = "wayback"
    save_url = "https://web.archive.org/save"
    status_url = "https://web.archive.org/save/status/{job_id}"

    def __init__(
        self,
        accesskey: str | None,
        secret: str | None,
        client: httpx.Client | None = None,
        poll_interval_s: float = 3.0,
        poll_timeout_s: float = 120.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._auth = f"LOW {accesskey}:{secret}" if accesskey and secret else None
        self._client = client
        self._poll_interval = poll_interval_s
        self._poll_timeout = poll_timeout_s
        self._sleep = sleep

    def route(self, url: str) -> AdapterResult | None:
        if is_x_host(url):
            return AdapterResult(
                "manual",
                error="manual-first (ADR-025): SPN2 answers x.com/twitter.com with "
                "error:blocked-url; archive it in the browser and paste the link back",
            )
        if self._auth is None:
            return AdapterResult(
                "manual",
                error="no SPN2 keys configured (ADR-024: NIT_WAYBACK_S3_ACCESSKEY/SECRET); "
                "manual-assist instead",
            )
        return None

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def submit(self, url: str) -> AdapterResult:
        headers = {"Accept": "application/json", "Authorization": self._auth or ""}
        try:
            response = self._http().post(self.save_url, data={"url": url}, headers=headers)
        except httpx.HTTPError as exc:
            return AdapterResult("transient", error=f"SPN2 submit failed: {exc.__class__.__name__}")
        if response.status_code in (401, 403):
            return AdapterResult("manual", error=f"SPN2 rejected the keys (HTTP {response.status_code})")
        if response.status_code == 429 or response.status_code >= 500:
            return AdapterResult("transient", error=f"SPN2 HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            return AdapterResult("transient", error=f"SPN2 HTTP {response.status_code}, non-JSON body")
        job_id = body.get("job_id")
        if not job_id:
            return self._classify(body)
        deadline = time.monotonic() + self._poll_timeout
        while time.monotonic() < deadline:
            self._sleep(self._poll_interval)
            try:
                status = self._http().get(self.status_url.format(job_id=job_id), headers=headers).json()
            except (httpx.HTTPError, ValueError) as exc:
                return AdapterResult("transient", error=f"SPN2 status poll failed: {exc.__class__.__name__}")
            if status.get("status") == "success":
                timestamp = status.get("timestamp")
                original = status.get("original_url") or url
                if not timestamp:
                    return AdapterResult("transient", error="SPN2 success without timestamp")
                return AdapterResult("done", archive_url=f"https://web.archive.org/web/{timestamp}/{original}")
            if status.get("status") == "error":
                return self._classify(status)
        return AdapterResult("transient", error=f"SPN2 job {job_id} still pending after {self._poll_timeout:.0f}s")

    @staticmethod
    def _classify(body: dict) -> AdapterResult:
        ext = str(body.get("status_ext") or "")
        message = f"SPN2 {ext or 'error'}: {str(body.get('message') or '')[:160]}".strip()
        if ext in _SPN2_MANUAL:
            return AdapterResult("manual", error=message)
        if ext in _SPN2_FAILED:
            return AdapterResult("failed", error=message)
        return AdapterResult("transient", error=message)


class ArchiveWorker:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        settings: Settings,
        adapters: dict[str, Adapter] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sessions = session_factory
        self._settings = settings
        self._adapters = adapters or {
            "wayback": WaybackAdapter(settings.wayback_s3_accesskey, settings.wayback_s3_secret),
            "archive_today": ArchiveTodayAdapter(),
        }
        self._intervals = {
            "wayback": settings.wayback_min_interval_s,
            "archive_today": settings.archive_today_min_interval_s,
        }
        self._monotonic = monotonic
        self._last_call: dict[str, float] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # --- lifecycle ---------------------------------------------------------
    def recover(self) -> int:
        """Jobs left in_progress by a killed process go back to the queue."""
        with self._sessions() as session:
            stuck = list(session.scalars(select(ArchiveJob).where(ArchiveJob.status == "in_progress")))
            now = now_iso()
            for job in stuck:
                transition(job, "pending", now)
                job.next_attempt_at = now
                job.last_error = "requeued after restart (was in_progress)"
            session.commit()
            return len(stuck)

    def start(self) -> None:
        recovered = self.recover()
        if recovered:
            logger.warning("archive worker requeued %d job(s) left in_progress", recovered)
        self._thread = threading.Thread(target=self._run, name="nit-archive-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                worked = self.tick()
            except Exception:  # keep the thread alive; the job row records state
                logger.exception("archive worker tick failed")
                worked = False
            if not worked:
                self._stop.wait(2.0)

    # --- one pass ----------------------------------------------------------
    def tick(self) -> bool:
        """Process at most one job. True if something changed."""
        with self._sessions() as session:
            due = list(
                session.scalars(
                    select(ArchiveJob)
                    .where(ArchiveJob.status == "pending", ArchiveJob.next_attempt_at <= now_iso())
                    .order_by(ArchiveJob.next_attempt_at, ArchiveJob.id)
                    .limit(50)
                )
            )
            for job in due:
                if self._short_circuit(session, job):
                    return True
                adapter = self._adapters[job.service]
                decided = adapter.route(job.target_url)
                if decided is not None:
                    transition(job, "in_progress", now_iso())
                    self._apply(session, job, decided)
                    return True
                if not self._slot_free(job.service):
                    continue
                job_id, url = job.id, job.target_url
                transition(job, "in_progress", now_iso())
                session.commit()
                break
            else:
                return False

        self._last_call[adapter.service] = self._monotonic()
        try:
            result = adapter.submit(url)
        except Exception as exc:  # an adapter bug must not strand the job in_progress
            logger.exception("adapter %s crashed on job %s", adapter.service, job_id)
            result = AdapterResult("transient", error=f"adapter error: {exc.__class__.__name__}")
        with self._sessions() as session:
            job = session.get(ArchiveJob, job_id)
            self._apply(session, job, result)
        return True

    def _slot_free(self, service: str) -> bool:
        last = self._last_call.get(service)
        return last is None or self._monotonic() - last >= self._intervals[service]

    def _short_circuit(self, session: Session, job: ArchiveJob) -> bool:
        prior = session.scalars(
            select(ArchiveJob)
            .where(
                ArchiveJob.service == job.service,
                ArchiveJob.target_url == job.target_url,
                ArchiveJob.status.in_(("done", "manual_done")),
                ArchiveJob.id != job.id,
            )
            .order_by(ArchiveJob.id)
        ).first()
        if prior is None:
            return False
        now = now_iso()
        transition(job, "in_progress", now)
        transition(job, "done", now)
        job.archive_url = prior.archive_url
        job.last_error = None
        job.next_attempt_at = None
        session.commit()
        logger.info("job %s reused archive of job %s (ADR-022)", job.id, prior.id)
        return True

    def _apply(self, session: Session, job: ArchiveJob, result: AdapterResult) -> None:
        now = now_iso()
        if result.kind == "done":
            transition(job, "done", now)
            job.archive_url = result.archive_url
            job.last_error = None
            job.next_attempt_at = None
        elif result.kind == "manual":
            transition(job, "manual_pending", now)
            job.last_error = result.error
            job.next_attempt_at = None
        elif result.kind == "failed":
            job.attempts += 1
            transition(job, "failed", now)
            job.last_error = result.error
            job.next_attempt_at = None
        else:
            job.attempts += 1
            job.last_error = result.error
            if job.attempts >= self._settings.archive_max_attempts:
                transition(job, "manual_pending", now)
                job.last_error = f"{result.error} — escalated after {job.attempts} attempts"
                job.next_attempt_at = None
            else:
                transition(job, "pending", now)
                delay = BACKOFF_S[min(job.attempts - 1, len(BACKOFF_S) - 1)]
                job.next_attempt_at = iso_after(delay)
        session.commit()

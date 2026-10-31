"""The main write path: ``POST /api/captures`` (ARCHITECTURE §3.1 / §6).

Server-side sequence, one DB transaction:

1. upsert the author by rest_id (creation seeds handle_history; a changed
   handle appends the newly observed one);
2. merge check — a ``pending_completion`` row with the same post_id is upgraded
   in place (id, seq, phase, capture_source='cli', archive jobs kept);
   otherwise a new row gets ``seq = MAX(seq)+1`` and ``phase`` from config;
3. write files atomically, re-verify SHA-256 from disk, write the sidecar once;
4. attach codes (validated), stamp taxonomy_version, optional inline edge;
5. enqueue both archive jobs (not when merging — they already exist).

Any failure rolls the transaction back and removes only the files this request
created; nothing half-written survives as evidence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import ApiError, conflict, unprocessable
from app.models import Evidence, EvidenceCode
from app.schemas.api import CaptureMeta
from app.services import accounts, archive_queue, edges, taxonomy
from app.services.evidence_store import (
    IntegrityError,
    WriteBatch,
    canonical_stem,
    folder_for,
    is_png,
    relative,
    sidecar_bytes,
)
from app.services.x_urls import parse_status_url, same_handle
from app.timeutil import now_iso

logger = logging.getLogger("news_integrity")

# Legal evidence-status transitions (ADR-013); `complete` is terminal.
EVIDENCE_TRANSITIONS = frozenset(
    {("pending_completion", "complete"), ("pending_completion", "archive_only")}
)


def transition_evidence(evidence: Evidence, target: str) -> None:
    if (evidence.status, target) not in EVIDENCE_TRANSITIONS:
        raise conflict(f"evidence {evidence.id} cannot go from {evidence.status!r} to {target!r}")
    evidence.status = target


@dataclass(frozen=True)
class CaptureResult:
    evidence_id: int
    account_id: str
    seq: int
    phase: str
    canonical_name: str
    screenshot_sha256: str
    viewport_sha256: str | None
    crop_failed: bool
    merged: bool
    edge_id: int | None

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def next_seq(session: Session, account_id: str) -> int:
    current = session.scalar(select(func.max(Evidence.seq)).where(Evidence.account_id == account_id))
    return (current or 0) + 1


def create_capture(
    session: Session,
    settings: Settings,
    vocab: taxonomy.Vocabulary,
    meta: CaptureMeta,
    viewport_png: bytes,
    crop_png: bytes | None,
) -> CaptureResult:
    if not is_png(viewport_png):
        raise unprocessable("viewport must be a PNG image")
    if crop_png is not None and not is_png(crop_png):
        raise unprocessable("crop must be a PNG image")

    parsed = parse_status_url(meta.post_url)
    if parsed is None:
        raise unprocessable("post_url must be an x.com / twitter.com /status/ permalink")
    if meta.post_id is not None and meta.post_id != parsed.post_id:
        raise unprocessable(f"post_id {meta.post_id} does not match the URL ({parsed.post_id})")
    if not same_handle(parsed.handle, meta.author.handle):
        # The permalink's path handle is the author's. A mismatch means the
        # extractor read the wrong article; refusing beats a wrong attribution.
        raise unprocessable(
            f"author @{meta.author.handle} does not match the permalink's @{parsed.handle}"
        )
    taxonomy.validate(session, meta.category, meta.codes)

    rest_id = meta.author.rest_id
    now = now_iso()
    batch = WriteBatch()
    try:
        _, new_handle = accounts.ensure_account(session, rest_id, meta.author.handle, now)

        pending = session.scalars(
            select(Evidence)
            .where(Evidence.post_id == parsed.post_id, Evidence.status == "pending_completion")
            .order_by(Evidence.id)
        ).first()
        if pending is not None and pending.account_id != rest_id:
            raise conflict(
                f"post {parsed.post_id} is queued as pending for account {pending.account_id}, "
                f"but this capture's author is {rest_id}; resolve the CLI entry first"
            )

        merged = pending is not None
        if merged:
            evidence = pending
            transition_evidence(evidence, "complete")
        else:
            evidence = Evidence(
                account_id=rest_id,
                seq=next_seq(session, rest_id),
                phase=settings.phase,
                post_url=parsed.canonical,
                post_id=parsed.post_id,
                capture_source="extension",
                status="complete",
                created_at=now,
            )
            session.add(evidence)

        evidence.post_text = meta.post_text
        evidence.posted_at = meta.posted_at
        evidence.captured_at = now
        evidence.handle_at_capture = meta.author.handle
        evidence.follower_count_at_capture = meta.author.follower_count
        evidence.category = meta.category
        evidence.note = meta.note
        evidence.taxonomy_version = vocab.version
        session.flush()

        crop_failed = meta.crop_failed or crop_png is None
        folder = folder_for(settings.evidence_dir, evidence.phase, rest_id)
        stem = canonical_stem(rest_id, evidence.seq)
        primary_path = folder / f"{stem}.png"
        primary_sha = batch.write(primary_path, viewport_png if crop_failed else crop_png)
        evidence.crop_failed = 1 if crop_failed else 0
        evidence.screenshot_path = relative(primary_path, settings.data_dir)
        evidence.screenshot_sha256 = primary_sha
        viewport_sha: str | None = None
        viewport_path: Path | None = None
        if not crop_failed:
            viewport_path = folder / f"{stem}-viewport.png"
            viewport_sha = batch.write(viewport_path, viewport_png)
            evidence.viewport_path = relative(viewport_path, settings.data_dir)
            evidence.viewport_sha256 = viewport_sha

        session.add_all(EvidenceCode(evidence_id=evidence.id, code=code) for code in meta.codes)
        if new_handle is not None:
            accounts.record_handle(session, rest_id, new_handle, now, evidence.id)

        edge_id: int | None = None
        if meta.edge is not None:
            edge = edges.create_edge(
                session,
                phase=evidence.phase,
                now=now,
                source_rest_id=rest_id,
                source_handle=meta.author.handle,
                target_rest_id=meta.edge.target_rest_id,
                target_handle=meta.edge.target_handle,
                edge_type=meta.edge.edge_type,
                post_url=parsed.canonical,
                evidence_id=evidence.id,
                source_already_observed=True,
            )
            edge_id = edge.id

        sidecar = {
            "evidence_id": evidence.id,
            "account_id": rest_id,
            "seq": evidence.seq,
            "phase": evidence.phase,
            "post_url": evidence.post_url,
            "post_id": evidence.post_id,
            "post_text": evidence.post_text,
            "posted_at": evidence.posted_at,
            "captured_at": now,
            "handle_at_capture": evidence.handle_at_capture,
            "follower_count_at_capture": evidence.follower_count_at_capture,
            "category": evidence.category,
            "codes": list(meta.codes),
            "taxonomy_version": vocab.version,
            "note": evidence.note,
            "capture_source": evidence.capture_source,
            "crop_failed": crop_failed,
            "files": {
                "primary": {"name": primary_path.name, "sha256": primary_sha},
                "viewport": (
                    {"name": viewport_path.name, "sha256": viewport_sha} if viewport_path else None
                ),
            },
            "extraction": dict(meta.extraction),
        }
        sidecar_path = folder / f"{stem}.json"
        evidence.sidecar_sha256 = batch.write(sidecar_path, sidecar_bytes(sidecar))
        evidence.sidecar_path = relative(sidecar_path, settings.data_dir)

        if not merged:
            archive_queue.enqueue_for(session, evidence, now)

        session.commit()
    except IntegrityError as exc:
        session.rollback()
        batch.rollback()
        logger.error("capture aborted, evidence write could not be verified: %s", exc)
        raise ApiError(500, f"evidence write could not be verified: {exc}") from exc
    except BaseException:
        session.rollback()
        batch.rollback()
        raise

    return CaptureResult(
        evidence_id=evidence.id,
        account_id=rest_id,
        seq=evidence.seq,
        phase=evidence.phase,
        canonical_name=primary_path.name,
        screenshot_sha256=primary_sha,
        viewport_sha256=viewport_sha,
        crop_failed=crop_failed,
        merged=merged,
        edge_id=edge_id,
    )

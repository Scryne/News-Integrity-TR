"""CLI retrospective flow: bulk-archive, the pending worklist, archive-only degrade.

ARCHITECTURE §3.3. The CLI assembles nothing itself — the user hands it URLs
they already looked at; this service only validates them and reserves an
evidence slot (seq) per post so archive jobs can start immediately. The browser
capture later upgrades the row in place (``captures.create_capture`` merge).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import ApiError, conflict, not_found, unprocessable
from app.models import Account, Evidence
from app.schemas.api import BulkArchiveIn
from app.services import accounts, archive_queue
from app.services.captures import next_seq, transition_evidence
from app.services.x_urls import parse_status_url
from app.timeutil import now_iso


def resolve_account(session: Session, handle: str, rest_id: str | None, now: str) -> Account:
    """The CLI never invents a rest_id (ARCHITECTURE §3.3 step 2)."""
    if rest_id is not None:
        account = session.get(Account, rest_id)
        if account is None:
            return accounts.observe(session, rest_id, handle, now)
        if handle.lower() not in accounts.known_handles(session, account):
            raise conflict(
                f"account {rest_id} is known as @{account.current_handle}, never as @{handle}; "
                "check the rest_id or the handle"
            )
        return account
    matches = accounts.find_by_handle(session, handle)
    if not matches:
        raise unprocessable(
            f"@{handle} is not a known account; capture one of its posts in the browser first "
            "or pass --rest-id"
        )
    if len(matches) > 1:
        ids = ", ".join(a.account_id for a in matches)
        raise conflict(f"@{handle} has been used by several accounts ({ids}); pass --rest-id")
    return matches[0]


def bulk_archive(session: Session, settings: Settings, body: BulkArchiveIn) -> dict:
    now = now_iso()
    try:
        account = resolve_account(session, body.account.handle, body.account.rest_id, now)
        handles = accounts.known_handles(session, account)
        created: list[dict] = []
        skipped: list[dict] = []
        seen: set[str] = set()
        for raw in body.urls:
            url = raw.strip()
            if not url:
                continue
            parsed = parse_status_url(url)
            if parsed is None:
                skipped.append({"url": url, "reason": "not an x.com/twitter.com /status/ link"})
                continue
            if parsed.handle.lower() not in handles:
                skipped.append(
                    {
                        "url": url,
                        "reason": f"handle mismatch: @{parsed.handle} is not "
                        f"@{account.current_handle} (or a previous handle)",
                    }
                )
                continue
            if parsed.post_id in seen:
                skipped.append({"url": url, "reason": "duplicate in this list"})
                continue
            seen.add(parsed.post_id)
            existing = session.scalars(
                select(Evidence).where(
                    Evidence.post_id == parsed.post_id, Evidence.account_id == account.account_id
                )
            ).first()
            if existing is not None:
                reason = (
                    "already pending completion"
                    if existing.status == "pending_completion"
                    else f"already {existing.status} as evidence {existing.id}"
                )
                skipped.append({"url": url, "reason": reason, "evidence_id": existing.id})
                continue
            evidence = Evidence(
                account_id=account.account_id,
                seq=next_seq(session, account.account_id),
                phase=settings.phase,
                post_url=parsed.canonical,
                post_id=parsed.post_id,
                capture_source="cli",
                status="pending_completion",
                created_at=now,
            )
            session.add(evidence)
            session.flush()
            archive_queue.enqueue_for(session, evidence, now)
            created.append(
                {"evidence_id": evidence.id, "seq": evidence.seq, "post_url": evidence.post_url}
            )
        session.commit()
    except BaseException:
        session.rollback()
        raise
    return {
        "account": {"account_id": account.account_id, "handle": account.current_handle},
        "created": created,
        "skipped": skipped,
    }


def list_pending(session: Session, post_id: str | None) -> list[Evidence]:
    query = (
        select(Evidence)
        .where(Evidence.status == "pending_completion")
        .order_by(Evidence.account_id, Evidence.seq)
    )
    if post_id:
        query = query.where(Evidence.post_id == post_id)
    return list(session.scalars(query))


def archive_only(session: Session, evidence_id: int, note: str | None) -> Evidence:
    evidence = session.get(Evidence, evidence_id)
    if evidence is None:
        raise not_found(f"evidence {evidence_id}")
    try:
        transition_evidence(evidence, "archive_only")
    except ApiError:
        raise conflict(
            f"archive-only is only valid from pending_completion (evidence is {evidence.status!r})"
        ) from None
    if note:
        evidence.note = note
    session.commit()
    return evidence

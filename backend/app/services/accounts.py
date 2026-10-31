"""Accounts keyed by rest_id; handle_history complete from birth (ADR-001/020).

Account creation and handle changes are split in two steps because
``handle_history.evidence_id`` points at the capture that observed the handle,
and that evidence row only gets its id after the account exists:

1. :func:`ensure_account` upserts the account and reports the handle that must
   be recorded (the initial one on creation, or the newly observed one);
2. :func:`record_handle` appends that history row once the evidence id is known.

History rows are only ever inserted — never updated or deleted.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, HandleHistory
from app.services.x_urls import same_handle


def ensure_account(
    session: Session, rest_id: str, handle: str, now: str
) -> tuple[Account, str | None]:
    account = session.get(Account, rest_id)
    if account is None:
        account = Account(
            account_id=rest_id,
            current_handle=handle,
            first_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(account)
        session.flush()
        return account, handle
    if not same_handle(account.current_handle, handle):
        account.current_handle = handle
        account.updated_at = now
        return account, handle
    return account, None


def record_handle(
    session: Session, account_id: str, handle: str, detected_at: str, evidence_id: int | None
) -> None:
    session.add(
        HandleHistory(
            account_id=account_id, handle=handle, detected_at=detected_at, evidence_id=evidence_id
        )
    )


def observe(
    session: Session, rest_id: str, handle: str, now: str, evidence_id: int | None = None
) -> Account:
    """Both steps at once, for writes that have no evidence row to wait for."""
    account, new_handle = ensure_account(session, rest_id, handle, now)
    if new_handle is not None:
        record_handle(session, rest_id, new_handle, now, evidence_id)
    return account


def find_by_handle(session: Session, handle: str) -> list[Account]:
    """Accounts whose current OR any historical handle matches (case-insensitive)."""
    lowered = handle.lower()
    ids = set(
        session.scalars(
            select(Account.account_id).where(func.lower(Account.current_handle) == lowered)
        )
    )
    ids |= set(
        session.scalars(
            select(HandleHistory.account_id).where(func.lower(HandleHistory.handle) == lowered)
        )
    )
    if not ids:
        return []
    return list(
        session.scalars(
            select(Account).where(Account.account_id.in_(ids)).order_by(Account.account_id)
        )
    )


def history(session: Session, account_id: str) -> list[HandleHistory]:
    return list(
        session.scalars(
            select(HandleHistory)
            .where(HandleHistory.account_id == account_id)
            .order_by(HandleHistory.detected_at, HandleHistory.id)
        )
    )


def known_handles(session: Session, account: Account) -> set[str]:
    names = {account.current_handle.lower()}
    names |= {row.handle.lower() for row in history(session, account.account_id)}
    return names

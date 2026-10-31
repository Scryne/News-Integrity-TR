"""Interaction edges (ARCHITECTURE §3.2, ADR-015).

The source is always the post author, so it always has a rest_id. The target
gets an account row only when its rest_id was actually extracted; otherwise the
edge keeps ``target_account_id = NULL`` and the raw handle — an identity is
never guessed. The handle is stored in ``target_handle_raw`` in both cases so
the export can always show who the edge pointed at when it was observed.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.errors import unprocessable
from app.models import Edge
from app.services import accounts
from app.services.x_urls import parse_status_url


def create_edge(
    session: Session,
    *,
    phase: str,
    now: str,
    source_rest_id: str,
    source_handle: str,
    target_rest_id: str | None,
    target_handle: str,
    edge_type: str,
    post_url: str,
    note: str | None = None,
    evidence_id: int | None = None,
    source_already_observed: bool = False,
) -> Edge:
    parsed = parse_status_url(post_url)
    if parsed is None:
        raise unprocessable("post_url must be an x.com / twitter.com /status/ link")
    if not source_already_observed:
        accounts.observe(session, source_rest_id, source_handle, now, evidence_id)
    if target_rest_id is not None:
        accounts.observe(session, target_rest_id, target_handle, now, evidence_id)
    edge = Edge(
        source_account_id=source_rest_id,
        target_account_id=target_rest_id,
        target_handle_raw=target_handle,
        edge_type=edge_type,
        phase=phase,
        post_url=parsed.canonical,
        observed_at=now,
        evidence_id=evidence_id,
        note=note,
    )
    session.add(edge)
    session.flush()
    return edge

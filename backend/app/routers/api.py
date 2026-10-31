"""HTTP routes (ARCHITECTURE §6). Thin: parse, call a service, shape the reply.

All writes go through these handlers — the CLI and the extension are clients
of this one write path (ADR-004).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.config import Settings
from app.errors import ApiError, not_found, unprocessable
from app.models import Account, Evidence
from app.schemas.api import (
    ArchiveOnlyIn,
    BulkArchiveIn,
    CaptureMeta,
    EdgeIn,
    ManualArchiveIn,
)
from app.services import (
    accounts,
    archive_queue,
    captures,
    edges,
    exports,
    pending,
    taxonomy,
)
from app.timeutil import now_iso

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_vocab(request: Request) -> taxonomy.Vocabulary:
    return request.app.state.vocabulary


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
VocabDep = Annotated[taxonomy.Vocabulary, Depends(get_vocab)]


async def _read_limited(upload: UploadFile, limit: int, name: str) -> bytes:
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise ApiError(413, f"{name} is larger than {limit // (1024 * 1024)} MB")
    return data


# --- health + vocabulary -----------------------------------------------------
@router.get("/healthz")
def healthz(settings: SettingsDep) -> dict:
    return {"status": "ok", "version": __version__, "data_dir": str(settings.data_dir), "phase": settings.phase}


@router.get("/api/taxonomy")
def get_taxonomy(
    session: SessionDep, vocab: VocabDep
) -> dict:
    return taxonomy.payload(session, vocab)


# --- captures ----------------------------------------------------------------
@router.post("/api/captures", status_code=201)
async def post_capture(
    meta: Annotated[str, Form()],
    viewport: Annotated[UploadFile, File()],
    session: SessionDep,
    settings: SettingsDep,
    vocab: VocabDep,
    crop: Annotated[UploadFile | None, File()] = None,
) -> dict:
    try:
        parsed = CaptureMeta.model_validate_json(meta)
    except ValidationError as exc:
        raise unprocessable(exc.errors(include_url=False, include_context=False)) from None
    viewport_png = await _read_limited(viewport, settings.max_image_bytes, "viewport")
    crop_png = await _read_limited(crop, settings.max_image_bytes, "crop") if crop is not None else None
    result = captures.create_capture(session, settings, vocab, parsed, viewport_png, crop_png)
    return result.as_dict()


# --- edges + accounts --------------------------------------------------------
@router.post("/api/edges", status_code=201)
def post_edge(
    body: EdgeIn,
    session: SessionDep,
    settings: SettingsDep,
) -> dict:
    try:
        edge = edges.create_edge(
            session,
            phase=settings.phase,
            now=now_iso(),
            source_rest_id=body.source.rest_id,
            source_handle=body.source.handle,
            target_rest_id=body.target.rest_id,
            target_handle=body.target.handle,
            edge_type=body.edge_type,
            post_url=body.post_url,
            note=body.note,
        )
        session.commit()
    except BaseException:
        session.rollback()
        raise
    return {"edge_id": edge.id, "target_resolved": edge.target_account_id is not None}


def _account_dict(session: Session, account: Account, with_history: bool) -> dict:
    count = len(
        list(session.scalars(select(Evidence.id).where(Evidence.account_id == account.account_id)))
    )
    out = {
        "account_id": account.account_id,
        "current_handle": account.current_handle,
        "first_seen_at": account.first_seen_at,
        "notes": account.notes,
        "evidence_count": count,
    }
    if with_history:
        out["handle_history"] = [
            {"handle": h.handle, "detected_at": h.detected_at, "evidence_id": h.evidence_id}
            for h in accounts.history(session, account.account_id)
        ]
    return out


@router.get("/api/accounts")
def get_accounts(session: SessionDep, handle: str | None = None) -> list[dict]:
    rows = (
        accounts.find_by_handle(session, handle.lstrip("@"))
        if handle
        else list(session.scalars(select(Account).order_by(Account.current_handle)))
    )
    return [_account_dict(session, a, with_history=False) for a in rows]


@router.get("/api/accounts/{account_id}")
def get_account(account_id: str, session: SessionDep) -> dict:
    account = session.get(Account, account_id)
    if account is None:
        raise not_found(f"account {account_id}")
    return _account_dict(session, account, with_history=True)


# --- pending / CLI flow ------------------------------------------------------
def _pending_dict(ev: Evidence) -> dict:
    return {
        "evidence_id": ev.id,
        "account_id": ev.account_id,
        "seq": ev.seq,
        "phase": ev.phase,
        "post_url": ev.post_url,
        "post_id": ev.post_id,
        "status": ev.status,
        "created_at": ev.created_at,
    }


@router.get("/api/pending")
def get_pending(session: SessionDep, post_id: str | None = None) -> list[dict]:
    return [_pending_dict(ev) for ev in pending.list_pending(session, post_id)]


@router.post("/api/evidence/{evidence_id}/archive-only")
def post_archive_only(
    evidence_id: int, session: SessionDep, body: ArchiveOnlyIn | None = None
) -> dict:
    ev = pending.archive_only(session, evidence_id, body.note if body else None)
    return _pending_dict(ev)


@router.post("/api/cli/bulk-archive", status_code=201)
def post_bulk_archive(
    body: BulkArchiveIn,
    session: SessionDep,
    settings: SettingsDep,
) -> dict:
    return pending.bulk_archive(session, settings, body)


# --- archive queue -----------------------------------------------------------
@router.get("/api/archive/jobs")
def get_jobs(session: SessionDep, status: str | None = None) -> list[dict]:
    return [archive_queue.job_dict(j) for j in archive_queue.list_jobs(session, status)]


@router.post("/api/archive/jobs/{job_id}/retry")
def post_retry(job_id: int, session: SessionDep) -> dict:
    return archive_queue.job_dict(archive_queue.retry(session, job_id, now_iso()))


@router.post("/api/archive/jobs/{job_id}/manual")
def post_manual(job_id: int, body: ManualArchiveIn, session: SessionDep) -> dict:
    job = archive_queue.complete_manually(session, job_id, body.archive_url, now_iso())
    return archive_queue.job_dict(job)


# --- exports -----------------------------------------------------------------
@router.get("/api/exports/edges.csv", response_class=PlainTextResponse)
def export_edges(session: SessionDep) -> PlainTextResponse:
    return PlainTextResponse(
        exports.edges_csv(session),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="edges.csv"'},
    )


@router.get("/api/exports/accounts/{account_id}/case-file.json")
def export_case_file(account_id: str, session: SessionDep) -> dict:
    return exports.case_file(session, account_id)


@router.get("/api/exports/manifest")
def export_manifest(
    session: SessionDep,
    settings: SettingsDep,
    verify: Annotated[bool, Query()] = False,
) -> dict:
    return exports.manifest(session, settings.data_dir, verify)

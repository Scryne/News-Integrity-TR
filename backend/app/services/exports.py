"""Exports: edges.csv, per-account case file, hash manifest (ARCHITECTURE §6).

Tier discipline (ARCHITECTURE §10): every evidence row in an export carries an
explicit ``tier``; ``archive_only`` rows are labelled degraded and
``pending_completion`` rows are labelled "not yet evidence" — no export mixes
tiers silently. Archive links live only here (and in ``archive_jobs``), never
in the immutable sidecars.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.models import Account, ArchiveJob, Edge, Evidence, EvidenceCode
from app.services import accounts
from app.services.evidence_store import sha256_hex
from app.timeutil import now_iso

TIER_LABEL = {
    "complete": "complete: screenshot + disk-verified hashes + archive links",
    "archive_only": "archive_only: DEGRADED, post was deleted before completion; archive links only",
    "pending_completion": "pending_completion: NOT YET EVIDENCE, slot reserved, archives running",
}

EDGE_COLUMNS = [
    "source_account_id",
    "source_handle",
    "target_account_id",
    "target_handle",
    "edge_type",
    "phase",
    "post_url",
    "observed_at",
    "evidence_id",
]


def edges_csv(session: Session) -> str:
    handles = dict(session.execute(select(Account.account_id, Account.current_handle)).all())
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(EDGE_COLUMNS)
    for edge in session.scalars(select(Edge).order_by(Edge.observed_at, Edge.id)):
        target_handle = (
            handles.get(edge.target_account_id) if edge.target_account_id else None
        ) or edge.target_handle_raw
        writer.writerow(
            [
                edge.source_account_id,
                handles.get(edge.source_account_id, ""),
                edge.target_account_id or "",
                target_handle or "",
                edge.edge_type,
                edge.phase,
                edge.post_url,
                edge.observed_at,
                edge.evidence_id if edge.evidence_id is not None else "",
            ]
        )
    return out.getvalue()


def _archives(session: Session, evidence_id: int) -> list[dict]:
    jobs = session.scalars(
        select(ArchiveJob).where(ArchiveJob.evidence_id == evidence_id).order_by(ArchiveJob.id)
    )
    return [
        {"service": j.service, "status": j.status, "archive_url": j.archive_url, "job_id": j.id}
        for j in jobs
    ]


def evidence_dict(session: Session, ev: Evidence) -> dict:
    codes = sorted(
        session.scalars(select(EvidenceCode.code).where(EvidenceCode.evidence_id == ev.id))
    )
    return {
        "evidence_id": ev.id,
        "seq": ev.seq,
        "tier": ev.status,
        "tier_label": TIER_LABEL[ev.status],
        "phase": ev.phase,
        "post_url": ev.post_url,
        "post_id": ev.post_id,
        "post_text": ev.post_text,
        "posted_at": ev.posted_at,
        "captured_at": ev.captured_at,
        "handle_at_capture": ev.handle_at_capture,
        "follower_count_at_capture": ev.follower_count_at_capture,
        "category": ev.category,
        "codes": codes,
        "taxonomy_version": ev.taxonomy_version,
        "note": ev.note,
        "capture_source": ev.capture_source,
        "crop_failed": bool(ev.crop_failed),
        "files": {
            "primary": {"path": ev.screenshot_path, "sha256": ev.screenshot_sha256},
            "viewport": {"path": ev.viewport_path, "sha256": ev.viewport_sha256},
            "sidecar": {"path": ev.sidecar_path, "sha256": ev.sidecar_sha256},
        },
        "archives": _archives(session, ev.id),
    }


def case_file(session: Session, account_id: str) -> dict:
    account = session.get(Account, account_id)
    if account is None:
        raise not_found(f"account {account_id}")
    rows = list(
        session.scalars(
            select(Evidence).where(Evidence.account_id == account_id).order_by(Evidence.seq)
        )
    )
    tiers = {tier: sum(1 for r in rows if r.status == tier) for tier in TIER_LABEL}
    edge_rows = session.scalars(
        select(Edge)
        .where(or_(Edge.source_account_id == account_id, Edge.target_account_id == account_id))
        .order_by(Edge.observed_at, Edge.id)
    )
    return {
        "generated_at": now_iso(),
        "account": {
            "account_id": account.account_id,
            "current_handle": account.current_handle,
            "first_seen_at": account.first_seen_at,
            "notes": account.notes,
        },
        "handle_history": [
            {"handle": h.handle, "detected_at": h.detected_at, "evidence_id": h.evidence_id}
            for h in accounts.history(session, account_id)
        ],
        "tiers": tiers,
        "evidence": [evidence_dict(session, r) for r in rows],
        "edges": [
            {
                "edge_id": e.id,
                "direction": "outgoing" if e.source_account_id == account_id else "incoming",
                "source_account_id": e.source_account_id,
                "target_account_id": e.target_account_id,
                "target_handle_raw": e.target_handle_raw,
                "edge_type": e.edge_type,
                "phase": e.phase,
                "post_url": e.post_url,
                "observed_at": e.observed_at,
                "evidence_id": e.evidence_id,
                "note": e.note,
            }
            for e in edge_rows
        ],
    }


def _verify_file(data_dir: Path, rel: str, expected: str | None) -> str:
    path = data_dir / rel
    if not path.is_file():
        return "missing"
    return "ok" if sha256_hex(path.read_bytes()) == expected else "mismatch"


def manifest(session: Session, data_dir: Path, verify: bool) -> dict:
    entries: list[dict] = []
    tracked: set[str] = set()
    rows = session.scalars(
        select(Evidence)
        .where(Evidence.screenshot_path.is_not(None))
        .order_by(Evidence.account_id, Evidence.seq)
    )
    for ev in rows:
        for role, rel, digest in (
            ("primary", ev.screenshot_path, ev.screenshot_sha256),
            ("viewport", ev.viewport_path, ev.viewport_sha256),
            ("sidecar", ev.sidecar_path, ev.sidecar_sha256),
        ):
            if rel is None:
                continue
            tracked.add(rel)
            entry = {
                "path": rel,
                "sha256": digest,
                "evidence_id": ev.id,
                "role": role,
                "status": ev.status,
                "phase": ev.phase,
            }
            if verify:
                entry["verify"] = _verify_file(data_dir, rel, digest)
            entries.append(entry)

    result: dict = {"generated_at": now_iso(), "verified": verify, "entries": entries}
    if verify:
        result["mismatches"] = [e for e in entries if e["verify"] != "ok"]
        evidence_root = data_dir / "evidence"
        on_disk = (
            sorted(
                p.relative_to(data_dir).as_posix() for p in evidence_root.rglob("*") if p.is_file()
            )
            if evidence_root.exists()
            else []
        )
        # Files in the evidence tree that no row vouches for (e.g. a planted or
        # leftover file). Reported, never deleted.
        result["untracked"] = [p for p in on_disk if p not in tracked]
        result["all_ok"] = not result["mismatches"] and not result["untracked"]
    return result

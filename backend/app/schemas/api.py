"""Request bodies for the HTTP API (ARCHITECTURE §6).

Identity discipline (``evidence-integrity`` rule 1): every rest_id / post_id is
a ``str`` constrained to digits. Pydantic v2 does not coerce a JSON number into
a ``str`` field, so a client that lets a snowflake id pass through a JS number
is rejected with 422 instead of silently storing a rounded id.

Provenance discipline (rule 6): every body forbids unknown fields, so a client
that tries to send ``phase`` or ``taxonomy_version`` gets 422 — both are
stamped server-side only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.services.x_urls import HANDLE_PATTERN, REST_ID_PATTERN

RestId = Annotated[str, StringConstraints(pattern=REST_ID_PATTERN)]
Handle = Annotated[str, StringConstraints(pattern=HANDLE_PATTERN)]
EdgeType = Literal["quote", "retweet", "reply", "mention"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AuthorIn(_Strict):
    rest_id: RestId
    handle: Handle
    follower_count: int | None = Field(default=None, ge=0)


class InlineEdgeIn(_Strict):
    target_rest_id: RestId | None = None
    target_handle: Handle
    edge_type: EdgeType


class CaptureMeta(_Strict):
    post_url: str = Field(max_length=500)
    post_id: Annotated[str, StringConstraints(pattern=REST_ID_PATTERN)] | None = None
    post_text: str | None = Field(default=None, max_length=20_000)
    posted_at: str | None = None
    author: AuthorIn
    category: str = Field(min_length=1, max_length=40)
    codes: list[str] = Field(min_length=1, max_length=40)
    note: str | None = Field(default=None, max_length=5_000)
    crop_failed: bool = False
    edge: InlineEdgeIn | None = None
    # Sidecar "extraction" block (x-dom-extraction rule 6): how each field was
    # obtained + the extractor version. Small, flat, string-valued.
    extraction: dict[str, str] = Field(default_factory=dict, max_length=20)

    @field_validator("posted_at")
    @classmethod
    def _iso_utc(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        try:
            moment = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("posted_at must be an ISO-8601 timestamp") from exc
        if moment.tzinfo is None:
            raise ValueError("posted_at must carry a timezone (X renders UTC 'Z')")
        return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    @field_validator("codes")
    @classmethod
    def _unique_codes(cls, value: list[str]) -> list[str]:
        cleaned = [code.strip().upper() for code in value]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("codes must not repeat")
        return cleaned

    @field_validator("extraction")
    @classmethod
    def _short_values(cls, value: dict[str, str]) -> dict[str, str]:
        for key, item in value.items():
            if len(key) > 40 or len(item) > 120:
                raise ValueError("extraction keys/values are short labels, not content")
        return value


class EdgeAccountIn(_Strict):
    rest_id: RestId | None = None
    handle: Handle


class EdgeSourceIn(_Strict):
    rest_id: RestId
    handle: Handle


class EdgeIn(_Strict):
    source: EdgeSourceIn
    target: EdgeAccountIn
    edge_type: EdgeType
    post_url: str = Field(max_length=500)
    note: str | None = Field(default=None, max_length=5_000)


class ArchiveOnlyIn(_Strict):
    note: str | None = Field(default=None, max_length=5_000)


class ManualArchiveIn(_Strict):
    archive_url: str = Field(min_length=10, max_length=1_000)


class BulkAccountIn(_Strict):
    handle: Handle
    rest_id: RestId | None = None


class BulkArchiveIn(_Strict):
    account: BulkAccountIn
    urls: list[str] = Field(min_length=1, max_length=500)

"""Application configuration (pydantic-settings).

Settings are read from ``NIT_``-prefixed environment variables and an optional
``.env`` file in the backend working directory. See ARCHITECTURE.md §9 for the
full documented config table.

Wayback key names: ADR-024 named them ``NIT_WAYBACK_S3_ACCESSKEY`` /
``NIT_WAYBACK_S3_SECRET`` while ARCHITECTURE §9 wrote ``NIT_WAYBACK_S3_ACCESS``.
Phase 3 settles on the ADR-024 names and accepts the §9 spelling as an alias,
so either ``.env`` works.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ADR-014: the backend binds to loopback only; the bind host is not configurable.
BIND_HOST = "127.0.0.1"

# CORS fallback origin pattern while NIT_EXTENSION_ID is unset (ADR-021).
EXTENSION_ORIGIN_REGEX = r"^chrome-extension://.*$"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # --- storage -----------------------------------------------------------
    # NIT_DATA_DIR — DB + evidence root (ARCHITECTURE §4.1 / §9).
    data_dir: Path = Path("./data")

    # --- network / binding -------------------------------------------------
    # NIT_PORT — bind port; host is hardcoded to 127.0.0.1 (ADR-014).
    port: int = 8765

    # --- methodology -------------------------------------------------------
    # NIT_PHASE — case-study phase (ADR-019). Stamped onto every evidence and
    # edge row at creation and used as the evidence folder prefix. Switched to
    # VK2 exactly once, at the start of sprint S2.
    phase: Literal["VK1", "VK2"] = "VK1"

    # --- security boundary -------------------------------------------------
    # NIT_EXTENSION_ID — installed (unpacked) extension id. When set, CORS is
    # locked to exactly chrome-extension://{id} (ADR-021). When unset (first
    # run, before the id is known), CORS falls back to the wildcard regex and
    # the app logs a prominent startup warning.
    extension_id: str | None = None

    # --- archive worker (ARCHITECTURE §3.4 / §9) ---------------------------
    # NIT_ARCHIVE_WORKER — run the queue-draining daemon thread in the backend
    # process. Tests turn it off and drive the worker tick directly.
    archive_worker: bool = True
    archive_max_attempts: int = 5
    archive_today_min_interval_s: float = 45
    wayback_min_interval_s: float = 60
    # ADR-024: authenticated SPN2. Never committed; absent keys route Wayback
    # jobs to manual_pending instead of silently doing nothing.
    wayback_s3_accesskey: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NIT_WAYBACK_S3_ACCESSKEY", "NIT_WAYBACK_S3_ACCESS"),
    )
    wayback_s3_secret: str | None = Field(
        default=None, validation_alias=AliasChoices("NIT_WAYBACK_S3_SECRET")
    )

    # --- request limits ----------------------------------------------------
    # A viewport PNG at 4K x 2 dpr is ~10 MB; 25 MB leaves headroom.
    max_image_bytes: int = 25 * 1024 * 1024

    # --- derived paths (ARCHITECTURE §4.1 layout) --------------------------
    @property
    def db_path(self) -> Path:
        """SQLite database file."""
        return self.data_dir / "news_integrity.db"

    @property
    def evidence_dir(self) -> Path:
        """Evidence store root: data/evidence/{phase}-{account_id}/."""
        return self.data_dir / "evidence"

    # --- CORS (ADR-021) ----------------------------------------------------
    @property
    def extension_pinned(self) -> bool:
        return bool(self.extension_id)

    def cors_middleware_kwargs(self) -> dict[str, object]:
        """Origin arguments for CORSMiddleware.

        Pinned to the installed extension origin when NIT_EXTENSION_ID is set,
        otherwise the wildcard chrome-extension:// regex + a startup warning
        (ADR-021). Localhost binding stays the primary boundary (ADR-014).
        """
        if self.extension_pinned:
            return {"allow_origins": [f"chrome-extension://{self.extension_id}"]}
        return {"allow_origin_regex": EXTENSION_ORIGIN_REGEX}


@lru_cache
def get_settings() -> Settings:
    return Settings()

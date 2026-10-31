"""Bring the schema to Alembic head at startup.

The backend is the single writer (ADR-004), so it is also the one place that
upgrades the schema: a cold start on an empty data dir, or on a DB from an
older build, converges to head before any request is served. Alembic's own
``alembic upgrade head`` stays valid for manual use; both paths run the same
revision scripts.
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy.engine import Engine

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def upgrade_to_head(engine: Engine) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

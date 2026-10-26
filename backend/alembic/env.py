"""Alembic environment.

Uses the app's declarative metadata as the autogenerate target and the app's
engine (so the ARCHITECTURE §5 connect-time pragmas from app.db apply to
migration connections too).
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context

# Make `import app...` work regardless of the invocation cwd: this file is
# backend/alembic/env.py, so its grandparent is the backend/ package root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.models  # noqa: F401  (registers all 8 tables on Base.metadata)
from app.config import get_settings
from app.db import Base, build_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = f"sqlite:///{get_settings().db_path.as_posix()}"
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = build_engine()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

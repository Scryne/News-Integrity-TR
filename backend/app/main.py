"""FastAPI application entry point.

Phase 1 / T1 scope: build the app, wire CORS per ADR-021, and expose the
lifespan hook. No endpoints are registered yet:

  * GET /healthz, GET /api/taxonomy, POST /api/captures  -> T6
  * idempotent taxonomy + category seeding                -> T3 (lifespan)
  * archive worker daemon thread                          -> Phase 3 (lifespan)

Each hooks into the marked places below without reshaping this module.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import BIND_HOST, Settings, get_settings
from app.db import SessionLocal
from app.services.taxonomy_seed import TaxonomySeedError, seed_taxonomy

logger = logging.getLogger("news_integrity")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "News Integrity TR backend starting (phase=%s, data_dir=%s)",
        settings.phase,
        settings.data_dir,
    )
    # T3: idempotent taxonomy + category seeding (ADR-016/017/018). One
    # transaction; upsert labels, never delete codes. A missing/malformed
    # codebook aborts startup rather than serving an incomplete vocabulary.
    try:
        with SessionLocal.begin() as session:
            seed_taxonomy(session)
    except TaxonomySeedError:
        logger.exception(
            "taxonomy seeding failed — refusing to start with an incomplete "
            "coding vocabulary; fix taxonomy.json and restart"
        )
        raise
    # Phase 3: the archive worker daemon thread starts here (and stops on exit).
    yield
    logger.info("News Integrity TR backend stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="News Integrity TR — Evidence Capture Toolkit",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS: pinned to the installed extension origin, or the wildcard
    # chrome-extension:// regex + a warning while NIT_EXTENSION_ID is unset
    # (ADR-021). Localhost binding remains the primary security boundary
    # (ADR-014).
    app.add_middleware(
        CORSMiddleware,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        **settings.cors_middleware_kwargs(),
    )
    if not settings.extension_pinned:
        logger.warning(
            "NIT_EXTENSION_ID is not set: CORS is using the wildcard "
            "'chrome-extension://*' origin. After loading the unpacked "
            "extension, copy its id from chrome://extensions into backend/.env "
            "to lock CORS to that one extension (README setup step, ADR-021)."
        )

    # T6: routers (healthz, taxonomy, captures) are included here.
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    _settings = get_settings()
    # ADR-014: loopback only; host is not configurable.
    uvicorn.run(app, host=BIND_HOST, port=_settings.port)

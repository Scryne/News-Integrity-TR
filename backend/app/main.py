"""FastAPI application entry point.

``create_app(settings)`` builds everything the process needs and keeps it on
``app.state`` — engine, session factory, seeded vocabulary, archive worker — so
tests can run the real app against a temporary data dir.

Startup order (lifespan): schema to Alembic head → idempotent taxonomy seeding
(ADR-016/017/018; a broken codebook aborts startup) → archive worker thread
(ADR-008; never awaited by a request).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import BIND_HOST, Settings, get_settings
from app.db import build_engine, make_session_factory
from app.errors import ApiError
from app.migrate import upgrade_to_head
from app.routers.api import router
from app.services.archive_worker import ArchiveWorker
from app.services.taxonomy import vocabulary_from
from app.services.taxonomy_seed import TaxonomySeedError, load_taxonomy, seed_taxonomy

logger = logging.getLogger("news_integrity")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "News Integrity TR backend starting (phase=%s, data_dir=%s)",
            settings.phase,
            settings.data_dir,
        )
        engine = build_engine(settings)
        upgrade_to_head(engine)
        sessions = make_session_factory(engine)
        try:
            with sessions.begin() as session:
                seed_taxonomy(session)
            vocabulary = vocabulary_from(load_taxonomy())
        except TaxonomySeedError:
            logger.exception(
                "taxonomy seeding failed — refusing to start with an incomplete "
                "coding vocabulary; fix taxonomy.json and restart"
            )
            raise
        app.state.settings = settings
        app.state.engine = engine
        app.state.sessions = sessions
        app.state.vocabulary = vocabulary
        worker = ArchiveWorker(sessions, settings)
        app.state.worker = worker
        if settings.archive_worker:
            worker.start()
        try:
            yield
        finally:
            worker.stop()
            engine.dispose()
            logger.info("News Integrity TR backend stopped")

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

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(router)
    return app


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    # ADR-014: loopback only; host is not configurable.
    uvicorn.run(create_app(settings), host=BIND_HOST, port=settings.port)


if __name__ == "__main__":
    main()

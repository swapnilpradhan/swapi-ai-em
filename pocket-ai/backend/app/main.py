"""Pocket.ai Studio API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import chat, coach, drive, meetings, slides, speakers
from .core.config import get_settings
from .core.logging import configure_logging, get_logger
from .services.registry import get_registry

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.media_root.mkdir(parents=True, exist_ok=True)
    log.info("startup", env=settings.app_env, stubs=get_registry().stub_backends)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Pocket.ai Studio",
    description=(
        "Meeting intelligence and executive coaching for Pocket.ai recordings. "
        "Every generated claim cites a transcript span; claims that fail validation "
        "are dropped rather than surfaced."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
for module in (meetings, drive, speakers, chat, slides, coach):
    app.include_router(module.router, prefix=API_PREFIX)


@app.get("/health")
async def health() -> dict:
    """Health, plus which services are running on stubs.

    Surfaced deliberately: stub output that looks real is a trap, so the API always
    says when it is synthetic.
    """
    settings = get_settings()
    stubs = get_registry().stub_backends
    return {
        "status": "ok",
        "version": "0.1.0",
        "environment": settings.app_env,
        "stub_backends": stubs,
        "note": (f"synthetic output from: {', '.join(stubs)}" if stubs else "all backends live"),
    }

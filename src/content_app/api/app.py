"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from content_app.api.routes_brand import router as brand_router
from content_app.api.routes_runs import router as runs_router
from content_app.config import configure_logging


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Apply ``LOG_LEVEL`` and other logging from settings (same as CLI)."""
    configure_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="content-app", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(runs_router, prefix="/api")
    app.include_router(brand_router, prefix="/api")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

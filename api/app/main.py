from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .database import check_database, mark_database
from .routers import admin, admin_apps, assets, galactic_map, health, images, operators, public, submissions, verifications

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_migrations_safely() -> None:
    settings = get_settings()
    if not settings.run_migrations_on_start:
        check_database()
        return
    try:
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
        check_database()
        logger.info("Database migrations completed.")
    except Exception as exc:
        # Do not crash the web service. /api/health reports the DB failure.
        logger.exception("Database migration/readiness failed; API will remain online for diagnostics.")
        mark_database(False, f"{type(exc).__name__}: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations_safely()
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    root_path="/api",
    root_path_in_servers=True,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Key", "X-Admin-Actor"],
)


@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    request_path = request.url.path.rstrip("/")
    is_admin_app_upload = (
        request.method == "POST"
        and "/admin/apps/" in request_path
        and request_path.endswith("/upload")
    )
    request_limit = (
        settings.max_admin_app_bytes + 2_000_000
        if is_admin_app_upload
        else settings.max_request_bytes
    )
    try:
        request_too_large = bool(content_length and int(content_length) > request_limit)
    except ValueError:
        request_too_large = True
    if request_too_large:
        return JSONResponse(status_code=413, content={"detail": "Request body is too large."})
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.exception("Unhandled API error")
    return JSONResponse(status_code=500, content={"detail": "Unexpected server error."})


@app.get("/")
def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


app.include_router(health.router)
app.include_router(public.router)
app.include_router(assets.public_router)
app.include_router(galactic_map.router)
app.include_router(submissions.router)
app.include_router(verifications.router)
app.include_router(images.router)
app.include_router(operators.router)
app.include_router(admin_apps.router)
app.include_router(assets.admin_router)
app.include_router(admin.router)

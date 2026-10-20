import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, engine, ensure_columns
from .routers import admin, internships, meta, recommendations, users
from .routers.auth import router as auth_router
from .routers.saved import router as saved_activity_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    ensure_columns()

    # Ensure baseline verified internship catalog (at least 27 open opportunities)
    # Runs during production / server startup; skipped in mock unit test environments
    if settings.enable_scheduler and os.environ.get("TESTING") != "true":
        try:
            from .database import SessionLocal
            from .models import Internship
            with SessionLocal() as db:
                open_count = db.query(Internship).filter(Internship.status.in_(["open", "closing_soon"])).count()
                if open_count < 27:
                    from scripts.seed_data import seed_listings
                    seed_listings(db)
        except Exception as e:
            logging.getLogger("internradar.main").warning("Baseline seed check skipped: %s", e)

    from .ai import semantic
    semantic.configure(enabled=settings.enable_semantic, model=settings.semantic_model)

    # Ensure upload directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)

    sched = None
    if settings.enable_scheduler:
        from .scheduler import start_scheduler
        sched = start_scheduler()
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(
    title="InternRadar API",
    version="2.0.0",
    description="Internship Discovery and Career Platform for India",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
for r in (
    meta.router,
    auth_router,
    internships.router,
    recommendations.router,
    saved_activity_router,
    users.router,
    admin.router,
):
    app.include_router(r)


# Serve static frontend files
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root():
    """Serve the frontend HTML app."""
    index_path = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return RedirectResponse("/api/docs")


@app.get("/health", tags=["meta"])
def health():
    return {"ok": True, "version": "2.0.0"}


@app.get("/{full_path:path}", include_in_schema=False)
def catch_all(full_path: str):
    """Fallback to frontend index.html for client-side navigation on non-API paths."""
    if full_path.startswith("api/") or full_path == "api":
        return RedirectResponse("/api/docs")
    index_path = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return RedirectResponse("/api/docs")

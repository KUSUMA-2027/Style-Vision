"""
StyleVision Backend — FastAPI Application Entry Point
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings

settings = get_settings()


from app.database import connect_to_mongo, close_mongo_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # --- Startup ---
    print(f"[StyleVision] {settings.app_name} backend starting ({settings.app_env} mode)")

    # Ensure required directories exist
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.catalogue_dir, exist_ok=True)
    for sub in ["outfits", "accessories", "makeup", "hairstyles"]:
        os.makedirs(os.path.join(settings.catalogue_dir, sub), exist_ok=True)

    # Connect to MongoDB database
    try:
        await connect_to_mongo()
    except Exception as exc:
        print(f"[StyleVision DB] Startup connection error: {exc}")

    print("[StyleVision] Startup complete. Swagger docs at /docs")

    yield

    # --- Shutdown ---
    await close_mongo_connection()
    print("[StyleVision] Shutting down")


# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="StyleVision API",
    description=(
        "Personalized virtual fashion and beauty styling system. "
        "Upload photos and explore outfit try-on, accessories, makeup, and hairstyles."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# In development, allow all origins so mobile devices on the LAN can connect cleanly
cors_origins = ["*"] if settings.app_env == "development" else settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# ── Static file serving for uploads (development only) ────────────────────────
# In production, serve static files via a CDN or dedicated media server.
if os.path.isdir(settings.upload_dir):
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

if os.path.isdir(settings.catalogue_dir):
    app.mount("/catalogue", StaticFiles(directory=settings.catalogue_dir), name="catalogue")


# ── Routers ───────────────────────────────────────────────────────────────────
from app.routers import auth, upload, catalogue, tryon, history, profile, admin, wardrobe

app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(catalogue.router)
app.include_router(wardrobe.router)
app.include_router(tryon.router)
app.include_router(history.router)
app.include_router(profile.router)
app.include_router(admin.router)


# ── Global Exception Handlers ─────────────────────────────────────────────────
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from fastapi import Request


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Format Pydantic request validation errors into a clean, predictable response."""
    errors = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err.get("loc", []))
        msg = err.get("msg", "Validation error")
        errors.append({"field": field, "message": msg})
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "status_code": 422,
            "details": errors,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Format explicit HTTP exceptions into uniform error payloads."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail if isinstance(exc.detail, str) else "Request Error",
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled server errors. Never leak internal stack traces or paths."""
    print(f"[ERROR] Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error. Please try again later.",
            "status_code": 500,
        },
    )


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"], summary="Health check")
async def health_check():
    """
    Returns the running status of the API and MongoDB connection.
    Use this to confirm full-stack availability.
    """
    db_status = "connected"
    try:
        from app.database import db_manager
        if db_manager.client is not None:
            await db_manager.client.admin.command("ping")
        else:
            db_status = "disconnected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.1.0",
        "environment": settings.app_env,
        "tryon_mode": settings.tryon_mode,
        "database": db_status,
    }


@app.get("/", tags=["System"], summary="Root", include_in_schema=False)
async def root():
    return {
        "message": f"Welcome to {settings.app_name} API",
        "docs": "/docs",
        "health": "/health",
    }

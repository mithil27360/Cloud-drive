from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback

from .database import engine, Base
from .config import settings
from .routes import auth, files, query, share, admin, profile  # , google_auth, magic_auth - TODO: Uncomment after build
from .middleware import SecurityHeadersMiddleware, RequestIDMiddleware
from .logging_config import logger

# Create tables
Base.metadata.create_all(bind=engine)

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"]
)

app = FastAPI(
    title="AI Cloud Drive",
    description="Self-hosted file storage with AI-powered search",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if settings.DEBUG else None,
)


# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,  # Cache preflight for 10 minutes
)

# Global exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, 'request_id', 'unknown')
    logger.error(f"HTTP {exc.status_code}: {exc.detail}", extra={"request_id": request_id})
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "request_id": request_id
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, 'request_id', 'unknown')
    logger.warning(f"Validation error: {exc.errors()}", extra={"request_id": request_id})
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "details": exc.errors(),
            "request_id": request_id
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, 'request_id', 'unknown')
    logger.error(
        f"Unhandled exception: {str(exc)}\n{traceback.format_exc()}",
        extra={"request_id": request_id}
    )
    # Don't expose internal errors in production
    error_message = str(exc) if settings.DEBUG else "Internal server error"
    return JSONResponse(
        status_code=500,
        content={
            "error": error_message,
            "request_id": request_id
        }
    )

# Include routers
app.include_router(auth.router)
# app.include_router(google_auth.router)  # TODO: Uncomment after build completes
# app.include_router(magic_auth.router)  # TODO: Uncomment after build completes
app.include_router(files.router)
app.include_router(query.router)
app.include_router(share.router)
app.include_router(admin.router)
app.include_router(profile.router)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to AI Cloud Drive API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }

@app.get("/health")
def health_check():
    """Health check endpoint for load balancers and orchestrators"""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG
    }

@app.get("/ready")
def readiness_check():
    """Readiness check - verify all dependencies are available"""
    checks = {"database": False, "redis": False, "minio": False}
    
    # Check database
    try:
        from .database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        checks["database"] = True
    except Exception:
        pass
    
    # Check Redis
    try:
        from .cache import cache
        cache.client.ping()
        checks["redis"] = True
    except Exception:
        pass
    
    # Check MinIO
    try:
        from .storage.minio_client import minio_client
        minio_client.client.list_buckets()
        checks["minio"] = True
    except Exception:
        pass
    
    all_ready = all(checks.values())
    return JSONResponse(
        status_code=200 if all_ready else 503,
        content={"ready": all_ready, "checks": checks}
    )

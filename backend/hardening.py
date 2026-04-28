"""
Production hardening utilities — installable as a single side-effect call from server.py.

Provides:
  - install_hardening(app, db)
  - Deep `/api/health` endpoint (db ping + LLM key presence + uptime + version)
  - Request ID middleware (X-Request-ID header for log correlation)
  - Structured logging (JSON-style key=value)
  - Generic exception handler (no stack-trace leak in production)
  - Simple in-memory rate limiter for sensitive endpoints

NOTE: For multi-instance deployments switch the rate limiter to Redis-backed.
"""
from __future__ import annotations
from collections import defaultdict, deque
from datetime import datetime, timezone
from time import monotonic
from typing import Callable, Deque, Dict
import logging
import os
import re
import time
import uuid

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("hardening")

# ---------- BUILD INFO ----------
APP_VERSION = os.environ.get("APP_VERSION", "1.0.247")  # bumped each release
APP_STARTED_AT = datetime.now(timezone.utc)
APP_BOOT_MONO = monotonic()


# ---------- IN-MEMORY RATE LIMITER ----------
class InMemoryRateLimiter:
    """
    Sliding-window rate limiter keyed by (scope, identifier).
    Identifier is typically client IP for unauthenticated routes.
    """

    def __init__(self):
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, scope: str, identifier: str, limit: int, window_sec: int) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        now = monotonic()
        cutoff = now - window_sec
        key = f"{scope}:{identifier}"
        bucket = self._buckets[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(window_sec - (now - bucket[0])))
            return False, retry_after
        bucket.append(now)
        return True, 0


_limiter = InMemoryRateLimiter()


def get_client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, limit: int, window_sec: int):
    """FastAPI dependency factory for rate limiting."""
    def _dep(request: Request):
        ip = get_client_ip(request)
        ok, retry_after = _limiter.check(scope, ip, limit, window_sec)
        if not ok:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Retry after {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
    return _dep


# ---------- REQUEST-ID + STRUCTURED LOG MIDDLEWARE ----------
class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    - Assigns a request_id (UUID) per request, exposed via X-Request-ID response header.
    - Logs structured single-line summary at completion.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.exception(
                f"request_id={rid} method={request.method} path={request.url.path} "
                f"status=500 latency_ms={elapsed_ms} err=unhandled"
            )
            raise
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = rid
        # Skip noisy paths
        if not request.url.path.startswith("/api/uploads/"):
            logger.info(
                f"request_id={rid} method={request.method} path={request.url.path} "
                f"status={response.status_code} latency_ms={elapsed_ms}"
            )
        return response


# ---------- GLOBAL EXCEPTION HANDLER ----------
async def generic_exception_handler(request: Request, exc: Exception):
    """Hide stack traces in production while preserving request_id for support."""
    rid = getattr(request.state, "request_id", "n/a")
    logger.exception(f"request_id={rid} unhandled exception")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error. Please contact support with this reference.",
            "request_id": rid,
        },
    )


# ---------- HEALTH ENDPOINT FACTORY ----------
def install_health(app: FastAPI, db) -> None:
    @app.get("/api/health", tags=["system"])
    async def health():
        result = {
            "status": "ok",
            "version": APP_VERSION,
            "started_at": APP_STARTED_AT.isoformat(),
            "uptime_sec": int(monotonic() - APP_BOOT_MONO),
            "checks": {},
        }

        # Mongo ping
        try:
            await db.command("ping")
            result["checks"]["mongodb"] = "ok"
        except Exception as e:
            result["checks"]["mongodb"] = f"error: {str(e)[:100]}"
            result["status"] = "degraded"

        # LLM key presence (do not call API, cost guardrail)
        if os.environ.get("EMERGENT_LLM_KEY"):
            result["checks"]["llm_key"] = "configured"
        else:
            result["checks"]["llm_key"] = "missing"
            result["status"] = "degraded"

        # Stripe key presence
        result["checks"]["stripe_key"] = "configured" if os.environ.get("STRIPE_API_KEY") else "missing"

        # Disk free check (warn if <500MB on /app)
        try:
            import shutil
            total, used, free = shutil.disk_usage("/app")
            result["checks"]["disk_free_mb"] = free // (1024 * 1024)
            if free < 500 * 1024 * 1024:
                result["status"] = "degraded"
                result["checks"]["disk"] = "low"
        except Exception:
            pass

        return result

    @app.get("/api/health/live", tags=["system"])
    async def liveness():
        return {"status": "alive"}

    @app.get("/api/health/ready", tags=["system"])
    async def readiness():
        try:
            await db.command("ping")
        except Exception:
            raise HTTPException(503, "database not ready")
        return {"status": "ready"}


# ---------- ENV VALIDATION ----------
REQUIRED_ENV = ["MONGO_URL", "DB_NAME"]
RECOMMENDED_ENV = ["EMERGENT_LLM_KEY", "JWT_SECRET"]


def validate_env() -> None:
    """Called at boot. Fails hard for required, warns for recommended."""
    missing_required = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing_required:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing_required)}")
    missing_recommended = [k for k in RECOMMENDED_ENV if not os.environ.get(k)]
    if missing_recommended:
        logger.warning(f"Missing recommended env vars (degraded mode): {', '.join(missing_recommended)}")


# ---------- ENTRY POINT ----------
def install_hardening(app: FastAPI, db, *, allowed_origins: list[str] | None = None) -> None:
    """Install all hardening utilities on the FastAPI app."""
    validate_env()
    install_health(app, db)
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(Exception, generic_exception_handler)
    logger.info(
        f"hardening installed version={APP_VERSION} "
        f"started_at={APP_STARTED_AT.isoformat()}"
    )

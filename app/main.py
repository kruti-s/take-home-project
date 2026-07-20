"""FastAPI app entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db import get_connection, init_db
from app.routers import documents

logger = logging.getLogger(__name__)

# Vite's default dev server origin/port, for the local React frontend in frontend/.
_DEV_FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize the SQLite schema once when the app starts up."""
    conn = get_connection()
    try:
        init_db(conn)
    finally:
        conn.close()
    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        A FastAPI app with all routers registered.
    """
    app = FastAPI(
        title="assessment",
        description="Document store with FTS5 search",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_DEV_FRONTEND_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(documents.router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Return server errors as JSON `{error, code}` instead of an opaque 500.

        Client errors (4xx) are raised as HTTPException in the routers and keep
        FastAPI's standard `{"detail": ...}` shape; this handler only catches
        genuinely unhandled failures. The exception itself is logged server-side
        and never echoed to the client.
        """
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "internal server error", "code": 500},
        )

    return app


app = create_app()

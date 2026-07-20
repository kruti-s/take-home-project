"""FastAPI app entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import get_connection, init_db
from app.routers import documents


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
    app.include_router(documents.router)
    return app


app = create_app()

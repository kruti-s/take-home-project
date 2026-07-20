"""FastAPI app entrypoint."""

from fastapi import FastAPI

from app.routers import documents


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        A FastAPI app with all routers registered.
    """
    app = FastAPI(title="sandstone", description="Document store with FTS5 search")
    app.include_router(documents.router)
    return app


app = create_app()

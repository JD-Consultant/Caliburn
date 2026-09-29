"""Application composition root; dependency creation is explicit at startup."""

from fastapi import FastAPI

from caliburn.transport.http.health import router as health_router


def create_app() -> FastAPI:
    """Create the app without reading legacy configuration or requiring model credentials."""
    app = FastAPI(title="Caliburn", version="0.1.0")
    app.include_router(health_router)
    return app

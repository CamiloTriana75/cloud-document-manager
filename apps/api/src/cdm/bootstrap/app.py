"""Composición de dependencias de CDM (bootstrap).

Construye la app FastAPI con adaptadores por entorno. Único punto que conoce
el adaptador HTTP y la configuración.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cdm.adapters.inbound.http import auth, documents, health, upload_sessions, workspaces
from cdm.adapters.inbound.http.correlation import CorrelationIdMiddleware
from cdm.adapters.inbound.http.errors import register_error_handlers
from cdm.config.logging import configure_logging
from cdm.config.settings import Settings, load_settings

_API_TITLE = "Cloud Document Manager API"
_API_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Crea la aplicación FastAPI con su configuración y routers."""
    settings = settings or load_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=_API_TITLE, version=_API_VERSION)
    app.dependency_overrides[load_settings] = lambda: settings
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Correlation-ID"],
        expose_headers=["X-Request-ID"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(workspaces.router)
    app.include_router(documents.router)
    app.include_router(upload_sessions.router)
    return app


app = create_app()

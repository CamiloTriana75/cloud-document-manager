"""Composición de dependencias de CDM (bootstrap).

Construye la app FastAPI con adaptadores por entorno. Único punto que conoce
el adaptador HTTP y la configuración.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cdm.adapters.inbound.http import health
from cdm.config.settings import Settings, load_settings

_API_TITLE = "Cloud Document Manager API"
_API_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Crea la aplicación FastAPI con su configuración y routers."""
    settings = settings or load_settings()
    app = FastAPI(title=_API_TITLE, version=_API_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(health.router)
    return app


app = create_app()

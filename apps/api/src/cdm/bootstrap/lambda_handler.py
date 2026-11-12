"""Handler ASGI para AWS Lambda vía Mangum (ADR-0002 / CDM-20 / CDM-119).

Este adaptador actúa como punto de entrada exclusivo para AWS Lambda detrás de
API Gateway (payload v2.0). Traduce eventos de proxy a peticiones ASGI y respuestas
FastAPI a formato API Gateway, manteniendo la aplicación agnóstica de AWS.
"""

from typing import Any

from mangum import Mangum

from cdm.bootstrap.app import create_app
from cdm.config.settings import load_settings

_settings = load_settings()
_fastapi_app = create_app(_settings)

# lifespan="off" evita retrasos de cold start por eventos asíncronos de inicio/cierre
# en un entorno serverless efímero.
handler: Any = Mangum(_fastapi_app, lifespan="off")

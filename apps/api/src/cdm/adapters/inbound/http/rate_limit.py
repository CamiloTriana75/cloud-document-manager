"""Control de tasa de peticiones (Rate Limiting) para emisión de URLs (CDM-51 / AGENTS.md §8, §14).

Previene abuso y denegación de servicio en la generación de URLs prefirmadas de S3
(tanto subida como descarga), salvaguardando los recursos de API Gateway, Lambda y S3.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock

from fastapi import HTTPException, Request, status


@dataclass
class RateLimitBucket:
    """Ventana deslizante de timestamps para una clave específica."""

    timestamps: list[float] = field(default_factory=list)


class InMemoryRateLimiter:
    """Limitador de tasa en memoria basado en ventana deslizante (thread-safe)."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, RateLimitBucket] = defaultdict(RateLimitBucket)
        self._lock = Lock()

    def is_allowed(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Comprueba si la solicitud está permitida.

        Retorna:
            (permitido, retry_after_seconds)
        """
        current_time = now if now is not None else time.time()
        cutoff = current_time - self.window_seconds

        with self._lock:
            bucket = self._buckets[key]
            # Limpiar timestamps fuera de la ventana
            bucket.timestamps = [ts for ts in bucket.timestamps if ts > cutoff]

            if len(bucket.timestamps) >= self.max_requests:
                earliest = bucket.timestamps[0]
                retry_after = max(1, int(earliest + self.window_seconds - current_time))
                return False, retry_after

            bucket.timestamps.append(current_time)
            return True, 0

    def reset(self) -> None:
        """Limpia todos los registros del limitador."""
        with self._lock:
            self._buckets.clear()


# Limitador predeterminado para emisión de URLs: 60 solicitudes por minuto por cliente
_DEFAULT_URL_RATE_LIMITER = InMemoryRateLimiter(max_requests=60, window_seconds=60)


def get_client_identifier(request: Request) -> str:
    """Obtiene una clave representativa del cliente basada en IP y Authorization."""
    auth_header = request.headers.get("authorization", "")
    client_ip = request.client.host if request.client else "unknown"

    if auth_header and auth_header.startswith("Bearer "):
        # Usar fragmento final de token como identificador de sesión autenticada
        token_snippet = auth_header[-16:]
        return f"auth:{token_snippet}:{client_ip}"
    return f"ip:{client_ip}"


def rate_limit_dependency(
    limiter: InMemoryRateLimiter = _DEFAULT_URL_RATE_LIMITER,
) -> Callable[[Request], None]:
    """Crea una dependencia FastAPI que verifica el límite de peticiones."""

    def dependency(request: Request) -> None:
        key = get_client_identifier(request)
        allowed, retry_after = limiter.is_allowed(key)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Límite de solicitudes de emisión de URLs excedido. Intente más tarde.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency

"""Puerto de almacenamiento de objetos (CDM-27 / AGENTS.md §6).

Contrato para la generación de URLs prefirmadas de descarga y gestión de objetos.
Los casos de uso dependen exclusivamente de esta interfaz, nunca de boto3 ni de S3.
"""

from __future__ import annotations

from typing import Protocol


class StoragePort(Protocol):
    """Contrato para interactuar con el almacenamiento binario seguro."""

    def generate_download_url(
        self,
        storage_key: str,
        expires_in_seconds: int = 900,
        filename: str | None = None,
    ) -> str:
        """Genera una URL temporal prefirmada para descarga segura.

        Parámetros:
            storage_key: Clave opaca del objeto en el bucket privado.
            expires_in_seconds: Tiempo de vida de la URL (default: 15 minutos).
            filename: Nombre opcional para la cabecera Content-Disposition.

        Retorna:
            URL prefirmada HTTPS válida temporalmente.
        """
        ...

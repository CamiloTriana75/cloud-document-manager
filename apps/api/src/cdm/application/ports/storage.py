"""Puerto de almacenamiento de objetos (CDM-27 / AGENTS.md §6).

Contrato para la generación de URLs prefirmadas de descarga y gestión de objetos.
Los casos de uso dependen exclusivamente de esta interfaz, nunca de boto3 ni de S3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ObjectMetadata:
    """Metadatos de un objeto inspeccionado en el almacenamiento (HeadObject)."""

    storage_key: str
    size_bytes: int
    content_type: str | None = None
    etag: str | None = None


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

    def generate_upload_url(
        self,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        expires_in_seconds: int = 900,
    ) -> str:
        """Genera una URL temporal prefirmada PUT para carga directa a S3 (CDM-29).

        Parámetros:
            storage_key: Clave opaca del objeto bajo el prefijo del tenant.
            content_type: Tipo MIME validado de la allowlist.
            size_bytes: Tamaño exacto esperado en bytes.
            expires_in_seconds: Caducidad corta de la URL (default: 15 minutos).

        Retorna:
            URL prefirmada HTTPS válida temporalmente para PUT directo.
        """
        ...

    def get_object_metadata(self, storage_key: str) -> ObjectMetadata | None:
        """Obtiene metadatos de un objeto en S3 (HeadObject / reconciliación CDM-32).

        Retorna None si el objeto no existe en el bucket.
        """
        ...

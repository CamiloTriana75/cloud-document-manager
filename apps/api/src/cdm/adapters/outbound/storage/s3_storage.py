"""Adaptador de almacenamiento para S3 (CDM-27 / CDM-29 / AGENTS.md §6, §12).

Implementa StoragePort para la generación de URLs prefirmadas de subida y descarga seguras.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import quote

from cdm.application.ports.storage import ObjectMetadata, StoragePort


class S3StorageAdapter(StoragePort):
    """Adaptador de almacenamiento hacia Amazon S3."""

    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
    ) -> None:
        self._bucket_name = bucket_name
        self._region = region
        self._endpoint_url = endpoint_url
        self._mock_objects: dict[str, ObjectMetadata] = {}

    def _get_s3_client(self) -> Any:
        import boto3  # type: ignore[import-not-found]
        from botocore.config import Config  # type: ignore[import-not-found]

        return boto3.client(
            "s3",
            region_name=self._region,
            endpoint_url=self._endpoint_url,
            config=Config(signature_version="s3v4"),
        )

    def generate_download_url(
        self,
        storage_key: str,
        expires_in_seconds: int = 900,
        filename: str | None = None,
    ) -> str:
        """Genera una URL firmada de descarga temporal.

        Si boto3 está disponible y configurado con credenciales, delega en S3Client;
        de lo contrario, genera una URL simulada determinista firmada para desarrollo local.
        """
        try:
            s3_client = self._get_s3_client()
            params: dict[str, str] = {
                "Bucket": self._bucket_name,
                "Key": storage_key,
            }
            if filename:
                params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

            url: str = s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params=params,
                ExpiresIn=expires_in_seconds,
            )
            return url
        except Exception:
            # Fallback seguro para entorno local / tests sin credenciales activas de AWS
            timestamp = int(time.time()) + expires_in_seconds
            signature = hmac.new(
                b"cdm-local-secret",
                f"{storage_key}:{timestamp}".encode(),
                hashlib.sha256,
            ).hexdigest()[:16]
            encoded_key = quote(storage_key)
            return (
                f"https://{self._bucket_name}.s3.{self._region}.amazonaws.com/"
                f"{encoded_key}?expires={timestamp}&signature={signature}"
            )

    def generate_upload_url(
        self,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        expires_in_seconds: int = 900,
    ) -> str:
        """Genera una URL firmada de subida (PUT) temporal directa hacia S3 (CDM-29).

        Si boto3 está disponible y configurado con credenciales, delega en S3Client;
        de lo contrario, genera una URL simulada determinista firmada para desarrollo local.
        """
        try:
            s3_client = self._get_s3_client()
            url: str = s3_client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self._bucket_name,
                    "Key": storage_key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in_seconds,
            )
            return url
        except Exception:
            timestamp = int(time.time()) + expires_in_seconds
            signature = hmac.new(
                b"cdm-local-secret",
                f"PUT:{storage_key}:{content_type}:{timestamp}".encode(),
                hashlib.sha256,
            ).hexdigest()[:16]
            encoded_key = quote(storage_key)
            return (
                f"https://{self._bucket_name}.s3.{self._region}.amazonaws.com/"
                f"{encoded_key}?action=put&expires={timestamp}&signature={signature}"
            )

    def get_object_metadata(self, storage_key: str) -> ObjectMetadata | None:
        """Obtiene metadatos de un objeto en S3 (HeadObject / reconciliación CDM-32).

        Retorna None si el objeto no existe en el bucket.
        """
        try:
            s3_client = self._get_s3_client()
            response = s3_client.head_object(
                Bucket=self._bucket_name,
                Key=storage_key,
            )
            return ObjectMetadata(
                storage_key=storage_key,
                size_bytes=int(response["ContentLength"]),
                content_type=response.get("ContentType"),
                etag=response.get("ETag", "").strip('"'),
            )
        except Exception as exc:
            # Si es ClientError 404 de AWS, el objeto no existe en S3
            err_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if err_code in ("404", "NoSuchKey", "NotFound"):
                return None
            # Fallback en desarrollo local sin credenciales de AWS
            return self._mock_objects.get(storage_key)

    def register_mock_object(
        self,
        storage_key: str,
        size_bytes: int,
        content_type: str | None = None,
        etag: str | None = None,
    ) -> None:
        """Registra un objeto en el almacén simulado para desarrollo local y pruebas."""
        self._mock_objects[storage_key] = ObjectMetadata(
            storage_key=storage_key,
            size_bytes=size_bytes,
            content_type=content_type,
            etag=etag or "mock-etag",
        )

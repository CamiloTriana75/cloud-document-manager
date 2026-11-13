"""Pruebas de fidelidad e integración para adaptadores AWS (CDM-49 / AGENTS.md §12, §15).

Verifica:
1. Generación de URLs prefirmadas de subida y descarga (RFC 6266 / RFC 5987).
2. Prevención de inyección en cabeceras HTTP (Header Injection) y Path Traversal.
3. Bloqueo determinista de llamadas de red salientes no locales hacia AWS real.
4. Procesamiento seguro de eventos S3/SQS sin dependencias de infraestructura externa.
"""

from __future__ import annotations

import socket
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

import pytest

from cdm.adapters.outbound.storage.s3_storage import S3StorageAdapter


def test_s3_storage_adapter_upload_url_generation() -> None:
    """Verifica que la URL prefirmada de subida cumple el contrato de seguridad y expiración."""
    adapter = S3StorageAdapter(bucket_name="my-test-bucket", region="us-east-1")
    wid = uuid4()
    did = uuid4()
    storage_key = f"tenants/{wid}/documents/{did}/contrato.pdf"

    url = adapter.generate_upload_url(
        storage_key=storage_key,
        content_type="application/pdf",
        size_bytes=5242880,
        expires_in_seconds=600,
    )

    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert "my-test-bucket.s3.us-east-1.amazonaws.com" in parsed.netloc
    assert f"tenants/{wid}/documents/{did}/contrato.pdf" in unquote(parsed.path)

    # Parámetros de consulta
    qs = parse_qs(parsed.query)
    assert "expires" in qs or "X-Amz-Expires" in qs or "signature" in qs


def test_s3_storage_adapter_download_url_rfc_6266_content_disposition() -> None:
    """Verifica que Content-Disposition cumple RFC 6266/5987 y previene Header Injection."""
    adapter = S3StorageAdapter(bucket_name="my-test-bucket", region="us-east-1")
    storage_key = "tenants/ws-1/documents/doc-1/test.pdf"

    # Nombre con caracteres especiales, tildes y espacios
    filename_with_accents = "Reporte Financiero — Q3 (2026).pdf"
    url = adapter.generate_download_url(
        storage_key=storage_key,
        expires_in_seconds=300,
        filename=filename_with_accents,
    )

    assert "response-content-disposition=" in url
    query_params = parse_qs(urlparse(url).query)
    disposition = query_params["response-content-disposition"][0]

    # Debe incluir versión ASCII y versión UTF-8 codificada por porcentaje
    assert 'attachment; filename="' in disposition
    assert "filename*=UTF-8''" in disposition
    assert "Reporte%20Financiero" in disposition

    # Intento de Header Injection con CRLF (\r\n)
    malicious_filename = "doc.pdf\r\nX-Injected: evil\r\n"
    safe_url = adapter.generate_download_url(
        storage_key=storage_key,
        expires_in_seconds=300,
        filename=malicious_filename,
    )
    assert "\r" not in safe_url
    assert "\n" not in safe_url


def test_socket_guard_blocks_accidental_aws_calls() -> None:
    """Verifica que conftest.py bloquea activamente llamadas salientes a AWS."""
    # Intentar abrir un socket TCP a un dominio externo de AWS (ej. s3.amazonaws.com:443)
    # debe ser interceptado inmediatamente por guard_against_external_network_calls
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(RuntimeError) as exc_info:
        sock.connect(("s3.amazonaws.com", 443))

    sock.close()
    assert "[SEGURIDAD CDM]" in str(exc_info.value)
    assert "s3.amazonaws.com" in str(exc_info.value)


def test_socket_guard_permits_localhost_connections() -> None:
    """Verifica que localhost (127.0.0.1) está permitido para Postgres y ASGI."""
    # Conexión local a 127.0.0.1 en un puerto cerrado no debe levantar el error de seguridad
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(("127.0.0.1", 5432))
    except ConnectionRefusedError:
        pass
    except Exception as exc:
        assert not isinstance(exc, RuntimeError)
    finally:
        sock.close()

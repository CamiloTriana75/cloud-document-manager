"""Pruebas unitarias de seguridad y hardening (CDM-51 / AGENTS.md §8, §12, §14).

Verifica:
1. Sanitización de logs contra fuga de credenciales, Bearer tokens y URLs prefirmadas.
2. Control de tasa (Rate Limiting) y mitigación de abuso en emisión de URLs (HTTP 429).
3. Hardening de políticas de archivo contra path traversal, null bytes y suplantación de MIME.
4. Principio de menor privilegio y generación server-side de storage keys.
"""

from __future__ import annotations

import io
import logging
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from cdm.adapters.inbound.http.rate_limit import InMemoryRateLimiter, rate_limit_dependency
from cdm.config.logging import SensitiveDataSanitizingFilter, sanitize_log_message
from cdm.domain.errors import FileTypeNotAllowedError, InvalidFileNameError
from cdm.domain.file_policy import (
    generate_storage_key,
    validate_and_sanitize_filename,
    validate_file_type,
)


class TestLogSanitization:
    """Verifica que el formateador/filtro ofusque credenciales y firmas en logs."""

    def test_sanitize_log_message_bearer_tokens(self) -> None:
        raw = "User logged in with header: Bearer mock.jwt.access.token.1234567890"
        sanitized = sanitize_log_message(raw)
        assert "mock.jwt.access" not in sanitized
        assert "Bearer [REDACTED]" in sanitized

    def test_sanitize_log_message_s3_presigned_url(self) -> None:
        raw = (
            "Issued download URL: "
            "https://test-bucket.s3.us-east-1.amazonaws.com/tenants/123/doc.pdf"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=abcdef1234567890"
        )
        sanitized = sanitize_log_message(raw)
        assert "X-Amz-Signature" not in sanitized
        assert "https://[S3_PRESIGNED_URL_REDACTED]" in sanitized

    def test_sanitize_log_message_passwords_and_secrets(self) -> None:
        raw = "Connecting to DB with password='superSecretPassword123' and secret: 'my-api-key'"
        sanitized = sanitize_log_message(raw)
        assert "superSecretPassword123" not in sanitized
        assert "my-api-key" not in sanitized
        assert "password=[REDACTED]" in sanitized

    def test_sanitizing_filter_in_logger_pipeline(self) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        handler.addFilter(SensitiveDataSanitizingFilter())

        test_logger = logging.getLogger("test_security_logger")
        test_logger.setLevel(logging.INFO)
        test_logger.addHandler(handler)
        test_logger.propagate = False

        test_logger.info("Authorization header received: Bearer secret-auth-token-99999")
        handler.flush()

        log_output = stream.getvalue()
        assert "secret-auth-token-99999" not in log_output
        assert "Bearer [REDACTED]" in log_output


class TestRateLimiter:
    """Verifica el control de tasa y cuotas para emisión de URLs."""

    def test_rate_limiter_allows_under_limit(self) -> None:
        limiter = InMemoryRateLimiter(max_requests=3, window_seconds=60)
        key = "client-1"

        allowed1, _ = limiter.is_allowed(key, now=100.0)
        allowed2, _ = limiter.is_allowed(key, now=101.0)
        allowed3, _ = limiter.is_allowed(key, now=102.0)

        assert allowed1 is True
        assert allowed2 is True
        assert allowed3 is True

    def test_rate_limiter_blocks_exceeded_requests_and_reports_retry_after(self) -> None:
        limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
        key = "client-blocked"

        limiter.is_allowed(key, now=100.0)
        limiter.is_allowed(key, now=110.0)

        allowed, retry_after = limiter.is_allowed(key, now=120.0)
        assert allowed is False
        assert retry_after == 40  # 100 + 60 - 120 = 40

    def test_rate_limiter_window_expiration(self) -> None:
        limiter = InMemoryRateLimiter(max_requests=1, window_seconds=10)
        key = "client-window"

        allowed1, _ = limiter.is_allowed(key, now=10.0)
        assert allowed1 is True

        allowed2, _ = limiter.is_allowed(key, now=15.0)
        assert allowed2 is False

        # Después de que pasa la ventana de 10s
        allowed3, _ = limiter.is_allowed(key, now=21.0)
        assert allowed3 is True

    def test_rate_limit_fastapi_dependency_integration(self) -> None:
        from fastapi import Depends

        test_limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
        app = FastAPI()

        @app.post("/test-url", dependencies=[Depends(rate_limit_dependency(test_limiter))])
        def dummy_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)

        res1 = client.post("/test-url")
        assert res1.status_code == status.HTTP_200_OK

        res2 = client.post("/test-url")
        assert res2.status_code == status.HTTP_200_OK

        # Tercera solicitud bloqueada por rate limit
        res3 = client.post("/test-url")
        assert res3.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Retry-After" in res3.headers
        assert "excedido" in res3.json()["detail"].lower()


class TestFileSecurityHardening:
    """Verifica que los ataques de manipulación de archivos sean repelidos."""

    @pytest.mark.parametrize(
        "malicious_filename",
        [
            "../../etc/passwd",
            "..\\..\\windows\\system32\\cmd.exe",
            "/absolute/root/file.pdf",
            "file\0with_null_byte.png",
            "test/subdir/doc.pdf",
            "test\\subdir\\doc.pdf",
            "   ",
            "",
            "a" * 256 + ".pdf",
        ],
    )
    def test_path_traversal_and_malicious_filenames_are_blocked(
        self, malicious_filename: str
    ) -> None:
        with pytest.raises(InvalidFileNameError):
            validate_and_sanitize_filename(malicious_filename)

    def test_valid_filename_is_sanitized_correctly(self) -> None:
        clean = validate_and_sanitize_filename("  reporte_anual_2026.pdf  ")
        assert clean == "reporte_anual_2026.pdf"

    def test_disallowed_mime_types_rejected(self) -> None:
        with pytest.raises(FileTypeNotAllowedError):
            validate_file_type("script.sh", "application/x-sh")

        with pytest.raises(FileTypeNotAllowedError):
            validate_file_type("binary.exe", "application/x-msdownload")

    def test_mismatched_mime_and_extension_rejected(self) -> None:
        # Intento de suplantar un ejecutable con MIME de PDF
        with pytest.raises(FileTypeNotAllowedError):
            validate_file_type("malware.exe", "application/pdf")

        # Intento de subir un PDF con MIME de imagen
        with pytest.raises(FileTypeNotAllowedError):
            validate_file_type("balance.pdf", "image/png")

    def test_server_generated_storage_key_enforces_tenant_partitioning(self) -> None:
        ws_id = uuid4()
        doc_id = uuid4()
        extension = ".pdf"

        key = generate_storage_key(ws_id, doc_id, extension)

        # Clave debe comenzar obligatoriamente por workspaces/{workspace_id}/documents/{document_id}
        expected_prefix = f"workspaces/{ws_id}/documents/{doc_id}"
        assert key.startswith(expected_prefix)
        assert key.endswith(".pdf")
        # No debe contener partes arbitrarias del cliente
        assert ".." not in key

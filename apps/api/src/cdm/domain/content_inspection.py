"""Dominio: Inspección de contenido y extracción de metadatos técnicos (CDM-38).

Módulo puro de dominio:
1. Detecta tipo MIME real por inspección de cabeceras binarias (Magic Bytes).
2. Detecta discrepancias entre MIME declarado y contenido real (prevención de spoofing).
3. Detecta binarios ejecutables o scripts no permitidos sin ejecutarlos ni renderizarlos.
4. Calcula y verifica checksum SHA-256 e integridad del binario.
5. Invariante de seguridad (AGENTS.md §4, §12): Cero ejecución de código, cero renderizado.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any

from cdm.domain.file_policy import ALLOWED_MIME_TYPES

# Firmas de cabeceras binarias conocidas (Magic Bytes)
_PDF_MAGIC = b"%PDF-"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_ZIP_MAGIC = b"PK\x03\x04"

# Firmas de binarios ejecutables o scripts potencialmente maliciosos
_EXECUTABLE_SIGNATURES: list[tuple[bytes, str]] = [
    (b"MZ", "application/x-dosexec"),  # Windows EXE / DLL
    (b"\x7fELF", "application/x-executable"),  # Linux ELF
    (b"\xfe\xed\xfa\xce", "application/x-mach-binary"),  # macOS Mach-O 32-bit
    (b"\xfe\xed\xfa\xcf", "application/x-mach-binary"),  # macOS Mach-O 64-bit
    (b"\xce\xfa\xed\xfe", "application/x-mach-binary"),  # macOS Mach-O reverse
    (b"\xcf\xfa\xed\xfe", "application/x-mach-binary"),  # macOS Mach-O reverse
    (b"#!", "text/x-shellscript"),  # Shell script (Shebang)
]


@dataclass(frozen=True)
class ContentValidationResult:
    """Resultado estructurado de la inspección de contenido de un archivo."""

    is_valid: bool
    detected_mime: str | None
    declared_mime: str
    normalized_extension: str
    computed_checksum: str
    size_bytes: int
    failure_reason: str | None = None
    extracted_metadata: dict[str, Any] | None = None


def compute_sha256(data: bytes) -> str:
    """Calcula el checksum SHA-256 de una secuencia de bytes en formato hexadecimal."""
    return hashlib.sha256(data).hexdigest()


def detect_mime_type(data: bytes, filename: str | None = None) -> str | None:
    """Detecta el tipo MIME real mediante análisis de cabeceras (magic bytes) y estructura.

    Parámetros:
        data: Fragmento inicial de bytes del archivo (o archivo completo).
        filename: Nombre original del archivo para resolver variantes de formatos empaquetados.

    Retorna:
        Tipo MIME detectado, o None si no corresponde a ningún formato conocido.
    """
    if not data:
        return None

    # 1. Detección defensiva de binarios ejecutables o scripts no permitidos
    for magic, exec_mime in _EXECUTABLE_SIGNATURES:
        if data.startswith(magic):
            return exec_mime

    # 2. Formatos binarios exactos de la allowlist
    if data.startswith(_PDF_MAGIC):
        return "application/pdf"

    if data.startswith(_PNG_MAGIC):
        return "image/png"

    if data.startswith(_JPEG_MAGIC):
        return "image/jpeg"

    # 3. Formatos Microsoft Office OpenXML (ZIP con XML interno)
    if data.startswith(_ZIP_MAGIC):
        ext = PurePath(filename).suffix.lower() if filename else ""
        if ext == ".docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if ext == ".xlsx":
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        # Archivo ZIP genérico no está en la allowlist del MVP
        return "application/zip"

    # 4. Formatos de texto (JSON, CSV, Markdown, Texto plano)
    try:
        # Intentar decodificar como UTF-8
        text_content = data.decode("utf-8")

        # Descartar archivos que contengan bytes nulos (binarios enmascarados como texto)
        if "\x00" in text_content:
            return None

        stripped = text_content.strip()

        # Detección de JSON estructurado
        if (stripped.startswith("{") and stripped.endswith("}")) or (
            stripped.startswith("[") and stripped.endswith("]")
        ):
            try:
                json.loads(text_content)
                return "application/json"
            except (ValueError, json.JSONDecodeError):
                pass

        ext = PurePath(filename).suffix.lower() if filename else ""
        if ext in (".md", ".markdown"):
            return "text/markdown"
        if ext == ".csv":
            return "text/csv"

        return "text/plain"

    except UnicodeDecodeError:
        # Contenido binario que no coincide con ninguna firma conocida
        return None


def validate_content_consistency(
    data: bytes,
    declared_mime: str,
    original_filename: str,
    expected_checksum: str | None = None,
) -> ContentValidationResult:
    """Valida la consistencia técnica entre el binario real y los metadatos declarados.

    Reglas de consistencia (CDM-38):
    1. El archivo no puede estar vacío (size > 0).
    2. El tipo MIME detectado por magic bytes debe coincidir con el MIME declarado.
    3. Si se suministró un checksum esperado, debe coincidir exactamente con el calculado.
    4. El tipo MIME detectado debe pertenecer a la allowlist oficial del MVP.
    """
    size_bytes = len(data)
    computed_checksum = compute_sha256(data)
    extension = PurePath(original_filename).suffix.lower()
    clean_declared_mime = declared_mime.strip().lower()

    # 1. Validación de archivo no vacío
    if size_bytes == 0:
        return ContentValidationResult(
            is_valid=False,
            detected_mime=None,
            declared_mime=clean_declared_mime,
            normalized_extension=extension,
            computed_checksum=computed_checksum,
            size_bytes=0,
            failure_reason="El archivo está vacío (0 bytes).",
        )

    # 2. Detección de MIME real
    detected_mime = detect_mime_type(data, filename=original_filename)

    # 3. Detección de binarios ejecutables o no permitidos
    if detected_mime in (
        "application/x-dosexec",
        "application/x-executable",
        "application/x-mach-binary",
        "text/x-shellscript",
    ):
        return ContentValidationResult(
            is_valid=False,
            detected_mime=detected_mime,
            declared_mime=clean_declared_mime,
            normalized_extension=extension,
            computed_checksum=computed_checksum,
            size_bytes=size_bytes,
            failure_reason="Contenido ejecutable o script no permitido detectado en el archivo.",
        )

    if detected_mime is None:
        return ContentValidationResult(
            is_valid=False,
            detected_mime=None,
            declared_mime=clean_declared_mime,
            normalized_extension=extension,
            computed_checksum=computed_checksum,
            size_bytes=size_bytes,
            failure_reason="Formato de archivo corrupto o no reconocido por sus firmas binarias.",
        )

    # 4. Verificación de pertenencia a la allowlist
    if detected_mime not in ALLOWED_MIME_TYPES:
        return ContentValidationResult(
            is_valid=False,
            detected_mime=detected_mime,
            declared_mime=clean_declared_mime,
            normalized_extension=extension,
            computed_checksum=computed_checksum,
            size_bytes=size_bytes,
            failure_reason=f"Tipo de archivo '{detected_mime}' no admitido en la plataforma.",
        )

    # 5. Detección de discrepancias entre tipo declarado y contenido real
    # Nota: text/plain, text/markdown y text/csv comparten codificación de texto
    text_types = {"text/plain", "text/markdown", "text/csv"}
    is_text_compatible = clean_declared_mime in text_types and detected_mime in text_types

    if detected_mime != clean_declared_mime and not is_text_compatible:
        return ContentValidationResult(
            is_valid=False,
            detected_mime=detected_mime,
            declared_mime=clean_declared_mime,
            normalized_extension=extension,
            computed_checksum=computed_checksum,
            size_bytes=size_bytes,
            failure_reason=(
                f"Discrepancia de tipo de archivo: declarado '{clean_declared_mime}', "
                f"pero el contenido real corresponde a '{detected_mime}'."
            ),
        )

    # 6. Verificación de checksum SHA-256 si se esperaba uno específico
    if expected_checksum:
        clean_expected = expected_checksum.strip().lower()
        if clean_expected != computed_checksum.lower():
            return ContentValidationResult(
                is_valid=False,
                detected_mime=detected_mime,
                declared_mime=clean_declared_mime,
                normalized_extension=extension,
                computed_checksum=computed_checksum,
                size_bytes=size_bytes,
                failure_reason="El checksum SHA-256 no coincide con el valor esperado.",
            )

    # Metadatos técnicos enriquecidos extraídos
    extracted_metadata: dict[str, Any] = {
        "mime_detected": detected_mime,
        "mime_declared": clean_declared_mime,
        "normalized_extension": extension,
        "checksum_sha256": computed_checksum,
        "validation_status": "VALID",
    }

    return ContentValidationResult(
        is_valid=True,
        detected_mime=detected_mime,
        declared_mime=clean_declared_mime,
        normalized_extension=extension,
        computed_checksum=computed_checksum,
        size_bytes=size_bytes,
        failure_reason=None,
        extracted_metadata=extracted_metadata,
    )

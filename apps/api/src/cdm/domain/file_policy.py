"""Políticas de validación de archivos para CDM (CDM-30 / AGENTS.md §10, §12).

Módulo puro de dominio: sin dependencias de frameworks ni de AWS.
Define la allowlist de tipos MIME, extensiones permitidas, saneamiento de nombres,
prevención estricta de path traversal y generación de claves S3 bajo el tenant.
"""

from __future__ import annotations

import re
from pathlib import PurePath
from uuid import UUID, uuid4

from cdm.domain.errors import (
    FileSizeExceededError,
    FileTypeNotAllowedError,
    InvalidChecksumError,
    InvalidDocumentDataError,
    InvalidFileNameError,
)

#: Allowlist oficial del MVP para tipos MIME y sus extensiones asociadas válidas.
ALLOWED_MIME_TYPES: dict[str, set[str]] = {
    "application/pdf": {".pdf"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "text/plain": {".txt"},
    "text/markdown": {".md", ".markdown"},
    "text/csv": {".csv"},
    "application/json": {".json"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
}

_MAX_FILENAME_LENGTH = 255
_SHA256_HEX_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


def validate_and_sanitize_filename(original_filename: str) -> str:
    """Valida y sanea el nombre original del archivo.

    Rechaza intentos de path traversal, rutas absolutas, separadores de directorio,
    caracteres nulos o de control, y nombres vacíos.

    Retorna:
        Nombre de archivo saneado y sin espacios residuales.

    Lanza:
        InvalidFileNameError: Si el nombre contiene caracteres peligrosos o es inválido.
    """
    if not original_filename:
        raise InvalidFileNameError("El nombre original del archivo no puede estar vacío.")

    clean_name = original_filename.strip()
    if not clean_name:
        raise InvalidFileNameError(
            "El nombre original del archivo no puede contener solo espacios."
        )

    if len(clean_name) > _MAX_FILENAME_LENGTH:
        raise InvalidFileNameError(
            f"El nombre del archivo supera el límite de {_MAX_FILENAME_LENGTH} caracteres."
        )

    # Detección de caracteres nulos
    if "\0" in clean_name:
        raise InvalidFileNameError("El nombre de archivo contiene caracteres nulos prohibidos.")

    # Detección de caracteres de control
    if any(ord(char) < 32 or ord(char) == 127 for char in clean_name):
        raise InvalidFileNameError(
            "El nombre de archivo contiene caracteres de control no permitidos."
        )

    # Detección estricta de path traversal y separadores de ruta
    if ".." in clean_name or "/" in clean_name or "\\" in clean_name:
        raise InvalidFileNameError(
            "El nombre contiene secuencias o separadores prohibidos (path traversal)."
        )

    # Verificación de que el nombre coincide con su base pura (evita 'C:archivo.txt' en Windows)
    pure = PurePath(clean_name)
    if pure.name != clean_name:
        raise InvalidFileNameError("El nombre del archivo no es un nombre de archivo base válido.")

    return clean_name


def validate_file_type(filename: str, declared_content_type: str) -> tuple[str, str]:
    """Valida que el tipo MIME declarado esté en la allowlist y coincida con la extensión.

    No confía ciegamente en el Content-Type declarado por el navegador ni en la extensión aislada.

    Retorna:
        Tupla (content_type_normalizado, extension_normalizada).

    Lanza:
        FileTypeNotAllowedError: Si el MIME no está admitido o no coincide con la extensión.
    """
    clean_mime = declared_content_type.strip().lower()
    if not clean_mime:
        raise FileTypeNotAllowedError("El tipo de contenido (MIME) no puede estar vacío.")

    if clean_mime not in ALLOWED_MIME_TYPES:
        allowed_list = sorted(ALLOWED_MIME_TYPES.keys())
        raise FileTypeNotAllowedError(
            f"El tipo MIME '{clean_mime}' no está permitido. Tipos admitidos: {allowed_list}."
        )

    allowed_extensions = ALLOWED_MIME_TYPES[clean_mime]
    extension = PurePath(filename).suffix.lower()

    if not extension:
        raise FileTypeNotAllowedError(
            f"El archivo debe poseer una extensión válida para '{clean_mime}'."
        )

    if extension not in allowed_extensions:
        raise FileTypeNotAllowedError(
            f"La extensión '{extension}' no corresponde al tipo MIME declarado '{clean_mime}'. "
            f"Extensiones válidas para este tipo: {sorted(allowed_extensions)}."
        )

    return clean_mime, extension


def validate_file_size(size_bytes: int, max_size_bytes: int) -> int:
    """Valida los límites de tamaño para el archivo a cargar.

    Retorna:
        El tamaño verificado en bytes.

    Lanza:
        InvalidDocumentDataError: Si el tamaño es menor o igual a 0.
        FileSizeExceededError: Si supera el tamaño máximo configurado.
    """
    if size_bytes <= 0:
        raise InvalidDocumentDataError(
            "El tamaño del archivo debe ser mayor a 0 bytes (mínimo 1 byte)."
        )

    if size_bytes > max_size_bytes:
        raise FileSizeExceededError(
            f"El tamaño del archivo ({size_bytes} bytes) supera el límite máximo permitido "
            f"de {max_size_bytes} bytes ({max_size_bytes // (1024 * 1024)} MB)."
        )

    return size_bytes


def validate_checksum(checksum_sha256: str | None) -> str | None:
    """Valida el formato del checksum SHA-256 si es provisto.

    Retorna:
        Checksum normalizado en minúsculas, o None si no se suministró.

    Lanza:
        InvalidChecksumError: Si el formato hexadecimal no es válido.
    """
    if checksum_sha256 is None:
        return None

    clean = checksum_sha256.strip()
    if not clean:
        return None

    if not _SHA256_HEX_PATTERN.fullmatch(clean):
        raise InvalidChecksumError(
            "El checksum SHA-256 debe contener exactamente 64 caracteres hexadecimales (0-9, a-f)."
        )

    return clean.lower()


def generate_storage_key(workspace_id: UUID, document_id: UUID, extension: str) -> str:
    """Genera una clave S3 opaca, única e inmutable bajo el prefijo del tenant.

    Formato:
        workspaces/{workspace_id}/documents/{document_id}/{opaque_token}{extension}

    Garantiza aislamiento estricto por tenant en S3 y previene sobrescrituras accidentales.
    """
    opaque_token = uuid4().hex
    clean_ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    return f"workspaces/{workspace_id}/documents/{document_id}/{opaque_token}{clean_ext}"

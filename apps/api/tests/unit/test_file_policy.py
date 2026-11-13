"""Pruebas unitarias de las políticas de validación de archivos (CDM-30 / AGENTS.md §10, §12).

Prueba exhaustivamente:
- Allowlist de tipos MIME y correspondencia con extensiones.
- Prevención de path traversal y caracteres peligrosos.
- Límites de tamaño mínimo y máximo configurable.
- Validación de checksum SHA-256.
- Generación de claves S3 opacas y aisladas por tenant.
"""

from uuid import uuid4

import pytest

from cdm.domain.errors import (
    FileSizeExceededError,
    FileTypeNotAllowedError,
    InvalidChecksumError,
    InvalidDocumentDataError,
    InvalidFileNameError,
)
from cdm.domain.file_policy import (
    generate_storage_key,
    validate_and_sanitize_filename,
    validate_checksum,
    validate_file_size,
    validate_file_type,
)


class TestFilenameValidation:
    """Pruebas de validación y saneamiento de nombres de archivo."""

    def test_valid_filenames_pass(self) -> None:
        assert validate_and_sanitize_filename("reporte_2026.pdf") == "reporte_2026.pdf"
        assert validate_and_sanitize_filename("  mi archivo (1).png  ") == "mi archivo (1).png"
        assert validate_and_sanitize_filename("datos-ventas.xlsx") == "datos-ventas.xlsx"

    def test_empty_or_whitespace_filename_raises(self) -> None:
        with pytest.raises(InvalidFileNameError, match="no puede estar vacío"):
            validate_and_sanitize_filename("")

        with pytest.raises(InvalidFileNameError, match="solo espacios"):
            validate_and_sanitize_filename("   \t  ")

    def test_path_traversal_relative_dots_raises(self) -> None:
        with pytest.raises(InvalidFileNameError, match="path traversal"):
            validate_and_sanitize_filename("../etc/passwd")

        with pytest.raises(InvalidFileNameError, match="path traversal"):
            validate_and_sanitize_filename("..\\boot.ini")

        with pytest.raises(InvalidFileNameError, match="path traversal"):
            validate_and_sanitize_filename("docs/../../secret.pdf")

    def test_path_separators_raises(self) -> None:
        with pytest.raises(InvalidFileNameError, match="path traversal"):
            validate_and_sanitize_filename("carpeta/archivo.pdf")

        with pytest.raises(InvalidFileNameError, match="path traversal"):
            validate_and_sanitize_filename("C:\\archivos\\archivo.pdf")

    def test_null_bytes_and_control_chars_raises(self) -> None:
        with pytest.raises(InvalidFileNameError, match="caracteres nulos"):
            validate_and_sanitize_filename("archivo\0malicioso.pdf")

        with pytest.raises(InvalidFileNameError, match="caracteres de control"):
            validate_and_sanitize_filename("archivo\x01\x1f.pdf")

    def test_filename_exceeding_max_length_raises(self) -> None:
        long_name = "a" * 252 + ".pdf"
        with pytest.raises(InvalidFileNameError, match="supera el límite"):
            validate_and_sanitize_filename(long_name)


class TestFileTypeValidation:
    """Pruebas de allowlist MIME y correspondencia con extensión."""

    @pytest.mark.parametrize(
        ("filename", "content_type", "expected_mime", "expected_ext"),
        [
            ("documento.pdf", "application/pdf", "application/pdf", ".pdf"),
            ("foto.PNG", "image/png", "image/png", ".png"),
            ("imagen.jpg", "image/jpeg", "image/jpeg", ".jpg"),
            ("imagen.jpeg", "IMAGE/JPEG", "image/jpeg", ".jpeg"),
            ("notas.txt", "text/plain", "text/plain", ".txt"),
            ("readme.md", "text/markdown", "text/markdown", ".md"),
            ("tabla.csv", "text/csv", "text/csv", ".csv"),
            ("config.json", "application/json", "application/json", ".json"),
            (
                "hoja.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".xlsx",
            ),
            (
                "informe.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".docx",
            ),
        ],
    )
    def test_allowed_types_pass(
        self, filename: str, content_type: str, expected_mime: str, expected_ext: str
    ) -> None:
        mime, ext = validate_file_type(filename, content_type)
        assert mime == expected_mime
        assert ext == expected_ext

    def test_disallowed_mime_raises(self) -> None:
        with pytest.raises(FileTypeNotAllowedError, match="no está permitido"):
            validate_file_type("script.sh", "application/x-sh")

        with pytest.raises(FileTypeNotAllowedError, match="no está permitido"):
            validate_file_type("app.exe", "application/x-msdownload")

        with pytest.raises(FileTypeNotAllowedError, match="no está permitido"):
            validate_file_type("archivo.bin", "application/octet-stream")

    def test_mime_extension_mismatch_raises(self) -> None:
        # Intento de spoofing: dice ser PDF pero el archivo es .exe
        with pytest.raises(FileTypeNotAllowedError, match="no corresponde"):
            validate_file_type("malicioso.exe", "application/pdf")

        # Dice ser PNG pero la extensión es .jpg
        with pytest.raises(FileTypeNotAllowedError, match="no corresponde"):
            validate_file_type("foto.jpg", "image/png")

    def test_missing_extension_raises(self) -> None:
        with pytest.raises(FileTypeNotAllowedError, match="extensión válida"):
            validate_file_type("sin_extension", "application/pdf")

    def test_empty_content_type_raises(self) -> None:
        with pytest.raises(FileTypeNotAllowedError, match="no puede estar vacío"):
            validate_file_type("doc.pdf", "")


class TestFileSizeValidation:
    """Pruebas de límites de tamaño."""

    def test_valid_size_passes(self) -> None:
        assert validate_file_size(1024, max_size_bytes=50 * 1024 * 1024) == 1024
        assert validate_file_size(1, max_size_bytes=100) == 1

    def test_zero_or_negative_size_raises(self) -> None:
        with pytest.raises(InvalidDocumentDataError, match="mayor a 0 bytes"):
            validate_file_size(0, max_size_bytes=1000)

        with pytest.raises(InvalidDocumentDataError, match="mayor a 0 bytes"):
            validate_file_size(-50, max_size_bytes=1000)

    def test_exceeding_max_size_raises(self) -> None:
        with pytest.raises(FileSizeExceededError, match="supera el límite"):
            validate_file_size(1001, max_size_bytes=1000)


class TestChecksumValidation:
    """Pruebas de formato de checksum SHA-256."""

    def test_none_or_empty_returns_none(self) -> None:
        assert validate_checksum(None) is None
        assert validate_checksum("") is None
        assert validate_checksum("   ") is None

    def test_valid_sha256_passes_and_lowercased(self) -> None:
        sha256 = "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855"
        assert validate_checksum(sha256) == sha256.lower()

    def test_invalid_length_raises(self) -> None:
        with pytest.raises(InvalidChecksumError, match="exactamente 64"):
            validate_checksum("abc123")

    def test_invalid_characters_raises(self) -> None:
        invalid_hex = "g" * 64
        with pytest.raises(InvalidChecksumError, match="caracteres hexadecimales"):
            validate_checksum(invalid_hex)


class TestStorageKeyGeneration:
    """Pruebas de generación segura de claves S3."""

    def test_storage_key_format_and_isolation(self) -> None:
        ws_id = uuid4()
        doc_id = uuid4()
        key = generate_storage_key(ws_id, doc_id, ".pdf")

        assert key.startswith(f"workspaces/{ws_id}/documents/{doc_id}/")
        assert key.endswith(".pdf")
        # El token opaco intermedio debe ser único
        key2 = generate_storage_key(ws_id, doc_id, ".pdf")
        assert key != key2

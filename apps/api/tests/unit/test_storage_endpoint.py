"""El adaptador S3 de la API respeta el endpoint de un emulador local (CDM-133).

La firma de URLs prefirmadas es un cálculo local de boto3: no hay llamadas de red.
"""

from cdm.adapters.inbound.http.dependencies import get_storage_port
from cdm.adapters.outbound.storage.s3_storage import S3StorageAdapter
from cdm.config.settings import Settings

EMULATOR = "http://localhost:9000"


def test_api_storage_port_uses_configured_s3_endpoint() -> None:
    settings = Settings(s3_bucket_name="cdm-documents-dev", s3_endpoint_url=EMULATOR)

    url = get_storage_port(settings).generate_upload_url(
        storage_key="workspaces/w/documents/d/a.txt", content_type="text/plain", size_bytes=10
    )

    assert url.startswith(f"{EMULATOR}/cdm-documents-dev/workspaces/w/documents/d/a.txt?")


def test_emulator_endpoint_uses_path_style_urls() -> None:
    """Con endpoint propio (moto, MinIO) el bucket va en la ruta: bucket.localhost no resuelve."""
    adapter = S3StorageAdapter(bucket_name="cdm-documents-dev", endpoint_url=EMULATOR)

    url = adapter.generate_download_url(storage_key="workspaces/w/documents/d/a.txt")

    assert url.startswith(f"{EMULATOR}/cdm-documents-dev/workspaces/w/documents/d/a.txt?")


def test_aws_urls_keep_virtual_hosted_style() -> None:
    adapter = S3StorageAdapter(bucket_name="cdm-dev-docs-123", region="us-east-1")

    url = adapter.generate_upload_url(
        storage_key="workspaces/w/documents/d/a.txt", content_type="text/plain", size_bytes=10
    )

    assert url.startswith("https://cdm-dev-docs-123.s3.us-east-1.amazonaws.com/workspaces/")

"""Crea el bucket de desarrollo en el emulador S3 local (compose.yaml).

Uso (con el emulador arriba): uv run --project apps/api python scripts/init_local_s3.py
Solo para desarrollo local; nunca apunta a AWS real.
"""

import os

import boto3
from botocore.exceptions import ClientError

ENDPOINT = os.environ.get("CDM_S3_ENDPOINT_URL", "http://localhost:9000")
BUCKET = os.environ.get("CDM_S3_BUCKET_NAME", "cdm-documents-dev")

s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)
try:
    s3.create_bucket(Bucket=BUCKET)
    print(f"Bucket creado: {BUCKET}")
except ClientError as exc:
    if exc.response["Error"]["Code"] not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
        raise
    print(f"Bucket ya existe: {BUCKET}")

# Módulo S3 Document Store — CDM (CDM-19 / CDM-73 / CDM-74)
#
# Almacenamiento seguro, privado y particionado por tenant para documentos y
# cargas directas desde Angular mediante URLs prefirmadas (AGENTS.md §12).
# Cifrado SSE-S3 gratis para respetar el AWS Free Plan (auditoría CDM-17).

data "aws_caller_identity" "current" {}

locals {
  # Nombre único global combinando prefijo y account_id si no se provee bucket_name explícito.
  bucket_name = coalesce(var.bucket_name, lower("${var.bucket_prefix}-${data.aws_caller_identity.current.account_id}"))
}

# 1. Bucket S3 privado
resource "aws_s3_bucket" "this" {
  bucket        = local.bucket_name
  force_destroy = var.force_destroy

  tags = var.tags
}

# 2. Block Public Access (Criterio 1: 100% de acceso público bloqueado)
resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 3. Ownership Controls: BucketOwnerEnforced deshabilita ACLs y asegura titularidad total
resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# 4. Versionado (controlable por variable; suspendido por defecto en dev para evitar costes de storage)
resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = var.versioning_enabled ? "Enabled" : "Suspended"
  }
}

# 5. Cifrado en reposo por defecto: SSE-S3 (AES256) con Bucket Key
# SSE-S3 no tiene coste adicional ni cobra por request de KMS, salvaguardando los créditos Free Plan.
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# 6. Configuración CORS para subida directa desde el navegador (Angular SPA)
resource "aws_s3_bucket_cors_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  cors_rule {
    id              = "allow-angular-direct-upload"
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "GET", "HEAD"]
    allowed_origins = var.allowed_cors_origins
    expose_headers  = ["ETag", "x-amz-server-side-encryption", "x-amz-request-id", "x-amz-id-2"]
    max_age_seconds = 3600
  }
}

# 7. Ciclo de vida (Lifecycle): limpieza de uploads incompletos y expiración de archivos temporales
resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  # Regla 1: Limpieza de subidas multipart incompletas/abandonadas
  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_multipart_upload_days
    }
  }

  # Regla 2: Expiración de subidas provisionales no confirmadas bajo prefijo temp/
  rule {
    id     = "expire-unconfirmed-temp-uploads"
    status = "Enabled"

    filter {
      prefix = "temp/"
    }

    expiration {
      days = var.temp_prefix_expiration_days
    }
  }

  # Regla 3: Si el versionado está activo, limpiar versiones no actuales obsoletas
  dynamic "rule" {
    for_each = var.versioning_enabled ? [1] : []
    content {
      id     = "cleanup-noncurrent-versions"
      status = "Enabled"

      filter {}

      noncurrent_version_expiration {
        noncurrent_days = var.noncurrent_version_expiration_days
      }
    }
  }
}

# 8. Política de Bucket: Denegar cualquier conexión sin TLS (HTTPS obligatorio)
resource "aws_s3_bucket_policy" "this" {
  bucket = aws_s3_bucket.this.id
  policy = data.aws_iam_policy_document.bucket_policy.json

  depends_on = [aws_s3_bucket_public_access_block.this]
}

data "aws_iam_policy_document" "bucket_policy" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.this.arn,
      "${aws_s3_bucket.this.arn}/*"
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

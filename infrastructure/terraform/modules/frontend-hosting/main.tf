# Módulo Frontend Hosting en S3 + CloudFront (CDM-23 / CDM-79 / CDM-80)
#
# Principios aplicados:
# - Bucket S3 100% privado (Block Public Access al 100% y cifrado SSE-S3 AES256).
# - Acceso exclusivo a través de CloudFront Origin Access Control (OAC).
# - Fallback de SPA (errores 403 y 404 redirigen a /index.html con HTTP 200).
# - Caché optimizada mediante políticas administradas de AWS.
# - Coste cubierto dentro del AWS Always Free Tier (1 TB/mes y 10M peticiones).

# Políticas administradas de CloudFront
data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_response_headers_policy" "security_headers" {
  name = "Managed-SecurityHeadersPolicy"
}

# 1. Bucket S3 para archivos estáticos del frontend (Angular)
resource "aws_s3_bucket" "frontend" {
  bucket_prefix = "${var.project_name}-${var.environment}-web-"
  force_destroy = var.force_destroy

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-web"
      Description = "Hosting estático de la SPA Angular de CDM"
    }
  )
}

# 2. Bloqueo total de acceso público en el bucket
resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 3. Cifrado en reposo SSE-S3 por defecto
resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 4. Origin Access Control (OAC) moderno para CloudFront -> S3
resource "aws_cloudfront_origin_access_control" "oac" {
  name                              = "${var.project_name}-${var.environment}-frontend-oac"
  description                       = "OAC para acceso seguro de CloudFront al bucket frontend de ${var.project_name}"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# 5. Política de bucket que permite lectura únicamente a CloudFront vía OAC
data "aws_iam_policy_document" "frontend_bucket_policy" {
  statement {
    sid       = "AllowCloudFrontServicePrincipalReadOnly"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.frontend.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = data.aws_iam_policy_document.frontend_bucket_policy.json
}

# 6. Distribución de CloudFront con soporte para SPA Routing
resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Distribucion CDN para Angular SPA - ${var.project_name} (${var.environment})"
  default_root_object = "index.html"
  price_class         = var.price_class

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "S3-${aws_s3_bucket.frontend.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id
  }

  default_cache_behavior {
    target_origin_id           = "S3-${aws_s3_bucket.frontend.id}"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security_headers.id
  }

  # Enrutamiento de SPA: cualquier ruta de Angular (403 o 404 de S3) se sirve con /index.html y HTTP 200
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-cdn"
    }
  )
}

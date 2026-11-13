# Outputs del módulo frontend-hosting (CDM-23 / CDM-80)

output "bucket_name" {
  description = "Nombre del bucket S3 para el hosting estático de Angular."
  value       = aws_s3_bucket.frontend.id
}

output "bucket_arn" {
  description = "ARN del bucket S3 del frontend."
  value       = aws_s3_bucket.frontend.arn
}

output "cloudfront_distribution_id" {
  description = "ID de la distribución de CloudFront (necesario para invalidar caché tras un deploy)."
  value       = var.enable_cloudfront ? aws_cloudfront_distribution.frontend[0].id : null
}

output "cloudfront_domain_name" {
  description = "Nombre de dominio asignado por CloudFront (p. ej. d123456abcdef8.cloudfront.net)."
  value       = var.enable_cloudfront ? aws_cloudfront_distribution.frontend[0].domain_name : null
}

output "cloudfront_url" {
  description = "URL HTTPS pública de la aplicación Angular."
  value       = var.enable_cloudfront ? "https://${aws_cloudfront_distribution.frontend[0].domain_name}" : null
}

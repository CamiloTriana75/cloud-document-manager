# Outputs del módulo s3-document-store (CDM-19)

output "bucket_id" {
  description = "ID del bucket S3."
  value       = aws_s3_bucket.this.id
}

output "bucket_name" {
  description = "Nombre final asignado al bucket S3."
  value       = aws_s3_bucket.this.bucket
}

output "bucket_arn" {
  description = "ARN del bucket S3 para políticas IAM y eventos SQS."
  value       = aws_s3_bucket.this.arn
}

output "bucket_domain_name" {
  description = "Nombre de dominio estándar de S3."
  value       = aws_s3_bucket.this.bucket_domain_name
}

output "bucket_regional_domain_name" {
  description = "Nombre de dominio regional de S3 (útil para URLs prefirmadas directas)."
  value       = aws_s3_bucket.this.bucket_regional_domain_name
}

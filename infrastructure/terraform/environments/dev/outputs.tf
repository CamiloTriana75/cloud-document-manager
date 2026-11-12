# Outputs del stack dev (CDM-18 / CDM-19 / CDM-20)

output "documents_bucket_name" {
  description = "Nombre del bucket S3 de almacenamiento de documentos."
  value       = module.s3_document_store.bucket_name
}

output "documents_bucket_arn" {
  description = "ARN del bucket S3 de almacenamiento de documentos."
  value       = module.s3_document_store.bucket_arn
}

output "documents_bucket_domain_name" {
  description = "Dominio regional del bucket S3."
  value       = module.s3_document_store.bucket_regional_domain_name
}

output "api_gateway_endpoint" {
  description = "URL base pública HTTPS del API Gateway."
  value       = module.apigw_http.api_endpoint
}

output "lambda_api_function_name" {
  description = "Nombre de la función Lambda de la API."
  value       = module.lambda_api.function_name
}

output "lambda_api_function_arn" {
  description = "ARN de la función Lambda de la API."
  value       = module.lambda_api.function_arn
}

output "rds_endpoint" {
  description = "Endpoint de conexión de RDS PostgreSQL (null si enable_rds = false)."
  value       = module.rds_postgres.db_endpoint
}

output "rds_secret_arn" {
  description = "ARN del secreto de credenciales de RDS (null si enable_rds = false)."
  value       = module.rds_postgres.secret_arn
}

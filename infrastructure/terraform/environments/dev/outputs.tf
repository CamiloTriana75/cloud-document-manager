# Outputs del stack dev (CDM-18 / CDM-19)

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

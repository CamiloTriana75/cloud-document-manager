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

output "frontend_bucket_name" {
  description = "Nombre del bucket S3 de hosting de la SPA Angular."
  value       = module.frontend_hosting.bucket_name
}

output "cloudfront_distribution_id" {
  description = "ID de la distribución CloudFront del frontend."
  value       = module.frontend_hosting.cloudfront_distribution_id
}

output "cloudfront_domain_name" {
  description = "Dominio público CloudFront de la aplicación Angular."
  value       = module.frontend_hosting.cloudfront_domain_name
}

output "frontend_url" {
  description = "URL HTTPS pública de la SPA Angular."
  value       = module.frontend_hosting.cloudfront_url
}

output "cognito_user_pool_id" {
  description = "ID del User Pool de Cognito para autenticación."
  value       = module.cognito.user_pool_id
}

output "cognito_user_pool_arn" {
  description = "ARN del User Pool de Cognito."
  value       = module.cognito.user_pool_arn
}

output "cognito_client_id" {
  description = "ID del App Client público de Cognito para la SPA Angular."
  value       = module.cognito.client_id
}

output "cognito_issuer_url" {
  description = "URL del emisor JWT de Cognito (iss)."
  value       = module.cognito.issuer_url
}

output "document_events_queue_arn" {
  description = "ARN de la cola SQS principal de eventos de documentos."
  value       = module.sqs_worker_queue.queue_arn
}

output "document_events_queue_url" {
  description = "URL de la cola SQS principal de eventos de documentos."
  value       = module.sqs_worker_queue.queue_url
}

output "document_events_dlq_arn" {
  description = "ARN de la Dead Letter Queue (DLQ) para eventos fallidos."
  value       = module.sqs_worker_queue.dlq_arn
}

output "document_events_dlq_url" {
  description = "URL de la Dead Letter Queue (DLQ) para eventos fallidos."
  value       = module.sqs_worker_queue.dlq_url
}

output "document_events_dlq_alarm_arn" {
  description = "ARN de la alarma CloudWatch para mensajes acumulados en la DLQ (CDM-39)."
  value       = module.sqs_worker_queue.dlq_alarm_arn
}

output "lambda_worker_function_name" {
  description = "Nombre de la función Lambda worker para eventos asíncronos."
  value       = module.lambda_worker.function_name
}

output "lambda_worker_function_arn" {
  description = "ARN de la función Lambda worker para eventos asíncronos."
  value       = module.lambda_worker.function_arn
}

output "cloudwatch_alerts_topic_arn" {
  description = "ARN del tópico SNS receptor de alarmas CloudWatch (CDM-52)."
  value       = module.observability.sns_alerts_topic_arn
}

output "cloudwatch_api_errors_alarm_arn" {
  description = "ARN de la alarma CloudWatch para errores de Lambda API."
  value       = module.observability.api_errors_alarm_arn
}

output "cloudwatch_worker_errors_alarm_arn" {
  description = "ARN de la alarma CloudWatch para errores de Lambda Worker."
  value       = module.observability.worker_errors_alarm_arn
}

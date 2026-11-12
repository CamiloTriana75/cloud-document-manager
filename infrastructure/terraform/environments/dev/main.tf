# Stack dev — CDM (CDM-18 / CDM-19)
#
# Módulos instanciados:
#   - s3_document_store : bucket privado de documentos (CDM-19)
#
# Módulos pendientes para siguientes tareas:
#   - sqs_worker_queue  : cola de eventos S3 + DLQ (CDM-35)
#   - lambda_api        : FastAPI vía Mangum (CDM-20)
#   - lambda_worker     : procesador asíncrono (CDM-36)
#   - cognito_pool      : User Pool + App Client (CDM-24)
#   - apigw_http        : HTTP API entrante (CDM-20)
#
# Regla: aplicar solo con revisión del plan y aprobación explícita del propietario.

module "s3_document_store" {
  source = "../../modules/s3-document-store"

  bucket_prefix        = "${var.project_name}-${var.environment}-docs"
  allowed_cors_origins = var.allowed_cors_origins
  force_destroy        = true  # Permite teardown limpio en entorno dev (AGENTS.md §13)
  versioning_enabled   = false # Mantiene consumo bajo en Free Plan (auditoría CDM-17)

  tags = local.tags
}

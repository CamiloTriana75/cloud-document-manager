# Stack dev — CDM (CDM-18 / CDM-19 / CDM-20)
#
# Módulos instanciados:
#   - s3_document_store : bucket privado de documentos (CDM-19)
#   - lambda_api        : FastAPI vía Mangum (CDM-20)
#   - apigw_http        : HTTP API entrante (CDM-20)
#
# Módulos pendientes para siguientes tareas:
#   - sqs_worker_queue  : cola de eventos S3 + DLQ (CDM-35)
#   - lambda_worker     : procesador asíncrono (CDM-36)
#   - cognito_pool      : User Pool + App Client (CDM-24)
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

module "lambda_api" {
  source = "../../modules/lambda-api"

  function_name      = "${var.project_name}-${var.environment}-api"
  runtime            = "python3.12"
  handler            = "cdm.bootstrap.lambda_handler.handler"
  memory_size        = var.lambda_memory_mb
  timeout            = 15
  log_retention_days = var.log_retention_days

  environment_variables = {
    ENVIRONMENT           = var.environment
    ALLOWED_CORS_ORIGINS  = join(",", var.allowed_cors_origins)
    DOCUMENTS_BUCKET_NAME = module.s3_document_store.bucket_name
  }

  tags = local.tags
}

module "apigw_http" {
  source = "../../modules/apigw-http"

  api_name             = "${var.project_name}-${var.environment}-http-api"
  lambda_invoke_arn    = module.lambda_api.invoke_arn
  lambda_function_name = module.lambda_api.function_name
  allowed_cors_origins = var.allowed_cors_origins

  tags = local.tags
}

module "rds_postgres" {
  source = "../../modules/rds-postgres"

  enable_rds   = var.enable_rds
  environment  = var.environment
  project_name = var.project_name

  tags = local.tags
}

module "frontend_hosting" {
  source = "../../modules/frontend-hosting"

  project_name  = var.project_name
  environment   = var.environment
  force_destroy = true

  tags = local.tags
}

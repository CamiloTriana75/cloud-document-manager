# Stack dev — CDM (CDM-18: esqueleto; los módulos se instancian en CDM-19..23).
#
# Módulos previstos (se crean cuando exista el recurso que los necesite):
#   - s3-document-store : bucket privado de documentos
#   - sqs-worker-queue  : cola de eventos S3 + DLQ
#   - lambda-api        : FastAPI vía Mangum
#   - lambda-worker     : procesador asíncrono
#   - cognito-pool      : User Pool + App Client
#   - apigw-http        : HTTP API entrante
#
# Reglas: este archivo instancia módulos con name/tags/límites desde variables;
# no contiene recursos directos. Aplicar solo con aprobación del propietario.

# En CDM-19+ se añaden aquí las llamadas a `module "..."` con:
#   source        = "../../modules/<modulo>"
#   name          = "${var.project_name}-${var.environment}"
#   tags          = local.tags
#   y el resto de parámetros desde las variables de este entorno.

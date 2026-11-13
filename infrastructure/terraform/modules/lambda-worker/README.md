# Módulo Lambda Worker — CDM

> Jira: **CDM-36** · Fecha: 2026-11-12
> Regla rectora: [`AGENTS.md`](../../../AGENTS.md) §6, §12, §13.

Módulo de Terraform para aprovisionar la función AWS Lambda consumidora de eventos SQS para el procesamiento asíncrono e idempotente de documentos en Cloud Document Manager (CDM).

---

## 1. Responsabilidad y Recursos Creados

1. **`aws_lambda_function.worker`:**
   - Ejecuta el handler Python 3.12 (`cdm.bootstrap.worker_handler.handler`).
   - Configuración de memoria (256 MB) y timeout (30 segundos), adecuado para el perfil de cómputo del worker.
   - En caso de no proveer un paquete `.zip` externo (`package_path = null`), genera y despliega un artefacto por defecto (`default_payload.zip`).

2. **`aws_lambda_event_source_mapping.sqs_trigger`:**
   - Vincula la cola SQS de eventos con la función Lambda.
   - **`function_response_types = ["ReportBatchItemFailures"]`**: Soporte esencial para fallos parciales de lote (*partial batch failure*). Solo los mensajes que fallen transitoriamente son devueltos a la cola SQS para reintento individual, evitando que los mensajes procesados con éxito se reprocesen.

3. **`aws_iam_role.worker_exec` y políticas asociadas:**
   - `AWSLambdaBasicExecutionRole` para emisión de logs en CloudWatch.
   - Política específica de mínimo privilegio para:
     - `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` sobre la cola SQS configurada.
     - `s3:GetObject`, `s3:HeadObject` sobre los objetos del bucket privado de documentos (`tenants/*`).

4. **`aws_cloudwatch_log_group.worker_logs`:**
   - Grupo de logs con retención configurable (por defecto 7 días), evitando acumulación de costes en almacenamiento de CloudWatch Logs.

---

## 2. Impacto en Costes y Free Plan (Auditoría CDM-17)

- **Cómputo Lambda:** Se sitúa dentro del Free Tier de AWS (1 millón de solicitudes y 3,200,000 segundos de cómputo mensual).
- **CloudWatch Logs:** Retención de 7 días para no superar el almacenamiento gratuito.
- **Sin VPC / Sin NAT Gateway:** No requiere NAT Gateway, protegiendo contra costes fijos no autorizados (cumplimiento estricto de `AGENTS.md` §13).

---

## 3. Ejemplo de Uso

```terraform
module "lambda_worker" {
  source = "../../modules/lambda-worker"

  function_name = "cdm-dev-document-worker"
  sqs_queue_arn = module.sqs_worker_queue.queue_arn
  s3_bucket_arn = module.s3_document_store.bucket_arn

  memory_size        = 256
  timeout            = 30
  log_retention_days = 7

  environment_variables = {
    ENVIRONMENT = "dev"
    DATABASE_URL = "postgresql+psycopg://user:pass@host:5432/db"
  }

  tags = {
    Project     = "cdm"
    Environment = "dev"
  }
}
```

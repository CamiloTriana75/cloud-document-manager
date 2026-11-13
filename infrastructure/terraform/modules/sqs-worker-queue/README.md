# Módulo SQS Worker Queue — CDM

> Jira: **CDM-35** · Fecha: 2026-11-12
> Regla rectora: [`AGENTS.md`](../../../AGENTS.md) §6, §12, §13.

Módulo de Terraform para aprovisionar el canal de eventos asíncronos desacoplado entre Amazon S3 y el worker AWS Lambda de CDM.

---

## 1. Responsabilidad y Recursos Creados

1. **`aws_sqs_queue.this` (Cola Principal):**
   - Recibe las notificaciones de evento `s3:ObjectCreated:*`.
   - `visibility_timeout_seconds`: 180 segundos por defecto (3 minutos). Cumple la recomendación oficial de AWS de configurar el timeout de visibilidad a **6x** la duración máxima esperada de la función Lambda consumidora (30s) para evitar que mensajes en procesamiento concurrente reaparezcan prematuramente.
   - `receive_wait_time_seconds`: 20 segundos (Long Polling habilitado), minimizando solicitudes vacías y costes operativos.
   - `sqs_managed_sse_enabled = true`: Cifrado en reposo SSE-SQS gestionado por AWS sin coste adicional ($0 en KMS), protegiendo la cuenta Free Plan.

2. **`aws_sqs_queue.dlq` (Dead Letter Queue):**
   - Almacena de forma persistente los mensajes que fallan tras `max_receive_count` reintentos (por defecto 3).
   - Retención extendida a 14 días (`1209600s`) para permitir diagnóstico operativo, alarmas en CloudWatch y redrive manual controlado.

3. **`aws_sqs_queue_policy.this` (Política de Mínimo Privilegio):**
   - Concede exclusivamente a `s3.amazonaws.com` el permiso `sqs:SendMessage`.
   - Protegida con condiciones estrictas:
     - `aws:SourceArn = <bucket_arn>`: solo el bucket autorizado puede enviar mensajes.
     - `aws:SourceAccount = <account_id>`: previene el problema del "deputy confuso".

---

## 2. Impacto en Costes y Free Plan (Auditoría CDM-17)

- **Cifrado:** SSE-SQS no genera llamadas a AWS KMS, por lo que su coste es $0.
- **Solicitudes SQS:** AWS incluye 1,000,000 de solicitudes SQS mensuales gratuitas en el Free Tier perpetuo.
- **Long Polling:** Al configurar `receive_wait_time_seconds = 20`, el consumidor no realiza peticiones de sondeo continuas innecesarias cuando la cola está vacía.

---

## 3. Ejemplo de Uso

```terraform
module "sqs_worker_queue" {
  source = "../../modules/sqs-worker-queue"

  queue_name                 = "cdm-dev-document-events"
  s3_bucket_arn              = module.s3_document_store.bucket_arn
  visibility_timeout_seconds = 180
  max_receive_count          = 3

  tags = {
    Project     = "cdm"
    Environment = "dev"
  }
}
```

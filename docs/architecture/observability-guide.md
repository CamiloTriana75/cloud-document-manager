# Guía de Observabilidad, Métricas y Trazabilidad con CloudWatch (CDM-52)

> **Documento rector de observabilidad, monitoreo y alarmas operativas.**  
> Aplica a la arquitectura serverless de Cloud Document Manager (CDM), abarcando la API FastAPI, el procesamiento asíncrono con SQS y Lambda Worker, y la persistencia en PostgreSQL y S3.

---

## 1. Filosofía de Observabilidad y Principios de Diseño

1. **Logs Estructurados:** Todos los eventos de logging se emiten en formato JSON estándar para permitir indexación y búsquedas analíticas instantáneas con **CloudWatch Logs Insights**.
2. **Correlación de Extremo a Extremo:** Cada petición HTTP o mensaje de evento asíncrono cuenta con un `request_id` trazable que vincula el flujo completo:
   $$\text{Browser} \xrightarrow{\text{X-Request-ID}} \text{FastAPI (API Gateway)} \xrightarrow{\text{UploadSession}} \text{S3 ObjectCreated} \xrightarrow{\text{SQS messageId}} \text{Lambda Worker}$$
3. **Privacidad y Sanitización Absoluta:** Ningún token de autenticación (Bearer/JWT), contraseña de base de datos ni URL prefirmada con firmas temporales HMAC (`X-Amz-Signature`) se escribe en los registros.
4. **Control Estricto de Costes en AWS:** Retención de logs fijada en 14 días para entornos de desarrollo/staging, impidiendo la acumulación indefinida de gigabytes y respetando el Free Plan y los créditos disponibles (AGENTS.md §13).

---

## 2. Esquema de Logs Estructurados (JSON)

Cada registro emitido por el `StructuredJsonFormatter` (`cdm/config/logging.py`) cumple la siguiente estructura:

```json
{
  "timestamp": "2026-11-12T23:30:00.123456Z",
  "level": "INFO",
  "logger": "cdm.application.use_cases.documents",
  "message": "Authorized document download for tenant=00000000-0000-4000-a000-000000000001 user=sub-12345 document=44444444-4444-4000-a000-000000000001 expires_in_seconds=900",
  "request_id": "c1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
  "tenant_id": "00000000-0000-4000-a000-000000000001",
  "document_id": "44444444-4444-4000-a000-000000000001"
}
```

### Campos Estándar:
- `timestamp`: Marca de tiempo en formato ISO-8601 UTC.
- `level`: Nivel de severidad (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
- `logger`: Nombre del módulo Python emisor.
- `message`: Mensaje descriptivo con sanitización automática aplicada.
- `request_id`: Identificador único de correlación (procedente de `X-Request-ID` o generado automáticamente).
- `tenant_id` *(opcional)*: UUID del espacio de trabajo asociado a la operación.
- `document_id` *(opcional)*: UUID del documento intervenido.
- `exception` *(opcional)*: Stack trace formateado en caso de errores no controlados.

---

## 3. Trazabilidad y Correlación Distribuida

### 3.1 Flujo HTTP Sincrónico (API Gateway + FastAPI)
- El cliente (navegador Angular) puede suministrar `X-Request-ID` o `X-Correlation-ID`.
- Si el cliente no lo envía, `CorrelationIdMiddleware` (`cdm/adapters/inbound/http/correlation.py`) genera un UUID criptográfico.
- La cabecera `X-Request-ID` se adjunta en la respuesta HTTP saliente para correlación desde el frontend.
- Los logs de la petición usan el contextvar `current_request_id`. Al terminar la respuesta, el contextvar se limpia para evitar fugas entre corrutinas.

### 3.2 Flujo Asíncrono de Procesamiento (S3 -> SQS -> Lambda Worker)
- S3 emite una notificación `ObjectCreated` hacia la cola SQS principal.
- Cuando el Lambda Worker procesa el lote (`process_sqs_event`), extrae el `messageId` de SQS y lo inyecta como `request_id` del contexto.
- Esto permite buscar en CloudWatch el ciclo de vida completo de un mensaje utilizando su `messageId`.

---

## 4. Métricas y Alarmas CloudWatch

Declaradas mediante Terraform en el módulo `observability-cloudwatch` (`infrastructure/terraform/modules/observability-cloudwatch`):

| Alarma CloudWatch | Métrica y Namespace | Umbral Conservador | Periodo | Acción / Severidad |
|---|---|---|---|---|
| **`api-errors-alarm`** | `AWS/Lambda` / `Errors` (API) | $\ge 5$ errores | 5 min (300s) | Notificación SNS / **Alta** |
| **`api-throttles-alarm`** | `AWS/Lambda` / `Throttles` (API) | $> 0$ eventos | 5 min (300s) | Notificación SNS / **Crítica** |
| **`worker-errors-alarm`** | `AWS/Lambda` / `Errors` (Worker) | $\ge 2$ errores | 5 min (300s) | Notificación SNS / **Alta** |
| **`sqs-dlq-messages-alarm`** | `AWS/SQS` / `ApproximateNumberOfMessagesVisible` | $> 0$ mensajes | 1 min (60s) | Notificación SNS / **CRÍTICA INMEDIATA** |

### Tópico SNS Centralizado
- Nombre: `${project_name}-${environment}-cloudwatch-alerts`.
- Las alarmas envían eventos tanto al activarse (`alarm_actions`) como al recuperarse (`ok_actions`).
- Permite conectar suscripciones de correo electrónico o webhooks operativos (Slack, PagerDuty).

---

## 5. Consultas Frecuentes en CloudWatch Logs Insights

### 5.1 Buscar todas las trazas de un documento por su ID
```sql
fields @timestamp, level, message, request_id, tenant_id
| filter document_id = "44444444-4444-4000-a000-000000000001"
| sort @timestamp desc
| limit 50
```

### 5.2 Rastrear un flujo completo mediante su `request_id`
```sql
fields @timestamp, logger, level, message
| filter request_id = "c1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"
| sort @timestamp asc
```

### 5.3 Errores y excepciones no controladas en las últimas 24 horas
```sql
fields @timestamp, logger, message, exception, request_id
| filter level in ["ERROR", "CRITICAL"]
| sort @timestamp desc
| limit 100
```

### 5.4 Distribución de peticiones por código de estado y tenant
```sql
stats count(*) by tenant_id, level
| sort count desc
```

---

## 6. Procedimiento ante Disparo de Alarmas

1. **Alarma de DLQ (`sqs-dlq-messages-alarm`):**
   - Indica que un documento falló sus 3 reintentos automáticos y fue enviado a la Dead Letter Queue.
   - Acceder a AWS SQS -> Cola `${project_name}-${environment}-document-events-dlq`.
   - Inspeccionar los mensajes en la DLQ con `ReceiveMessage` para determinar el motivo del fallo (`failure_reason` en PostgreSQL).
   - Corregida la causa, utilizar el comando SQS Redrive para reinyectar los mensajes a la cola principal.
2. **Alarma de Errores de API (`api-errors-alarm`):**
   - Ejecutar la consulta 5.3 en Logs Insights sobre `/aws/lambda/${project_name}-${environment}-api`.
   - Verificar si el error proviene de timeout de conexión a PostgreSQL o fallos en el verificador de Cognito.

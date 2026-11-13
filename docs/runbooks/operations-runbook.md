# Runbook de Operaciones: Diagnóstico Lambda, SQS/DLQ y Contingencia de Cargas

> **Identificador:** RB-OPS-001  
> **Ámbito:** Operaciones en Producción y Desarrollo / Cloud Document Manager (CDM)  
> **Criterios de Aceptación:** CDM-53 · *AGENTS.md* (§8, §12, §13, §14)  
> **Última Actualización:** 2026-11-12  

---

## 1. Niveles de Severidad y Matriz de Escalamiento

| Severidad | Impacto | Ejemplo Típico | SLA de Atención | Canal de Alerta |
|---|---|---|---|---|
| **SEV-1 (Crítica)** | Interrupción total del servicio; nadie puede subir ni consultar documentos. | Base de datos PostgreSQL inalcanzable; saturación global de Lambda API; fallo masivo de autenticación Cognito. | Inmediata (< 15 min) | Alarma CloudWatch SNS (Email / Pager) |
| **SEV-2 (Mayor)** | Degradación parcial; procesamiento asíncrono detenido o acumulación de fallos en DLQ. | Mensajes acumulados en Dead Letter Queue (`sqs_dlq_messages >= 1`); timeout recurrente en Lambda Worker. | < 1 hora | Alarma CloudWatch SNS |
| **SEV-3 (Menor)** | Incidencias puntuales de clientes o rechazos de archivos esperados. | Fallos de validación MIME de usuario; timeouts de URLs prefirmadas en redes lentas. | Siguiente día hábil | Dashboard CloudWatch Logs |

---

## 2. Diagnóstico de Incidencias en AWS Lambda API

### 2.1 Alarma: `cdm-dev-lambda-api-errors`
- **Métrica:** `AWS/Lambda` / `Errors` >= 5 durante 5 minutos.
- **Síntoma:** Clientes reciben respuestas HTTP 500 Internal Server Error o HTTP 502 Bad Gateway desde API Gateway.

#### Procedimiento de Investigación:
1. **Consultar logs de error recientes mediante CloudWatch Logs Insights:**
   ```sql
   fields @timestamp, @message, request_id, tenant_id, path, error
   | filter level in ["ERROR", "CRITICAL"]
   | sort @timestamp desc
   | limit 20
   ```
2. **Identificar la causa raíz:**
   - **Excepción de Conexión a Base de Datos (`OperationalError`, `Timeout`):**
     - Verificar conectividad de PostgreSQL (o instancia RDS).
     - Comprobar si el pool de conexiones (`pool_size=10`, `max_overflow=20`) se encuentra saturado por picos de concurrencia.
     - *Acción:* Reiniciar el servicio de base de datos o incrementar temporalmente el límite de conexiones si los recursos de memoria lo permiten.
   - **Expiración de Tokens o Error de JWKS de Cognito:**
     - Si los logs registran fallos al descargar las claves públicas (`https://cognito-idp.{region}.amazonaws.com/.../.well-known/jwks.json`), verificar conectividad saliente y estado de servicio de AWS Cognito.

### 2.2 Alarma: `cdm-dev-lambda-api-throttles`
- **Métrica:** `AWS/Lambda` / `Throttles` >= 1 en 5 minutos.
- **Síntoma:** Clientes reciben HTTP 429 Too Many Requests emitido directamente por AWS Lambda.

#### Procedimiento de Mitigación:
1. Verificar si la cuota regional de ejecuciones concurrentes de la cuenta AWS ha sido alcanzada.
2. Si un tenant o IP específica está ejecutando un ataque de denegación o scraping, revisar los logs agrupados por IP:
   ```sql
   fields @timestamp, client_ip, path
   | stats count() as requests by client_ip
   | sort requests desc
   | limit 10
   ```
3. Comprobar que el middleware de rate limiting (`apps/api/src/cdm/adapters/inbound/http/rate_limit.py`) esté activo y ajustado a 60 req/min para endpoints críticos.

---

## 3. Diagnóstico y Tratamiento de Fallos en SQS & Lambda Worker

El procesamiento asíncrono extrae metadatos técnicos y transiciona el estado de los documentos de `UPLOADED` a `READY` o `FAILED`.

### 3.1 Alarma: `cdm-dev-sqs-dlq-messages`
- **Métrica:** `AWS/SQS` / `ApproximateNumberOfMessagesVisible` >= 1 en `cdm-dev-document-events-dlq`.
- **Significado:** Un evento de S3 falló 3 veces consecutivas (`maxReceiveCount = 3`) al ser procesado por el Lambda Worker y fue segregado a la cola de mensajes muertos.

#### Protocolo de Actuación Seguro (Cumplimiento *AGENTS.md* §12, §14):
> [!IMPORTANT]
> **REGLA DE SEGURIDAD:** Nunca copiar ni registrar en texto plano el contenido de los mensajes de la cola en tickets públicos o chats compartidos sin verificar que las URLs prefirmadas o identificadores no expongan datos sensibles.

1. **Inspeccionar el mensaje en la DLQ sin eliminarlo:**
   ```bash
   aws sqs receive-message \
     --queue-url "https://sqs.us-east-1.amazonaws.com/<ACCOUNT_ID>/cdm-dev-document-events-dlq" \
     --max-number-of-messages 1 \
     --visibility-timeout 30 \
     --attribute-names All
   ```
2. **Analizar el `messageId` y buscar su traza en CloudWatch Logs:**
   En Cloud Document Manager, el worker inyecta el `messageId` de SQS en el contexto de logging estructurado (`request_id`). Ejecutar en CloudWatch Logs Insights para el grupo `/aws/lambda/cdm-dev-worker`:
   ```sql
   fields @timestamp, request_id, document_id, message, error
   | filter request_id = "<MESSAGE_ID_DE_SQS>"
   | sort @timestamp asc
   ```
3. **Clasificación del Fallo:**
   - **Fallo Transitorio (Infraestructura / Timeout / Caída temporal de DB):**
     - La causa externa ya fue resuelta.
     - **Acción:** Ejecutar Redrive manual hacia la cola principal mediante AWS CLI:
       ```bash
       aws sqs start-message-move-task \
         --source-arn "arn:aws:sqs:us-east-1:<ACCOUNT_ID>:cdm-dev-document-events-dlq" \
         --destination-arn "arn:aws:sqs:us-east-1:<ACCOUNT_ID>:cdm-dev-document-events-queue"
       ```
     - Verificar que los mensajes sean consumidos y la DLQ regrese a 0.
   - **Fallo Definitivo (Archivo corrupto / violación de formato):**
     - El worker normalmente atrapa estos errores y marca el documento como `FAILED` sin reintentar.
     - Si por alguna razón un mensaje malformado o envenenado no pudo ser procesado por el código, purgarlo manualmente tras registrar el incidente:
       ```bash
       aws sqs delete-message \
         --queue-url "https://sqs.us-east-1.amazonaws.com/<ACCOUNT_ID>/cdm-dev-document-events-dlq" \
         --receipt-handle "<RECEIPT_HANDLE>"
       ```

---

## 4. Diagnóstico de Errores en la Carga Directa a Amazon S3

La carga binaria directa desde el navegador Angular hacia S3 puede presentar las siguientes anomalías:

### 4.1 Error: `403 Forbidden` / Fallo de CORS en el Navegador
- **Síntoma:** La consola del navegador reporta: `Access to XMLHttpRequest from origin 'http://localhost:4200' has been blocked by CORS policy`.
- **Causas Posibles:**
  1. El bucket S3 no tiene configurada la regla CORS para el origen de la SPA (`allowed_origins = ["http://localhost:4200"]` en dev).
  2. Los encabezados enviados por el navegador en la petición `PUT` no coinciden exactamente con los permitidos por la regla CORS de S3 (`PUT`, `Content-Type`).
- **Verificación y Solución:**
  Revisar la configuración en `infrastructure/terraform/modules/s3-storage/main.tf` y verificar con AWS CLI:
  ```bash
  aws s3api get-bucket-cors --bucket "<BUCKET_NAME>"
  ```

### 4.2 Error: `SignatureDoesNotMatch` o `AccessDenied` en PUT Directo
- **Síntoma:** S3 responde `403 Forbidden` con código XML `SignatureDoesNotMatch`.
- **Causas Posibles:**
  1. **Discrepancia en `Content-Type`:** La URL prefirmada se generó con un `Content-Type` (ej. `application/pdf`), pero la petición `fetch`/`XMLHttpRequest` del frontend envió otro o lo omitió.
  2. **Encabezados adicionales:** Se incluyeron encabezados de autorización o metadatos no firmados.
- **Solución:**
  El frontend debe enviar estrictamente los mismos encabezados acordados en la respuesta de `POST /upload-sessions`:
  ```typescript
  fetch(presignedUrl, {
    method: 'PUT',
    headers: { 'Content-Type': declaredContentType },
    body: file
  });
  ```

### 4.3 Error: `Request has expired` (URL Prefirmada Vencida)
- **Síntoma:** El usuario tardó más de 15 minutos (900 segundos) entre la selección del archivo y el inicio de la transmisión.
- **Comportamiento Esperado:** La aplicación Angular detecta el fallo y permite al usuario reintentar con un clic, generando una nueva sesión provisional mediante `POST /upload-sessions`.

### 4.4 Error: Discrepancia en Tamaño (`File Size Mismatch`) al Confirmar
- **Síntoma:** La llamada `POST /workspaces/{id}/documents/{id}/complete` falla con error 400.
- **Causa:** El backend ejecuta `HeadObject` en S3 y compara el `ContentLength` real contra el `expected_size` registrado en la sesión provisional. Si difieren significativamente, la carga se rechaza para evitar inyecciones o truncamientos.
- **Solución:** Solicitar al usuario que repita la carga con el archivo íntegro.

---

## 5. Consultas Frecuentes en CloudWatch Logs Insights

### Conteo de Errores por Tipo de Excepción (Últimas 24 horas):
```sql
fields @timestamp, error, path, level
| filter level in ["ERROR", "CRITICAL"]
| stats count() as error_count by error
| sort error_count desc
```

### Tiempos de Respuesta y Latencia de Endpoints API:
```sql
fields @timestamp, path, duration_ms, status_code
| filter ispresent(duration_ms)
| stats avg(duration_ms) as latencia_media, max(duration_ms) as latencia_max by path
| sort latencia_media desc
```

### Auditoría de Acciones Destructivas por Tenant:
```sql
fields @timestamp, tenant_id, request_id, message
| filter message like /eliminado/ or message like /DELETE/
| sort @timestamp desc
| limit 50
```

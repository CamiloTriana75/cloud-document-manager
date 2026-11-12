# Política de Ciclo de Vida, Expiración y Limpieza de Cargas (CDM-34)

> Jira: **CDM-34** · Fecha: 2026-11-12
> Regla rectora: [`AGENTS.md`](../../AGENTS.md) §10, §12 (Almacenamiento seguro e integridad S3/DB).

Este documento formaliza la estrategia defensiva de ciclo de vida para sesiones de carga prefirmada, expiración de intenciones abandonadas, cancelación explícita por el usuario y purga segura de objetos huérfanos sin riesgo de pérdida de datos.

---

## 1. Ciclo de Vida de las Sesiones de Carga (`UploadSession`)

Una sesión de carga modela la intención provisional de transferir un archivo binario directamente a Amazon S3 mediante una URL prefirmada HTTPS:

```text
                  ┌────────────────┐
                  │    PENDING     │
                  └──────┬──┬──┬───┘
                         │  │  │
      Confirmación S3    │  │  │ Cancelación explícita
      (complete upload)  │  │  │ (POST .../cancel)
                         ▼  │  ▼
        ┌────────────────┐  │ ┌────────────────┐
        │   COMPLETED    │  │ │   CANCELLED    │
        └────────────────┘  │ └────────────────┘
                            │
                            │ Caducidad vencida
                            │ (Cleanup job)
                            ▼
                    ┌────────────────┐
                    │    EXPIRED     │
                    └────────────────┘
```

### Transiciones de Estado
1. **`PENDING`**: Sesión inicializada con URL prefirmada de vida corta (por defecto 900s / 15 minutos). El documento provisional se encuentra en `PENDING_UPLOAD`.
2. **`COMPLETED`**: La carga ha sido verificada en S3 mediante `HeadObject` (`CompleteDocumentUploadUseCase`). El documento pasa a `UPLOADED`.
3. **`CANCELLED`**: El usuario o la aplicación interrumpen la transferencia de forma explícita (`POST /upload-sessions/{id}/cancel`). Si existiera un objeto binario parcial en S3, es purgado inmediatamente. El documento pasa a `FAILED`.
4. **`EXPIRED`**: La sesión superó su vigencia (`now >= expires_at`) sin haber sido confirmada. El proceso de limpieza transiciona la sesión a `EXPIRED` y el documento a `FAILED`.

---

## 2. Invariante de No Eliminación de Documentos Válidos

> [!IMPORTANT]
> **REGLA CRÍTICA DE INTEGRIDAD (Criterio 3 & 5 de CDM-34)**:
> La rutina de limpieza **NUNCA** elimina documentos confirmados ni sus objetos binarios en S3.
> 
> Si un documento se encuentra en cualquiera de los siguientes estados:
> - `UPLOADED` (confirmado por el cliente y validado físicamente en S3)
> - `PROCESSING` (siendo analizado asíncronamente por Lambda)
> - `READY` (listo y disponible en el catálogo del workspace)
> 
> El proceso de limpieza omite cualquier acción destructiva, preserva el binario intacto y asegura la concordancia entre PostgreSQL y S3.

---

## 3. Estrategia de Purga de Objetos Huérfanos

La limpieza de cargas incompletas se realiza en dos capas complementarias:

### A. Capa de Aplicación (`CleanupExpiredUploadSessionsUseCase`)
- **Frecuencia:** Ejecutable de forma programada o bajo demanda mediante endpoint de administración (`POST /api/v1/workspaces/{workspace_id}/upload-sessions/cleanup`).
- **Comportamiento:**
  1. Consulta las sesiones en estado `PENDING` cuya fecha `expires_at` es menor o igual al tiempo actual.
  2. Verifica el estado del documento asociado en la base de datos:
     - Si está en `UPLOADED`, `PROCESSING` o `READY`: omite la eliminación y reconcilia la sesión a `COMPLETED`.
     - Si continúa en `PENDING_UPLOAD`: marca la sesión como `EXPIRED`, el documento como `FAILED` con motivo `upload_session_expired`, y elimina el objeto en S3 vía `StoragePort.delete_object(storage_key)`.
  3. Emite un informe estructurado con el número de sesiones expiradas, objetos purgados y documentos confirmados preservados.

### B. Capa de Infraestructura S3 Lifecycle (`infrastructure/terraform/modules/s3-document-store`)
- **Multipart Uploads Abortados:** Regla S3 `abort-incomplete-multipart-uploads` configurada para abortar y purgar fragmentos incompletos tras `abort_incomplete_multipart_upload_days` (por defecto 7 días).
- **Subidas en Prefijo Temporal:** Regla S3 `expire-unconfirmed-temp-uploads` configurada para expirar automáticamente objetos en `temp/` tras `temp_prefix_expiration_days` (por defecto 1 día).

---

## 4. Auditoría y Trazabilidad

Todas las cancelaciones y ejecuciones de limpieza emiten registros en logs estructurados con:
- `workspace_id`: Tenant asociado.
- `session_id` y `document_id`: Identificadores únicos correlacionados.
- Métricas: número de sesiones expiradas y objetos eliminados.
- **Sin datos sensibles:** Nunca se registran credenciales, tokens ni URLs prefirmadas completas.

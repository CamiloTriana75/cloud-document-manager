# ADR-0005: Procesamiento asíncrono S3 → SQS → Lambda worker

- **Fecha:** 2026-11-12 · **Estado:** Aceptado · **Jira:** CDM-11, CDM-35, CDM-36, CDM-38, CDM-39

## Contexto

Tras cada carga, el documento necesita validación de contenido, checksum y metadatos técnicos. Esto no debe ocurrir dentro de la request HTTP del usuario.

## Opciones consideradas

1. **Procesar dentro del `complete` (síncrono)** — acopla latencia del usuario al trabajo pesado; `HeadObject`+hash de 50 MB puede tardar; bloquea el flujo.
2. **S3 Event Notification → SQS → Lambda worker (+ DLQ)** — desacopla, reintenta de forma controlada, estándar del stack acordado.
3. **S3 Event directo a Lambda (sin SQS)** — S3 reintenta automáticamente, pero sin DLQ nativa ni control de visibilidad; peor observabilidad de fallos.
4. **Paso intermedio por EventBridge** — flexibilidad extra innecesaria para un único tipo de evento en MVP.

## Decisión

- Notificación `ObjectCreated` del bucket → **cola SQS** → **Lambda worker**.
- **DLQ** con alarmas CloudWatch de `ApproximateNumberOfMessagesVisible`/age.
- **Idempotencia:** el worker identifica cada evento por `bucket + key + (versionId|etag + size)` y persiste un registro de eventos procesados; un mensaje repetido no duplica metadatos ni retrocede estados (`READY`→`PROCESSING` prohibido, `domain-model.md` §4.6).
- Reintentos: máximo de receives configurado (por defecto 3); superado → DLQ con causa y correlación logueadas sin datos sensibles. Operación de reintento manual documentada en runbook (CDM-53).
- Visibility timeout > p99 de procesamiento estimado (hash de 50 MB); se ajusta con métricas reales.
- El worker usa los **mismos casos de uso y puertos** que la API (núcleo compartido); su handler solo traduce el evento SQS.

## Consecuencias

- El usuario ve estados (`UPLOADED → PROCESSING → READY/FAILED`) mediante polling; sin WebSockets.
- Eventos de objetos ajenos al flujo (borrados externos, otras keys) se ignoran con log.
- Riesgo: entrega al menos una vez → toda la lógica del worker es idempotente por diseño, y hay pruebas obligatorias de eventos duplicados (CDM-36/CDM-49).

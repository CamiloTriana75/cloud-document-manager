# Product Charter — Cloud Document Manager (CDM)

> Fuente de verdad: [`AGENTS.md`](../AGENTS.md) (documento rector). Este charter materializa el acuerdo registrado en el issue Jira **CDM-1**. Ante conflicto, manda `AGENTS.md`.

- **Fecha:** 2026-11-12
- **Jira:** [CDM-1](https://ix-football.atlassian.net/browse/CDM-1)
- **Estado:** Aceptado

## 1. Propósito

Aplicación web para cargar, almacenar, procesar, consultar y descargar documentos de forma segura, con arquitectura cloud demostrable y control estricto de costes. Proyecto de portafolio que demuestra backend Python, frontend Angular, arquitectura hexagonal, multi-tenancy, AWS, IaC, automatización, seguridad y pruebas.

## 2. Usuarios y roles

- Usuarios autenticados mediante Amazon Cognito.
- Roles iniciales con jerarquía `VIEWER` < `MEMBER` < `EDITOR` < `ADMIN` < `OWNER` (decisión del propietario, ADR-0001):
  - `OWNER`: control total del workspace y miembros; transferencia/eliminación.
  - `ADMIN`: administra miembros, roles y documentos.
  - `EDITOR`: como `MEMBER` + eliminación lógica de documentos + gestión de metadatos.
  - `MEMBER`: sube, lista, consulta y descarga documentos.
  - `VIEWER`: solo lectura (catálogo, detalle, descarga).
- Detalle y consecuentes: [`adr/0001-roles-de-workspace.md`](adr/0001-roles-de-workspace.md) y AGENTS.md §3.2.

## 3. Alcance del MVP

1. Autenticación y autorización (Cognito + JWT).
2. Aislamiento de datos por workspace/tenant.
3. Carga directa y segura a S3 mediante URLs prefirmadas.
4. Metadatos y estados del documento en PostgreSQL.
5. Procesamiento asíncrono S3 → SQS → Lambda.
6. Catálogo: listado, búsqueda básica, filtros, detalle, descarga segura, eliminación lógica.
7. Auditoría, observabilidad, pruebas, CI/CD e infraestructura reproducible.

El flujo de aceptación completo está en AGENTS.md §22 (criterio de éxito MVP 0.1).

## 4. Fuera de alcance del MVP

OCR avanzado, antivirus comercial, edición colaborativa, firma electrónica, versionado binario avanzado, app móvil, facturación SaaS, migración masiva de documentos. Evaluables en releases posteriores (AGENTS.md §4).

## 5. Stack

Ver AGENTS.md §5. Resumen: Angular + TypeScript / Python + FastAPI (hexagonal) / PostgreSQL + SQLAlchemy + Alembic / AWS (S3, API Gateway, Lambda, SQS, Cognito, CloudWatch) / Terraform / pytest, Ruff, mypy, ESLint / GitHub Actions / Docker Compose en local. Emuladores AWS (LocalStack) solo con fidelidad verificada.

## 6. Arquitectura objetivo

Angular (estático) → CloudFront/S3 → API Gateway → FastAPI en Lambda (adaptador ASGI) → PostgreSQL.

- Binarios van directo del navegador a S3 (URL prefirmada); nunca atraviesan FastAPI.
- S3 notifica ingesta vía SQS; Lambda worker valida, enriquece metadatos y actualiza estado en PostgreSQL (idempotente, con DLQ).
- Diagrama completo: AGENTS.md §6.
- Prohibido sin decisión explícita + estimación: NAT Gateway, balanceadores, clústeres siempre encendidos, recursos de coste fijo.

## 7. Principios de ingeniería

Ver AGENTS.md §2, §8 y §14. Síntesis:

- Hexagonal: dominio sin dependencias de FastAPI, AWS ni ORM; dependencias apuntan al dominio.
- Tipado estricto, validación en los límites, re-comprobación de permisos en casos de uso.
- Sin duplicación de lógica; abstracciones solo con necesidad demostrable.
- Mínimo privilegio IAM; `tenant_id` obligatorio en consultas; `storage_key` opaco generado en servidor.
- Idempotencia en consumidores SQS; reintentos y DLQ.
- No confiar en nombre de archivo ni `Content-Type` del navegador.
- Ningún secreto en el repositorio.

## 8. Gestión de calidad: DoR / DoD

Formalizados en AGENTS.md §18 y §19.

- **DoR:** propósito claro, criterios verificables, dependencias identificadas, tamaño razonable (ideal ≤ 5 puntos), sin decisiones críticas pendientes.
- **DoD:** criterios cumplidos, pruebas en local y CI, lint/type-check limpios, docs actualizadas, revisión de seguridad y multi-tenancy, sin secretos en el diff, plan de infra revisado antes de aplicar.

## 9. Gobierno Kanban

- Columnas: *Por hacer → En curso → Listo*.
- **WIP máximo: 2** en *En curso*; no iniciar trabajo nuevo si hay trabajo bloqueado.
- *Pull:* seleccionar siempre el elemento prioritario Ready y sin dependencias abiertas.
- Bloqueos: etiqueta `blocked`, motivo explicado, siguiente paso registrado.
- Revisión diaria (5–10 min): mover tarjetas, detectar bloqueos, revisar WIP.
- Replenishment semanal: aclarar y priorizar siguiente lote.
- Review semanal: demo de flujo funcional y comprobación de aceptación.
- Retro quincenal: máximo 1 mejora de proceso, convertida en acción.
- No se inventan story points ni fechas; estimar al refinar.

## 10. Ramificación y entrega

Estrategia de ramas: ver [`development/branching.md`](development/branching.md).

Plan de incrementos (AGENTS.md §17):

| Incremento | Contenido | Épica Jira |
|---|---|---|
| 0 | Decisiones, repositorio, CI, entorno local | CDM-2, CDM-3 |
| 1 | Identidad, workspace y permisos | CDM-4 |
| 2 | Carga segura y almacenamiento | CDM-5 |
| 3 | Procesamiento asíncrono y catálogo | CDM-6, CDM-7 |
| 4 | UI completa, auditoría y endurecimiento | CDM-8 |
| 5 | Despliegue final, docs, demo y limpieza | CDM-9 |

## 11. Gestión AWS Free Plan

- Validar en AWS Console: fecha de fin del plan, saldo de créditos, servicios habilitados (Jira CDM-17).
- Activar AWS Budgets/alertas y revisar Cost Explorer antes de cada despliegue.
- No asumir que un recurso es gratis por aparecer en la consola.
- Checklist de exportación/backup y destrucción de entornos temporales antes del fin del plan.

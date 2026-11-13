# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y este proyecto se adhiere a [Semantic Versioning](https://semver.org/lang/es/).

---

## [0.1.0] - 2026-11-13

### Añadido
- **Arquitectura Hexagonal Backend:**
  - Núcleo de dominio puro (`apps/api/src/cdm/domain/`) con entidades `User`, `Workspace`, `Membership`, `Document`, `UploadSession` y value objects de roles y estados.
  - Puertos de aplicación (`ports/`) y casos de uso desacoplados para gestión de espacios, sesiones de carga, procesamiento y catálogos.
  - Adaptadores inbound HTTP en FastAPI montados sobre Mangum para AWS Lambda (`/api/v1`).
  - Adaptadores outbound de persistencia con SQLAlchemy 2.0 y migraciones de base de datos con Alembic.
  - Adaptadores outbound de almacenamiento Amazon S3 y verificación de tokens JWT contra Amazon Cognito JWKS.
- **Frontend Angular 22 Zoneless:**
  - SPA reactiva basada en Signals y `provideZonelessChangeDetection()`.
  - Componentes accesibles WCAG AA: diseño responsive, skip link, contraste alto, foco visible y roles ARIA semánticos.
  - Vistas completas para autenticación (login, registro, confirmación), selección y creación de workspaces, administración de miembros, flujo de carga con progreso y catálogo documental con filtros/paginación.
  - Detalle modal de documentos con metadatos técnicos y acciones autorizadas (descarga y borrado lógico).
- **Procesamiento Asíncrono Serverless:**
  - Canalización de eventos de Amazon S3 (`s3:ObjectCreated:*`) hacia Amazon SQS.
  - Función AWS Lambda Worker con reporte de fallos parciales (`batchItemFailures`) y Dead Letter Queue (DLQ).
  - Inspección técnica en memoria de magic bytes y checksums SHA-256.
- **Seguridad Multi-Tenant y Hardening:**
  - Aislamiento estricto por tenant en PostgreSQL indexado por `workspace_id`.
  - Rutas de almacenamiento opacas bajo prefijos canónicos de tenant en S3 (`workspaces/{id}/documents/{id}/...`).
  - Middleware de limitación de tasa (`InMemoryRateLimiter`) a 60 req/min en endpoints críticos.
  - Filtro de sanitización automática en tiempo real de credenciales, Bearer tokens y firmas S3 (`SensitiveDataSanitizingFilter`).
- **Observabilidad y Alarmas CloudWatch:**
  - Logging estructurado JSON con inyección de variables de contexto (`X-Request-ID`, SQS `messageId`, `tenant_id`, `document_id`).
  - Módulo Terraform `observability-cloudwatch` con tópico SNS y 4 alarmas de salud (`lambda_api_errors`, `lambda_api_throttles`, `lambda_worker_errors`, `sqs_dlq_messages`).
- **Infraestructura como Código (Terraform):**
  - Módulos parametrizados: `cognito`, `s3-storage`, `sqs-worker-queue`, `lambda-api`, `lambda-worker` y `observability-cloudwatch`.
  - Entorno `dev` sin costes ocultos ni recursos prohibidos (*AGENTS.md* §13: sin NAT Gateways ni balanceadores continuos).
- **Suites de Pruebas y Calidad:**
  - Backend: 268 pruebas unitarias, de integración, contrato y aislamiento multi-tenant.
  - Frontend Unit: 100 pruebas en Vitest de componentes y servicios.
  - Frontend E2E: 18 pruebas en Playwright de journeys de usuario.
  - Script de demostración automatizado `scripts/demo_e2e_walkthrough.py`.
- **Documentación Operativa Integral:**
  - Diagrama de arquitectura global [`docs/architecture/system-architecture.md`](docs/architecture/system-architecture.md).
  - Guía de observabilidad [`docs/architecture/observability-guide.md`](docs/architecture/observability-guide.md).
  - Revisión de seguridad OWASP [`docs/architecture/security-review-owasp.md`](docs/architecture/security-review-owasp.md).
  - Runbook de contingencias operativas [`docs/runbooks/operations-runbook.md`](docs/runbooks/operations-runbook.md).
  - Procedimiento de backup y restore [`docs/runbooks/backup-restore.md`](docs/runbooks/backup-restore.md).
  - Protocolo de teardown y salida segura de AWS [`docs/runbooks/aws-teardown.md`](docs/runbooks/aws-teardown.md).

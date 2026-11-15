# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y este proyecto se adhiere a [Semantic Versioning](https://semver.org/lang/es/).

---

## [Unreleased]

### Seguridad
- **Bypass de autenticación cerrado (CDM-130):** el verificador JWT aceptaba sin firma cualquier token con prefijo `mock-`, incluso con Cognito configurado. Ahora, con User Pool, siempre se verifica la firma. El modo sin firma exige `CDM_AUTH_MOCK_ENABLED=true` sin User Pool y está prohibido con `CDM_ENV=prod`.
- **Invitaciones (CDM-130):** las invitaciones por correo solo se vinculan, y el correo solo se actualiza, cuando el token trae `email_verified`.

### Añadido
- **Despliegue en la nube funcionando de extremo a extremo (CDM-129):** frontend en Vercel (https://cloud-document-manager.vercel.app, ADR-0011) y PostgreSQL gestionado en Neon para las Lambdas (ADR-0010). Runbook en `docs/runbooks/cloud-deployment.md` y prueba de humo `scripts/cloud_smoke_test.py` (19 comprobaciones).
- **Cuentas con confirmación por código:** el registro lleva a `/auth/confirm` cuando Cognito lo exige, se puede reenviar el código y el login de una cuenta sin confirmar redirige a esa pantalla.
- **URL base de la API centralizada:** `apiBaseUrlInterceptor` resuelve la URL; el token solo se envía a la API propia y se usa el ID token, que incluye `email` y `email_verified`.
- **Concurrencia de Lambda:** reintento con backoff para lecturas ante 429/502/503/504, estadísticas del dashboard pedidas en serie y worker limitado a 2 ejecuciones concurrentes.
- **Desarrollo local:** emulador S3 (moto) en `compose.yaml` y `scripts/init_local_s3.py`.
- Escena 3D procedural con three.js cargado bajo demanda (ADR-0009), con respaldo CSS y soporte de `prefers-reduced-motion`.
- Carga de varios archivos con cola, progreso, cancelación y reintento por archivo (AGENTS.md §9).
- `pnpm run check:contrast`: verificación WCAG AA de los tokens, ejecutada en CI.
- `E2E_PORT` para correr Playwright junto a otro `ng serve`.

### Cambiado
- **Rediseño visual del frontend (CDM-121, CDM-107, CDM-108):** tema oscuro verde-azulado con acento naranja, tipografía Geist servida por la app, design system por capas (`src/styles/`) y componentes compartidos documentados en `docs/architecture/design-system.md`.
- **Dashboard de documentos:** pestañas-carpeta por estado con conteos reales, KPIs calculados con la API existente, catálogo con búsqueda diferida y cancelación, panel de Actividad en vivo y drawer de detalle con línea de tiempo.
- **Shell:** navegación central, selector de workspace y menú de usuario accesibles; drawer móvil con `<dialog>` nativo.
- **Inicio, miembros, creación de workspace, login y registro** rediseñados; tras crear un workspace se abre su catálogo.

### Corregido
- **Lambdas sin configuración:** recibían variables sin prefijo `CDM_` que la aplicación no lee, así que la API desplegada corría en modo mock y sin base de datos.
- **Subida directa a S3:** el rol de la API no tenía `s3:PutObject` y las URLs prefirmadas de subida devolvían 403.
- **Paquete de Lambda:** se excluían los `.dist-info` y SQLAlchemy 2.1 rechazaba psycopg (`version 0.0.0.0`).
- **Emulador S3 local:** la API no pasaba `CDM_S3_ENDPOINT_URL` al adaptador; ahora lo pasa y usa direccionamiento por ruta.
- **Settings:** se lee el `.env` de la raíz del repo (antes nunca se cargaba desde `apps/api`) y `.env.example` se alinea con los nombres reales.
- **Frontend:** decodificación base64url y UTF-8 de los JWT de Cognito (la sesión restaurada mostraba un usuario ficticio); el token no se enviaba a API Gateway porque se excluía todo `*.amazonaws.com`.
- **CI de `develop`:** mypy fallaba con los imports de `boto3` (`import-untyped`).
- Filtro por tipo enviaba prefijos MIME que el backend compara por igualdad (devolvía 0 resultados).
- Búsqueda del catálogo sin debounce ni cancelación (respuestas fuera de orden).
- `<main>` anidado en autenticación, diálogos sin gestión de foco, emojis como iconos.
- El registro navegaba a una ruta inexistente (`/workspaces`).

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

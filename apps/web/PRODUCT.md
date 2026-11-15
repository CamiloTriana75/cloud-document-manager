# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Equipos y organizaciones que trabajan en **workspaces** aislados y almacenan, organizan, consultan y descargan documentos. Cada persona tiene un rol por workspace: `OWNER`, `ADMIN`, `EDITOR`, `MEMBER` o `VIEWER` (ADR-0001).
- Audiencia secundaria: revisores técnicos que evalúan CDM como proyecto de portafolio (backend Python, Angular, AWS, arquitectura hexagonal).

## Product Purpose

Gestión documental multi-tenant: una persona inicia sesión, entra a un workspace, sube documentos directo a S3 privado mediante URL prefirmada, ve cómo se confirman y procesan de forma asíncrona (S3 → SQS → Lambda), los encuentra en el catálogo, los descarga con una URL temporal y los elimina lógicamente. Ningún workspace puede ver datos, archivos ni metadatos de otro. El éxito del MVP 0.1 es ese flujo completo, seguro y probado.

## Positioning

Aislamiento estricto por workspace resuelto en el backend, carga directa al almacenamiento sin que el binario pase por la API y procesamiento asíncrono idempotente con estados visibles para el usuario.

## Operating Context

Navegador de escritorio (y móvil) durante la jornada de trabajo. Flujo principal: login → workspace → carga → seguimiento de estado → catálogo y detalle → descarga → borrado. `OWNER` y `ADMIN` administran miembros y roles.

## Capabilities and Constraints

- Formatos permitidos: PDF, PNG, JPG/JPEG, TXT, MD, CSV, JSON, DOCX, XLSX; tamaño máximo 50 MB.
- Estados de documento: `PENDING_UPLOAD` → `UPLOADED` → `PROCESSING` → `READY`; rama de error `FAILED`; borrado lógico `DELETED`.
- La autorización siempre la decide el backend; la UI solo refleja permisos.
- UI en español.
- Fuera del MVP: IA, OCR, búsqueda semántica, firma electrónica, versionado avanzado, facturación y antivirus. Nunca afirmar que un archivo está libre de malware.

## Brand Commitments

- Nombre: **CDM — Cloud Document Manager**.
- Dirección visual fijada por el propietario (2026-11-13): dashboard oscuro verde-azulado con acento naranja y escena 3D animada, según `docs/superpowers/specs/2026-11-13-ui-redesign-design.md`.

## Evidence on Hand

- Documentación real en `docs/` (arquitectura, ADRs, runbooks, release notes v0.1.0).
- No existen clientes, testimonios, métricas de uso, benchmarks ni precios reales: no se inventan.

## Product Principles

1. Aislamiento y seguridad antes que conveniencia.
2. Estados honestos: la UI muestra solo lo que el backend confirma.
3. La tarea primero: subir, encontrar y descargar sin fricción.
4. Cero datos decorativos o funciones simuladas.

## Accessibility & Inclusion

WCAG 2.1 AA: contraste, foco visible, navegación por teclado, labels y mensajes de estado accesibles (AGENTS.md §9).

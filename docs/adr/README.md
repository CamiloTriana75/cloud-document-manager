# Registro de Decisiones de Arquitectura (ADR)

| ADR | Título | Estado |
|---|---|---|
| [0001](0001-roles-de-workspace.md) | Modelo de roles del workspace | Aceptado |
| [0002](0002-fastapi-lambda-mangum.md) | FastAPI en Lambda con adaptador ASGI (Mangum) | Aceptado |
| [0003](0003-persistencia-postgresql-entornos.md) | Estrategia de persistencia PostgreSQL por entorno | Aceptado (producción condicionada a CDM-17) |
| [0004](0004-s3-presigned-upload.md) | Carga directa a S3 con URL prefirmada (PUT) | Aceptado |
| [0005](0005-sqs-lambda-worker.md) | Procesamiento asíncrono S3 → SQS → Lambda | Aceptado |
| [0006](0006-multi-tenant-y-usuarios.md) | Estrategia multi-tenant y provisión de usuarios | Aceptado |

Plantilla mínima por ADR: contexto, opciones consideradas, decisión, consecuencias, riesgos, fecha (AGENTS.md §21).

# Cloud Document Manager (CDM)

Aplicación web SaaS multi-tenant para almacenar, organizar y consultar documentos en la nube de forma segura: carga directa a S3 con URLs prefirmadas, metadatos en PostgreSQL y procesamiento asíncrono S3 → SQS → Lambda.

> **Estado:** MVP 0.1 en construcción. Ver [`docs/product-charter.md`](docs/product-charter.md) y el tablero Jira **CDM**.

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | Angular + TypeScript |
| Backend | Python + FastAPI (arquitectura hexagonal) |
| Datos | PostgreSQL + SQLAlchemy + Alembic |
| Cloud | AWS S3 · API Gateway · Lambda · SQS · Cognito · CloudWatch |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| Local | Docker Compose |

## Documentación

| Documento | Contenido |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Documento rector: reglas de ingeniería, seguridad, costes y protocolo para agentes |
| [`docs/product-charter.md`](docs/product-charter.md) | Charter: propósito, roles, alcance, gobierno Kanban |
| [`docs/product/mvp-journeys.md`](docs/product/mvp-journeys.md) | Journeys del MVP, matriz de permisos, límites |
| [`docs/architecture/domain-model.md`](docs/architecture/domain-model.md) | Modelo de dominio, diagramas, invariantes |
| [`docs/adr/`](docs/adr/README.md) | Decisiones de arquitectura (ADR) |
| [`docs/development/branching.md`](docs/development/branching.md) | Estrategia de ramas |
| [`docs/development/conventions.md`](docs/development/conventions.md) | Estructura del monorepo, convenciones y herramientas |

## Estructura del repositorio

Monorepo (ver detalle en [`docs/development/conventions.md`](docs/development/conventions.md)):

```text
apps/api        # FastAPI hexagonal
apps/web        # Angular
infrastructure/ # Terraform
docs/           # producto, arquitectura, ADRs, desarrollo
```

## Desarrollo local

Solo PostgreSQL corre en Docker; la API corre nativa con hot reload:

```bash
cp .env.example .env            # rellenar valores locales; .env nunca se commitea
docker compose up -d            # PostgreSQL 16 en localhost:5432

cd apps/api
uv sync                         # entorno virtual + dependencias fijadas en uv.lock
uv run alembic upgrade head     # ciclo de migraciones
uv run uvicorn cdm.bootstrap.app:app --reload   # http://localhost:8000/health

uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```

Frontend:

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm exec ng build
pnpm exec ng test --no-watch
```

Los mismos checks corren en CI (`.github/workflows/ci.yml`) en cada pull request y en push a `main`/`develop`: ruff + mypy + pytest (con PostgreSQL 16 como service container y migraciones Alembic) para el backend, build + vitest para el frontend. El pipeline falla si cualquier comprobación falla. Versiones fijadas: Python 3.12.12, uv 0.12.18, Node 24.21.0, pnpm 12.14.0, PostgreSQL 16.

## Reglas rápidas para colaboradores (y agentes)

1. Leer `AGENTS.md` completo antes de proponer cambios.
2. Ramas desde `develop`; commits `tipo(scope): ... (CDM-XX)`.
3. Aislamiento multi-tenant no negociable: toda consulta de tenant filtra por `workspace_id` autorizado.
4. Nada se considera terminado sin pruebas, lint limpio y doc actualizada.
5. Recursos AWS: nunca crear sin estimación de coste + aprobación del propietario.

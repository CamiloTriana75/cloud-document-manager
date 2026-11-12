# Conventions — CDM

> Jira: **CDM-12** (CDM-59, CDM-60) · Fecha: 2026-11-12 · Fuente rectora: `AGENTS.md`.

## 1. Estructura del monorepo

```text
cloud-document-manager/
├── AGENTS.md                  # documento rector (ya existe)
├── README.md
├── .gitignore / .editorconfig / .env.example
├── compose.yaml               # PostgreSQL local (CDM-15)
├── apps/
│   ├── api/                   # Python + FastAPI (CDM-13)
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   ├── src/cdm/           # domain | application | adapters | config | bootstrap
│   │   └── tests/             # unit | integration | contract
│   └── web/                   # Angular (CDM-14)
│       ├── package.json
│       └── src/
├── infrastructure/
│   └── terraform/             # modules/ + environments/{dev,prod} (CDM-18)
├── docs/                      # product | architecture | adr | development | runbooks | api
├── scripts/                   # automatización local
└── .github/workflows/         # CI/CD (CDM-22)
```

Regla (AGENTS.md §7): las carpetas se crean **cuando hay código que las necesite** — no se materializa la estructura vacía de golpe. Ahora mismo existen: docs, raíz de config. `apps/`, `infrastructure/`, `scripts/`, `.github/workflows/` llegan con CDM-13, CDM-15, CDM-18 y CDM-22 respectivamente.

Prohibido: módulos `utils`, `common`, `helpers` como cajones de sastre. Cada módulo tiene una responsabilidad nombrada.

## 2. Herramientas y gestores (decisión, pendiente de fijar versión exacta)

| Capa | Gestor | Nota |
|---|---|---|
| Backend Python | `uv` | Versiones de Python (≥3.12) y dependencias se fijan en `pyproject.toml` al crearlo (CDM-13), verificando compatibilidad — no versiones arbitrarias. |
| Frontend Angular | `pnpm` | Versión de Node/pnpm/Angular se fija en `package.json` al inicializar (CDM-14). |
| Calidad Python | `ruff` (lint+format), `pytest`, `mypy` | Gates de CI (CDM-22). |
| Calidad Angular | ESLint + builder de producción | Gates de CI (CDM-22). |
| Terraform | `terraform fmt`/`validate` (+ TFLint/Checkov si se incorpora) | CDM-18. |

No mezclar gestores: Python solo `uv`, Node solo `pnpm`.

## 3. Nombres

- **Git/ramas:** `main`, `develop`, `feat/inc<N>-<tema>` (ver `branching.md`).
- **Commits:** `feat|fix|test|docs|refactor|chore(scope): descripción (CDM-XX)` — issue Jira siempre.
- **Python:** `snake_case` módulos/funciones, `PascalCase` clases, constantes `UPPER_SNAKE`. Paquetes: `cdm.domain`, `cdm.application`, `cdm.adapters`, `cdm.config`, `cdm.bootstrap`.
- **TypeScript/Angular:** `camelCase` variables/funciones, `PascalCase` clases/componentes; archivos de componente `<nombre>.component.ts`; `kebab-case` en archivos.
- **DB/Alembic:** tablas `snake_case` plural; migraciones `<fecha>_<slug>.py` generadas por Alembic.
- **AWS/Terraform:** recursos `cdm-<entorno>-<recurso>`; variables `snake_case`; tags obligatorios `project=cdm`, `env`, `managed-by=terraform`.
- **Variables de entorno:** prefijo `CDM_`, `UPPER_SNAKE` (ver `.env.example`).

## 4. Calidad y gates (aplicables desde CDM-13/14)

- CI falla si: lint, type-check, pruebas o build crítico fallan (AGENTS.md §15).
- Prohibido silenciar errores: `# type: ignore`, `any`, `eslint-disable`, exclusiones de cobertura sin justificación concreta en el PR.
- Tests obligatorios por cambio: unit para dominio/casos de uso; integración con PostgreSQL real; contract de API; negativas de tenant antes de release.
- Documentación se actualiza en el mismo PR que el cambio (charter §10, DoD).

## 5. Dependencias

- Añadir dependencia solo si la stdlib o las existentes no bastan (AGENTS.md §20). Justificarla en el PR.
- Fijar versiones exactas; lockfiles (`uv.lock`, `pnpm-lock.yaml`) sí se commitean.
- Auditoría de dependencias en CI cuando exista tooling (CDM-22).

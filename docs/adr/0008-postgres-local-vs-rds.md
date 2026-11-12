# ADR-0008: PostgreSQL local (Docker) para el MVP; RDS diferido

**Estado:** Aceptado (propietario, 2026-11-12)
**Fecha:** 2026-11-12 · **Jira:** CDM-17 (épica CDM-3)

## Contexto

AGENTS.md §13 exige verificar coste y elegibilidad de RDS antes de provisionar. La auditoría de la cuenta (CDM-17, `docs/runbooks/aws-account-audit.md`) concluye:

- Cuenta en **Free Plan** con $100 de créditos hasta 2027-05-12.
- **RDS no tiene free tier** ni límites *always free*: un `db.t4g.micro` PostgreSQL single-AZ cuesta ≈$13-18/mes + ≈$2-3/mes de almacenamiento gp3 (20 GB) → **drenaría ≈$15-20/mes de créditos** (≈$90-120 en 6 meses = el saldo casi completo).
- PostgreSQL 16 ya corre en Docker Compose local con migraciones Alembic probadas y es la base del pipeline CI (service container).

## Opciones consideradas

1. **PostgreSQL local (Docker) para el MVP:** costo $0; arquitectura hexagonal permite cambiar el adaptador de persistencia/DSN sin tocar dominio ni casos de uso; la API desplegada en AWS usaría una DSN apuntando a la BD disponible.
2. **RDS `db.t4g.micro` en `us-east-1`:** PostgreSQL administrado real; consume la mayoría del saldo de créditos; riesgo de que la cuenta se agote y suspenda antes del MVP.
3. **Aurora Serverless v2:** similar o más caro que RDS en este tamaño.

## Decisión (propuesta)

**Opción 1:** mantener PostgreSQL 16 en Docker Compose para desarrollo/integración. El despliegue en AWS del backend (Lambda) se probará con la BD local expuesta solo en entorno de desarrollo controlado, o con un túnel seguro; **RDS se introduce como tarea posterior cuando haya decisión de plan (Paid) o créditos dedicados**. Alternativa intermedia futura: RDS solo durante ventanas de demo (crear/destuir con teardown — coste prorrateado ≈$0.02/hora).

## Consecuencias

- El despliegue real del API Lambda tendrá que resolver el acceso a la BD (túnel, demo temporal con RDS, o plan Paid) — se documentará en la épica de despliegue; **no se crea RDS sin nueva aprobación**.
- El flujo de datos del MVP sigue íntegro en local: migraciones Alembic + tests de integración reales en CI (Postgres 16 service container) — ya verificado en CDM-22.
- Evita que el saldo de $100 se derrame en una BD antes de desplegar el flujo principal (S3/SQS/Lambda/Cognito que sí son gratis).

## Riesgos

- La demo final con Lambda requiere un mecanismo de acceso a BD — mitigación: ventana RDS temporal con teardown, o ejecutar el worker/API localmente contra AWS (S3/SQS/Cognito reales ya gratis).
- Sincronización de esquema entre local y una futura RDS: Alembic mantiene el mismo ciclo de migraciones — sin trabajo extra.

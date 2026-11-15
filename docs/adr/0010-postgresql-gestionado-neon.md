# ADR-0010: PostgreSQL gestionado en Neon para el entorno desplegado

- **Fecha:** 2026-11-15 · **Estado:** Aceptado · **Jira:** CDM-129, CDM-131
- **Relación:** complementa ADR-0003 y ADR-0008 (RDS sigue diferido; no se reabre).

## Contexto

La API y el worker desplegados en Lambda (`cdm-dev-api`, `cdm-dev-worker`) no tenían base de datos: ADR-0008 dejó PostgreSQL en Docker Compose para desarrollo y difirió RDS por coste (≈ USD 15–20/mes, sin free tier). Con la Lambda fuera de VPC, una base de datos local no es alcanzable y meter la Lambda en una VPC exigiría NAT Gateway (prohibido por AGENTS.md §13) o endpoints VPC con coste para llegar a Cognito JWKS, S3 y SQS.

Para tener el flujo completo funcionando en la nube (CDM-129) hace falta un PostgreSQL alcanzable desde Lambda sin VPC, cifrado en tránsito y sin coste fijo.

## Opciones consideradas

1. **RDS `db.t4g.micro` público con security group abierto** — expone el puerto 5432 a Internet y cuesta ≈ USD 15–20/mes. Descartado.
2. **RDS privado + Lambda en VPC** — requiere NAT Gateway o varios endpoints VPC con coste para JWKS/S3/SQS. Descartado por coste y complejidad.
3. **Neon (PostgreSQL serverless gestionado, plan gratuito)** — PostgreSQL 16 real, TLS obligatorio, autosuspensión (sin coste en reposo), región `aws-us-east-1` junto a la Lambda, pooler de conexiones (PgBouncer) adecuado para Lambda. La organización del propietario ya usa Neon.
4. **Aurora Serverless v2** — coste mínimo por ACU incluso en reposo. Descartado.

## Decisión

- Proyecto Neon `cloud-document-manager-dev` (`round-lab-24970843`), región `aws-us-east-1`, PostgreSQL 16, base de datos `cdm`, rol `cdm_app`.
- Las Lambdas usan el **endpoint con pooler** (`…-pooler…neon.tech`) con `sslmode=require` y `channel_binding=require`; las migraciones Alembic se aplican contra el **endpoint directo** (DDL fuera del pooler).
- La DSN llega a Terraform como variable sensible `database_url` (`TF_VAR_database_url`), validada (driver `postgresql+psycopg` y TLS obligatorio), y a las Lambdas como `CDM_DATABASE_URL`. Nunca se escribe en archivos versionados (`*.tfvars` está en `.gitignore`).
- El código no cambia: la arquitectura hexagonal solo necesita otra DSN (ADR-0003).

## Consecuencias

- Coste USD 0 dentro de los límites del plan gratuito de Neon (almacenamiento y horas de cómputo mensuales); la base de datos se suspende sin uso y la primera petición tras el reposo tarda algo más.
- La DSN queda en el estado local de Terraform y en la configuración cifrada de la Lambda; quien tenga acceso a esos dos sitios puede leerla.
- Un segundo proveedor (Neon) además de AWS: su caída deja la API sin persistencia.

## Riesgos

- **Límites del plan gratuito** (almacenamiento ~0,5 GB por proyecto, horas de cómputo): suficientes para el MVP; vigilar el consumo en la consola de Neon.
- **Secreto en variables de entorno de Lambda:** aceptable para dev; para producción, migrar a SSM Parameter Store (SecureString) o Secrets Manager.
- **Rotación de la contraseña:** rotarla en Neon y volver a aplicar Terraform con la nueva `TF_VAR_database_url`.

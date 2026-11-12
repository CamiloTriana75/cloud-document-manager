# ADR-0003: Estrategia de persistencia PostgreSQL por entorno

- **Fecha:** 2026-11-12 · **Estado:** Aceptado (parcial: producción condicionada a CDM-17) · **Jira:** CDM-11, CDM-15, CDM-17, CDM-21

## Contexto

PostgreSQL es la base de datos acordada. El despliegue en AWS depende de la elegibilidad real de la cuenta (Free Plan/creditos, límites, región) — pendiente de auditar en CDM-17. La regla del proyecto prohíbe crear recursos de coste continuo (RDS incluido) sin estimación y aprobación.

## Opciones consideradas

1. **RDS PostgreSQL directamente** — riesgo de coste continuo sin validación previa; rechazado hasta auditar CDM-17.
2. **DynamoDB u otro almacén no relacional** — cambia el stack acordado y el modelo relacional de memberships/documentos; rechazado.
3. **PostgreSQL en Docker Compose (dev/tests) + decisión de producción diferida a CDM-17** — desarrolla el flujo completo sin coste y sin bloquear el MVP.

## Decisión

- **Desarrollo y pruebas:** PostgreSQL 16 en Docker Compose (CDM-15), con migraciones Alembic reales contra ese motor. Las pruebas de integración corren contra PostgreSQL real, no contra SQLite ni mocks.
- **Producción:** se resolverá con dos salidas posibles tras CDM-17:
  - a) RDS PostgreSQL (instancia mínima, Single-AZ, stop automático fuera de uso) si la elegibilidad/coste lo aprueban;
  - b) Permanecer en local/demo hasta aprobación, sin provisionar nada con coste.
- Conectividad: sin NAT Gateway; si RDS se aprueba, se estudiará acceso vía Lambda dentro de VPC con endpoints necesarios, evaluando coste de cada endpoint antes de crearlo.

## Consecuencias

- El esqueleto completo (API, catálogo, uploads) es demostrable localmente desde el día uno.
- Ningún despliegue de base de datos en la nube hasta tener cifras reales de la cuenta (CDM-17 + presupuesto).
- El código solo conoce la URL de conexión por variable de entorno; el motor y el host no cambian la capa de dominio.
- Riesgo: diferencias operativas RDS vs local (SSL, parámetros); mitigación: configuración por entorno en `config/`, probada antes de cualquier despliegue real.

# ADR-0006: Estrategia multi-tenant y provisión de usuarios

- **Fecha:** 2026-11-12 · **Estado:** Aceptado · **Jira:** CDM-11, CDM-27, CDM-28

## Contexto

Múltiples organizaciones comparten la plataforma. Un error de aislamiento filtra documentos entre clientes: es el fallo más grave posible del producto (prioridad 1 en AGENTS.md §2). También hay que decidir cuándo existe un `UserReference` local.

## Opciones consideradas

1. **Base de datos por tenant (schema o DB separada)** — aislamiento fuerte, pero N conexiones, migraciones × N y coste (RDS múltiple); inviable con restricciones de coste.
2. **Row-level tenancy en tablas compartidas + enforcement en capa de aplicación** — simple, escalable, suficiente con enforcement sistemático y probado.
3. **RLS (Row-Level Security) de PostgreSQL** — defensa extra, pero complica sesiones/roles de conexión y las pruebas con SQLAlchemy; se pospone como endurecimiento futuro.
4. **Tenant por prefijo de bucket** — solo aísla almacenamiento, no metadatos; insuficiente solo.

## Decisión

**Opción 2 + partición de storage, con RLS como candidato de endurecimiento posterior:**

- Tablas compartidas con `workspace_id` obligatorio e indexado en todo dato de tenant.
- **Enforcement en tres capas, sin excepciones:**
  1. Casos de uso: resuelven membership desde JWT (via `cognito_sub`) + DB, nunca desde el cliente.
  2. Repositorios: toda query de documento/miembro lleva `workspace_id` como parámetro obligatorio (API de repositorio que lo exige; imposible consultar "global").
  3. Pruebas: matriz negativa completa por rol y cross-tenant (CDM-28) como gate de CI.
- **S3 particionado por tenant:** `workspaces/{workspace_id}/…` + clave opaca (ADR-0004); el bucket es único.
- **AuditEvent** registra cambios de autorización y ciclo de vida por tenant (sin datos sensibles).

**Provisión de usuarios:**
- El `UserReference` local se crea en el primer acceso con JWT válido (provisión lazy idempotente por `cognito_sub`); no dependemos de triggers de Cognito.
- Invitaciones al workspace: flujo mínimo MVP = `OWNER`/`ADMIN` crea membership `INVITED` con email conocido; el usuario invitado ve el workspace pendiente al iniciar sesión y al aceptar pasa a `ACTIVE`. Los detalles de registro de invitados nuevos (si no tienen cuenta) se refinan en CDM-26 sin bloquear el resto.

## Consecuencias

- Un bug de filtro rompería el aislamiento → la matriz negativa de pruebas es obligatoria y bloquea release (AGENTS.md §15).
- Añadir RLS después es aditivo (no reescribe el modelo); se reevaluará con evidencia (CDM-51).
- La provisión lazy evita polling de Cognito y simplifica el despliegue; requiere índice único en `cognito_sub`.

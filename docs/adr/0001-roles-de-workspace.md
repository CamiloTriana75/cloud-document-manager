# ADR-0001: Modelo de roles del workspace

- **Fecha:** 2026-11-12
- **Estado:** Aceptado (decisión del propietario)
- **Jira:** CDM-1

## Contexto

El charter inicial de CDM-1 describía roles `OWNER/ADMIN/EDITOR/VIEWER`, mientras que AGENTS.md definía `OWNER/ADMIN/MEMBER`. Existía una discrepancia sin resolver que bloqueaba el diseño de la matriz de permisos y las pruebas de aislamiento (CDM-26, CDM-27, CDM-28).

## Opciones consideradas

1. **Mantener `OWNER/ADMIN/MEMBER`** (AGENTS.md original): simple, pero sin rol de solo lectura ni rol intermedio para gestión documental.
2. **`OWNER/ADMIN/EDITOR/VIEWER`** (CDM-1 original): pierde la semántica de `MEMBER` como rol base de carga ya asentada en la documentación.
3. **Modelo de 5 roles con jerarquía** — `VIEWER < MEMBER < EDITOR < ADMIN < OWNER`: conserva `MEMBER`, añade lectura pura y gestión documental intermedia.

## Decisión

Opción 3. Roles del workspace:

| Rol | Capacidades |
|---|---|
| `OWNER` | Control total del workspace y miembros; transferencia/eliminación del workspace. |
| `ADMIN` | Administra miembros, roles y documentos; elimina cualquier documento. |
| `EDITOR` | Todo lo de `MEMBER` + eliminación lógica de documentos + gestión de metadatos. |
| `MEMBER` | Sube, lista, consulta y descarga documentos. |
| `VIEWER` | Solo lectura: catálogo, detalle y descarga. |

## Consecuencias

- La matriz de permisos y las pruebas de aislamiento (CDM-28) deben cubrir los 5 roles, incluidas pruebas negativas (`MEMBER`/`VIEWER` sin capacidades administrativas).
- `VIEWER` no puede iniciar sesiones de carga (opción de producto reversible; reevaluable tras uso real).
- Los checks visuales de rol en Angular son solo UX; la autorización real vive en los casos de uso backend.

## Riesgos

- Cinco roles aumentan la superficie de la matriz de autorización; mitigar con un solo componente de política de permisos reutilizable, sin duplicar lógica.
- Posible solapamiento percibido entre `MEMBER` y `EDITOR` en el MVP (diferencia: eliminación lógica y metadatos); documentar en la UI de administración de miembros.

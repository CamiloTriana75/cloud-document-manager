# Estándar de API — CDM

> Jira: **CDM-16** (CDM-67, CDM-68) · Fecha: 2026-11-12 · Aplica a toda la API pública.
> Fuente rectora: `AGENTS.md` §11 y §14. Contratos exactos: OpenAPI generado por FastAPI (`/docs`).

## 1. Versionado

- Prefijo obligatorio: **`/api/v1`** para todos los endpoints de dominio.
- `GET /health` vive fuera del prefijo (raíz): es de infraestructura, no de la API de dominio.
- Cambios incompatibles ⇒ nueva versión `/api/v2` en paralelo; nunca romper `v1` sin deprecación anunciada.
- La versión del contrato se refleja en `openapi.json` (`info.version`) — mismo ciclo que el release del backend.

## 2. Convenciones de endpoints

| Regla | Ejemplo |
|---|---|
| Sustantivos en plural, kebab-case sin verbos en el path | `POST /api/v1/workspaces/{workspace_id}/upload-sessions` |
| `POST` crea o dispara acciones no idempotentes | crear workspace, iniciar carga |
| `GET` solo lectura, idempotente | listar catálogo, detalle |
| `DELETE` elimina (lógico en CDM) | eliminar documento |
| Acciones sobre un recurso → sub-recurso con verbo en último tramo | `POST …/documents/{id}/download-url` |
| Contexto de tenant **siempre** en el path (`workspace_id`) | nunca por query/body/header |
| IDs en paths: UUID, sin significado semántico | no slugs ni nombres como ID |
| Paginación/filtros por query string | `?limit=25&cursor=…&status=READY` |

## 3. Errores: envelope único y estable

**Toda** respuesta de error (4xx/5xx) usa el mismo envelope — sin `detail` crudo de FastAPI, sin stack traces, sin estructura interna:

```json
{
  "error": {
    "code": "not_found",
    "message": "El recurso solicitado no existe.",
    "details": null
  }
}
```

| Campo | Regla |
|---|---|
| `code` | Estable, `snake_case`, clicable desde el frontend (i18n y decisión de UI). |
| `message` | En español, comprensible, orientado al usuario; **sin** detalles internos (paths, SQL, AWS SDK). |
| `details` | Solo para `validation_error`: lista `{field, message}` con ruta de campo (`body.limit`). |

### Códigos estándar

| `code` | HTTP | Cuándo |
|---|---|---|
| `validation_error` | 422 | Input inválido en el borde (Pydantic/parametría). Incluye `details`. |
| `not_found` | 404 | Recurso inexistente **o** de otro tenant (nunca 403 en cross-tenant: no revelar existencia). |
| `permission_denied` | 403 | Miembro válido sin rol para la acción. |
| `not_a_member` | 403 | Usuario sin membership activa en el workspace. |
| `conflict` | 409 | Estado inválido (ej. `complete` sobre documento ya confirmado). |
| `file_policy_violation` | 413/415 según causa | Formato no permitido o tamaño excedido. |
| `unauthenticated` | 401 | Token ausente/inválido/expirado. |
| `internal_error` | 500 | Fallback. Mensaje genérico; el detalle va a logs, no a la respuesta. |

Reglas de seguridad (AGENTS.md §14):
- Cross-tenant ⇒ `not_found` 404 (jamás confirmar existencia con 403).
- 500 nunca expone excepción, stack ni URL prefirmada.
- Mensajes de 401/403 no distinguen entre "no existe" y "no puedes" más allá de lo necesario.

## 4. Paginación: cursor estable

- Query: `limit` (default `25`, máx `100`, min `1`) + `cursor` (opaco, base64 del último ID ordenado).
- Respuesta:

```json
{
  "items": [ "…recursos…" ],
  "next_cursor": "eyJvZmZzZXQiOiAyNX0="
}
```

- `next_cursor: null` ⇒ última página. El cursor **nunca** usa offset expuesto ni es adivinable como operación de mutación.
- Orden determinista obligatorio (por defecto `created_at DESC, id DESC`) para paginación estable.
- Se prohíbe devolver colecciones sin límite: todo listado usa `PageParams`.

## 5. Validación

- **Borde:** Pydantic valida schemas HTTP (body, query, path). Errores → `validation_error` 422 con `details` por campo.
- **Caso de uso:** re-valida invariantes y permisos; violaciones → errores de dominio tipados mapeados por §3.
- Sin validación duplicada con reglas distintas: una sola definición por restricción.

## 6. Contrato OpenAPI

- FastAPI genera `openapi.json` en `/docs` y `/openapi.json`.
- Todo router declara `tags` (`workspaces`, `documents`, `members`, `health`) y `status_code` explícitos.
- Responses de error documentados vía `responses={…}` con el envelope (se centraliza en un dict compartido `ERROR_RESPONSES`).
- Los tests de contrato (pytest + TestClient) son la barrera: formato de envelope, códigos y paginación se prueban obligatoriamente (CDM-49).

## 7. Headers

- `Authorization: Bearer <JWT>` obligatorio salvo `/health`.
- Respuestas listado no exponen `total` (costoso y filtrable); si un día se necesita, endpoint dedicado o header propio.
- Caché: `Cache-Control: no-store` en todo endpoint autenticado (tokens y datos de tenant).

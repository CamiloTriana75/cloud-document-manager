# Journeys, actores y criterios de éxito del MVP

> Jira: **CDM-10** · Fecha: 2026-11-12 · Estado: Aceptado
> Fuente de verdad complementaria: `AGENTS.md`, `docs/product-charter.md`, `docs/adr/0001-roles-de-workspace.md`.

## 1. Actores

| Actor | Descripción |
|---|---|
| Visitante | Persona sin sesión activa. Solo puede registrarse o iniciar sesión. |
| Usuario autenticado | Identidad validada por Cognito (JWT). Puede pertenecer a 0..n workspaces. |
| Miembro | Usuario autenticado con membership en el workspace activo. Su rol define capacidades (ver §3). |
| Sistema asíncrono | Lambda worker que procesa eventos S3→SQS. No es usuario, no usa la API HTTP. |

Los roles del workspace: `OWNER`, `ADMIN`, `EDITOR`, `MEMBER`, `VIEWER` (ADR-0001). Un mismo usuario puede tener roles distintos en workspaces distintos.

## 2. Journeys

Cada journey indica actor, flujo principal, resultado observable y escenarios alternos/de error. Los IDs se usarán en las pruebas E2E (CDM-50).

### J1 · Registro e inicio de sesión (Cognito)

**Actor:** Visitante.
**Flujo:** registro con email → verificación → inicio de sesión → SPA obtiene tokens → `GET /api/v1/me`.
**Resultado observable:** el usuario ve el selector de workspaces (o vacío si no pertenece a ninguno) con su perfil cargado.
**Alternos/errores:**
- Email ya registrado → mensaje claro, ruta a login.
- Código de verificación incorrecto/expirado → reintento permitido.
- Sesión expirada durante uso → redirección a login sin perder contexto visual.
- JWT inválido/firmado por otro issuer → API responde 401; sin detalles internos.

### J2 · Crear y seleccionar workspace

**Actor:** Usuario autenticado.
**Flujo:** crea workspace (nombre + slug) → queda como `OWNER` con membership `ACTIVE` → workspace queda seleccionado. Alternativa: selecciona un workspace existente de su lista; el backend verifica membership antes de aceptar el cambio de contexto.
**Resultado observable:** la vista principal muestra el nombre del workspace y catálogo vacío (estado vacío accesible).
**Alternos/errores:**
- Slug duplicado → sugerencia de variante.
- Selección de workspace sin membership → 403 del backend; el cliente nunca decide autorización.
- Membership `SUSPENDED` o `INVITED` → no se permite entrar; mensaje explicativo.

### J3 · Carga de documentos (S3 prefirmado)

**Actor:** `MEMBER` o superior.
**Flujo:** selecciona uno o varios archivos (drag-and-drop o picker) → la SPA pide sesión de carga por archivo (`POST …/upload-sessions` con nombre, tamaño, tipo declarado) → backend valida allowlist/tamaño/membership, genera `storage_key` opaca y devuelve URL prefirmada de vida corta + headers exactos → la SPA hace PUT directo a S3 con progreso → al terminar, `POST …/documents/{id}/complete`.
**Resultado observable:** documento visible en el catálogo con estado `UPLOADED`; progreso por archivo y cancelación disponibles.
**Alternos/errores:**
- Formato no permitido o tamaño > límite → rechazo antes de crear la sesión, mensaje por archivo.
- PUT interrumpido/cancelado → la sesión queda expirando; objeto huérfano se limpia por lifecycle (§4); estado no avanza a `UPLOADED`.
- `complete` sin objeto en S3 o tamaño/metadata inconsistentes → `HeadObject` falla o difiere → estado `FAILED`/error comprensible, reintento posible.
- URL prefirmada expirada → nueva sesión de carga, no reutilización de la URL.

### J4 · Procesamiento asíncrono (S3 → SQS → Lambda)

**Actor:** Sistema asíncrono.
**Flujo:** `ObjectCreated` en el bucket → notificación a SQS → worker valida y enriquece metadatos (checksum, tipo real) de forma idempotente → estado `PROCESSING` → `READY`.
**Resultado observable (para el usuario, vía J5):** el documento pasa a `READY`; la SPA hace polling razonable y muestra el cambio de estado.
**Alternos/errores:**
- Evento duplicado → idempotencia: no duplica metadatos ni hace retroceder `READY` → `PROCESSING`.
- Evento de objeto ajeno (borrado externo, otra key) → se ignora con log, sin cambio de estado.
- Fallo de procesamiento tras reintentos → mensaje a DLQ; documento en `FAILED` con causa registrada sin datos sensibles.

### J5 · Consulta del catálogo y detalle

**Actor:** Miembro (cualquier rol).
**Flujo:** listado paginado con búsqueda por nombre y filtros (estado, tipo, rango de fechas) → detalle con metadatos, estado de procesamiento e historial visible.
**Resultado observable:** catálogo con paginación estable; detalle muestra `status`, tamaño, tipo, checksum (cuando exista), quién y cuándo subió.
**Alternos/errores:**
- Documento de otro workspace → no aparece nunca (query filtrado por `workspace_id` autorizado; nunca "cargar y comprobar después").
- Página/filtro inválido → 422 con mensaje claro; sin listados no acotados.
- Documento `DELETED` → excluido del catálogo; acceso directo devuelve 404 sin revelar existencia.

### J6 · Descarga autorizada

**Actor:** Miembro (cualquier rol).
**Flujo:** botón "Descargar" en detalle → `POST …/documents/{id}/download-url` → backend autoriza membership+rol → URL temporal de un solo objeto → la SPA abre la descarga.
**Resultado observable:** el navegador descarga el archivo con su nombre original saneado.
**Alternos/errores:**
- Sin membership activa → 403, sin enumerar si el documento existe en otro tenant.
- URL expirada → solicitar otra; la URL no da acceso a ningún otro objeto.
- Objeto ausente en S3 → 409/404 consistente con el estado del documento.

### J7 · Eliminación lógica

**Actor:** `EDITOR` o superior.
**Flujo:** acción "Eliminar" → confirmación destructiva explícita (nombre del documento) → `DELETE …/documents/{id}` → backend autoriza rol → `deleted_at` + estado `DELETED` de forma transaccional.
**Resultado observable:** desaparece del catálogo; el objeto S3 se retiene para borrado físico controlado posterior (fuera del flujo de usuario).
**Alternos/errores:**
- `MEMBER`/`VIEWER` intenta eliminar → 403 y botón no visible (UX, no seguridad).
- Documento ya `DELETED` → 404 idempotente, sin doble borrado.
- Confirmación cancelada → sin cambios.

## 3. Matriz de permisos (MVP)

| Operación | OWNER | ADMIN | EDITOR | MEMBER | VIEWER |
|---|:---:|:---:|:---:|:---:|:---:|
| Crear workspace (se convierte en OWNER) | ✓ | ✓ | ✓ | ✓ | ✓ |
| Ver workspace propio / catálogo / detalle | ✓ | ✓ | ✓ | ✓ | ✓ |
| Descargar documentos | ✓ | ✓ | ✓ | ✓ | ✓ |
| Subir documentos | ✓ | ✓ | ✓ | ✓ | — |
| Editar metadatos de documentos | ✓ | ✓ | ✓ | — | — |
| Eliminar lógicamente documentos | ✓ | ✓ | ✓ | — | — |
| Listar miembros | ✓ | ✓ | ✓ | — | — |
| Invitar / gestionar miembros y roles | ✓ | ✓ | — | — | — |
| Transferir / eliminar workspace | ✓ | — | — | — | — |

Notas:
- La matriz es la base de las pruebas de aislamiento (CDM-28): cada ✗ es una prueba negativa obligatoria.
- Toda operación exige membership `ACTIVE` en el workspace del documento; el rol enviado por el cliente no es prueba de nada.
- "Crear workspace" es capacidad del usuario autenticado, no del rol (no hay rol aún en ese momento).

## 4. Límites iniciales del MVP (propuesta reversible)

> Supuestos acordados por defecto, documentados por AGENTS.md §18 (decisión pequeña y reversible). Cualquier cambio se registra aquí y en ADR si afecta seguridad.

| Límite | Valor propuesto | Justificación |
|---|---|---|
| Formatos admitidos | `pdf`, `png`, `jpg`/`jpeg`, `docx`, `xlsx`, `txt`, `csv`, `md` | Allowlist explícita por extensión **y** validación real de contenido en el worker; nunca solo Content-Type del navegador. |
| Tamaño máximo por archivo | 50 MB | Controlable vía variable de entorno; margen cómodo dentro del Free Plan de S3. |
| Expiración de sesión de carga | 30 min | URLs prefirmadas de vida corta (≤ 15 min dentro de ese margen). |
| Retención de objetos huérfanos | Prefijo `staging/` con lifecycle de borrado a los 7 días | Limpia cargas incompletas sin tocar documentos confirmados. |
| Borrado físico de documentos | Fuera del flujo de usuario; proceso controlado posterior (CDM-34/CMD-53) | La eliminación del MVP es lógica. |
| Volumen de prueba del MVP | ≤ 200 documentos y ≤ 500 MB por workspace de prueba | Mantiene el costo y las pruebas dentro del Free Plan. |
| Paginación | ≤ 100 ítems/página, cursor estable | Previene enumeración y respuestas no acotadas. |

## 5. Fuera de alcance

Explícito en `docs/product-charter.md` §4 (CDM-1): OCR avanzado, antivirus comercial, edición colaborativa, firma electrónica, versionado binario avanzado, app móvil, facturación SaaS, migración masiva.

# Rediseño visual de la UI Angular — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rediseñar todas las pantallas de `apps/web` con el lenguaje visual aprobado (oscuro verde-azulado, glass, acento naranja, escena 3D) sobre un design system compartido, corrigiendo los defectos detectados.

**Architecture:** Estilos globales por capas (`fonts → tokens → base → components`) + componentes `shared/ui` con comportamiento (icono, diálogo, menú, pestañas-carpeta, visualizaciones) + estado de página en stores con señales. La escena 3D vive en un chunk diferido (`three`). Los datos del dashboard salen solo de `GET /documents` con filtros exactos.

**Tech Stack:** Angular 22 (standalone, zoneless, señales), RxJS 7.8, Vitest + jsdom, Playwright, pnpm, `three` (nuevo, diferido).

**Spec:** `docs/superpowers/specs/2026-11-13-ui-redesign-design.md`

## Global Constraints

- Solo tema oscuro. Paleta base: lienzo `#0d1e20`, panel `#14292a`, tarjeta `#263b3c`, tarjeta elevada `#3e5858`, pista `#365958`, acento `#fa7752` (texto oscuro encima), positivo `#7cfb81`, bobina `#469385`.
- Contraste AA: texto normal ≥ 4.5:1, texto grande/UI ≥ 3:1, verificado por cálculo y registrado en `docs/architecture/design-system.md`.
- Tipografía Geist + Geist Mono servidas desde `public/fonts/` (OFL), sin CDN.
- Sin datos inventados en KPIs/Actividad; sin botones de funciones inexistentes; sin IA.
- Sin cambios en backend ni contratos de API. Filtros de tipo con MIME exactos de `apps/api/src/cdm/domain/file_policy.py`.
- `three` solo en chunk diferido; bundle inicial < 500 kB (aviso del builder); estilos por componente < 16 kB.
- Todo movimiento se desactiva con `prefers-reduced-motion: reduce`.
- Componentes: `ChangeDetectionStrategy.OnPush`, `input()/output()`, `host: {}` en lugar de `@HostListener`, sin `CommonModule` (importar pipes sueltos).
- Textos de UI en español; nombres de código en inglés.
- Commits `tipo(scope): descripción (CDM-XXX)` con trailer `Co-Authored-By`.

## Review Focus

1. **Búsqueda rápida con respuestas desordenadas** — teclear "rep" y luego "reporte": solo debe mostrarse el resultado de la última búsqueda. Test en Task 3.2 (`switchMap` cancela la petición previa).
2. **Workspace sin documentos** — KPIs en 0 sin dividir entre cero (porcentajes 0 %), sparkline vacía y estado vacío con CTA solo si el rol puede subir. Tests en Task 3.1 y 3.3.
3. **Más de 100 cargas en 7 días** — la sparkline se oculta en lugar de mostrar un dato parcial. Test en Task 3.1.
4. **Soltar varios archivos con uno inválido** — los válidos se suben y el inválido queda "rechazado" con su motivo, sin bloquear la cola. Test en Task 4.1.
5. **Rol VIEWER** — no ve CTA de carga, zona de soltar ni acciones de borrado; el aviso de solo lectura es visible. Tests en Task 3.3 y 4.2.

---

## Estructura de archivos

```
apps/web/
├── public/fonts/                         Geist-Variable.woff2, GeistMono-Variable.woff2, OFL.txt
├── src/styles.css                        solo @import de las capas
├── src/styles/{fonts,tokens,base,components}.css
└── src/app/
    ├── app.{ts,html,css,spec.ts}          shell
    ├── layout/workspace-switcher/         menú de workspaces (reemplaza core/workspaces/workspace-selector.*)
    ├── layout/user-menu/                  avatar + menú de usuario
    ├── core/browser/page-visibility.service.ts
    ├── core/documents/document-status.ts  metadatos de estado, carpetas, opciones de tipo
    ├── core/documents/file-kind.ts        MIME → tipo visual (icono)
    ├── core/documents/upload-policy.ts    validación de archivo
    ├── core/documents/document-stats.service.ts
    ├── core/documents/upload-queue.service.ts
    ├── shared/format/{format-bytes,format-date}.ts + pipes
    ├── shared/ui/icon/                    registro tipado + componente
    ├── shared/ui/dialog/                  <dialog> nativo (reemplaza shared/ui/modal)
    ├── shared/ui/menu/                    menú accesible + directiva de ítem
    ├── shared/ui/folder-tabs/
    ├── shared/ui/kpi-card/, segmented-bar/, sparkline/, role-ladder/
    ├── shared/ui/empty-state/, avatar/
    ├── shared/ui/coil-scene/              componente + coil-geometry.ts + coil-renderer.ts (three)
    ├── shared/ui/{alert,spinner,status-badge,role-badge,form-field}/  reestilizados
    └── pages/
        ├── home/                          landing + lanzador
        ├── documents/catalog/             página + catalog.store.ts + components/{document-table,activity-panel,document-detail}
        ├── documents/upload/
        ├── workspaces/{create,members}/
        └── auth/{auth-layout,login,register,confirm}/
docs/adr/0009-escena-3d-three-js.md
docs/architecture/design-system.md
```

---

## Fase 1 — Fundamentos (CDM-107, CDM-108)

### Task 1.1: Fuentes, tokens, base y clases globales

**Files:**
- Create: `apps/web/public/fonts/Geist-Variable.woff2`, `GeistMono-Variable.woff2`, `OFL.txt` (del paquete npm `geist`, extraído en scratchpad, sin añadir dependencia)
- Create: `apps/web/src/styles/fonts.css`, `tokens.css`, `base.css`, `components.css`
- Modify: `apps/web/src/styles.css` (solo `@import`), `apps/web/src/index.html` (preload de fuentes, `theme-color`)
- Create: `docs/architecture/design-system.md` (tokens + tabla de contraste)

**Interfaces — Produces:** custom properties `--color-{canvas,panel,card,card-raised,track,border,border-strong,text,text-secondary,text-tertiary,accent,accent-hover,on-accent,positive,warning,danger,info,focus}` y `--color-*-soft`; `--space-{1..16}`, `--radius-{xs,sm,md,lg,pill}`, `--font-{sans,mono}`, `--text-{xs,sm,md,base,lg,xl,2xl,metric,display}`, `--duration-{fast,base}`, `--ease-out`, `--shadow-{panel,popover}`, `--layout-max`, `--header-height`, `--z-{header,popover,dialog,toast}`. Clases: `.btn`, `.btn--primary|secondary|ghost|danger|icon|sm`, `.field`, `.field__label|hint|error`, `.input`, `.select`, `.chip`, `.chip--active`, `.surface-card`, `.surface-panel`, `.eyebrow`, `.display-title`, `.section-title`, `.data-table`, `.skeleton`, `.mono`, `.tabular`, `.sr-only`, `.skip-link`, `.page`, `.page__hero`.

- [ ] Step 1: Script de contraste en scratchpad (Node) que calcule ratios WCAG de cada par texto/fondo de los tokens; ajustar `--color-text-secondary` y `--color-text-tertiary` hasta cumplir (secundario ≥ 4.5 sobre `card`; terciario solo para texto ≥ 18.66px o UI ≥ 3:1).
- [ ] Step 2: Escribir las cuatro capas y `styles.css`; registrar ratios en `design-system.md`.
- [ ] Step 3: `pnpm exec ng build` → sin errores ni avisos de presupuesto; `pnpm exec ng test --no-watch` → 100/100 (el markup aún no cambia).
- [ ] Step 4: Commit `feat(web): tokens, tipografía y estilos base del design system (CDM-107)`.

### Task 1.2: Icono tipado

**Files:** Create `shared/ui/icon/icons.ts`, `shared/ui/icon/icon.ts`, `shared/ui/icon/icon.spec.ts`

**Interfaces — Produces:** `type IconName` (unión literal), `type IconNode = readonly ['path'|'circle'|'line'|'polyline'|'rect', Readonly<Record<string, string | number>>]`, `ICONS: Record<IconName, readonly IconNode[]>`; `IconComponent` (`app-icon`): `name = input.required<IconName>()`, `size = input(18)`, `strokeWidth = input(1.75)`; host `aria-hidden="true"`, sin `innerHTML`.

- [ ] Step 1: Tests: `renders one svg child per node of ICONS['upload']`; `applies size to width/height`; `host is aria-hidden`.
- [ ] Step 2: Run → FAIL (componente inexistente).
- [ ] Step 3: Implementar registro (estilo Lucide, viewBox 24) con los iconos usados por las pantallas y componente con `@for`/`@switch` sobre `svg:*`.
- [ ] Step 4: Run → PASS. Commit `feat(web): componente de iconos tipado sin innerHTML (CDM-108)`.

### Task 1.3: Formato, estados y política de archivos

**Files:** Create `shared/format/format-bytes.ts`, `format-date.ts`, `bytes.pipe.ts`, `date-time.pipe.ts`, `relative-time.pipe.ts` (+ `format.spec.ts`); `core/documents/document-status.ts`, `file-kind.ts`, `upload-policy.ts` (+ specs); `core/browser/page-visibility.service.ts` (+ spec)

**Interfaces — Produces:**
- `formatBytes(bytes: number): string` — `0 → '0 B'`, `1536 → '1.5 KB'`, `52428800 → '50 MB'`.
- `formatDateTime(iso: string): string` (es-CO, `dateStyle: 'medium', timeStyle: 'short'`), `formatRelativeTime(iso: string, now?: Date): string` (`Intl.RelativeTimeFormat('es', { numeric: 'auto' })`), `shortId(id: string): string` (8 primeros caracteres).
- Pipes `bytes`, `dateTime`, `relativeTime`.
- `type StatusTone = 'positive'|'accent'|'info'|'warning'|'danger'|'neutral'`; `DOCUMENT_STATUS_META: Record<DocumentStatus, { label: string; tone: StatusTone; step: 0|1|2|3; inFlight: boolean }>` con etiquetas Pendiente/Subido/Procesando/Listo/Fallido/Eliminado; `type StatusFilter = 'ALL' | DocumentStatus`; `STATUS_FOLDERS` = Todos, Listos, Procesando, Pendientes, Fallidos; `DOCUMENT_TYPE_OPTIONS: readonly { label: string; value: string | null }[]` con los 9 MIME exactos del backend; `isInFlight(status): boolean` (UPLOADED, PROCESSING).
- `type FileKind = 'pdf'|'image'|'document'|'spreadsheet'|'text'|'data'|'other'`; `fileKind(contentType: string): FileKind`; `FILE_KIND_ICON: Record<FileKind, IconName>`.
- `validateUploadFile(file: File): string | null` (mensajes actuales de `upload.ts`); añadir `.markdown` a `ALLOWED_UPLOAD_EXTENSIONS` (paridad con backend).
- `PageVisibilityService.visible: Signal<boolean>` (escucha `visibilitychange`).

- [ ] Step 1: Tests de cada función con los valores de arriba; `validateUploadFile` para extensión no permitida, 0 bytes, > 50 MB y válido; `isInFlight`; `fileKind('application/pdf') === 'pdf'`, `fileKind('image/png') === 'image'`.
- [ ] Step 2: Run → FAIL. Step 3: implementar. Step 4: Run → PASS.
- [ ] Step 5: Commit `feat(web): formato, metadatos de estado y política de carga compartidos (CDM-108)`.

### Task 1.4: Visualizaciones (KPI, barra segmentada, sparkline, escalera de rol)

**Files:** Create `shared/ui/{segmented-bar,sparkline,kpi-card,role-ladder}/*.ts` + specs

**Interfaces — Produces:**
- `SegmentedBarComponent` (`app-segmented-bar`): `segments = input.required<readonly { value: number; tone: StatusTone; label: string }[]>()`, `label = input.required<string>()`; `role="img"` con `aria-label` = label + "label: N%"; anchos proporcionales; total 0 → solo pista.
- `SparklineComponent` (`app-sparkline`): `points = input.required<readonly number[]>()`, `label = input.required<string>()`; SVG `viewBox 0 0 100 32`, línea + área; todos 0 → línea plana en la base.
- `KpiCardComponent` (`app-kpi-card`): `label`, `value: string | number`, `unit?`, `caption?`, `captionTone: 'positive'|'neutral' = 'neutral'`, `highlighted = false`, `loading = false`; slot `[kpiVisual]`.
- `RoleLadderComponent` (`app-role-ladder`): `role = input.required<WorkspaceRole>()`; 5 segmentos VIEWER→OWNER, llenos hasta el nivel; texto "Tu rol" + rol; `role="img"` con `aria-label="Rol EDITOR, nivel 3 de 5"`.

- [ ] Step 1: Tests: proporciones (`[1,1,2]` → 25/25/50 %), aria-labels, sparkline con 7 puntos genera path con 7 vértices, ladder EDITOR → 3 segmentos activos, KPI `loading` muestra skeleton y oculta valor.
- [ ] Step 2: FAIL → Step 3: implementar → Step 4: PASS.
- [ ] Step 5: Commit `feat(web): componentes de visualización para KPIs y roles (CDM-108)`.

### Task 1.5: Interacción (diálogo, menú, pestañas-carpeta)

**Files:** Create `shared/ui/dialog/*`, `shared/ui/menu/*`, `shared/ui/folder-tabs/*` + specs. Delete `shared/ui/modal/*`.

**Interfaces — Produces:**
- `DialogComponent` (`app-dialog`): `open = input(false)`, `variant = input<'modal'|'drawer'>('modal')`, `label = input<string|null>(null)`, `labelledBy = input<string|null>(null)`, `closed = output<void>()`. `showModal()` si existe (fallback atributo `open` en jsdom); Esc (`cancel`) y clic en backdrop emiten `closed`; al cerrar devuelve el foco al elemento previo.
- `MenuComponent` (`app-menu`): `label = input.required<string>()`, `align = input<'start'|'end'>('end')`, `open: WritableSignal<boolean>`, `close(): void`; trigger con `aria-haspopup="menu"`, `aria-expanded`, contenido `[menuTrigger]`. `MenuItemDirective` (`[appMenuItem]`): `role` `menuitem`/`menuitemradio`, `checked = input<boolean|null>(null)`, `tabindex=-1`. Teclado: ↓/↑ cíclico, Home/End, Esc cierra y enfoca trigger, Tab cierra; clic fuera cierra; al abrir enfoca el primer ítem.
- `FolderTabsComponent` (`app-folder-tabs`): `tabs = input.required<readonly { id: string; label: string; count: number | null }[]>()`, `active = input.required<string>()`, `controls = input.required<string>()`, `activeChange = output<string>()`; `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls`, roving tabindex con ←/→/Home/End.

- [ ] Step 1: Tests: diálogo abre/cierra y emite en Esc; menú abre con clic, ↓ mueve foco, Esc cierra y devuelve foco; pestañas ← → cambian foco y Enter/clic emiten `activeChange`.
- [ ] Step 2: FAIL → Step 3: implementar → Step 4: PASS.
- [ ] Step 5: Commit `feat(web): diálogo nativo, menú y pestañas accesibles (CDM-108)`.

### Task 1.6: Reestilizar componentes existentes y completar catálogo de UI

**Files:** Modify `shared/ui/{alert,spinner,status-badge,role-badge,form-field}/*`; Create `shared/ui/empty-state/*`, `shared/ui/avatar/*`; Modify `docs/architecture/design-system.md` (API de componentes).

**Interfaces — Produces:** `StatusBadgeComponent` (`app-status-badge`, `status` input) conserva clases `doc-status-<status>` (E2E) y muestra 3 puntos según `step`; `RoleBadgeComponent` conserva `role-<role>`; `AlertComponent` usa `app-icon`; `EmptyStateComponent` (`icon`, `title`, `description`, acciones proyectadas); `AvatarComponent` (`name`, `size = 32`) con iniciales.

- [ ] Step 1: Ajustar specs existentes a los nuevos íconos/markup; tests nuevos para empty-state y avatar ("Ana María" → "AM").
- [ ] Step 2: Implementar; `ng test` en verde; `ng lint` limpio.
- [ ] Step 3: Commit `refactor(web): reestilizar componentes compartidos con el design system (CDM-108)`.

---

## Fase 2 — Shell y escena 3D (CDM-122)

### Task 2.1: Escena 3D diferida + ADR-0009

**Files:** Create `shared/ui/coil-scene/{coil-geometry.ts,coil-geometry.spec.ts,coil-renderer.ts,coil-scene.ts,coil-scene.spec.ts}`, `docs/adr/0009-escena-3d-three-js.md`; Modify `docs/adr/README.md`, `apps/web/package.json` (`three`, `@types/three` dev, versiones exactas).

**Interfaces — Produces:**
- `ringPlacements(count: number, majorRadius: number): { angle: number; position: [number, number, number] }[]` — anillos equiespaciados sobre la circunferencia.
- `createCoilRenderer(canvas: HTMLCanvasElement, options: { ringCount: number; maxPixelRatio: number; animate: boolean }): CoilRenderer` con `start()`, `stop()`, `renderOnce()`, `resize(width: number, height: number)`, `dispose()`. `InstancedMesh` de arandelas (LatheGeometry de perfil redondeado), `MeshPhysicalMaterial` teal metálico con clearcoat, `RoomEnvironment` + PMREM, ACES, fondo transparente.
- `CoilSceneComponent` (`app-coil-scene`): `variant = input<'hero'|'ambient'>('hero')`; importa `./coil-renderer` en `afterNextRender` solo si hay WebGL2; `IntersectionObserver` + `PageVisibilityService` para `start/stop`; reduced motion → `renderOnce()`; sin WebGL → `.coil-fallback` (gradientes CSS); `dispose()` en destroy; `aria-hidden="true"`.

- [ ] Step 1: Tests: `ringPlacements(4, 2)` devuelve ángulos 0, π/2, π, 3π/2 y radios 2; en jsdom (sin WebGL) el componente muestra fallback y no crea renderer.
- [ ] Step 2: FAIL → Step 3: implementar (versión de `three` estable fijada, con fecha > 2 semanas) → Step 4: PASS.
- [ ] Step 5: `ng build` → `three` aparece solo en un lazy chunk; inicial < 500 kB. Captura Playwright de la escena aislada comparada con la referencia.
- [ ] Step 6: Commit `feat(web): escena 3D diferida con three.js y ADR-0009 (CDM-122)`.

### Task 2.2: Shell (header, selector de workspace, menú de usuario, drawer)

**Files:** Modify `app.{ts,html,css,spec.ts}`; Create `layout/workspace-switcher/*`, `layout/user-menu/*`; Delete `core/workspaces/workspace-selector.*`.

**Interfaces — Consumes:** `MenuComponent`, `MenuItemDirective`, `DialogComponent`, `IconComponent`, `AvatarComponent`, `RoleBadgeComponent`. **Produces:** `WorkspaceSwitcherComponent` (`app-workspace-switcher`) — carga workspaces al iniciar si hay sesión, ítems `menuitemradio`, acciones "Miembros y roles" y "Nuevo workspace", navegación al cambiar conserva la sección actual; `UserMenuComponent` (`app-user-menu`) — nombre, correo, rol activo, botón "Cerrar sesión" (`(logout)` output). `App` mantiene `isMobileMenuOpen`, `toggleMobileMenu()`, `closeMobileMenu()`, `onLogout()`.

- [ ] Step 1: Actualizar `app.spec.ts`: marca con "Cloud Document Manager"; nav con Inicio/Documentos/Cargar/Miembros; menú de usuario abre y su botón "Cerrar sesión" ejecuta logout y navega a `/auth/login`; drawer móvil abre/cierra (Esc). Specs nuevos del switcher (selección cambia workspace activo y ruta).
- [ ] Step 2: FAIL → Step 3: implementar header transparente sobre el hero (nav central con subrayado activo `aria-current="page"`) → Step 4: PASS.
- [ ] Step 5: E2E `auth-journey` (banner, "Cerrar sesión") ajustado al menú; `pnpm e2e` del journey → PASS.
- [ ] Step 6: Commit `feat(web): shell con navegación central, selector de workspace y menú de usuario (CDM-122)`.

---

## Fase 3 — Dashboard de documentos (CDM-123)

### Task 3.1: Estadísticas del workspace

**Files:** Create `core/documents/document-stats.service.ts` + spec

**Interfaces — Produces:** `type CountedStatus = 'READY'|'PROCESSING'|'UPLOADED'|'PENDING_UPLOAD'|'FAILED'`; `interface DocumentStats { total: number; byStatus: Record<CountedStatus, number>; lastWeek: number; dailyUploads: readonly number[] | null }`; `DocumentStatsService.load(workspaceId: string, now?: Date): Observable<DocumentStats>` — 5 peticiones `limit=1&status=X` + 1 `created_after=now-7d&limit=100`, en paralelo; `total` = suma; `lastWeek` = total de la ventana; `dailyUploads` = `bucketByDay(...)` o `null` si la ventana > 100. `bucketByDay(createdAt: readonly string[], now: Date, days = 7): number[]` (más antiguo → hoy, días locales).

- [ ] Step 1: Tests con `HttpTestingController`: 6 peticiones con los parámetros exactos; suma correcta; `dailyUploads` null con total 101; workspace vacío → todo 0 y 7 ceros.
- [ ] Step 2: FAIL → Step 3: implementar → Step 4: PASS. Commit `feat(web): estadísticas del workspace desde la API de catálogo (CDM-123)`.

### Task 3.2: Store del catálogo

**Files:** Create `pages/documents/catalog/catalog.store.ts` + spec

**Interfaces — Consumes:** `DocumentService.listDocuments`, `DocumentStatsService.load`. **Produces:** `CatalogStore` (provider de componente) con señales `workspaceId`, `documents`, `total`, `loading`, `refreshing`, `error`, `status: StatusFilter`, `contentType: string | null`, `searchInput`, `page`, `pageSize` (25; opciones 10/25/50), `sort: { column: SortColumn; direction: 'asc'|'desc' }`, `stats: DocumentStats | null`, `recent: DocumentItem[]`; computados `sortedDocuments` (orden de la página actual), `totalPages`, `rangeStart`, `rangeEnd`, `hasNext`, `hasPrev`, `hasActiveFilters`, `inFlight` (alguno UPLOADED/PROCESSING en `recent` ∪ `documents`); métodos `init(workspaceId)`, `setStatus`, `setContentType`, `setSearch` (debounce 300 ms), `clearSearch` (inmediato), `resetFilters`, `setPage`, `setPageSize`, `toggleSort`, `refresh({ silent })`, `upsert(doc)`, `remove(id)`, `poll()` (refresca página + recientes y recarga `stats` solo si cambió algún par id/estado). `SortColumn = 'original_filename'|'content_type'|'size_bytes'|'created_at'|'status'`.

- [ ] Step 1: Tests (fakeAsync o timers de Vitest): `setSearch('re'); setSearch('reporte')` → una sola petición con `search=reporte` tras 300 ms; respuesta tardía de una petición cancelada no sobrescribe; cambiar filtro vuelve a página 1; `poll()` sin cambios de estado no recarga stats y con cambio sí.
- [ ] Step 2: FAIL → Step 3: implementar con `Subject` + `switchMap` + `takeUntilDestroyed` → Step 4: PASS. Commit `feat(web): store del catálogo con búsqueda diferida y cancelación (CDM-123)`.

### Task 3.3: Página del dashboard

**Files:** Modify `pages/documents/catalog/catalog.{ts,html,css,spec.ts}`; Create `pages/documents/catalog/components/{document-table,activity-panel,document-detail}/*` + specs; Modify `e2e/document-catalog-and-actions-journey.spec.ts`, `e2e/fixtures/mock-api.ts` (leer `search`, respetar `limit`).

**Interfaces — Consumes:** `CatalogStore`, `UploadQueueService.enqueue` (Task 4.1; hasta entonces la zona de soltar navega a `/upload`), componentes de Fase 1, `CoilSceneComponent`. **Produces:**
- `DocumentTableComponent`: inputs `documents`, `sort`, `canDelete`, `canRetry`, `busyId`; outputs `sortChange`, `openDetail`, `download`, `retry`, `remove`. Tabla `aria-label="Lista de documentos del espacio"`, `aria-sort` en `th`, botón de detalle con nombre accesible "Ver detalle técnico del documento", menú "Más acciones".
- `ActivityPanelComponent`: inputs `recent`, `uploads`, `canUpload`; outputs `filesDropped: File[]`, `openDocument`.
- `DocumentDetailComponent` (contenido del drawer): input `document`, permisos, `busyId`; outputs `download`, `retry`, `remove`, `close`; título `h2` = nombre del archivo, sección "Metadatos Técnicos (JSONB)", línea de tiempo por `step`.
- Página: hero (eyebrow "Documentos", `h1` = nombre del workspace, ID corto, slug, `app-role-ladder`), `app-coil-scene`, `app-folder-tabs` (`controls="catalog-panel"`), 3 `app-kpi-card` (Documentos + sparkline; Listos %; Pipeline con barra segmentada), tarjeta con `h2` "Catálogo de documentos", chips (tipo con `DOCUMENT_TYPE_OPTIONS`, búsqueda `placeholder="Buscar documento por nombre..."`, botón "Limpiar búsqueda"), tabla, paginación, Actividad, aviso VIEWER ("Navegando con rol VIEWER…"), drawer de detalle (`app-dialog variant="drawer"`, botón "Cerrar detalle"), confirmación (`h2` "¿Eliminar documento?", "Sí, eliminar"). Descarga con `window.open(url, '_blank', 'noopener,noreferrer')`. Polling cada 5 s con pestaña visible y `inFlight()`.

- [ ] Step 1: Reescribir `catalog.spec.ts` sobre el nuevo markup: render de KPIs con stats mock, cambio de carpeta llama `setStatus`, VIEWER sin CTA/acciones, workspace vacío muestra estado vacío, error muestra alerta con "Reintentar". Specs de los tres subcomponentes.
- [ ] Step 2: FAIL → Step 3: implementar → Step 4: PASS (`ng test`).
- [ ] Step 5: Ajustar E2E y fixture; `pnpm e2e` (catálogo) → PASS. Captura vs referencia.
- [ ] Step 6: Commit(s) `feat(web): dashboard de documentos con carpetas, KPIs y actividad (CDM-123)`.

---

## Fase 4 — Carga multi-archivo (CDM-124)

### Task 4.1: Cola de carga

**Files:** Create `core/documents/upload-queue.service.ts` + spec

**Interfaces — Consumes:** `DocumentService.uploadWithProgress`, `DocumentService.getDocument`, `validateUploadFile`. **Produces:** `type QueuePhase = 'queued'|'rejected'|UploadPhase`; `interface UploadQueueItem { id: string; workspaceId: string; file: File; phase: QueuePhase; progress: number; loadedBytes: number; error: string | null; documentId: string | null; documentStatus: DocumentStatus | null }`; `UploadQueueService` (root): `items: Signal<readonly UploadQueueItem[]>`, `itemsFor(workspaceId): Signal<readonly UploadQueueItem[]>`, `activeCount`, `enqueue(workspaceId, files)`, `cancel(id)`, `retry(id)`, `remove(id)`, `clearFinished(workspaceId)`; `MAX_CONCURRENT_UPLOADS = 2`; tras `completed`, consulta el documento cada 2.5 s (máx. 8) hasta READY/FAILED.

- [ ] Step 1: Tests: 3 archivos válidos → solo 2 en curso; uno inválido queda `rejected` con mensaje y no bloquea; `cancel` deja `cancelled` y arranca el siguiente; `retry` vuelve a `queued`.
- [ ] Step 2: FAIL → Step 3: implementar → Step 4: PASS. Commit `feat(web): cola de carga con concurrencia limitada (CDM-124)`.

### Task 4.2: Página de carga + zona de Actividad conectada

**Files:** Modify `pages/documents/upload/upload.{ts,html,css,spec.ts}`, `pages/documents/catalog/catalog.ts` (soltar → `enqueue`), `e2e/document-upload-journey.spec.ts`

**Interfaces — Consumes:** `UploadQueueService`, `CoilSceneComponent`, componentes de Fase 1. **Produces:** dropzone `role="region"` con nombre "Zona de carga de archivos…", input `#file-upload-input` `multiple`, texto "Formatos admitidos: PDF, PNG, JPG, TXT, MD, CSV, JSON, DOCX, XLSX (Máximo 50 MB)", lista de cola con `role="progressbar"` por archivo, acciones Cancelar/Reintentar/Quitar/"Ver en el catálogo", aviso VIEWER "Permiso insuficiente para carga".

- [ ] Step 1: Reescribir `upload.spec.ts` (encola al seleccionar, VIEWER deshabilitado, progreso visible, rechazo visible).
- [ ] Step 2: FAIL → Step 3: implementar → Step 4: PASS; E2E de carga ajustado → PASS.
- [ ] Step 5: Commit `feat(web): carga multi-archivo con progreso por archivo (CDM-124)`.

---

## Fase 5 — Inicio (CDM-125)

### Task 5.1: Landing y lanzador

**Files:** Modify `pages/home/home.{ts,html,css,spec.ts}`

**Interfaces — Produces:** sin sesión: hero con `app-coil-scene`, `h1` de propuesta de valor, CTA "Crear cuenta" / "Iniciar sesión", tres tarjetas (carga directa a S3, aislamiento por workspace, procesamiento asíncrono) y píldora de estado de API (`HealthService`, reintento). Con sesión: `h1` "Hola, {nombre}", tarjetas de workspace (nombre, `app-role-ladder`, slug, fecha) que activan el workspace y navegan a documentos, tarjeta "Nuevo workspace".

- [ ] Step 1: Ajustar `home.spec.ts` (estado API ok/error, lanzador lista workspaces, clic activa y navega). FAIL → implementar → PASS.
- [ ] Step 2: Commit `feat(web): landing pública y lanzador de workspaces (CDM-125)`.

---

## Fase 6 — Miembros y crear workspace (CDM-126)

### Task 6.1: Miembros

**Files:** Modify `pages/workspaces/members/members.{ts,html,css,spec.ts}`

**Interfaces — Produces:** hero (eyebrow "Miembros", `h1` "Miembros de {workspace}"), resumen (total, admins), tarjeta "Invitar a un nuevo miembro" (OWNER/ADMIN; `#member-email`, `#member-role`, botón "Agregar miembro"), tabla con `app-avatar`, `app-role-badge`, estado; quitar la rama muerta de `availableRoles`.

- [ ] Step 1: Ajustar spec → FAIL → implementar → PASS. Commit `feat(web): página de miembros con el nuevo sistema visual (CDM-126)`.

### Task 6.2: Crear workspace

**Files:** Modify `pages/workspaces/create/create.{ts,html,css,spec.ts}`

**Interfaces — Produces:** `h1` "Crear espacio de trabajo", `#ws-name`, `#ws-slug`, vista previa del slug, mensajes de error actuales, botón "Crear espacio de trabajo".

- [ ] Step 1: Ajustar spec → FAIL → implementar → PASS; E2E `workspace-management-journey` → PASS.
- [ ] Step 2: Commit `feat(web): creación de workspace con vista previa de slug (CDM-126)`.

---

## Fase 7 — Autenticación (CDM-127)

### Task 7.1: Layout de auth, login, registro y confirmación

**Files:** Create `pages/auth/auth-layout/auth-layout.ts`; Modify `pages/auth/{login,register,confirm}/*`

**Interfaces — Produces:** `AuthLayoutComponent` (`app-auth-layout`): panel visual con `app-coil-scene` + contenido proyectado; sin `<main>` propio. Login: `h1` "Iniciar sesión", labels "Correo electrónico"/"Contraseña", botón mostrar/ocultar, botón "Entrar a CDM", mensajes actuales. Registro: checklist en vivo (8+ caracteres, mayúscula, minúscula, número, símbolo) ligada al validador existente; tras auto-login navega a `/`. Confirmación: mismo layout.

- [ ] Step 1: Ajustar specs (incluye: registro navega a `['/']`; checklist marca requisitos). FAIL → implementar → PASS; E2E `auth-journey` → PASS.
- [ ] Step 2: Commit `feat(web): pantallas de autenticación con layout dividido y checklist de contraseña (CDM-127)`.

---

## Fase 8 — QA y cierre (CDM-128)

### Task 8.1: Verificación integral y limpieza

**Files:** Modify `apps/web/README.md`, `CHANGELOG.md` (`[Unreleased]`), `docs/architecture/design-system.md`; eliminar CSS/código muerto.

- [ ] Step 1: `pnpm exec ng build`, `ng lint`, `ng test --no-watch`, `pnpm e2e` → todo en verde; registrar tamaños de bundle.
- [ ] Step 2: Auditoría Lighthouse (accesibilidad ≥ 95) en catálogo, carga y login; revisar foco y teclado manualmente; capturas 1440×1080 y 390×844 comparadas con la referencia.
- [ ] Step 3: `git diff develop --stat` revisado (sin secretos, sin video, sin artefactos).
- [ ] Step 4: Commit `docs(web): documentar design system y cerrar QA del rediseño (CDM-128)`; Jira: subtareas a "Listo" solo con DoD cumplido.

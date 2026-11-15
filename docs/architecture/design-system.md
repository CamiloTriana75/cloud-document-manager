# Design system del frontend (CDM-107 / CDM-108)

- **Fecha:** 2026-11-13
- **Spec:** `docs/superpowers/specs/2026-11-13-ui-redesign-design.md`
- **Código:** `apps/web/src/styles/` (capas globales) y `apps/web/src/app/shared/ui/` (componentes)

## Capas de estilos

`src/styles.css` solo importa, en orden:

1. `fonts.css` — Geist y Geist Mono variables (100–900), subconjunto latino, servidas desde `public/fonts/` (licencia SIL OFL 1.1 en `public/fonts/OFL.txt`).
2. `tokens.css` — custom properties (colores, tipografía, espaciado, radios, sombras, movimiento, layout, capas).
3. `base.css` — reset, tipografía base, selección, cursor, scrollbars, foco, skip link, `prefers-reduced-motion`.
4. `components.css` — primitivas compartidas: `.page`, `.page-hero`, `.breadcrumbs`, `.display-title`, `.section-title`, `.surface-panel`, `.surface-card`, `.btn` (+ `--primary|secondary|ghost|danger|icon|sm|block`), `.field`, `.input`, `.select`, `.chip`, `.data-table`, `.th-sort`, `.skeleton`, `.progress`, `.progress-dots`.

Los componentes Angular solo añaden su layout propio; no redefinen botones, campos ni colores.

## Tokens

| Grupo | Tokens |
|---|---|
| Superficies | `--color-canvas` `#0d1e20`, `--color-panel` `#14292a`, `--color-card` `#243a3b`, `--color-card-hover`, `--color-card-raised` `#3b5556`, `--color-field`, `--color-track`, `--color-coil` |
| Texto | `--color-text` `#eef4f3`, `--color-text-secondary` `#b4c8c7`, `--color-text-tertiary` `#93abaa` |
| Acento | `--color-accent` `#fa7752` (solo relleno; texto encima `--color-on-accent`), `--color-accent-text` `#ff9b7a` (acento como texto), `--color-accent-soft` |
| Estados | `--color-positive` `#7cfb81`, `--color-warning` `#f5c451`, `--color-danger` `#ff8b8b`, `--color-info` `#86d9e2` y sus `*-soft` |
| Tipografía | `--font-sans`, `--font-mono`, escala fija en rem `--text-xs … --text-2xl`, `--text-metric` (44 px), `--text-display` (56 px; 36 px en ≤ 720 px) |
| Espacio | `--space-1 … --space-16` (base 4 px) |
| Radios | `--radius-xs` 6 · `sm` 10 · `md` 14 · `lg` 18 · `xl` 24 · `pill` |
| Movimiento | `--duration-fast` 150 ms, `--duration-base` 220 ms, `--duration-slow` 320 ms, `--ease-out` |

Reglas de uso:

- El naranja es relleno de acción primaria, pestaña activa y progreso; nunca texto pequeño sobre oscuro (para eso existe `--color-accent-text`).
- Geist Mono solo para datos: IDs, claves de almacenamiento, hashes.
- Bordes decorativos con `--color-border`; los campos de formulario usan `--color-field-border` (≥ 3:1 contra la superficie, WCAG 1.4.11).

## Contraste verificado

`pnpm run check:contrast` (`apps/web/scripts/check-contrast.mjs`) lee `tokens.css`, compone los colores con alfa sobre su base y falla si algún par queda bajo el mínimo. Corre en CI tras el lint.

| Par | Ratio | Mínimo |
|---|---|---|
| texto / lienzo · panel · tarjeta · tarjeta elevada | 15.42 · 13.67 · 10.82 · 7.20 | 4.5 |
| texto secundario / lienzo · panel · tarjeta · tarjeta elevada | 9.83 · 8.71 · 6.90 · 4.59 | 4.5 |
| texto terciario / lienzo · panel · tarjeta · campo | 7.07 · 6.26 · 4.96 · 5.79 | 4.5 |
| acento como texto / lienzo · panel · tarjeta | 8.35 · 7.41 · 5.86 | 4.5 |
| tinta sobre acento · sobre acento hover · sobre peligro | 7.07 · 8.21 · 8.13 | 4.5 |
| positivo · aviso · peligro · info / tarjeta | 9.16 · 7.40 · 5.34 · 7.48 | 4.5 |
| estado sobre su fondo suave (positivo · aviso · peligro · info · acento) | 6.70 · 5.57 · 4.63 · 5.53 · 4.74 | 4.5 |
| borde de campo / tarjeta · panel | 3.40 · 4.30 | 3 |
| anillo de foco / lienzo · tarjeta | 9.69 · 6.80 | 3 |

## Componentes compartidos (`src/app/shared/ui/`)

Todos son standalone, `OnPush` y usan `input()`/`output()`.

| Componente | Selector | Entradas / salidas | Accesibilidad |
|---|---|---|---|
| Icono | `app-icon` | `name: IconName` (requerido), `size = 18`, `strokeWidth = 1.75` | Decorativo (`aria-hidden`); el control que lo usa lleva el nombre. Registro tipado en `icons.ts` (Lucide, ISC), sin `innerHTML`. |
| Diálogo | `app-dialog` | `open`, `variant: 'modal' \| 'drawer'`, `label` o `labelledBy`; `(closed)` | `<dialog>` nativo: capa superior, fondo inerte, Escape y clic en el fondo emiten `closed`, devuelve el foco. |
| Menú | `app-menu` + `[appMenuItem]` | `label` (requerido), `align: 'start' \| 'end'`, `triggerClass`; ítems con `menuRole: 'menuitem' \| 'menuitemradio'` y `menuChecked` | Patrón ARIA menu button: flechas, Home/End, Escape devuelve foco, Tab cierra. Popover API cuando existe. |
| Pestañas-carpeta | `app-folder-tabs` | `tabs: FolderTab[]`, `active`, `controls`, `label`; `(activeChange)` | Patrón tabs con activación manual y roving tabindex. |
| KPI | `app-kpi-card` | `label`, `value`, `unit`, `caption`, `captionTone`, `highlighted`, `loading`, `actionLabel`; `(action)`; slot `[kpiVisual]` | Título `h3`; `aria-busy` mientras carga. |
| Barra segmentada | `app-segmented-bar` | `segments: BarSegment[]`, `label` | `role="img"` con el desglose en porcentajes. |
| Sparkline | `app-sparkline` | `points: number[]`, `label`, `tone` | `role="img"` con etiqueta; sin `url(#id)` (compatible con `<base href>`). |
| Escalera de rol | `app-role-ladder` | `role: WorkspaceRole` | `role="img"`: "Rol EDITOR, nivel 3 de 5". |
| Estado de documento | `app-status-badge` | `status: DocumentStatus` | Etiqueta textual + `aria-label`; puntos de avance animados solo en estados en curso. Clases `doc-status-<estado>` estables para E2E. |
| Rol | `app-role-badge` | `role: WorkspaceRole` | `aria-label` "Rol de usuario: …"; clases `role-<rol>`. |
| Alerta | `app-alert` | `type: 'info' \| 'success' \| 'warning' \| 'danger'`, `dismissible`; `(dismiss)` | `role="status"` o `alert` según gravedad; `aria-live` asertivo en peligro. |
| Estado vacío | `app-empty-state` | `icon`, `title` (requerido), `description`; acciones proyectadas | Título `h3`. |
| Avatar | `app-avatar` | `name` (requerido), `size = 32` | Decorativo; el nombre se muestra como texto. |
| Spinner | `app-spinner` | `size`, `label` | `role="status"` con texto oculto. Para contenido que carga se usa `.skeleton`. |
| Error de campo | `app-form-error` | `message`, `id` | `role="alert"`; el control lo referencia con `aria-describedby`. |

Utilidades de formato (`src/app/shared/format/`): `formatBytes`, `formatDateTime`, `formatDate`, `formatRelativeTime`, `shortId` y los pipes `bytes`, `dateTime`, `relativeTime` (es-CO). Metadatos de estado de documento, carpetas y tipos MIME exactos: `core/documents/document-status.ts`.

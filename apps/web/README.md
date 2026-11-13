# CDM — Web (Angular)

SPA de Cloud Document Manager: Angular 22 standalone y zoneless, señales, Vitest y Playwright. Gestor de paquetes: **pnpm 12.14.0** (`packageManager` en `package.json`).

## Comandos

| Comando | Qué hace |
|---|---|
| `pnpm start` | Dev server en `http://localhost:4200` con proxy de `/api` y `/health` al backend local (`proxy.conf.json`). |
| `pnpm build` | Build de producción (presupuestos: inicial 500 kB aviso / 1 MB error). |
| `pnpm lint` | angular-eslint, incluidas reglas de accesibilidad de plantillas. |
| `pnpm test` | Pruebas unitarias con Vitest (`ng test`). |
| `pnpm run check:contrast` | Verifica el contraste WCAG AA de los tokens de color (`scripts/check-contrast.mjs`). |
| `pnpm e2e` | Journeys E2E con Playwright y API simulada (`e2e/fixtures/mock-api.ts`). `E2E_PORT=4310 pnpm e2e` levanta su propio servidor si ya tienes otro `ng serve` en 4200. |

## Estructura

```
src/
├── styles.css                 importa las capas globales
├── styles/                    fonts · tokens · base · components (design system)
└── app/
    ├── app.*                  shell: header, navegación, drawer móvil
    ├── layout/                selector de workspace y menú de usuario
    ├── core/                  servicios de API, auth, documentos (estado, estadísticas, cola de carga), workspaces
    ├── shared/format/         formato de bytes, fechas e IDs (es-CO)
    ├── shared/ui/             componentes compartidos (icono, diálogo, menú, carpetas, KPIs, escena 3D…)
    └── pages/                 inicio, documentos (dashboard y carga), workspaces, autenticación
```

## Diseño

- Sistema visual y API de componentes: [`docs/architecture/design-system.md`](../../docs/architecture/design-system.md).
- Spec del rediseño: [`docs/superpowers/specs/2026-11-13-ui-redesign-design.md`](../../docs/superpowers/specs/2026-11-13-ui-redesign-design.md).
- Escena 3D (three.js diferido): [ADR-0009](../../docs/adr/0009-escena-3d-three-js.md).
- Contexto de producto para herramientas de diseño: [`PRODUCT.md`](PRODUCT.md).

Reglas: solo tema oscuro; el naranja es relleno de acción primaria y nunca texto pequeño; Geist Mono solo para datos; todo movimiento respeta `prefers-reduced-motion`; la UI refleja permisos pero la autorización la decide siempre el backend.

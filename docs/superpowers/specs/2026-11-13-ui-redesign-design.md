# Rediseño visual de la UI Angular — Diseño

- **Fecha:** 2026-11-13
- **Estado:** aprobado por el propietario (2026-11-13)
- **Jira:** CDM-121 (subtareas CDM-122…CDM-128), CDM-107 y CDM-108 (design system y accesibilidad)
- **Rama:** `feat/inc6-ui-redesign` (desde `develop`)
- **Referencia visual:** clip de 5 s de un dashboard documental oscuro (proporcionado por el propietario, no versionado)

## 1. Intención

CDM es un proyecto de portafolio. La UI actual funciona, pero se ve genérica (tema claro azul, estilos duplicados por página) y no comunica la calidad del backend. El objetivo es que el frontend se vea y se comporte como un SaaS profesional, adaptando el lenguaje visual de la referencia a las funciones reales del MVP, y que el código del frontend quede ordenado alrededor de un design system real.

## 2. Objetivos, no objetivos y anti-objetivos

**Objetivos**

- Lenguaje visual único en todas las pantallas: shell, inicio, catálogo, detalle, carga, miembros, creación de workspace, login y registro.
- Design system real: tokens globales + componentes compartidos usados por todas las páginas (hoy `shared/ui` existe y no se usa).
- Corregir los defectos encontrados en el análisis (sección 9).
- Accesibilidad AA y presupuestos de bundle respetados.

**No objetivos**

- Funciones de IA: el panel "Document AI" de la referencia queda fuera del MVP (AGENTS.md §4) y se reemplaza por un panel de **Actividad** con datos reales.
- Cambios de backend o de contratos de API.
- Tema claro: solo tema oscuro, que es la esencia de la referencia.
- Notificaciones o ajustes: el producto no los tiene; no se dibujan botones falsos.

**Anti-objetivos (sería un fracaso aunque "funcione")**

- KPIs o gráficos con datos inventados o decorativos.
- Copiar marca, logo o textos de la referencia.
- Animación que degrade el rendimiento o ignore `prefers-reduced-motion`.
- Romper flujos existentes: auth, carga directa a S3, polling de estados, autorización por rol en UI.

## 3. Restricciones

- AGENTS.md §9 (frontend), §14 (seguridad), §15 (pruebas), §20 (protocolo).
- Angular 22 standalone y zoneless, Vitest, Playwright, pnpm.
- API de documentos: `limit ≤ 100`, orden fijo `created_at desc`, filtros exactos (`status`, `content_type` por igualdad, `search`, `created_after`/`created_before`), sin endpoint de estadísticas.
- Presupuestos de build: inicial 500 kB (aviso) / 1 MB (error); estilos por componente 16 kB (aviso) / 32 kB (error).
- Cambios del propietario sin commit (auto-login tras registro) preservados en commit propio (`4ce3f69`).

## 4. Enfoques considerados

| Decisión | Opciones | Elegida y motivo |
|---|---|---|
| Escena 3D | (a) `three` cargado bajo demanda; (b) CSS 3D sin dependencia; (c) shader WebGL propio (raymarching) | **(a)**: iluminación PBR real con poco código; (b) se ve plano; (c) más difícil de mantener y coste GPU por píxel. Se documenta en ADR-0009. |
| Pestañas-carpeta | (a) por estado; (b) por familia de tipo de archivo | **(a)**: el backend filtra estado por igualdad; (b) exige filtro por familia en backend (mejora futura). |
| Métricas | (a) conteos con `limit=1` por filtro; (b) endpoint de estadísticas | **(a)**: solo usa la API existente; (b) queda como mejora futura de backend. |

## 5. Lenguaje visual

Paleta muestreada de la referencia y ajustada para contraste AA:

| Rol | Valor base | Uso |
|---|---|---|
| Lienzo | `#0d1e20` | fondo de la app |
| Panel | `#14292a` | cuerpo del "folder" principal |
| Tarjeta | `#263b3c` | KPIs, tabla, Actividad |
| Tarjeta elevada | `#3e5858` | tarjeta/pestaña activa (glass) |
| Pista | `#365958` | barras y segmentos vacíos |
| Acento | `#fa7752` | CTA, pestaña activa, progreso; texto oscuro encima |
| Positivo | `#7cfb81` | deltas positivos, "Listo" |
| Bobina 3D | `#469385` con brillos claros | escena |

- **Tipografía:** Geist (UI y display, pesos finos para títulos y cifras grandes) y Geist Mono (IDs, claves, tamaños); fuentes servidas por la propia app (licencia OFL), sin CDN. Cifras tabulares en métricas y tablas.
- **Superficies:** bordes hairline (`rgba(255,255,255,.06–.10)`), radios 12–16 px, brillo superior sutil, sin sombras duras.
- **Movimiento:** 150–300 ms, `cubic-bezier(.16,1,.3,1)`; todo se desactiva con `prefers-reduced-motion`.
- **Iconografía:** un solo registro tipado de iconos de trazo (estilo Lucide), sin emojis.

## 6. Mapeo referencia → CDM

| Referencia | CDM |
|---|---|
| Logo + nav central con subrayado activo | Marca CDM + Inicio · Documentos · Cargar · Miembros |
| Campana, ajustes, avatar | Selector de workspace + avatar con menú (perfil, rol, cerrar sesión) |
| Eyebrow "Documents" + título gigante | Eyebrow de sección + nombre del workspace |
| Counterparty ID / Industry | ID corto del workspace / slug |
| Reliability Score (barra segmentada) | Escalera de rol de 5 niveles (VIEWER → OWNER) |
| Pestañas-carpeta por categoría | Pestañas-carpeta por estado con conteo real |
| KPI "Total" con sparkline | Total de documentos, "+N en 7 días" y sparkline de cargas diarias |
| KPI "Compliance Score" | % de documentos listos |
| KPI "AI Assisted Review" (3 segmentos) | Pipeline: listos / en proceso / fallidos |
| Tabla "Overview" con chips | Catálogo de documentos con chips (tipo, orden) y búsqueda |
| Panel "Document AI" (chat) | Panel **Actividad**: últimos documentos y su estado en vivo + barra para soltar archivos |
| Bobina 3D animada | Bobina procedural propia (three.js), rotación lenta |

## 7. Pantallas

1. **Shell:** barra superior transparente sobre el hero, nav central, selector de workspace (listbox accesible), menú de usuario; en móvil, drawer con `<dialog>` nativo.
2. **Inicio:** sin sesión, landing con escena 3D, propuesta de valor y estado de la API; con sesión, tarjetas de workspaces (rol, fecha) + "Nuevo workspace".
3. **Dashboard de documentos** (`/workspaces/:id/documents`): hero + escena 3D, pestañas-carpeta, KPIs, catálogo y Actividad (ver boceto en la conversación de aprobación).
4. **Detalle:** drawer lateral (`<dialog>`) con metadatos, línea de tiempo de estados y acciones autorizadas; confirmación de borrado con `<dialog>`.
5. **Carga:** dropzone glass + cola multi-archivo con progreso, cancelación y reintento por archivo; tarjeta de política (formatos, 50 MB).
6. **Miembros:** resumen, invitación (OWNER/ADMIN) y tabla con chips de rol y estado.
7. **Crear workspace:** formulario glass con vista previa del slug.
8. **Login / registro:** layout dividido (escena 3D + formulario), mostrar/ocultar contraseña, checklist de requisitos de contraseña en vivo (política de Cognito).

## 8. Arquitectura del frontend

- `src/styles/`: `tokens.css`, `base.css`, `utilities.css` y `fonts.css` globales; los componentes solo añaden layout propio.
- `shared/ui/`: icono, botón (directiva), panel, KPI, barra segmentada, sparkline, pestañas-carpeta, chip de estado y de rol, escalera de rol, diálogo (`<dialog>` nativo con gestión de foco), menú, skeleton, estado vacío, toast/alerta, avatar, escena 3D.
- `core/documents/`: `document-status.ts` (etiquetas, tonos y orden en un solo lugar), servicio de estadísticas, servicio de cola de carga; pipes de bytes y fecha.
- `pages/documents/catalog/`: store de catálogo con señales (filtros, paginación, búsqueda con debounce + `switchMap`), subcomponentes de tabla, Actividad y detalle.
- Prácticas: `OnPush`, señales e `input()/output()`, `host` en lugar de `@HostListener`, sin `CommonModule`, `takeUntilDestroyed`, polling pausado con la pestaña oculta.

**Datos del dashboard (solo API existente)**

- Conteos: `limit=1` sin filtro (total) y con `status=READY|PROCESSING|UPLOADED|PENDING_UPLOAD|FAILED`.
- "+N en 7 días": `created_after = ahora − 7 d`, `limit=1`.
- Sparkline: `created_after = ahora − 7 d`, `limit=100`, agrupado por día; se oculta si hay más de 100 en la ventana (no se muestra un dato parcial como completo).
- Actividad: primera página (`limit=8`) y refresco cada 5 s mientras haya documentos en proceso.

## 9. Defectos a corregir

- Filtro de tipo envía prefijos (`image/`, `text/`, `application/vnd`) y el backend compara por igualdad: con la API real devuelve 0. Pasa a MIME exactos.
- Búsqueda sin debounce ni cancelación: respuestas fuera de orden pueden mostrar resultados viejos.
- `<main>` anidado en login/registro; modales sin trampa ni retorno de foco; emojis como iconos.
- Carga de un solo archivo (AGENTS.md §9 pide uno o varios).
- El registro navega a `/workspaces` (ruta inexistente).
- Componentes de `shared/ui` sin uso y estilos duplicados por página.

## 10. Accesibilidad y rendimiento

- Contraste AA verificado por cálculo para cada par texto/fondo de los tokens; texto oscuro sobre naranja.
- Foco visible, navegación por teclado en menús y listbox, `aria-sort` en encabezados, regiones `aria-live` para progreso y estados.
- three.js en chunk diferido, solo si hay WebGL y espacio; pausa con `IntersectionObserver` y `visibilitychange`; DPR limitado; recursos liberados al destruir; fallback CSS.

## 11. Verificación

- `ng build` (presupuestos), `ng lint`, `ng test`, `pnpm e2e` en verde en cada fase.
- Pruebas nuevas para componentes compartidos, servicios y store.
- Capturas con Playwright comparadas con la referencia; auditoría de accesibilidad (Lighthouse/axe).

## 12. Fases (un commit o más por fase)

0. Spec, plan, Jira, rama.
1. Fundamentos: fuentes, tokens, base, iconos y componentes base (CDM-107, CDM-108).
2. Shell + escena 3D + ADR-0009 (CDM-122).
3. Dashboard de documentos (CDM-123).
4. Carga multi-archivo (CDM-124).
5. Inicio (CDM-125).
6. Miembros y crear workspace (CDM-126).
7. Login y registro (CDM-127).
8. QA, limpieza y documentación (CDM-128).

## 13. Riesgos

- Tamaño de `three` (~150 kB gz): mitigado con carga diferida, fuera del bundle inicial.
- GPU modesta: DPR limitado, geometría acotada, pausa fuera de pantalla, fallback estático.
- Cambios de markup rompen E2E: se mantienen nombres accesibles estables y se actualizan las pruebas en la misma fase.
- Presupuesto de estilos por componente: estilos compartidos en globales, componentes delgados.

## 14. Decisiones que quedan al implementador

Detalles de microcopy, tamaños exactos, número de anillos de la bobina, densidad de tabla y breakpoints, siempre dentro de las reglas anteriores.

# ADR-0009: Escena 3D del frontend con three.js cargado bajo demanda

- **Fecha:** 2026-11-13 · **Estado:** Aceptado · **Jira:** CDM-121, CDM-122

## Contexto

El rediseño visual aprobado (`docs/superpowers/specs/2026-11-13-ui-redesign-design.md`) incluye una escena 3D animada detrás del hero: una bobina de anillos metálicos teal que gira lentamente. AGENTS.md pide no añadir dependencias por comodidad y mantener rendimiento y accesibilidad; el bundle inicial tiene un presupuesto de 500 kB (aviso) y 1 MB (error).

## Opciones consideradas

1. **three.js cargado con `import()` dinámico** — geometría instanciada, materiales PBR y entorno de iluminación con poco código propio; chunk diferido de ~113 kB comprimido (550 kB sin comprimir, medido en el build).
2. **CSS 3D sin dependencias** — anillos con transformaciones 3D y gradientes; sin iluminación ni reflejos reales, el resultado se ve plano frente a la referencia. Descartado.
3. **Shader WebGL propio (raymarching de SDF)** — cero dependencias y control total, pero más difícil de mantener y con coste de GPU por píxel. Descartado.
4. **Video o imagen pre-renderizada** — barato en runtime, pero exige producir y versionar el asset y no se adapta al tamaño ni al movimiento reducido. Descartado.

## Decisión

- `three` (versión exacta `0.186.1`, `@types/three` `0.186.0` en desarrollo) solo se importa desde `shared/ui/coil-scene/coil-renderer.ts`, que `CoilSceneComponent` carga con `import()` después del primer render. three.js nunca entra al bundle inicial.
- La geometría es procedural y propia (`coil-geometry.ts`, probada sin WebGL): arandelas con aristas redondeadas (`LatheGeometry`) repartidas sobre una circunferencia en un único `InstancedMesh` (una llamada de dibujo), `MeshPhysicalMaterial` con clearcoat y un entorno `RoomEnvironment` vía PMREM.
- Salvaguardas: sin WebGL2, en equipos con ≤ 2 núcleos o ≤ 2 GB de memoria, o si falla la carga, queda un fondo CSS. El bucle se detiene fuera de pantalla (`IntersectionObserver`) y con la pestaña oculta (`PageVisibilityService`). Con `prefers-reduced-motion` se dibuja un único fotograma. DPR limitado (1.75 en escritorio, 1.25 en móvil) y menos anillos en pantallas pequeñas. Al destruir se liberan geometría, material, entorno y contexto.
- La escena es decorativa (`aria-hidden="true"`, `pointer-events: none`).

## Consecuencias

- Primera visita a una pantalla con escena: descarga adicional diferida (~113 kB comprimidos) que no bloquea la interacción; el fondo CSS cubre la espera y se funde con la escena al primer fotograma.
- Las pruebas unitarias (jsdom, sin WebGL) cubren el respaldo y la geometría; la escena real se verifica con capturas de Playwright en Chromium.

## Riesgos

- GPU modestas: mitigado con los límites anteriores; si el rendimiento no es aceptable, el respaldo CSS es suficiente para el producto.
- Actualizaciones mayores de three.js pueden cambiar APIs: la versión está fijada y el uso se concentra en un solo archivo.

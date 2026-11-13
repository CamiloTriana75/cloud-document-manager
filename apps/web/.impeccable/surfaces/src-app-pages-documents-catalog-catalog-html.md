---
version: 1
slug: "src-app-pages-documents-catalog-catalog-html"
primary_target: "src/app/pages/documents/catalog/catalog.html"
related_targets: ["src/app/app.html","src/app/pages/documents/upload/upload.html","src/app/pages/workspaces/members/members.html"]
---

## Scope

Dashboard de documentos del workspace (`/workspaces/:id/documents`) y, por herencia, todo el shell autenticado. Modo: Operate.

## Audience and job

Miembros de un workspace que suben, siguen, encuentran, descargan y eliminan documentos; OWNER/ADMIN además reintentan fallidos. Restricciones: solo datos reales de la API existente, permisos reflejados por rol, español, WCAG AA.

## Direction contract

THESIS: El workspace como una carpeta física sobre la que gira la nube: el nombre del workspace manda, las carpetas de estado "entran" al panel de trabajo. Rechaza el admin genérico de sidebar + tarjetas planas sobre gris.

OWN-WORLD: Lienzo #0d1e20, panel #14292a, tarjetas #263b3c con bordes hairline y brillo superior, tarjeta/pestaña activa #3e5858. Naranja #fa7752 solo en acción primaria, pestaña activa y progreso; verde #7cfb81 en deltas y "Listo". Geist fina para nombre del workspace y cifras; Geist Mono solo para IDs. Bobina 3D teal metálica girando detrás del hero.

STORY: Reconoce su workspace y su rol, ve cuántos documentos hay y en qué estado, encuentra uno y lo descarga; sigue en vivo lo que se procesa y suelta archivos nuevos sin cambiar de pantalla.

FIRST VIEWPORT: Header transparente (marca a la izquierda, nav central con subrayado, selector de workspace y avatar a la derecha). Migas "Inicio / Documentos" y nombre del workspace grande y fino a la izquierda; ID, slug y escalera de rol a la derecha; bobina centrada detrás. Cinco pestañas-carpeta con conteo; la activa se eleva y se funde con el panel. Dentro: tres KPIs en fila, Actividad a la derecha en dos filas, catálogo bajo los KPIs. Acción primaria naranja: "Subir documento" en la barra del catálogo y botón de la zona de soltar.

FORM: dirección fijada por el propietario con un video de referencia; sin tirada de concept-seed; seed key: n/a (brief-pinned); construcción code-led (sin generación de imágenes). Movimiento firma: pestaña-carpeta que se eleva y funde con el panel + bobina girando.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

Número de anillos y encuadre exacto de la bobina; densidad de tabla en móvil.

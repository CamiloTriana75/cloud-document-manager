# ADR-0002: FastAPI en Lambda con adaptador ASGI (Mangum)

- **Fecha:** 2026-11-12 · **Estado:** Aceptado · **Jira:** CDM-11, CDM-20

## Contexto

La API se ejecuta en AWS Lambda detrás de API Gateway (charter §6). FastAPI es una app ASGI; Lambda recibe eventos proxy, no peticiones ASGI. Hace falta un traductor y una estrategia de empaquetado.

## Opciones consideradas

1. **Mangum** — adaptador ASGI→Lambda maduro y ampliamente usado; mantiene la app FastAPI idéntica en local y Lambda.
2. **Servidor persistente (ECS/Fargate o EC2)** — sin coste fijo; viola la restricción de coste del proyecto.
3. **Reescribir handlers como funciones Lambda puras** — duplica lógica HTTP, rompe hexagonal, sin OpenAPI.
4. **AWS Lambda Web Adapter** — corre el servidor ASGI dentro de Lambda; viable pero añade capa de runtime innecesaria para un MVP.

## Decisión

Usar **Mangum** como adaptador único: `handler = Mangum(app)`. La app FastAPI vive en `bootstrap` y es agnóstica del entorno. Empaquetado con capas de dependencias o image de contenedor Lambda, a decidir en CDM-20 según límites de tamaño; el código de aplicación no cambia en ningún caso.

## Consecuencias

- La misma app sirve desarrollo local (uvicorn), pruebas (httpx/TestClient) y producción (Mangum) — cero duplicación.
- Cold starts aceptables para MVP; sin optimización prematura.
- Binarios nunca pasan por la API (ADR-0004), así que el límite de payload de Lambda no afecta al flujo principal.
- Riesgo: Mangum es dependencia de terceros activamente mantenida pero externa al ecosistema oficial; mitigación: el adaptador se aisla en un punto único (`bootstrap/lambda.py`) y es reemplazable.

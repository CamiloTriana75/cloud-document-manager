# ADR-0004: Carga directa a S3 con URL prefirmada (PUT)

- **Fecha:** 2026-11-12 · **Estado:** Aceptado · **Jira:** CDM-11, CDM-29, CDM-31, CDM-32

## Contexto

Los binarios no deben atravesar la API (límites de payload de Lambda, coste, latencia). El navegador necesita permiso temporal y acotado para escribir un único objeto.

## Opciones consideradas

1. **Upload vía API (multipart a través de FastAPI/Lambda)** — payload límite ~6-10 MB en Lambda proxy, coste de invocación por MB, acopla binario a la API; rechazado.
2. **URL prefirmada de PUT** — acotada a un objeto y operación, vida corta, sin credenciales en el navegador.
3. **Credenciales temporales STS en el navegador** — requiere SDK en cliente y política más compleja de acotar; superficie de riesgo mayor; descartado para MVP.
4. **S3 Transfer Acceleration / multipart UI SDK** — coste extra y complejidad innecesarios con archivos ≤ 50 MB.

## Decisión

- El backend genera **una URL prefirmada de PUT** por documento, alcance a una única `storage_key`, expiración ≤ 15 min.
- La URL incluye **headers fijados por el backend** (`Content-Type` de la allowlist, `Content-Length` previsto); el cliente no elige nada.
- Anti-overwrite: la `storage_key` es única (UUID); la sesión es de un solo uso; el `complete` verifica con `HeadObject` presencia, tamaño y metadata antes de confirmar estado en DB.
- El objeto se escribe en prefijo `staging/` (particionado por workspace) y el worker/confirmación lo registra como documento; lifecycle limpia staging huérfano a 7 días.
- CORS del bucket: orígenes exactos del frontend por entorno, nunca `*` en producción.

## Consecuencias

- S3 nunca acepta un PUT fuera de una sesión válida (key imposible de adivinar + expiración corta).
- La integridad real se valida en servidor (tipo/tamaño reales vs declarados), no confiamos en el navegador.
- Riesgo: `HeadObject` en `complete` añade una llamada; aceptable a este volumen.

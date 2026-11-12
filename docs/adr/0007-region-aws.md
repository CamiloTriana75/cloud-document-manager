# ADR-0007: Región AWS `us-east-1`

**Estado:** Propuesta — pendiente aprobación del propietario
**Fecha:** 2026-11-12 · **Jira:** CDM-17 (épica CDM-3)

## Contexto

CDM necesita región única para desplegar el MVP (S3, SQS, Lambda, API Gateway, Cognito, CloudWatch). La cuenta está en AWS Free Plan con $100 de créditos hasta 2027-05-12 (ver `docs/runbooks/aws-account-audit.md`). El propietario está en Colombia (latencia hacia EE. UU. es la mejor opción cercana).

## Opciones consideradas

1. **`us-east-1` (N. Virginia):** precio más bajo de las regiones US; todos los servicios del stack disponibles sin excepción; mayor capacidad y cuotas frescas; latencia ≈80-100 ms desde Bogotá.
2. **`us-east-2` (Ohio):** igual precio, latencia ligeramente peor desde Colombia.
3. **`sa-east-1` (São Paulo):** latencia ≈100-120 ms pero servicios ≈2× más caros → drena créditos más rápido.
4. **`eu-west-1` (Irlanda):** latencia ≈140 ms, precio mayor que us-east-1.

## Decisión (propuesta)

**`us-east-1`.** Minimiza coste (lo crítico en Free Plan), tiene disponibilidad garantizada de todos los servicios del MVP y latencia razonable.

## Consecuencias

- Terraform `environments/{dev,prod}` fijan `region = "us-east-1"` vía variable default.
- Los créditos Free Plan aplican en cualquier región global; `us-east-1` es la más barata, así que protege el saldo.
- Una sola región para todo el MVP (frontend deferido a localhost/CloudFront en fase posterior).
- Si algún día se requiere latencia baja para usuarios LATAM en producción, se evaluará con plan Paid — fuera de alcance MVP.

## Riesgos

- Menor latencia frente a `sa-east-1` — irrelevante para portafolio/MVP.
- Ninguno de coste: us-east-1 es la región con tarifas base más bajas.

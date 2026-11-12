# Módulo Terraform: `apigw-http`

> Jira: **CDM-20** (subtarea **CDM-120**) · Épica: **CDM-3**

Módulo reutilizable para aprovisionar un API Gateway HTTP API (v2) conectado a AWS Lambda mediante integración proxy con payload v2.0.

## Responsabilidad

Gestiona la API HTTP pública, su etapa `$default` con despliegue automático, la configuración de CORS restrictivo y los permisos IAM de invocación a la Lambda.

## Ventajas sobre REST API tradicional

- **Menor coste y latencia:** HTTP API tiene menor sobrecarga de red y coste ≈70% menor.
- **Límites Always Free:** 1 millón de llamadas mensuales gratuitas en el Free Plan.
- **Payload Format v2.0:** Formato compacto y nativamente compatible con adaptadores ASGI como Mangum.

## Entradas

| Variable | Tipo | Default | Descripción |
|---|---|---|---|
| `api_name` | string | *requerido* | Nombre de la API. |
| `lambda_invoke_arn` | string | *requerido* | ARN de invocación de la Lambda. |
| `lambda_function_name` | string | *requerido* | Nombre de la función Lambda. |
| `allowed_cors_origins` | list(string) | `["http://localhost:4200"]` | Orígenes permitidos para CORS. |
| `tags` | map(string) | `{}` | Etiquetas adicionales. |

## Salidas

| Output | Descripción |
|---|---|
| `api_id` | ID del API Gateway. |
| `api_endpoint` | URL base pública de la API (ej. `https://xyz.execute-api.us-east-1.amazonaws.com`). |
| `stage_id` | ID del stage `$default`. |

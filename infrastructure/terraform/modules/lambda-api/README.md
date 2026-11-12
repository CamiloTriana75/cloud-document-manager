# Módulo Terraform: `lambda-api`

> Jira: **CDM-20** (subtarea **CDM-119**) · Épica: **CDM-3**

Módulo reutilizable para aprovisionar la función AWS Lambda encargada de ejecutar el backend FastAPI mediante el adaptador ASGI Mangum (ADR-0002).

## Responsabilidad

Gestiona la función Lambda, su rol IAM de ejecución con mínimo privilegio (`AWSLambdaBasicExecutionRole`), el grupo de logs en CloudWatch con retención controlada y las variables de entorno.

## Restricciones y Costes (Free Plan)

- **Límites Always Free:** 1 millón de invocaciones y 400.000 GB-segundos mensuales cubren holgadamente el uso del portafolio.
- **Memoria:** Configurada por defecto en 256 MB para balancear velocidad de arranque y coste.
- **Timeout:** 15 segundos (las operaciones pesadas o de ingesta van por el worker asíncrono, nunca por la API HTTP).
- **Logs:** Retención fijada en 14 días para evitar cargos acumulativos de almacenamiento en CloudWatch Logs (auditoría CDM-17).

## Entradas

| Variable | Tipo | Default | Descripción |
|---|---|---|---|
| `function_name` | string | *requerido* | Nombre único de la función Lambda. |
| `handler` | string | `"cdm.bootstrap.lambda_handler.handler"` | Handler del adaptador Mangum. |
| `runtime` | string | `"python3.12"` | Runtime oficial de Python. |
| `memory_size` | number | `256` | Memoria en MB (128 a 512). |
| `timeout` | number | `15` | Timeout en segundos (1 a 60). |
| `log_retention_days` | number | `14` | Días de retención de logs. |
| `environment_variables` | map(string) | `{}` | Variables de entorno (sin secretos). |
| `package_path` | string | `null` | Ruta al archivo `.zip` del artefacto. |

## Salidas

| Output | Descripción |
|---|---|
| `function_name` | Nombre de la función Lambda. |
| `function_arn` | ARN de la función Lambda. |
| `invoke_arn` | ARN de invocación para API Gateway. |
| `role_arn` | ARN del rol IAM de ejecución. |
| `log_group_name` | Nombre del grupo de logs en CloudWatch. |

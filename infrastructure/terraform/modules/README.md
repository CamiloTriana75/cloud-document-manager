# Módulos Terraform — convenciones

Cada módulo cubre **una** responsabilidad (AGENTS.md §13: módulos pequeños y reutilizables; no cajones de sastre). Se crean cuando existe el recurso que necesitan (CDM-19..23), nunca por adelantado.

## Convenciones

1. **Nombre:** `modules/<servicio-rol>/` — p. ej. `s3-document-store`, `sqs-worker-queue`, `lambda-api`, `cognito-pool`, `apigw-http`.
2. **Archivos por módulo:** `main.tf` (recursos), `variables.tf`, `outputs.tf`, `versions.tf` (`required_providers` si aplica). Sin `terraform {}` duplicado — eso vive solo en el entorno.
3. **Etiquetas:** los recursos toman tags desde `variables.tf` del módulo (`var.tags` map) o del `default_tags` del provider — nunca hardcoded.
4. **Nada fuera del módulo:** un módulo no crea otros módulos ni recursos ajenos a su responsabilidad.
5. **Coste:** cada módulo documenta en su header qué recursos crea y si tienen coste fuera de los límites *always free* (ver `docs/runbooks/aws-account-audit.md`).
6. **Proporcionar:** el entorno (`environments/dev`) instancia el módulo con `name`, `tags`, y límites (retención, tamaños) desde sus variables.

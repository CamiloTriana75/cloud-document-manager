# Runbook: despliegue en la nube (AWS dev + Neon + Vercel)

> Jira: **CDM-129** (subtareas CDM-130 a CDM-133) · Fecha: 2026-11-15
> Decisiones: [ADR-0010](../adr/0010-postgresql-gestionado-neon.md) (PostgreSQL en Neon) y [ADR-0011](../adr/0011-frontend-en-vercel.md) (frontend en Vercel).
> Regla rectora: [`AGENTS.md`](../../AGENTS.md) §13. Ningún `terraform apply` sin revisar el plan y sin aprobación del propietario.

## 1. Mapa del entorno

| Pieza | Dónde | Identificador |
|---|---|---|
| Frontend (Angular) | Vercel, proyecto `cloud-document-manager` | https://cloud-document-manager.vercel.app |
| API (FastAPI + Mangum) | Lambda `cdm-dev-api` detrás de API Gateway HTTP | `terraform output api_gateway_endpoint` |
| Worker | Lambda `cdm-dev-worker`, disparada por SQS `cdm-dev-document-events` | DLQ `cdm-dev-document-events-dlq` |
| Identidad | Cognito User Pool + App Client SPA | `terraform output cognito_user_pool_id` / `cognito_client_id` |
| Documentos | S3 privado `cdm-dev-docs-<cuenta>` (eventos → SQS) | `terraform output documents_bucket_name` |
| Base de datos | Neon `cloud-document-manager-dev` (PostgreSQL 16, `aws-us-east-1`) | DSN solo en `TF_VAR_database_url` |

Límite de la cuenta: **10 ejecuciones concurrentes de Lambda** en total. El worker está limitado a 2 (`max_concurrency`) y el frontend escalona sus lecturas y reintenta los 503 transitorios. Para subir el límite, pedir el aumento de la cuota *Concurrent executions* (Service Quotas → AWS Lambda).

## 2. Base de datos (una vez, o al rotar la contraseña)

1. En Neon, copia la cadena de conexión del rol `cdm_app`. Para la Lambda usa el host **con** `-pooler` y, para migraciones, el host directo (**sin** `-pooler`). Formato SQLAlchemy:
   `postgresql+psycopg://cdm_app:<password>@<host>/cdm?sslmode=require&channel_binding=require`
2. Aplica las migraciones contra el endpoint directo:
   ```bash
   cd apps/api
   CDM_DATABASE_URL='<dsn-directa>' uv run alembic upgrade head
   CDM_DATABASE_URL='<dsn-directa>' uv run alembic current   # debe indicar (head)
   ```

## 3. Backend e infraestructura (Terraform)

```bash
# 1. Empaquetar el código de la API y el worker (conserva los .dist-info: SQLAlchemy los necesita)
uv run --project apps/api python scripts/package_lambda_api.py -o build/cdm-api-lambda.zip

# 2. Plan con la DSN del pooler como variable sensible (no se imprime ni se guarda en archivos)
cd infrastructure/terraform/environments/dev
export TF_VAR_database_url='<dsn-pooler>'
terraform fmt -check -recursive ../.. && terraform validate
terraform plan -out=tfplan

# 3. Revisar el plan: solo actualizaciones esperadas, nada de destrucciones ni recursos con coste.
# 4. Con aprobación del propietario:
terraform apply tfplan
```

Variables que reciben las Lambdas (nombres `CDM_*` de `cdm.config.settings`): `CDM_ENV`, `CDM_DATABASE_URL`, `CDM_CORS_ORIGINS`, `CDM_COGNITO_REGION`, `CDM_COGNITO_USER_POOL_ID`, `CDM_COGNITO_CLIENT_ID`, `CDM_S3_BUCKET_NAME`, `CDM_S3_REGION`, `CDM_MAX_UPLOAD_SIZE_BYTES`. En AWS **nunca** se define `CDM_AUTH_MOCK_ENABLED`: con User Pool configurado toda petición exige un JWT firmado.

Para autorizar otro dominio del frontend, añádelo a `allowed_cors_origins` (`variables.tf`) y vuelve a aplicar: actualiza API Gateway, el CORS del bucket y FastAPI.

## 4. Frontend (Vercel)

La configuración pública del build está en `apps/web/src/environments/environment.prod.ts` (URL de API Gateway e identificadores de Cognito, que no son secretos). Si cambian los outputs de Terraform, actualízala.

```bash
# Desde la raíz del repo (el proyecto usa rootDirectory = apps/web y .vercelignore)
vercel link --yes --project cloud-document-manager   # solo la primera vez
vercel deploy --prod --yes
```

El build en Vercel usa `apps/web/vercel.json`: pnpm 12.14.0 vía `npx`, salida `dist/web/browser`, fallback SPA y cabeceras de seguridad.

## 5. Verificación (smoke test)

```bash
uv run --no-project --with boto3 --with httpx python scripts/cloud_smoke_test.py
```

Necesita credenciales AWS con permisos de administración sobre el User Pool. Crea un usuario temporal confirmado (sin enviar correo) y lo elimina al terminar. Comprueba:
- `/health` y CORS desde el dominio de Vercel.
- Rechazo de tokens sin firma.
- Login real.
- Creación de workspace.
- Subida directa a S3.
- Confirmación y procesamiento hasta `READY` por el worker.
- Catálogo, descarga, aislamiento (404 en un workspace ajeno) y borrado lógico.

Salida esperada: `19/19 comprobaciones OK`.

## 6. Diagnóstico rápido

| Síntoma | Causa probable | Acción |
|---|---|---|
| API devuelve 503 en ráfagas | Límite de 10 ejecuciones concurrentes de Lambda (métrica `Throttles`) | Esperar o pedir el aumento de cuota; el frontend ya reintenta lecturas |
| 500 con `requires version 3.0.2 or greater of the psycopg DBAPI` | Paquete sin `.dist-info` | Reempaquetar con el script actual y aplicar |
| 401 con un token válido | `CDM_COGNITO_*` mal configurado o el frontend usa otro User Pool | Revisar `environment.prod.ts` y las variables de la Lambda |
| PUT a S3 con 403 | Rol de la API sin `s3:PutObject` o URL caducada | Revisar `module.lambda_api` y repetir la carga |
| Error de CORS en el navegador | Dominio fuera de `allowed_cors_origins` | Añadirlo y aplicar Terraform |
| Documento se queda en `UPLOADED` | Worker sin base de datos o mensajes en la DLQ | Logs de `/aws/lambda/cdm-dev-worker` y [runbook SQS/DLQ](sqs-dlq-replay-and-monitoring.md) |

## 7. Rollback

- **Frontend:** en Vercel, *Promote* de un despliegue anterior (o `vercel rollback`).
- **Backend:** volver al commit anterior, reempaquetar y `terraform apply` (solo cambia `source_code_hash`).
- **Base de datos:** las migraciones Alembic son reversibles (`alembic downgrade -1`). Neon conserva 6 h de historial para restauración puntual.

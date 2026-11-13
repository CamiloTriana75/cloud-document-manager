# Runbook: Despliegue, Smoke Test y Rollback de Lambda API — CDM

> Jira: **CDM-20** (subtareas **CDM-119** y **CDM-120**) · Fecha: 2026-11-12
> Regla rectora: [`AGENTS.md`](../../AGENTS.md) §13 (AWS, costes y Terraform) y §20 (Protocolo de agentes).

Este runbook documenta el procedimiento reproducible para empaquetar, desplegar, validar y hacer rollback del backend FastAPI sobre AWS Lambda y API Gateway HTTP API.

---

## 1. Empaquetado del Artefacto

El empaquetado de la aplicación se realiza de forma determinística utilizando `uv`:

```bash
# Genera el archivo ZIP en build/cdm-api-lambda.zip con dependencias para Linux x86_64
python scripts/package_lambda_api.py -o build/cdm-api-lambda.zip
```

### Características del paquete:
- **Runtime:** Python 3.12 (`x86_64-manylinux2014`).
- **Adaptador:** Mangum (`lifespan="off"`).
- **Exclusiones:** Se purgan archivos `__pycache__`, `.pyc`, tests y dependencias de desarrollo (`pytest`, `ruff`, `mypy`).

---

## 2. Despliegue con Terraform (Staging / Dev)

> ⚠️ **REGLA DE ORO:** Nunca ejecutar `terraform apply` sin revisar antes el plan y contar con la aprobación expresa del propietario.

```bash
cd infrastructure/terraform/environments/dev

# 1. Inicializar providers y módulos
terraform init

# 2. Formatear y validar sintaxis estática
terraform fmt -check -recursive
terraform validate

# 3. Generar plan de ejecución para revisión
terraform plan -var="lambda_package_path=../../../build/cdm-api-lambda.zip" -out=tfplan

# 4. Aplicar tras aprobación expresa
terraform apply tfplan
```

---

## 3. Smoke Test del Endpoint Desplegado

Una vez aplicado, Terraform imprime el output `api_gateway_endpoint`.

### Verificación del endpoint de salud (`GET /health`):
```bash
# Obtener URL del endpoint
API_URL=$(terraform output -raw api_gateway_endpoint)

# Smoke test HTTP 200
curl -i -X GET "$API_URL/health"
```

**Respuesta esperada (HTTP 200 OK):**
```json
{
  "status": "ok",
  "service": "cdm-api",
  "version": "0.1.0"
}
```

### Verificación de error envelope estandarizado (`GET /ruta-invalida`):
```bash
curl -i -X GET "$API_URL/ruta-invalida"
```

**Respuesta esperada (HTTP 404 Not Found):**
```json
{
  "error": {
    "code": "not_found",
    "message": "Not Found"
  }
}
```

### Verificación de CORS:
```bash
curl -i -X OPTIONS "$API_URL/health" \
  -H "Origin: http://localhost:4200" \
  -H "Access-Control-Request-Method: GET"
```

**Respuesta esperada:** Headers `Access-Control-Allow-Origin: http://localhost:4200` y `Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS, HEAD`.

---

## 4. Procedimiento de Rollback

En caso de fallo en el smoke test o anomalía detectada en CloudWatch:

### Opción A: Rollback rápido de código (reversión de versión anterior del ZIP)
```bash
# Re-desplegar la versión ZIP estable anterior
aws lambda update-function-code \
  --function-name cdm-dev-api \
  --zip-file fileb://build/cdm-api-lambda-previous.zip
```

### Opción B: Rollback de infraestructura mediante Terraform
```bash
# Regresar el commit de Terraform al hash estable anterior
git checkout <commit_anterior_estable> -- infrastructure/terraform

# Generar plan de reversión y aplicar
terraform plan -out=tfplan_rollback
terraform apply tfplan_rollback
```

### Opción C: Destrucción de prueba (Teardown completo)
```bash
terraform plan -destroy -out=tfplan_destroy
terraform apply tfplan_destroy
```

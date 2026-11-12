# Módulo Terraform: `s3-document-store`

> Jira: **CDM-19** (subtareas **CDM-73** y **CDM-74**) · Épica: **CDM-3**

Módulo reutilizable para aprovisionar el almacenamiento privado de documentos de Cloud Document Manager (CDM).

## Responsabilidad

Gestiona exclusivamente el bucket S3 privado, sus controles de acceso, cifrado, reglas CORS y ciclo de vida de objetos para la ingesta de documentos.

## Características de Seguridad (AGENTS.md §12)

1. **Bloqueo Público Total:**
   - S3 Block Public Access activado al 100% (`block_public_acls`, `block_public_policy`, `ignore_public_acls`, `restrict_public_buckets`).
   - `object_ownership = "BucketOwnerEnforced"` (deshabilita ACLs obsoletas).
2. **Cifrado en Reposo:**
   - Cifrado por defecto SSE-S3 (`AES256`) con Bucket Key.
   - **Coste:** $0 adicional (sin coste por llamada KMS ni mensualidad de clave), protegiendo los créditos de la cuenta Free Plan (ADR-0007 / `docs/runbooks/aws-account-audit.md`).
3. **Cifrado en Tránsito:**
   - Política de bucket con regla `DenyInsecureTransport` (`aws:SecureTransport = "false"`).
4. **CORS Restringido:**
   - Métodos permitidos: `PUT`, `GET`, `HEAD`.
   - Headers permitidos: `*` (incluye `content-type`, `x-amz-*`).
   - Headers expuestos: `ETag`, `x-amz-server-side-encryption`, `x-amz-request-id`, `x-amz-id-2`.
   - Orígenes: configurables por variable (nunca `*` en producción).
5. **Ciclo de Vida (Lifecycle):**
   - Aborto de subidas multipart incompletas a los 7 días.
   - Expiración automática de cargas temporales no confirmadas bajo el prefijo `temp/` a las 24 horas.
   - Expiración de versiones no actuales tras 30 días si el versionado se activa.

## Convención de Claves / Prefijos (CDM-73)

Las claves de almacenamiento en S3 son generadas opacamente por el servidor y siguen el siguiente esquema de particionamiento:

* **Documentos confirmados:**
  `tenants/{tenant_id}/documents/{document_id}/{opaque_key}`
* **Sesiones de carga provisionales / temporales:**
  `temp/{upload_session_id}/{opaque_key}`

*Nota de seguridad:* Nunca se utiliza el nombre original del archivo enviado por el usuario como clave directa de S3 para evitar colisiones, sobreescrituras e inyecciones de ruta.

## Uso

```hcl
module "s3_document_store" {
  source = "../../modules/s3-document-store"

  bucket_prefix        = "cdm-dev-docs"
  allowed_cors_origins = ["http://localhost:4200"]
  force_destroy        = true  # Solo en dev para pruebas limpias
  versioning_enabled   = false # Ahorro de almacenamiento en Free Plan

  tags = local.tags
}
```

## Entradas

| Variable | Tipo | Default | Descripción |
|---|---|---|---|
| `bucket_name` | string | `null` | Nombre explícito del bucket (si se omite, se usa prefijo + account ID). |
| `bucket_prefix` | string | `"cdm-dev-docs"` | Prefijo para generar el nombre único. |
| `force_destroy` | bool | `false` | Permite destruir el bucket aunque contenga objetos (útil para dev). |
| `versioning_enabled` | bool | `false` | Activa el versionado de S3. |
| `allowed_cors_origins` | list(string) | `["http://localhost:4200"]` | Orígenes permitidos para CORS. |
| `abort_incomplete_multipart_upload_days` | number | `7` | Días para cancelar multipart uploads inconclusos. |
| `temp_prefix_expiration_days` | number | `1` | Días para expirar objetos en `temp/`. |
| `tags` | map(string) | `{}` | Etiquetas adicionales. |

## Salidas

| Output | Descripción |
|---|---|
| `bucket_id` | ID del bucket S3. |
| `bucket_name` | Nombre del bucket creado. |
| `bucket_arn` | ARN del bucket para políticas IAM y eventos SQS. |
| `bucket_domain_name` | Nombre de dominio global de S3. |
| `bucket_regional_domain_name` | Nombre de dominio regional de S3. |

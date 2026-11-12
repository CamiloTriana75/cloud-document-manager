# Variables del módulo s3-document-store (CDM-19)

variable "bucket_name" {
  description = "Nombre explícito del bucket S3. Si no se especifica, se genera automáticamente usando bucket_prefix y el account_id."
  type        = string
  default     = null
}

variable "bucket_prefix" {
  description = "Prefijo para el nombre del bucket S3 si bucket_name no se proporciona (minúsculas, números y guiones)."
  type        = string
  default     = "cdm-dev-docs"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,50}[a-z0-9]$", var.bucket_prefix))
    error_message = "El prefijo debe tener entre 3 y 52 caracteres, usar minúsculas, números y guiones, y no comenzar ni terminar con guión."
  }
}

variable "force_destroy" {
  description = "Permite destruir el bucket aunque contenga objetos (útil para dev/teardown según AGENTS.md §13)."
  type        = bool
  default     = false
}

variable "versioning_enabled" {
  description = "Habilitar versionado de objetos. En dev se recomienda false para proteger la cuota de almacenamiento del Free Plan."
  type        = bool
  default     = false
}

variable "allowed_cors_origins" {
  description = "Lista de orígenes permitidos para peticiones CORS (subida directa desde Angular). Nunca '*' en producción."
  type        = list(string)
  default     = ["http://localhost:4200"]
}

variable "abort_incomplete_multipart_upload_days" {
  description = "Días tras los cuales se abortan y limpian subidas multipart incompletas."
  type        = number
  default     = 7

  validation {
    condition     = var.abort_incomplete_multipart_upload_days >= 1 && var.abort_incomplete_multipart_upload_days <= 30
    error_message = "Los días para abortar subidas multipart incompletas deben estar entre 1 y 30."
  }
}

variable "temp_prefix_expiration_days" {
  description = "Días tras los cuales se eliminan objetos temporales no confirmados bajo el prefijo 'temp/'."
  type        = number
  default     = 1

  validation {
    condition     = var.temp_prefix_expiration_days >= 1 && var.temp_prefix_expiration_days <= 7
    error_message = "Los días de expiración para temp/ deben estar entre 1 y 7."
  }
}

variable "noncurrent_version_expiration_days" {
  description = "Días de retención para versiones no actuales si el versionado está activo."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Etiquetas adicionales específicas del bucket."
  type        = map(string)
  default     = {}
}

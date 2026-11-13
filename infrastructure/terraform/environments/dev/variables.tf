# Variables del entorno dev (CDM-18). Secretos: nunca aquí.

variable "aws_region" {
  description = "Región AWS del stack (ADR-0007: us-east-1)."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Nombre del entorno (dev | prod)."
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Nombre corto del proyecto para naming de recursos."
  type        = string
  default     = "cdm"
}

variable "owner" {
  description = "Propietario responsable de los recursos y el coste (tag Owner)."
  type        = string
  default     = "Camilo Triana"
}

variable "log_retention_days" {
  description = "Retención de logs CloudWatch en días. Corta para no consumir créditos (auditoría CDM-17 §3)."
  type        = number
  default     = 14

  validation {
    condition     = contains([1, 3, 7, 14, 30], var.log_retention_days)
    error_message = "Solo se permiten 1, 3, 7, 14 o 30 días (coste de logs controlado)."
  }
}

variable "max_file_size_mb" {
  description = "Tamaño máximo de documento aceptado en MB (política de archivos, AGENTS.md §12)."
  type        = number
  default     = 50

  validation {
    condition     = var.max_file_size_mb >= 1 && var.max_file_size_mb <= 100
    error_message = "El tamaño máximo debe estar entre 1 y 100 MB."
  }
}

variable "allowed_cors_origins" {
  description = "Orígenes CORS permitidos para la API y el bucket S3. Nunca '*' en producción."
  type        = list(string)
  default     = ["http://localhost:4200"]
}

variable "lambda_memory_mb" {
  description = "Memoria por defecto de las funciones Lambda (MB). 128 MB es el mínimo del free tier."
  type        = number
  default     = 256

  validation {
    condition     = var.lambda_memory_mb >= 128 && var.lambda_memory_mb <= 512
    error_message = "La memoria Lambda debe estar entre 128 y 512 MB para MVP."
  }
}

variable "enable_rds" {
  description = "Flag de seguridad para aprovisionar RDS. Por defecto false para evitar consumo de créditos (ADR-0008)."
  type        = bool
  default     = false
}

variable "enable_cloudfront" {
  description = "Habilita la distribución CloudFront para el frontend (CDM-80). Requiere verificación previa de la cuenta AWS por soporte."
  type        = bool
  default     = false
}

variable "common_tags" {
  description = "Etiquetas adicionales aplicables a todos los recursos."
  type        = map(string)
  default     = {}
}

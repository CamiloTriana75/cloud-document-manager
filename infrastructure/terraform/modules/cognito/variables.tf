# Variables del módulo cognito (CDM-24)

variable "project_name" {
  description = "Prefijo para los nombres de los recursos."
  type        = string
  default     = "cdm"
}

variable "environment" {
  description = "Entorno de despliegue (dev | prod)."
  type        = string
}

variable "aws_region" {
  description = "Región AWS (us-east-1 según ADR-0007)."
  type        = string
  default     = "us-east-1"
}

variable "callback_urls" {
  description = "URLs de retorno permitidas para OAuth Authorization Code con PKCE."
  type        = list(string)
  default     = ["http://localhost:4200/auth/callback"]
}

variable "logout_urls" {
  description = "URLs de redirección tras cerrar sesión."
  type        = list(string)
  default     = ["http://localhost:4200/auth/login"]
}

variable "enable_domain" {
  description = "Habilita un dominio prefijo para Cognito Hosted UI y endpoints OAuth."
  type        = bool
  default     = true
}

variable "domain_prefix" {
  description = "Prefijo personalizado para el dominio de Cognito (si está vacío, se genera automáticamente)."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Etiquetas a aplicar a todos los recursos del módulo."
  type        = map(string)
  default     = {}
}

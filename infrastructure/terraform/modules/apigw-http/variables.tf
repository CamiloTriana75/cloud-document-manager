# Variables del módulo apigw-http (CDM-20)

variable "api_name" {
  description = "Nombre de la API en API Gateway."
  type        = string
}

variable "lambda_invoke_arn" {
  description = "ARN de invocación de la función Lambda backend."
  type        = string
}

variable "lambda_function_name" {
  description = "Nombre de la función Lambda para conceder permisos de invocación."
  type        = string
}

variable "allowed_cors_origins" {
  description = "Lista de orígenes permitidos para CORS (nunca '*' en producción)."
  type        = list(string)
  default     = ["http://localhost:4200"]
}

variable "tags" {
  description = "Etiquetas adicionales para los recursos de API Gateway."
  type        = map(string)
  default     = {}
}

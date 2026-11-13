# Variables del módulo observability-cloudwatch (CDM-52)

variable "project_name" {
  description = "Nombre base del proyecto."
  type        = string
}

variable "environment" {
  description = "Entorno de despliegue (dev, prod)."
  type        = string
}

variable "api_function_name" {
  description = "Nombre de la función Lambda API para monitoreo."
  type        = string
}

variable "worker_function_name" {
  description = "Nombre de la función Lambda Worker para monitoreo."
  type        = string
}

variable "dlq_queue_name" {
  description = "Nombre de la Dead Letter Queue (DLQ) de SQS para detección de mensajes no procesables."
  type        = string
}

variable "api_error_threshold" {
  description = "Umbral de errores acumulados en 5 minutos para alarmar la Lambda API."
  type        = number
  default     = 5
}

variable "worker_error_threshold" {
  description = "Umbral de errores acumulados en 5 minutos para alarmar la Lambda Worker."
  type        = number
  default     = 2
}

variable "tags" {
  description = "Mapa de etiquetas estandarizadas para los recursos de observabilidad."
  type        = map(string)
  default     = {}
}

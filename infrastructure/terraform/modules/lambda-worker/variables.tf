# Variables para el módulo Lambda Worker — CDM (CDM-36)

variable "function_name" {
  description = "Nombre de la función AWS Lambda worker"
  type        = string
}

variable "handler" {
  description = "Punto de entrada de la función Lambda"
  type        = string
  default     = "cdm.bootstrap.worker_handler.handler"
}

variable "runtime" {
  description = "Runtime de Python para la función Lambda"
  type        = string
  default     = "python3.12"
}

variable "memory_size" {
  description = "Memoria asignada a la función Lambda en MB"
  type        = number
  default     = 256
}

variable "timeout" {
  description = "Timeout máximo de ejecución en segundos"
  type        = number
  default     = 30
}

variable "log_retention_days" {
  description = "Días de retención de logs en CloudWatch"
  type        = number
  default     = 7
}

variable "package_path" {
  description = "Ruta opcional al archivo .zip con el código empaquetado. Si es null, usa el placeholder default."
  type        = string
  default     = null
}

variable "sqs_queue_arn" {
  description = "ARN de la cola SQS consumida por el worker"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN del bucket S3 privado que contiene los documentos"
  type        = string
}

variable "batch_size" {
  description = "Cantidad máxima de mensajes que Lambda procesa por lote (1 a 10)"
  type        = number
  default     = 10
}

variable "environment_variables" {
  description = "Mapa de variables de entorno para la función Lambda"
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Etiquetas aplicables a los recursos del módulo"
  type        = map(string)
  default     = {}
}

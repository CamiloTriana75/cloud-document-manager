# Variables del módulo SQS Worker Queue (CDM-35)

variable "queue_name" {
  type        = string
  description = "Nombre asignado a la cola principal SQS de eventos de documentos."
}

variable "dlq_name" {
  type        = string
  description = "Nombre opcional para la Dead Letter Queue. Si se omite, se añade sufijo -dlq."
  default     = null
}

variable "s3_bucket_arn" {
  type        = string
  description = "ARN del bucket S3 emisor de los eventos (usado en la condición aws:SourceArn de la política SQS)."
}

variable "visibility_timeout_seconds" {
  type        = number
  description = "Tiempo de visibilidad de los mensajes en segundos (recomendado: 6x timeout de Lambda worker, default 180s = 3m)."
  default     = 180

  validation {
    condition     = var.visibility_timeout_seconds >= 30 && var.visibility_timeout_seconds <= 43200
    error_message = "El visibility_timeout_seconds debe estar entre 30 y 43200 segundos."
  }
}

variable "message_retention_seconds" {
  type        = number
  description = "Retención de mensajes en la cola principal en segundos (default 4 días = 345600s)."
  default     = 345600

  validation {
    condition     = var.message_retention_seconds >= 60 && var.message_retention_seconds <= 1209600
    error_message = "El message_retention_seconds debe estar entre 60 y 1209600 segundos (14 días)."
  }
}

variable "dlq_message_retention_seconds" {
  type        = number
  description = "Retención de mensajes en la DLQ en segundos (default 14 días = 1209600s)."
  default     = 1209600

  validation {
    condition     = var.dlq_message_retention_seconds >= 60 && var.dlq_message_retention_seconds <= 1209600
    error_message = "El dlq_message_retention_seconds debe estar entre 60 y 1209600 segundos (14 días)."
  }
}

variable "receive_wait_time_seconds" {
  type        = number
  description = "Tiempo de espera para long polling en segundos (0 a 20s, default 20s para minimizar llamadas vacías y costes)."
  default     = 20

  validation {
    condition     = var.receive_wait_time_seconds >= 0 && var.receive_wait_time_seconds <= 20
    error_message = "El receive_wait_time_seconds debe estar entre 0 y 20 segundos."
  }
}

variable "max_receive_count" {
  type        = number
  description = "Número máximo de entregas antes de desviar el mensaje fallido a la DLQ (default: 3)."
  default     = 3

  validation {
    condition     = var.max_receive_count >= 1 && var.max_receive_count <= 100
    error_message = "El max_receive_count debe estar entre 1 y 100."
  }
}

variable "tags" {
  type        = map(string)
  description = "Etiquetas aplicables a los recursos SQS."
  default     = {}
}

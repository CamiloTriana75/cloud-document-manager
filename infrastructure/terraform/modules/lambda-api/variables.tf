# Variables del módulo lambda-api (CDM-20)

variable "function_name" {
  description = "Nombre de la función Lambda."
  type        = string
}

variable "handler" {
  description = "Punto de entrada de la función Lambda (módulo.objeto)."
  type        = string
  default     = "cdm.bootstrap.lambda_handler.handler"
}

variable "runtime" {
  description = "Runtime de Python para la función Lambda."
  type        = string
  default     = "python3.12"
}

variable "memory_size" {
  description = "Cantidad de memoria en MB asignada a la función Lambda."
  type        = number
  default     = 256

  validation {
    condition     = var.memory_size >= 128 && var.memory_size <= 512
    error_message = "La memoria debe estar entre 128 y 512 MB para controlar costes en Free Plan."
  }
}

variable "timeout" {
  description = "Tiempo máximo de ejecución en segundos antes de timeout."
  type        = number
  default     = 15

  validation {
    condition     = var.timeout >= 1 && var.timeout <= 60
    error_message = "El timeout debe estar entre 1 y 60 segundos."
  }
}

variable "log_retention_days" {
  description = "Días de retención en CloudWatch Logs (auditoría CDM-17: retención corta para evitar cobros de logs)."
  type        = number
  default     = 14
}

variable "environment_variables" {
  description = "Variables de entorno inyectadas a la función Lambda (nunca secretos en plano)."
  type        = map(string)
  default     = {}
}

variable "package_path" {
  description = "Ruta opcional al archivo ZIP empaquetado. Si se omite, se genera un paquete base reproducible."
  type        = string
  default     = null
}

variable "s3_bucket_arn" {
  description = "ARN del bucket S3 de documentos para acotar la política IAM con menor privilegio (CDM-51)."
  type        = string
  default     = null
}

variable "tags" {
  description = "Etiquetas adicionales específicas para la función Lambda."
  type        = map(string)
  default     = {}
}

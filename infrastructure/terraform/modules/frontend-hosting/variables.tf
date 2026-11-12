# Variables del módulo frontend-hosting (CDM-23 / CDM-79 / CDM-80)

variable "project_name" {
  description = "Prefijo para los nombres de los recursos."
  type        = string
  default     = "cdm"
}

variable "environment" {
  description = "Entorno de despliegue (dev | prod)."
  type        = string
}

variable "price_class" {
  description = "Clase de precio de CloudFront. PriceClass_100 cubre Norteamérica y Europa y queda dentro del Always Free Tier (1 TB/mes)."
  type        = string
  default     = "PriceClass_100"

  validation {
    condition     = contains(["PriceClass_100", "PriceClass_200", "PriceClass_All"], var.price_class)
    error_message = "Debe ser PriceClass_100, PriceClass_200 o PriceClass_All."
  }
}

variable "force_destroy" {
  description = "Permite destruir el bucket aunque contenga objetos estáticos (recomendado true en dev)."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Etiquetas a aplicar a todos los recursos del módulo."
  type        = map(string)
  default     = {}
}

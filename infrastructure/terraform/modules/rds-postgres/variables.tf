# Variables del módulo rds-postgres (CDM-21 / CDM-75 / CDM-76)

variable "enable_rds" {
  description = "Flag de seguridad para aprovisionar RDS. Por defecto false para evitar consumo de créditos (ADR-0008)."
  type        = bool
  default     = false
}

variable "project_name" {
  description = "Prefijo para los nombres de los recursos."
  type        = string
  default     = "cdm"
}

variable "environment" {
  description = "Entorno de despliegue (dev | prod)."
  type        = string
}

variable "vpc_id" {
  description = "ID de la VPC donde residirá RDS. Si es null, se consulta la VPC por defecto de la cuenta."
  type        = string
  default     = null
}

variable "subnet_ids" {
  description = "Lista de IDs de subredes privadas para el DB Subnet Group (mínimo 2 en distintas AZs). Si está vacía, se usan las subredes por defecto."
  type        = list(string)
  default     = []
}

variable "backend_security_group_ids" {
  description = "IDs de Security Groups con permiso de entrada en el puerto 5432 (por ejemplo, el Security Group de Lambda)."
  type        = list(string)
  default     = []
}

variable "instance_class" {
  description = "Clase de la instancia RDS. db.t4g.micro es la más económica para PostgreSQL (ADR-0008)."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "Almacenamiento inicial en GiB (mínimo 20 GiB para gp3)."
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Límite superior de auto-escalado de almacenamiento en GiB. Igual al inicial para evitar costes imprevistos."
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Nombre de la base de datos inicial a crear."
  type        = string
  default     = "cdm"
}

variable "db_username" {
  description = "Nombre del usuario administrador de la base de datos."
  type        = string
  default     = "cdm_admin"
}

variable "skip_final_snapshot" {
  description = "Determina si se omite el snapshot final al destruir la instancia (true para desarrollo efímero)."
  type        = bool
  default     = true
}

variable "deletion_protection" {
  description = "Evita la destrucción accidental de la base de datos."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Etiquetas a aplicar a todos los recursos del módulo."
  type        = map(string)
  default     = {}
}

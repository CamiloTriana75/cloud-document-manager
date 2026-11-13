# Outputs del módulo rds-postgres (CDM-21 / CDM-76)

output "db_endpoint" {
  description = "Endpoint de conexión a la base de datos (host:puerto)."
  value       = try(aws_db_instance.this[0].endpoint, null)
}

output "db_address" {
  description = "Dirección de host (DNS) de la base de datos."
  value       = try(aws_db_instance.this[0].address, null)
}

output "db_port" {
  description = "Puerto de escucha de PostgreSQL (por defecto 5432)."
  value       = try(aws_db_instance.this[0].port, null)
}

output "db_name" {
  description = "Nombre de la base de datos."
  value       = try(aws_db_instance.this[0].db_name, null)
}

output "secret_arn" {
  description = "ARN del secreto en AWS Secrets Manager con las credenciales de conexión."
  value       = try(aws_secretsmanager_secret.db_credentials[0].arn, null)
}

output "security_group_id" {
  description = "ID del Security Group asociado a la instancia RDS."
  value       = try(aws_security_group.rds[0].id, null)
}

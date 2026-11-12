# Módulo RDS PostgreSQL — Cloud Document Manager (CDM-21 / CDM-75 / CDM-76)
#
# Principios aplicados:
# - enable_rds = false por defecto para no agotar los créditos del AWS Free Plan (ADR-0008).
# - Single-AZ db.t4g.micro con 20 GiB gp3 (coste mínimo en caso de aprovisionamiento).
# - Totalmente privado (publicly_accessible = false) sin NAT Gateway.
# - Credenciales generadas aleatoriamente y almacenadas en AWS Secrets Manager (cero credenciales en Git).
# - Teardown limpio con skip_final_snapshot = true y recovery_window_in_days = 0 para desarrollo.

# Consulta opcional de VPC y subredes por defecto si no se especifican explícitamente
data "aws_vpc" "default" {
  count   = var.enable_rds && var.vpc_id == null ? 1 : 0
  default = true
}

data "aws_subnets" "default" {
  count = var.enable_rds && length(var.subnet_ids) == 0 ? 1 : 0
  filter {
    name   = "vpc-id"
    values = [var.vpc_id != null ? var.vpc_id : data.aws_vpc.default[0].id]
  }
}

# DB Subnet Group (requiere subredes en al menos 2 zonas de disponibilidad)
resource "aws_db_subnet_group" "this" {
  count = var.enable_rds ? 1 : 0

  name        = "${var.project_name}-${var.environment}-db-subnet-group"
  description = "Subredes para la base de datos PostgreSQL de ${var.project_name} (${var.environment})"
  subnet_ids  = length(var.subnet_ids) > 0 ? var.subnet_ids : data.aws_subnets.default[0].ids

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-db-subnet-group"
    }
  )
}

# Security Group para RDS: solo ingress en puerto 5432 desde los Security Groups permitidos
resource "aws_security_group" "rds" {
  count = var.enable_rds ? 1 : 0

  name        = "${var.project_name}-${var.environment}-rds-sg"
  description = "Control de acceso a PostgreSQL CDM (sin acceso publico ni NAT Gateway)"
  vpc_id      = var.vpc_id != null ? var.vpc_id : data.aws_vpc.default[0].id

  dynamic "ingress" {
    for_each = length(var.backend_security_group_ids) > 0 ? [1] : []
    content {
      description     = "Acceso PostgreSQL desde el backend Lambda"
      from_port       = 5432
      to_port         = 5432
      protocol        = "tcp"
      security_groups = var.backend_security_group_ids
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-rds-sg"
    }
  )
}

# Generación segura de contraseña administrativa
resource "random_password" "db_password" {
  count = var.enable_rds ? 1 : 0

  length           = 24
  special          = false
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Secreto en AWS Secrets Manager para evitar credenciales persistidas en Git o logs
resource "aws_secretsmanager_secret" "db_credentials" {
  count = var.enable_rds ? 1 : 0

  name                    = "${var.project_name}-${var.environment}-rds-credentials"
  description             = "Credenciales de conexion para RDS PostgreSQL CDM (${var.environment})"
  recovery_window_in_days = 0 # Eliminación inmediata sin ventana de 30 días al hacer teardown

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  count = var.enable_rds ? 1 : 0

  secret_id = aws_secretsmanager_secret.db_credentials[0].id
  secret_string = jsonencode({
    engine   = "postgres"
    host     = aws_db_instance.this[0].address
    port     = aws_db_instance.this[0].port
    dbname   = var.db_name
    username = var.db_username
    password = random_password.db_password[0].result
  })
}

# Instancia RDS PostgreSQL
resource "aws_db_instance" "this" {
  count = var.enable_rds ? 1 : 0

  identifier = "${var.project_name}-${var.environment}-postgres"

  engine         = "postgres"
  engine_version = "16.3"
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db_password[0].result

  db_subnet_group_name   = aws_db_subnet_group.this[0].name
  vpc_security_group_ids = [aws_security_group.rds[0].id]

  publicly_accessible = false
  multi_az            = false

  skip_final_snapshot = var.skip_final_snapshot
  deletion_protection = var.deletion_protection

  backup_retention_period    = 1
  backup_window              = "03:00-04:00"
  maintenance_window         = "Mon:04:30-Mon:05:30"
  auto_minor_version_upgrade = true

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-postgres"
    }
  )
}

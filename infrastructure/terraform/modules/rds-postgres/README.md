# Módulo Terraform: RDS PostgreSQL (CDM-21)

Módulo reutilizable para aprovisionar una base de datos PostgreSQL 16 administrada en AWS RDS, optimizada para control de costes y sin requerir NAT Gateway.

## Características

- **Seguridad Financiera (`enable_rds = false` por defecto):** No crea ningún recurso a menos que se active explícitamente, protegiendo la bolsa de \$100 USD del AWS Free Plan ([ADR-0008](../../../docs/adr/0008-postgres-local-vs-rds.md)).
- **Coste Mínimo:** Configurado con `db.t4g.micro` Single-AZ y 20 GiB `gp3` sin auto-escalado ilimitado de almacenamiento.
- **Topología Segura sin NAT Gateway:** Subredes privadas, `publicly_accessible = false` y Security Group con ingress restringido únicamente al backend.
- **Credenciales Seguras:** Generación de contraseña aleatoria con `random_password` y persistencia automática en AWS Secrets Manager.
- **Teardown Ágil:** Parámetros preparados para destrucción rápida (`skip_final_snapshot = true` y `recovery_window_in_days = 0`) en entornos de desarrollo o demos efímeras.

## Uso

```hcl
module "rds_postgres" {
  source = "../../modules/rds-postgres"

  enable_rds                 = var.enable_rds
  environment                = var.environment
  project_name               = var.project_name
  backend_security_group_ids = [module.lambda_api.security_group_id]

  tags = local.tags
}
```

## Inputs

| Nombre | Tipo | Default | Descripción |
|---|---|---|---|
| `enable_rds` | `bool` | `false` | Activa o desactiva la creación de recursos RDS. |
| `project_name` | `string` | `"cdm"` | Prefijo para nombres de recursos. |
| `environment` | `string` | N/A | Entorno de despliegue (`dev`, `prod`). |
| `vpc_id` | `string` | `null` | VPC donde desplegar (consulta la default si es null). |
| `subnet_ids` | `list(string)` | `[]` | Subredes para DB Subnet Group (mínimo 2 en distintas AZs). |
| `backend_security_group_ids` | `list(string)` | `[]` | Security Groups con acceso permitido al puerto 5432. |
| `instance_class` | `string` | `"db.t4g.micro"` | Tipo de instancia RDS. |
| `allocated_storage` | `number` | `20` | Almacenamiento inicial en GiB. |
| `max_allocated_storage` | `number` | `20` | Límite máximo de almacenamiento. |
| `db_name` | `string` | `"cdm"` | Nombre de la base de datos inicial. |
| `db_username` | `string` | `"cdm_admin"` | Usuario administrador. |
| `skip_final_snapshot` | `bool` | `true` | Omite snapshot final al destruir. |
| `deletion_protection` | `bool` | `false` | Protección contra borrado accidental. |
| `tags` | `map(string)` | `{}` | Etiquetas de infraestructura. |

## Outputs

| Nombre | Descripción |
|---|---|
| `db_endpoint` | Endpoint host:puerto de la base de datos. |
| `db_address` | Hostname DNS de la base de datos. |
| `db_port` | Puerto de escucha (5432). |
| `db_name` | Nombre de la base de datos. |
| `secret_arn` | ARN del secreto con credenciales en AWS Secrets Manager. |
| `security_group_id` | ID del Security Group de RDS. |

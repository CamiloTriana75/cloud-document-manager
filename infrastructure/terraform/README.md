# Terraform — CDM

Infraestructura declarada como código, pequeña, parametrizable y destruible (AGENTS.md §13). Región: `us-east-1` (ADR-0007). PostgreSQL: local (ADR-0008).

## Estructura

```text
infrastructure/terraform/
├── modules/            # módulos reutilizables por responsabilidad
│   └── README.md       # convenciones de módulo
└── environments/
    ├── dev/            # stack de desarrollo (aprobación: ya concedida para recursos always-free)
    └── prod/           # se crea solo con plan revisado + aprobación explícita del propietario
```

- Cada módulo vive en `modules/<nombre>/` y recibe `tags`/`name` desde el entorno; nunca crea recursos fuera de su responsabilidad.
- Los entornos componen módulos y fijan variables; no duplican lógica.

## Comandos (desde `environments/dev`)

```bash
terraform init                # descarga providers fijados; crea .terraform.lock.hcl (se versiona)
terraform fmt -recursive      # formato; CI verifica con -check
terraform validate            # validación estática
terraform plan -out=tfplan    # plan revisable ANTES de aplicar (tfplan/ está en .gitignore)
terraform apply tfplan        # aplica SOLO con aprobación explícita del propietario (AGENTS.md §13)
terraform destroy             # destruye; revisar el plan de destrucción antes
```

**Reglas de oro:**

1. Nunca `apply` ni `destroy` sin revisar el plan y la autorización del propietario (costes).
2. Estado: local por ahora (`terraform.tfstate`, en `.gitignore`). Al haber bucket de estado (CDM-19+) se migrará a backend S3 con locking; nunca commitear `*.tfstate*`.
3. Todos los recursos quedan etiquetados vía `default_tags` del provider: `Project=CDM`, `Environment`, `Owner=Camilo Triana`.
4. Variables con `description`; secretos por variables de entorno/SSM, nunca en `.tf` ni en Git.
5. Tear-down de sesión temporal: checklist en `docs/runbooks/aws-account-audit.md` §6.

## Gates

- `terraform fmt -check -recursive` y `terraform validate` corren en CI (job `infra`, `.github/workflows/ci.yml`).

# Módulo Terraform: Amazon Cognito User Pool & App Client (CDM-24)

Módulo reutilizable para aprovisionar el proveedor de identidad de usuarios con Amazon Cognito, configurado para clientes públicos Single-Page Application (SPA) en Angular.

## Características

- **Seguridad en Navegador:** App Client público con `generate_secret = false` (sin secretos expuestos en el frontend).
- **Flujos OAuth Seguros:** Configurado para `Authorization Code` con PKCE y flujos SRP/Password para SDKs.
- **Prevención de Enumeración:** `prevent_user_existence_errors = "ENABLED"` para evitar que atacantes descubran qué correos están registrados.
- **Tokens y Sesión:** Tokens de acceso e ID válidos por 60 minutos; refresh token válido por 30 días con revocación de tokens habilitada.
- **Gratuito:** Totalmente cubierto por la cuota mensual permanente de 10,000 MAUs del Free Tier de Cognito.

## Uso

```hcl
module "cognito" {
  source = "../../modules/cognito"

  project_name  = var.project_name
  environment   = var.environment
  aws_region    = var.aws_region
  callback_urls = ["http://localhost:4200/auth/callback", module.frontend_hosting.cloudfront_url]
  logout_urls   = ["http://localhost:4200/auth/login", "${module.frontend_hosting.cloudfront_url}/auth/login"]

  tags = local.tags
}
```

## Inputs

| Nombre | Tipo | Default | Descripción |
|---|---|---|---|
| `project_name` | `string` | `"cdm"` | Prefijo para los nombres de los recursos. |
| `environment` | `string` | N/A | Entorno (`dev`, `prod`). |
| `aws_region` | `string` | `"us-east-1"` | Región AWS del User Pool. |
| `callback_urls` | `list(string)` | `["http://localhost:4200/auth/callback"]` | URLs autorizadas de retorno OAuth. |
| `logout_urls` | `list(string)` | `["http://localhost:4200/auth/login"]` | URLs autorizadas de redirección tras logout. |
| `enable_domain` | `bool` | `true` | Crea un dominio para endpoints OAuth y Hosted UI. |
| `domain_prefix` | `string` | `""` | Prefijo de dominio personalizado. |
| `tags` | `map(string)` | `{}` | Etiquetas de infraestructura. |

## Outputs

| Nombre | Descripción |
|---|---|
| `user_pool_id` | ID del User Pool. |
| `user_pool_arn` | ARN del User Pool. |
| `client_id` | ID del App Client público. |
| `issuer_url` | URL del emisor JWT (`https://cognito-idp.{region}.amazonaws.com/{pool_id}`). |
| `cognito_domain` | Dominio asignado en Cognito. |

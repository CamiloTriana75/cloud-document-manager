# Módulo Cognito User Pool & App Client — Cloud Document Manager (CDM-24)
#
# Principios aplicados:
# - User Pool configurado para inicio de sesión por correo electrónico verificado.
# - App Client exclusivo para SPA sin secret (generate_secret = false).
# - Flujo Authorization Code con PKCE para máxima seguridad en navegadores.
# - prevent_user_existence_errors = "ENABLED" para mitigar ataques de enumeración de cuentas.
# - Tokens de vida corta (1 hora para Access e ID Token) y Refresh Token de 30 días con revocación activa.
# - Coste cubierto dentro del Free Tier de Cognito (10,000 MAUs mensuales gratuitas de forma indefinida).

resource "aws_cognito_user_pool" "this" {
  name = "${var.project_name}-${var.environment}-user-pool"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  user_attribute_update_settings {
    attributes_require_verification_before_update = ["email"]
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Tu codigo de verificacion para Cloud Document Manager"
    email_message        = "Bienvenido a Cloud Document Manager. Tu codigo de verificacion es: {####}."
  }

  schema {
    attribute_data_type = "String"
    name                = "email"
    required            = true
    mutable             = true

    string_attribute_constraints {
      min_length = 5
      max_length = 254
    }
  }

  schema {
    attribute_data_type = "String"
    name                = "name"
    required            = false
    mutable             = true

    string_attribute_constraints {
      min_length = 1
      max_length = 100
    }
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-user-pool"
      Description = "Directorio de identidades de usuarios para ${var.project_name} (${var.environment})"
    }
  )
}

# Sufijo aleatorio para garantizar unicidad global del dominio de Cognito
resource "random_string" "domain_suffix" {
  count = var.enable_domain ? 1 : 0

  length  = 8
  special = false
  upper   = false
}

resource "aws_cognito_user_pool_domain" "this" {
  count = var.enable_domain ? 1 : 0

  domain       = var.domain_prefix != "" ? var.domain_prefix : "${var.project_name}-${var.environment}-${random_string.domain_suffix[0].result}"
  user_pool_id = aws_cognito_user_pool.this.id
}

# App Client para Angular SPA (sin secreto de cliente)
resource "aws_cognito_user_pool_client" "spa" {
  name         = "${var.project_name}-${var.environment}-spa-client"
  user_pool_id = aws_cognito_user_pool.this.id

  # Cero secretos en clientes públicos / frontend (criterio de seguridad no negociable)
  generate_secret = false

  # Flujos permitidos: SRP y contraseña directa para SDK/SPA, y Authorization Code para OAuth
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  # Evita revelar si un usuario existe durante login o recuperación de contraseña
  prevent_user_existence_errors = "ENABLED"

  supported_identity_providers = ["COGNITO"]

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"] # Authorization Code con PKCE
  allowed_oauth_scopes                 = ["email", "openid", "profile"]

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  enable_token_revocation = true

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

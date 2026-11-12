# Outputs del módulo cognito (CDM-24)

output "user_pool_id" {
  description = "ID del User Pool de Cognito."
  value       = aws_cognito_user_pool.this.id
}

output "user_pool_arn" {
  description = "ARN del User Pool de Cognito."
  value       = aws_cognito_user_pool.this.arn
}

output "user_pool_endpoint" {
  description = "Endpoint del proveedor de identidad de Cognito."
  value       = aws_cognito_user_pool.this.endpoint
}

output "client_id" {
  description = "ID del App Client público para la SPA Angular (sin client secret)."
  value       = aws_cognito_user_pool_client.spa.id
}

output "issuer_url" {
  description = "URL del emisor (iss) para validación de tokens JWT en FastAPI."
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.this.id}"
}

output "cognito_domain" {
  description = "Dominio configurado de Cognito para OAuth y Hosted UI."
  value       = try(aws_cognito_user_pool_domain.this[0].domain, null)
}

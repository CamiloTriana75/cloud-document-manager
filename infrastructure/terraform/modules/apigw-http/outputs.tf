# Outputs del módulo apigw-http (CDM-20)

output "api_id" {
  description = "ID de la HTTP API en API Gateway."
  value       = aws_apigatewayv2_api.this.id
}

output "api_endpoint" {
  description = "URL base pública del API Gateway (HTTPS)."
  value       = aws_apigatewayv2_api.this.api_endpoint
}

output "api_execution_arn" {
  description = "ARN de ejecución de la API para permisos IAM."
  value       = aws_apigatewayv2_api.this.execution_arn
}

output "stage_id" {
  description = "ID del stage $default desplegado."
  value       = aws_apigatewayv2_stage.default.id
}

# Outputs del módulo lambda-api (CDM-20)

output "function_name" {
  description = "Nombre de la función Lambda."
  value       = aws_lambda_function.api.function_name
}

output "function_arn" {
  description = "ARN de la función Lambda."
  value       = aws_lambda_function.api.arn
}

output "invoke_arn" {
  description = "ARN de invocación de la función Lambda (para integraciones API Gateway)."
  value       = aws_lambda_function.api.invoke_arn
}

output "role_name" {
  description = "Nombre del rol IAM de ejecución de la Lambda."
  value       = aws_iam_role.lambda_exec.name
}

output "role_arn" {
  description = "ARN del rol IAM de ejecución de la Lambda."
  value       = aws_iam_role.lambda_exec.arn
}

output "log_group_name" {
  description = "Nombre del Log Group de CloudWatch."
  value       = aws_cloudwatch_log_group.lambda_logs.name
}

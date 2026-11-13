# Outputs para el módulo Lambda Worker — CDM (CDM-36)

output "function_name" {
  description = "Nombre de la función AWS Lambda worker"
  value       = aws_lambda_function.worker.function_name
}

output "function_arn" {
  description = "ARN de la función AWS Lambda worker"
  value       = aws_lambda_function.worker.arn
}

output "role_arn" {
  description = "ARN del rol IAM de ejecución del worker"
  value       = aws_iam_role.worker_exec.arn
}

output "log_group_name" {
  description = "Nombre del Log Group de CloudWatch para el worker"
  value       = aws_cloudwatch_log_group.worker_logs.name
}

output "event_source_mapping_uuid" {
  description = "Identificador UUID del Event Source Mapping entre SQS y Lambda"
  value       = aws_lambda_event_source_mapping.sqs_trigger.uuid
}

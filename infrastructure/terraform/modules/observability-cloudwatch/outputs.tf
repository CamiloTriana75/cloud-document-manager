# Outputs del módulo observability-cloudwatch (CDM-52)

output "sns_alerts_topic_arn" {
  description = "ARN del tópico SNS receptor de alarmas de CloudWatch."
  value       = aws_sns_topic.alerts.arn
}

output "api_errors_alarm_arn" {
  description = "ARN de la alarma CloudWatch para errores de la Lambda API."
  value       = aws_cloudwatch_metric_alarm.lambda_api_errors.arn
}

output "worker_errors_alarm_arn" {
  description = "ARN de la alarma CloudWatch para errores del Lambda Worker."
  value       = aws_cloudwatch_metric_alarm.lambda_worker_errors.arn
}

output "dlq_messages_alarm_arn" {
  description = "ARN de la alarma CloudWatch para mensajes acumulados en la DLQ de SQS."
  value       = aws_cloudwatch_metric_alarm.sqs_dlq_messages.arn
}

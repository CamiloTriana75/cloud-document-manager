# Outputs del módulo SQS Worker Queue (CDM-35)

output "queue_arn" {
  description = "ARN de la cola SQS principal para suscripciones de eventos S3 y permisos Lambda."
  value       = aws_sqs_queue.this.arn
}

output "queue_url" {
  description = "URL de la cola SQS principal para operaciones de envío/recepción de mensajes."
  value       = aws_sqs_queue.this.url
}

output "queue_name" {
  description = "Nombre asignado a la cola SQS principal."
  value       = aws_sqs_queue.this.name
}

output "dlq_arn" {
  description = "ARN de la Dead Letter Queue para monitorización y alarmas CloudWatch."
  value       = aws_sqs_queue.dlq.arn
}

output "dlq_url" {
  description = "URL de la Dead Letter Queue para inspección y reprocesamiento de mensajes fallidos."
  value       = aws_sqs_queue.dlq.url
}

output "dlq_name" {
  description = "Nombre asignado a la Dead Letter Queue."
  value       = aws_sqs_queue.dlq.name
}

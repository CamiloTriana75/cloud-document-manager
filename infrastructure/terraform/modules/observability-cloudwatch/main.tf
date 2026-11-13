# Módulo de Observabilidad y Alarmas CloudWatch — CDM (CDM-52 / AGENTS.md §8, §13)
#
# Métricas y alarmas conservadoras para funciones Lambda, colas SQS/DLQ y panel de visualización.
# Diseñado sin costes fijos permanentes para respetar el plan y los créditos de AWS.

# 1. Tópico SNS para centralización de notificaciones de alarma
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-${var.environment}-cloudwatch-alerts"

  tags = var.tags
}

# 2. Alarma: Errores en la función Lambda API
resource "aws_cloudwatch_metric_alarm" "lambda_api_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-api-errors-alarm"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.api_error_threshold
  alarm_description   = "Alarma disparada cuando la Lambda API acumula errores >= ${var.api_error_threshold} en 5 minutos."
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.api_function_name
  }

  tags = var.tags
}

# 3. Alarma: Throttling / Concurrencia excedida en la Lambda API
resource "aws_cloudwatch_metric_alarm" "lambda_api_throttles" {
  alarm_name          = "${var.project_name}-${var.environment}-api-throttles-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Alarma disparada cuando la Lambda API sufre estrangulamiento (throttling)."
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.api_function_name
  }

  tags = var.tags
}

# 4. Alarma: Errores en la función Lambda Worker (procesamiento asíncrono)
resource "aws_cloudwatch_metric_alarm" "lambda_worker_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-worker-errors-alarm"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.worker_error_threshold
  alarm_description   = "Alarma disparada cuando el Worker acumula errores >= ${var.worker_error_threshold} en 5 minutos."
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.worker_function_name
  }

  tags = var.tags
}

# 5. Alarma Crítica: Mensajes visibles en la Dead Letter Queue (DLQ)
resource "aws_cloudwatch_metric_alarm" "sqs_dlq_messages" {
  alarm_name          = "${var.project_name}-${var.environment}-sqs-dlq-messages-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "Alarma CRÍTICA: Hay mensajes sin procesar en la Dead Letter Queue (DLQ). Requiere investigación."
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = var.dlq_queue_name
  }

  tags = var.tags
}

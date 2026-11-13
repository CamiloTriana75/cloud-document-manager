# Módulo SQS Worker Queue — CDM (CDM-35 / AGENTS.md §6, §12)
#
# Canal de mensajería desacoplado para eventos S3 ObjectCreated.
# Configura la cola principal de procesamiento y su Dead Letter Queue (DLQ)
# con redrive policy, long polling y política de permisos mínimos para S3.
# Cifrado SSE-SQS gestionado sin coste adicional para salvaguardar el AWS Free Plan.

data "aws_caller_identity" "current" {}

locals {
  dlq_name = coalesce(var.dlq_name, "${var.queue_name}-dlq")
}

# 1. Dead Letter Queue (DLQ): almacena mensajes que fallan tras agotar reintentos
resource "aws_sqs_queue" "dlq" {
  name                      = local.dlq_name
  message_retention_seconds = var.dlq_message_retention_seconds
  sqs_managed_sse_enabled   = true

  tags = merge(
    var.tags,
    {
      Name = local.dlq_name
      Role = "dlq"
    }
  )
}

# 2. Cola principal de eventos de documentos
resource "aws_sqs_queue" "this" {
  name                       = var.queue_name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = var.receive_wait_time_seconds
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge(
    var.tags,
    {
      Name = var.queue_name
      Role = "worker-queue"
    }
  )
}

# 3. Política de cola SQS: Mínimo privilegio permitiendo solo a S3 publicar eventos
# Restringido estrictamente al bucket de documentos mediante aws:SourceArn
data "aws_iam_policy_document" "queue_policy" {
  statement {
    sid     = "AllowS3BucketToPublishEvents"
    effect  = "Allow"
    actions = ["sqs:SendMessage"]

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    resources = [aws_sqs_queue.this.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [var.s3_bucket_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_sqs_queue_policy" "this" {
  queue_url = aws_sqs_queue.this.id
  policy    = data.aws_iam_policy_document.queue_policy.json
}

# 4. Alarma CloudWatch para monitorizar mensajes en la Dead Letter Queue (CDM-39 / AGENTS.md §12)
resource "aws_cloudwatch_metric_alarm" "dlq_messages_visible" {
  alarm_name          = "${local.dlq_name}-messages-visible"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 1
  alarm_description   = "Alarma cuando hay 1 o mas mensajes en la DLQ (${local.dlq_name}) requiriendo inspeccion o redrive."

  dimensions = {
    QueueName = aws_sqs_queue.dlq.name
  }

  tags = var.tags
}

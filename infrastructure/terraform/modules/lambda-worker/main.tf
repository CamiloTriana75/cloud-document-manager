# Módulo Lambda Worker — CDM (CDM-36 / AGENTS.md §6, §12)
#
# Ejecuta el procesador asíncrono de documentos disparado por eventos SQS.
# Configura event_source_mapping con ReportBatchItemFailures para partial batch failure.

data "archive_file" "default_package" {
  type        = "zip"
  output_path = "${path.module}/default_payload.zip"

  source {
    content  = "# Placeholder CDM Worker Lambda Handler\ndef handler(event, context):\n    return {'batchItemFailures': []}\n"
    filename = "index.py"
  }
}

locals {
  actual_package_path = var.package_path != null && var.package_path != "" ? var.package_path : data.archive_file.default_package.output_path
}

# 1. Rol IAM de ejecución con mínimo privilegio
resource "aws_iam_role" "worker_exec" {
  name = "${var.function_name}-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# 2. Política básica de ejecución (CloudWatch logs)
resource "aws_iam_role_policy_attachment" "worker_basic" {
  role       = aws_iam_role.worker_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# 3. Política de lectura de la cola SQS
data "aws_iam_policy_document" "worker_sqs" {
  statement {
    sid    = "AllowSQSConsumption"
    effect = "Allow"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ]
    resources = [var.sqs_queue_arn]
  }

  statement {
    sid    = "AllowS3ObjectRead"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:HeadObject"
    ]
    resources = ["${var.s3_bucket_arn}/*"]
  }
}

resource "aws_iam_role_policy" "worker_sqs_policy" {
  name   = "${var.function_name}-sqs-s3-policy"
  role   = aws_iam_role.worker_exec.id
  policy = data.aws_iam_policy_document.worker_sqs.json
}

# 4. Log Group en CloudWatch con retención controlada
resource "aws_cloudwatch_log_group" "worker_logs" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# 5. Función AWS Lambda Worker
resource "aws_lambda_function" "worker" {
  function_name = var.function_name
  role          = aws_iam_role.worker_exec.arn
  handler       = var.handler
  runtime       = var.runtime

  filename         = local.actual_package_path
  source_code_hash = filebase64sha256(local.actual_package_path)

  memory_size = var.memory_size
  timeout     = var.timeout

  environment {
    variables = var.environment_variables
  }

  depends_on = [
    aws_cloudwatch_log_group.worker_logs,
    aws_iam_role_policy_attachment.worker_basic,
  ]

  tags = var.tags
}

# 6. Event Source Mapping con soporte para ReportBatchItemFailures (CDM-36)
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn        = var.sqs_queue_arn
  function_name           = aws_lambda_function.worker.arn
  batch_size              = var.batch_size
  function_response_types = ["ReportBatchItemFailures"]
  enabled                 = true

  depends_on = [
    aws_iam_role_policy.worker_sqs_policy
  ]
}

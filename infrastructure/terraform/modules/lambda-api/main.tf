# Módulo Lambda API — CDM (CDM-20 / CDM-119 / CDM-120)
#
# Ejecuta FastAPI bajo Mangum (ADR-0002) en arquitectura serverless efímera.
# Configuración conservadora de memoria/timeout para respetar el AWS Free Plan.

# Paquete base por defecto si no se pasa var.package_path
data "archive_file" "default_package" {
  type        = "zip"
  output_path = "${path.module}/default_payload.zip"

  source {
    content  = "# Placeholder CDM Lambda Handler\ndef handler(event, context):\n    return {'statusCode': 200, 'body': 'OK'}\n"
    filename = "index.py"
  }
}

locals {
  actual_package_path = var.package_path != null && var.package_path != "" ? var.package_path : data.archive_file.default_package.output_path
}

# 1. Rol IAM de ejecución con mínimo privilegio
resource "aws_iam_role" "lambda_exec" {
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

# 2. Política básica de ejecución: solo escribir logs a CloudWatch
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# 3. Política S3 least-privilege acotada al tenant (CDM-51 / AGENTS.md §13)
data "aws_iam_policy_document" "lambda_s3_least_privilege" {
  count = var.attach_s3_policy ? 1 : 0

  statement {
    sid    = "AllowS3TenantScopedObjectAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:HeadObject",
      "s3:DeleteObject",
    ]
    resources = [
      "${var.s3_bucket_arn}/workspaces/*",
      "${var.s3_bucket_arn}/tenants/*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda_s3" {
  count  = var.attach_s3_policy ? 1 : 0
  name   = "${var.function_name}-s3-tenant-policy"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_s3_least_privilege[0].json
}

# 4. Log Group en CloudWatch con retención controlada para no drenar créditos Free Plan
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# 4. Función AWS Lambda
resource "aws_lambda_function" "api" {
  function_name = var.function_name
  role          = aws_iam_role.lambda_exec.arn
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
    aws_cloudwatch_log_group.lambda_logs,
    aws_iam_role_policy_attachment.lambda_basic,
  ]

  tags = var.tags
}

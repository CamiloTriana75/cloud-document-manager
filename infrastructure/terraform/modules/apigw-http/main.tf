# Módulo API Gateway HTTP API — CDM (CDM-20 / CDM-120)
#
# Expone la API RESTful serverless detrás de una HTTP API v2 con baja latencia,
# menor coste que REST API y soporte nativo para payload format v2.0.

# 1. API Gateway HTTP API
resource "aws_apigatewayv2_api" "this" {
  name          = var.api_name
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins  = var.allowed_cors_origins
    allow_methods  = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"]
    allow_headers  = ["Authorization", "Content-Type", "x-amz-*"]
    expose_headers = ["*"]
    max_age        = 3600
  }

  tags = var.tags
}

# 2. Stage $default con despliegue automático
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true

  tags = var.tags
}

# 3. Integración proxy con Lambda (payload format 2.0 para Mangum)
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.lambda_invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

# 4. Rutas principales hacia Lambda
# Ruta genérica proxy para todas las operaciones /api/v1/* y /health
resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "root" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "ANY /"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# 5. Permiso IAM para que API Gateway invoque la función Lambda
resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

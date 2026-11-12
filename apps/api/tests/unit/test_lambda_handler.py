"""Pruebas unitarias para el handler ASGI de AWS Lambda (Mangum).

Verifica que el adaptador Mangum procese eventos proxy v2.0 de API Gateway
correctamente y devuelva respuestas válidas sin dependencias de red externas.
"""

import json
from typing import Any

from cdm.bootstrap.lambda_handler import handler


def test_lambda_handler_processes_health_check() -> None:
    """Verifica que un evento GET /health sea procesado por Mangum devolviendo HTTP 200."""
    event: dict[str, Any] = {
        "version": "2.0",
        "routeKey": "GET /health",
        "rawPath": "/health",
        "rawQueryString": "",
        "headers": {
            "accept": "application/json",
            "host": "test.execute-api.us-east-1.amazonaws.com",
            "user-agent": "pytest-client",
        },
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "testapi",
            "http": {
                "method": "GET",
                "path": "/health",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest-client",
            },
            "stage": "$default",
            "time": "12/Nov/2026:14:00:00 +0000",
            "timeEpoch": 1731420000,
        },
        "isBase64Encoded": False,
    }

    class MockLambdaContext:
        function_name = "cdm-dev-api"
        memory_limit_in_mb = 256
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:cdm-dev-api"
        aws_request_id = "test-request-id"

    response = handler(event, MockLambdaContext())

    assert response["statusCode"] == 200
    assert "headers" in response

    body = json.loads(response["body"])
    assert body["status"] == "ok"
    assert body["service"] == "cdm-api"
    assert body["version"] == "0.1.0"


def test_lambda_handler_processes_not_found_envelope() -> None:
    """Verifica que una ruta inexistente devuelva el error envelope 404 estandarizado."""
    event: dict[str, Any] = {
        "version": "2.0",
        "routeKey": "GET /ruta-inexistente",
        "rawPath": "/ruta-inexistente",
        "rawQueryString": "",
        "headers": {
            "accept": "application/json",
            "host": "test.execute-api.us-east-1.amazonaws.com",
        },
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/ruta-inexistente",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest-client",
            },
        },
        "isBase64Encoded": False,
    }

    class MockLambdaContext:
        function_name = "cdm-dev-api"

    response = handler(event, MockLambdaContext())

    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["code"] == "not_found"

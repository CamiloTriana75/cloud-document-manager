"""Prueba de humo del stack desplegado (CDM-129). Ver docs/runbooks/cloud-deployment.md.

Uso: uv run --no-project --with boto3 --with httpx python scripts/cloud_smoke_test.py

Requiere credenciales AWS con permisos de administración del User Pool: crea un usuario
temporal confirmado (sin enviar correo) y lo elimina al terminar. No imprime tokens,
contraseñas ni URLs firmadas. Los valores por defecto son los identificadores públicos
del entorno dev (outputs de Terraform); se pueden sobrescribir con variables de entorno.
"""

import os
import secrets
import sys
import time

import boto3
import httpx

API = os.environ.get(
    "CDM_SMOKE_API_URL", "https://5hjor3n08d.execute-api.us-east-1.amazonaws.com"
)
ORIGIN = os.environ.get("CDM_SMOKE_ORIGIN", "https://cloud-document-manager.vercel.app")
POOL_ID = os.environ.get("CDM_SMOKE_USER_POOL_ID", "us-east-1_CHy8S2TKT")
CLIENT_ID = os.environ.get("CDM_SMOKE_CLIENT_ID", "2f0u5p9odjllof3jqs0ls54jpj")

cognito = boto3.client("cognito-idp", region_name="us-east-1")
email = f"cdm-smoke-{secrets.token_hex(4)}@example.com"
password = "Sm0ke!" + secrets.token_urlsafe(12)
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("OK  " if ok else "FAIL") + f" {name} {detail}")


try:
    # 0. Salud y preflight CORS desde el dominio de Vercel
    r = httpx.get(f"{API}/health", timeout=30)
    check("GET /health", r.status_code == 200, str(r.status_code))
    pre = httpx.options(
        f"{API}/api/v1/workspaces",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
        timeout=30,
    )
    check(
        "CORS preflight API (Vercel)",
        pre.headers.get("access-control-allow-origin") == ORIGIN,
        str(pre.status_code),
    )

    # 1. Seguridad: token sin firma rechazado
    r = httpx.get(
        f"{API}/api/v1/me",
        headers={"Authorization": "Bearer mock-access-token-1.e30.e30.mock-signature"},
        timeout=30,
    )
    check("token sin firma rechazado", r.status_code == 401, str(r.status_code))

    # 2. Usuario temporal confirmado, sin enviar correo
    cognito.admin_create_user(
        UserPoolId=POOL_ID,
        Username=email,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "name", "Value": "Smoke Test"},
        ],
        MessageAction="SUPPRESS",
    )
    cognito.admin_set_user_password(
        UserPoolId=POOL_ID, Username=email, Password=password, Permanent=True
    )
    auth = cognito.initiate_auth(
        ClientId=CLIENT_ID,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": email, "PASSWORD": password},
    )["AuthenticationResult"]
    headers = {"Authorization": f"Bearer {auth['IdToken']}", "Origin": ORIGIN}
    check("login Cognito (USER_PASSWORD_AUTH)", bool(auth.get("IdToken")))

    client = httpx.Client(base_url=API, headers=headers, timeout=60)
    r = client.get("/api/v1/me")
    check(
        "GET /me con ID token",
        r.status_code == 200 and r.json()["data"]["email"] == email,
        str(r.status_code),
    )
    check(
        "CORS en respuesta real",
        r.headers.get("access-control-allow-origin") == ORIGIN,
        str(r.headers.get("access-control-allow-origin")),
    )

    # 3. Workspace
    r = client.post(
        "/api/v1/workspaces", json={"name": f"Smoke CDM-129 {secrets.token_hex(2)}"}
    )
    check("crear workspace", r.status_code == 201, str(r.status_code))
    ws_id = r.json()["data"]["id"]
    r = client.get("/api/v1/workspaces")
    check(
        "listar workspaces",
        r.status_code == 200 and any(w["id"] == ws_id for w in r.json()["data"]),
        str(r.status_code),
    )

    # 4. Carga directa a S3
    content = b"CDM smoke test - documento de prueba en texto plano.\n" * 20
    r = client.post(
        f"/api/v1/workspaces/{ws_id}/upload-sessions",
        json={
            "original_filename": "smoke.txt",
            "content_type": "text/plain",
            "size_bytes": len(content),
        },
    )
    check("crear sesión de carga", r.status_code in (200, 201), str(r.status_code))
    session = r.json()["data"]
    doc_id = session["document_id"]
    s3_pre = httpx.options(
        session["upload_url"],
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=30,
    )
    check(
        "CORS preflight S3 (Vercel)",
        s3_pre.headers.get("access-control-allow-origin") == ORIGIN,
        str(s3_pre.status_code),
    )
    put = httpx.put(
        session["upload_url"],
        content=content,
        headers={**session["required_headers"], "Origin": ORIGIN},
        timeout=60,
    )
    check(
        "PUT directo a S3 con URL prefirmada",
        put.status_code == 200,
        str(put.status_code),
    )

    r = client.post(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/complete")
    check(
        "confirmar carga",
        r.status_code == 200,
        f"{r.status_code} {r.json().get('data', {}).get('status')}",
    )

    # 5. Procesamiento asíncrono S3 -> SQS -> worker
    status = None
    for _ in range(30):
        r = client.get(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}")
        status = r.json()["data"]["status"]
        if status in ("READY", "FAILED"):
            break
        time.sleep(3)
    check("worker deja el documento en READY", status == "READY", str(status))

    r = client.get(f"/api/v1/workspaces/{ws_id}/documents")
    check(
        "catálogo lista el documento",
        r.status_code == 200 and any(d["id"] == doc_id for d in r.json()["data"]),
        str(r.status_code),
    )

    # 6. Descarga autorizada
    r = client.post(
        f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/download-url", json={}
    )
    check("URL de descarga", r.status_code == 200, str(r.status_code))
    dl = httpx.get(r.json()["data"]["download_url"], timeout=60)
    check(
        "descarga con URL temporal",
        dl.status_code == 200 and dl.content == content,
        str(dl.status_code),
    )

    # 7. Aislamiento: otro workspace inexistente/ajeno devuelve 404
    r = client.get("/api/v1/workspaces/00000000-0000-4000-a000-000000000000/documents")
    check("workspace ajeno -> 404", r.status_code == 404, str(r.status_code))

    # 8. Borrado lógico
    r = client.delete(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}")
    check("borrado lógico", r.status_code in (200, 204), str(r.status_code))
    r = client.get(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}")
    check("documento borrado ya no accesible", r.status_code == 404, str(r.status_code))
finally:
    try:
        cognito.admin_delete_user(UserPoolId=POOL_ID, Username=email)
        print("cleanup: usuario temporal de Cognito eliminado")
    except Exception as exc:  # noqa: BLE001
        print(f"cleanup: no se pudo eliminar el usuario temporal: {type(exc).__name__}")

failed = [name for name, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} comprobaciones OK")
sys.exit(1 if failed else 0)

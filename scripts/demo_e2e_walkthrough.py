#!/usr/bin/env python3
"""Script de Demostración End-to-End del MVP 0.1 — Cloud Document Manager (CDM-54).

Demuestra el flujo funcional completo de forma programática y reproducible:
1. Verificación de salud de la API (/health).
2. Identidad y autenticación de usuario simulada (/api/v1/me).
3. Creación y selección de workspaces (/api/v1/workspaces).
4. Verificación de membresía y rol de tenant (/members).
5. Inicio de sesión de carga y generación de URL prefirmada (/upload-sessions).
6. Confirmación de carga y verificación de objeto (/complete).
7. Procesamiento asíncrono SQS -> Lambda Worker (extracción de metadatos -> READY).
8. Consulta de catálogo con filtros y paginación (/documents).
9. Detalle de documento y metadatos técnicos.
10. Descarga autorizada con URL temporal (/download-url).
11. Verificación de seguridad: Aislamiento Multi-Tenant (Anti-IDOR / 404).
12. Eliminación lógica del documento.

Cumple con: AGENTS.md §1, §3, §4, §8, §10, §12, §14.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Dominio y Persistencia
from cdm.adapters.inbound.http.auth import get_current_user
from cdm.adapters.inbound.http.dependencies import get_db_session, get_storage_port
from cdm.adapters.outbound.persistence.models import (
    Base,
    UserModel,
)
from cdm.adapters.outbound.persistence.repositories import SqlAlchemyDocumentRepository
from cdm.application.ports.storage import ObjectMetadata, StoragePort
from cdm.application.use_cases.process_document_event import ProcessDocumentEventUseCase
from cdm.bootstrap.app import create_app
from cdm.bootstrap.worker_handler import process_sqs_event
from cdm.config.settings import Settings
from cdm.domain.identity import AuthenticatedUser

# Colores ANSI para presentación visual
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class InMemoryMockStorage(StoragePort):
    """Storage adapter en memoria para la demostración local."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def generate_upload_url(
        self,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        expires_in_seconds: int = 900,
    ) -> str:
        sig = uuid4().hex[:16]
        return (
            f"https://cdm-demo-documents.s3.us-east-1.amazonaws.com/{storage_key}"
            f"?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature={sig}"
        )

    def generate_download_url(
        self,
        storage_key: str,
        expires_in_seconds: int = 900,
        filename: str | None = None,
    ) -> str:
        sig = uuid4().hex[:16]
        disp = ""
        if filename:
            disp = f"&response-content-disposition=attachment%3B+filename%3D{filename}"
        return (
            f"https://cdm-demo-documents.s3.us-east-1.amazonaws.com/{storage_key}"
            f"?X-Amz-Signature={sig}{disp}"
        )

    def get_object_metadata(self, storage_key: str) -> ObjectMetadata | None:
        return ObjectMetadata(
            storage_key=storage_key,
            size_bytes=24576,
            content_type="application/pdf",
            etag='"demo-etag-sha256"',
        )

    def delete_object(self, storage_key: str) -> bool:
        self.objects.pop(storage_key, None)
        return True

    def get_object_bytes(
        self,
        storage_key: str,
        byte_range: tuple[int, int] | None = None,
    ) -> bytes | None:
        # Cabecera de PDF sintético válido
        pdf_header = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\ntrailer\n%%EOF"
        pdf_bytes = pdf_header + b"0" * 24500
        if byte_range:
            start, end = byte_range
            return pdf_bytes[start : end + 1]
        return pdf_bytes


def print_step(num: int, title: str) -> None:
    sep = "─" * 68
    print(
        f"\n{BOLD}{CYAN}════════════════════════════════════════════════════════════════════{RESET}"
    )
    print(f"{BOLD}{BLUE} Paso {num}: {title}{RESET}")
    print(f"{BOLD}{CYAN}{sep}{RESET}")


def run_demo() -> bool:
    print(f"\n{BOLD}{GREEN}╔══════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{GREEN}║  DEMOSTRACIÓN DE FLUJO END-TO-END — CLOUD DOCUMENT MGR   ║{RESET}")
    print(f"{BOLD}{GREEN}║                RELEASE MVP 0.1.0 (CDM-54)                ║{RESET}")
    print(f"{BOLD}{GREEN}╚══════════════════════════════════════════════════════════╝{RESET}")

    # 1. Configurar base de datos en memoria para la demo
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()

    storage_mock = InMemoryMockStorage()

    # Usuario principal (Owner)
    primary_user = AuthenticatedUser(
        cognito_sub="cognito-sub-owner-demo-1234",
        email="camilo.triana@example.com",
        name="Camilo Triana (Product Owner)",
        email_verified=True,
    )

    # Usuario externo sin acceso (para prueba anti-IDOR)
    intruder_user = AuthenticatedUser(
        cognito_sub="cognito-sub-intruder-9999",
        email="intruder@external.com",
        name="Intruder User",
        email_verified=True,
    )

    current_test_user = primary_user

    def mock_get_current_user() -> AuthenticatedUser:
        return current_test_user

    def mock_get_db_session() -> Iterator[Session]:
        yield session

    def mock_get_storage_port() -> StoragePort:
        return storage_mock

    # Registrar usuario en DB
    db_user = UserModel(
        id=uuid4(),
        cognito_sub=primary_user.cognito_sub,
        email=primary_user.email,
        display_name=primary_user.name,
    )
    session.add(db_user)
    session.commit()

    # Crear App FastAPI
    settings = Settings(
        database_url="sqlite:///:memory:",
        cognito_user_pool_id="us-east-1_DemoPool",
        cognito_client_id="demo-client-id",
        cognito_region="us-east-1",
    )
    app = create_app(settings)
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db_session] = mock_get_db_session
    app.dependency_overrides[get_storage_port] = mock_get_storage_port

    client = TestClient(app)

    # -------------------------------------------------------------
    # PASO 1: Health Check
    # -------------------------------------------------------------
    print_step(1, "Health Check de la API")
    resp = client.get("/health")
    assert resp.status_code == 200, f"Error en health check: {resp.text}"
    health_data = resp.json()
    print(f"{GREEN}✓ GET /health -> Status 200 OK{RESET}")
    print(f"  Payload: {json.dumps(health_data)}")

    # -------------------------------------------------------------
    # PASO 2: Identidad Autenticada
    # -------------------------------------------------------------
    print_step(2, "Verificación de Perfil de Usuario (/api/v1/me)")
    resp = client.get("/api/v1/me")
    assert resp.status_code == 200
    user_envelope = resp.json()
    user_data = user_envelope.get("data", user_envelope)
    print(f"{GREEN}✓ GET /api/v1/me -> Status 200 OK{RESET}")
    print(
        f"  Usuario: {user_data.get('name')} | Email: {user_data.get('email')} | "
        f"Sub: {user_data.get('sub')}"
    )

    # -------------------------------------------------------------
    # PASO 3: Creación de Workspace
    # -------------------------------------------------------------
    print_step(3, "Creación de Workspace para el Tenant")
    create_ws_payload = {
        "name": "Acme Global Engineering",
        "slug": "acme-global-eng",
    }
    resp = client.post("/api/v1/workspaces", json=create_ws_payload)
    assert resp.status_code == 201, f"Error creando workspace: {resp.text}"
    ws_envelope = resp.json()
    ws_data = ws_envelope.get("data", ws_envelope)
    workspace_id = ws_data["id"]
    print(f"{GREEN}✓ POST /api/v1/workspaces -> Status 201 Created{RESET}")
    print(
        f"  Workspace: ID = {workspace_id} | Nombre: {ws_data['name']} | "
        f"Rol: {ws_data.get('role', 'OWNER')}"
    )

    # -------------------------------------------------------------
    # PASO 4: Verificación de Miembros del Workspace
    # -------------------------------------------------------------
    print_step(4, "Consulta de Miembros y Roles del Workspace")
    resp = client.get(f"/api/v1/workspaces/{workspace_id}/members")
    assert resp.status_code == 200
    members_envelope = resp.json()
    members = members_envelope.get("data", members_envelope)
    print(f"{GREEN}✓ GET /workspaces/{workspace_id}/members -> Status 200 OK{RESET}")
    print(
        f"  Total miembros: {len(members)} | "
        f"Primer miembro: {members[0]['email']} ({members[0]['role']})"
    )

    # -------------------------------------------------------------
    # PASO 5: Inicio de Sesión de Carga (S3 Presigned URL)
    # -------------------------------------------------------------
    print_step(5, "Solicitud de Carga Directa a S3 (/upload-sessions)")
    upload_session_payload = {
        "original_filename": "Q4-Financial-Report-2026.pdf",
        "content_type": "application/pdf",
        "size_bytes": 24576,  # 24 KB
    }
    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/upload-sessions",
        json=upload_session_payload,
    )
    assert resp.status_code == 201, f"Error en upload session: {resp.text}"
    upload_session_envelope = resp.json()
    upload_session_data = upload_session_envelope.get("data", upload_session_envelope)
    document_id = upload_session_data["document_id"]
    presigned_url = upload_session_data["upload_url"]
    storage_key = upload_session_data["storage_key"]

    print(f"{GREEN}✓ POST /upload-sessions -> Status 201 Created{RESET}")
    print(f"  Storage Key opaco generado en servidor: {storage_key}")
    print(f"  URL Prefirmada (S3): {presigned_url[:75]}... [Firma HMAC SHA256]")
    print("  Expiración: 15 minutos (900s) | Headers requeridos: Content-Type: application/pdf")

    # -------------------------------------------------------------
    # PASO 6: Confirmación de Carga (Direct Upload Complete)
    # -------------------------------------------------------------
    print_step(6, "Confirmación de Carga de Archivo (/complete)")
    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/complete",
    )
    assert resp.status_code == 200, f"Error en complete: {resp.text}"
    complete_envelope = resp.json()
    doc_after_complete = complete_envelope.get("data", complete_envelope)
    print(f"{GREEN}✓ POST /documents/{document_id}/complete -> Status 200 OK{RESET}")
    status_str = doc_after_complete["status"]
    print(f"  Estado actual del documento: {BOLD}{status_str}{RESET} (Esperando worker)")

    # -------------------------------------------------------------
    # PASO 7: Procesamiento Asíncrono SQS -> Lambda Worker
    # -------------------------------------------------------------
    print_step(7, "Procesamiento Asíncrono de Evento S3 (SQS -> Lambda Worker)")
    sqs_event = {
        "Records": [
            {
                "messageId": f"sqs-msg-{uuid4().hex[:8]}",
                "receiptHandle": "mock-receipt-handle",
                "body": json.dumps(
                    {
                        "Records": [
                            {
                                "eventVersion": "2.1",
                                "eventSource": "aws:s3",
                                "eventName": "ObjectCreated:Put",
                                "s3": {
                                    "bucket": {"name": "cdm-demo-documents"},
                                    "object": {
                                        "key": storage_key,
                                        "size": 24576,
                                        "eTag": "mock-etag-sha256",
                                    },
                                },
                            }
                        ]
                    }
                ),
            }
        ]
    }

    worker_use_case = ProcessDocumentEventUseCase(
        document_repo=SqlAlchemyDocumentRepository(session),
        storage=storage_mock,
        expected_bucket_name="cdm-demo-documents",
    )
    worker_result = process_sqs_event(
        sqs_event,
        use_case=worker_use_case,
    )
    session.commit()
    failures = worker_result.get("batchItemFailures", [])
    assert len(failures) == 0, f"Fallo procesando lote SQS: {failures}"
    print(f"{GREEN}✓ Lambda Worker procesó evento SQS/S3 exitosamente (0 fallos en lote).{RESET}")

    # -------------------------------------------------------------
    # PASO 8: Consulta de Catálogo con Filtros
    # -------------------------------------------------------------
    print_step(8, "Consulta del Catálogo Documental (/documents?status=READY)")
    resp = client.get(f"/api/v1/workspaces/{workspace_id}/documents?status=READY")
    assert resp.status_code == 200
    catalog_envelope = resp.json()
    items = catalog_envelope.get("data", [])
    assert len(items) >= 1, "El documento procesado no aparece en el catálogo"
    doc_item = items[0]
    print(f"{GREEN}✓ GET /documents?status=READY -> Status 200 OK{RESET}")
    print(f"  Total documentos encontrados: {len(items)}")
    print(
        f"  Nombre: {doc_item['original_filename']} | Tamaño: {doc_item['size_bytes']} bytes | "
        f"Estado: {BOLD}{GREEN}{doc_item['status']}{RESET}"
    )

    # -------------------------------------------------------------
    # PASO 9: Detalle y Metadatos Técnicos
    # -------------------------------------------------------------
    print_step(9, "Consulta de Detalle y Metadatos Técnicos")
    resp = client.get(f"/api/v1/workspaces/{workspace_id}/documents/{document_id}")
    assert resp.status_code == 200
    detail_envelope = resp.json()
    detail = detail_envelope.get("data", detail_envelope)
    print(f"{GREEN}✓ GET /documents/{document_id} -> Status 200 OK{RESET}")
    print(f"  Detalle: {detail['original_filename']}")
    print(f"  Metadatos Técnicos: {json.dumps(detail.get('technical_metadata', {}))}")

    # -------------------------------------------------------------
    # PASO 10: Descarga Autorizada con URL Temporal
    # -------------------------------------------------------------
    print_step(10, "Generación de URL de Descarga Autorizada (/download-url)")
    resp = client.post(f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/download-url")
    assert resp.status_code == 200
    download_envelope = resp.json()
    download_info = download_envelope.get("data", download_envelope)
    print(f"{GREEN}✓ POST /documents/{document_id}/download-url -> Status 200 OK{RESET}")
    print(f"  URL Temporal de Descarga: {download_info['download_url'][:75]}... [Vida: 300s]")

    # -------------------------------------------------------------
    # PASO 11: Aislamiento Multi-Tenant (Anti-IDOR / Anti-Tampering)
    # -------------------------------------------------------------
    print_step(11, "Verificación de Seguridad: Aislamiento Multi-Tenant (Anti-IDOR)")
    current_test_user = intruder_user
    resp = client.get(f"/api/v1/workspaces/{workspace_id}/documents/{document_id}")
    assert resp.status_code == 404, f"Fallo de aislamiento multi-tenant: {resp.status_code}"
    print(f"{GREEN}✓ Intento de acceso ajeno -> HTTP 404 NOT FOUND (Aislamiento verificado){RESET}")
    current_test_user = primary_user

    # -------------------------------------------------------------
    # PASO 12: Eliminación Lógica del Documento
    # -------------------------------------------------------------
    print_step(12, "Eliminación Lógica del Documento (/documents/{id})")
    resp = client.delete(f"/api/v1/workspaces/{workspace_id}/documents/{document_id}")
    assert resp.status_code in (200, 204), f"Error eliminando documento: {resp.text}"
    print(
        f"{GREEN}✓ DELETE /documents/{document_id} -> Status {resp.status_code} "
        f"(Borrado lógico confirmado){RESET}"
    )

    # Verificar que ya no aparece en el catálogo activo
    resp = client.get(f"/api/v1/workspaces/{workspace_id}/documents")
    active_docs = resp.json().get("data", [])
    deleted_ids = [d["id"] for d in active_docs if d["id"] == str(document_id)]
    assert len(deleted_ids) == 0, "El documento eliminado sigue apareciendo en el catálogo activo"
    print(f"{GREEN}✓ El documento ya no figura en consultas activas del catálogo.{RESET}")

    # -------------------------------------------------------------
    # RESUMEN FINAL
    # -------------------------------------------------------------
    print(f"\n{BOLD}{GREEN}╔══════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{GREEN}║  ¡DEMOSTRACIÓN EXITOSA! CRITERIOS DEL MVP VALIDADOS      ║{RESET}")
    print(f"{BOLD}{GREEN}║  - Aislamiento Multi-Tenant: Verificado (Anti-IDOR 404)  ║{RESET}")
    print(f"{BOLD}{GREEN}║  - Flujo S3 Presigned Upload -> Complete: Operativo      ║{RESET}")
    print(f"{BOLD}{GREEN}║  - Procesamiento SQS -> Lambda Worker -> READY: OK       ║{RESET}")
    print(f"{BOLD}{GREEN}║  - Catálogo, Detalle, Descarga y Borrado Lógico: OK      ║{RESET}")
    print(f"{BOLD}{GREEN}╚══════════════════════════════════════════════════════════╝{RESET}\n")

    return True


if __name__ == "__main__":
    success = run_demo()
    sys.exit(0 if success else 1)

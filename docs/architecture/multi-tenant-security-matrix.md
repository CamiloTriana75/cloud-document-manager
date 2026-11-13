# Matriz de Seguridad y Aislamiento Multi-Tenant (CDM-28)

> Documento de referencia de seguridad y matriz de control de acceso basada en roles (RBAC) para Cloud Document Manager (CDM).

## 1. Principios Rectores de Aislamiento

De acuerdo con **AGENTS.md §2, §3, §8 y §14**, la seguridad y el aislamiento entre workspaces constituyen la máxima prioridad arquitectónica del producto:

1. **Aislamiento Físico y Lógico:** Múltiples organizaciones (*workspaces*) comparten la misma infraestructura de backend y base de datos, pero **ningún usuario de un workspace puede acceder, consultar, modificar ni inferir datos de otro workspace**.
2. **Contexto de Tenant Verificado en Backend:** El backend nunca confía en parámetros enviados por el cliente (`workspace_id`, `tenant_id`, rol o `storage_key`). Todo contexto se resuelve a partir del token JWT validado y la membresía activa (`ACTIVE`) persistida en PostgreSQL.
3. **Prevención Estricta de IDOR y Enumeración (BOLA):**
   - Si un usuario solicita acceso a un workspace al que no pertenece, el servidor responde con un `404 Not Found` idéntico al que respondería para un UUID aleatorio que no existe.
   - Si un usuario intenta acceder a un documento ajeno conociendo su UUID, el filtro SQL exige obligatoriamente `workspace_id == tenant.workspace_id`, retornando `404 Not Found`.
   - No se produce fuga de información (*information leakage*): las respuestas de error no revelan existencia, nombres de workspaces, trazas de excepción ni metadatos de otros inquilinos.
4. **Repositorios Blindados:** La interfaz `DocumentRepositoryPort` y su implementación SQLAlchemy no exponen métodos de consulta global. Toda lectura o mutación recibe `workspace_id` de forma obligatoria.

---

## 2. Matriz de Permisos por Rol (RBAC)

Conforme a **ADR-0001 (2026-11-12)**, la jerarquía de roles es:
$$\text{VIEWER (10)} < \text{MEMBER (20)} < \text{EDITOR (30)} < \text{ADMIN (40)} < \text{OWNER (50)}$$

| Operación | Endpoint | OWNER | ADMIN | EDITOR | MEMBER | VIEWER | EXTERNO / AJENO |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Listar documentos** | `GET /workspaces/{id}/documents` | 200 | 200 | 200 | 200 | 200 | **404** (Anti-IDOR) |
| **Detalle de documento** | `GET /workspaces/{id}/documents/{doc_id}` | 200 | 200 | 200 | 200 | 200 | **404** (Anti-IDOR) |
| **Descargar documento** | `POST /workspaces/{id}/documents/{doc_id}/download-url` | 200 | 200 | 200 | 200 | 200 | **404** (Anti-IDOR) |
| **Subir documento** | `POST /workspaces/{id}/documents` | 201 | 201 | 201 | 201 | **403** (Forbidden) | **404** (Anti-IDOR) |
| **Eliminar documento** | `DELETE /workspaces/{id}/documents/{doc_id}` | 200 | 200 | 200 | **403** (Forbidden) | **403** (Forbidden) | **404** (Anti-IDOR) |
| **Listar miembros** | `GET /workspaces/{id}/members` | 200 | 200 | 200 | 200 | 200 | **404** (Anti-IDOR) |
| **Invitar/gestionar miembros** | `POST /workspaces/{id}/members` | 201 | 201 | **403** (Forbidden) | **403** (Forbidden) | **403** (Forbidden) | **404** (Anti-IDOR) |
| **Nombrar OWNER** | `POST /workspaces/{id}/members` (`role=OWNER`) | 201 | **403** (Escalation) | **403** (Forbidden) | **403** (Forbidden) | **403** (Forbidden) | **404** (Anti-IDOR) |

---

## 3. Cobertura y Evidencia de Pruebas Automatizadas

La suite automatizada en `apps/api/tests/unit/test_multi_tenant_isolation_matrix.py` valida:

1. **Escenario de Dos Tenants Independientes:**
   - Creación en base de datos SQLite de `Workspace Alpha` y `Workspace Beta` con miembros asignados a cada rol y documentos confidenciales independientes.
   - Creación de un `Usuario Gamma` totalmente externo a ambos tenants.
2. **Matriz Parametrizada por Rol:**
   - 30 casos de prueba parametrizados (`@pytest.mark.parametrize`) evaluando cada rol contra cada endpoint.
3. **Pruebas Negativas de Acceso Cruzado (Cross-Tenant):**
   - Intentos directos de listar, consultar detalle, descargar o eliminar documentos de `Workspace Beta` ejecutados por usuarios autenticados en `Workspace Alpha`.
   - Verificación de que el estado en base de datos del tenant agredido permanece inalterado.
4. **Resistencia contra Ataques de Fuerza Bruta y Adivinación de IDs:**
   - Comparación estricta de respuestas entre UUIDs aleatorios no existentes y UUIDs válidos de otros tenants, verificando respuestas idénticas en status y cuerpo.

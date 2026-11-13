# Revisión de Seguridad de Archivos, IAM, S3 y Superficie API (CDM-51)

> **Documento rector de seguridad y hardening antes de release.**  
> Cumplimiento estricto con las directrices de `AGENTS.md` (§2, §3, §12, §14), el modelo de roles acordado en **ADR-0001**, la persistencia de datos en **ADR-0003** y los estándares de la industria (**OWASP File Upload Cheat Sheet** y **OWASP API Security Top 10**).

---

## 1. Resumen Ejecutivo y Alcance

Cloud Document Manager (CDM) es una plataforma SaaS multi-tenant diseñada para el almacenamiento, organización y consulta segura de documentos corporativos en la nube.

Esta revisión de seguridad consolida el análisis de riesgos, la verificación de controles preventivos y las auditorías de código e infraestructura antes de la publicación del release MVP.

### Principios Fundamentales Aplicados
1. **Aislamiento Multi-Tenant Absoluto:** Ningún usuario o tenant puede acceder a los metadatos o archivos de otro workspace, incluso si conoce o adivina un UUID, URL o `storage_key`.
2. **Defensa en Profundidad (Defense in Depth):** Múltiples capas de validación independientes (Frontend -> API Gateway -> Middleware -> Casos de uso -> Repositorios SQL -> Políticas IAM/S3).
3. **Mínimo Privilegio (Least Privilege):** Cada componente (API, Worker, Usuario) posee exclusivamente los permisos mínimos indispensables para su función.
4. **Sin Fuga de Secretos ni Credenciales:** Cero tokens, contraseñas, URLs prefirmadas o volcados de memoria en logs, repositorios o respuestas públicas.

---

## 2. Checklist OWASP File Upload

| # | Control OWASP | Estado en CDM | Implementación Técnica y Ubicación |
|---|---|---|---|
| **OFU-1** | **Allowlist de Tipos MIME y Extensiones** | **APROBADO** | Allowlist estricta en dominio (`ALLOWED_MIME_TYPES`). Valida bidireccionalmente que el MIME coincida con la extensión. Archivos ejecutables o scripts (`.exe`, `.sh`, `.bat`, etc.) son rechazados en el borde. (`cdm/domain/file_policy.py`). |
| **OFU-2** | **Prevención de Path Traversal** | **APROBADO** | Rechazo de nombres con `..`, `/`, `\`, caracteres nulos (`\0`), secuencias de escape y validación con `PurePath.name`. Límite máximo de 255 caracteres (`validate_and_sanitize_filename`). |
| **OFU-3** | **Claves de Almacenamiento Generadas en Servidor** | **APROBADO** | La clave S3 jamás se confía al cliente. El backend genera `workspaces/{workspace_id}/documents/{document_id}/{opaque_token}.{ext}` con UUIDs criptográficos. |
| **OFU-4** | **Almacenamiento Fuera de la Raíz Web** | **APROBADO** | Los archivos residen en un bucket Amazon S3 privado con *S3 Block Public Access* al 100% (4 directivas activas). |
| **OFU-5** | **Transferencia Directa sin Ejecución en API** | **APROBADO** | El cliente transmite el binario directo a S3 vía PUT con URL prefirmada de vida corta. La API FastAPI nunca toca ni almacena el binario en disco local, previniendo explotación de memory leaks o desbordamientos. |
| **OFU-6** | **Control de Tamaño y Archivos Vacíos** | **APROBADO** | Rechazo inmediato de archivos de 0 bytes o mayores a 50 MB (`MAX_UPLOAD_SIZE_BYTES = 52428800`). Validación duplicada en cliente y backend. |
| **OFU-7** | **Reconciliación y Verificación de Integridad** | **APROBADO** | Al solicitar `/complete`, la API realiza `HeadObject` en S3 para verificar la presencia física del objeto y corroborar que el tamaño coincida exactamente con la sesión. Soporte para verificación de checksum SHA-256. |
| **OFU-8** | **Limpieza de Cargas Huérfanas y Abort Incomplete** | **APROBADO** | Regla de Lifecycle S3 `abort_incomplete_multipart_upload` y caso de uso de mantenimiento `CleanupExpiredUploadSessionsUseCase` para expirar sesiones vencidas y eliminar temporales no confirmados. |

---

## 3. Revisión OWASP API Security Top 10

### API1: Broken Object Level Authorization (BOLA / IDOR)
- **Riesgo:** Un usuario del Workspace A intenta consultar, descargar o eliminar un documento del Workspace B manipulando el `document_id`.
- **Mitigación CDM:** Todas las consultas y mutaciones exigen el `TenantContext` autenticado y validado. Las consultas SQL en SQLAlchemy fuerzan de manera obligatoria la condición `WHERE workspace_id = :tenant_id AND id = :doc_id`. No existe consulta que busque globalmente por ID y filtre a posteriori.
- **Verificación:** Pruebas de integración IDOR en `tests/integration/test_postgres_repositories.py` (`test_cross_tenant_isolation_idor_protection`) y suites E2E en Playwright.

### API2: Broken Authentication
- **Riesgo:** Falsificación o reutilización de tokens JWT, o suplantación de identidad.
- **Mitigación CDM:** Integración con Amazon Cognito. La API valida la firma criptográfica usando JWKS oficial (`https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json`), expiración (`exp`), emisor (`iss`), cliente (`client_id`) y tipo de token (`token_use == 'access'`).
- **Verificación:** `cdm/adapters/outbound/cognito_verifier.py` y pruebas de autenticación unitarias y E2E.

### API3: Broken Object Property Level Authorization
- **Riesgo:** Asignación masiva (Mass Assignment) de atributos reservados (cambio de rol, status forzado a `READY`, modificación de `storage_key`).
- **Mitigación CDM:** Separación estricta entre modelos de dominio y esquemas Pydantic HTTP (`BaseModel`). Los DTOs de entrada no exponen atributos internos. La mutación de estados sólo es posible mediante métodos de dominio con validación de invariantes (`Document.transition_to()`).

### API4: Unrestricted Resource Consumption
- **Riesgo:** Ataques de denegación de servicio por emisión masiva de URLs prefirmadas o agotamiento de base de datos con consultas no paginadas.
- **Mitigación CDM:**
  1. **Rate Limiting:** Implementado en `cdm/adapters/inbound/http/rate_limit.py`. Limita la emisión de URLs a 60 solicitudes por minuto por cliente/IP. Responde con `HTTP 429 Too Many Requests` y cabecera estándar `Retry-After`.
  2. **Paginación Obligatoria:** Paginación server-side forzada con límites acotados (`limit <= 100`, default 25).
  3. **Límites de Carga:** Tamaño máximo de archivo fijado en 50 MB.

### API5: Broken Function Level Authorization
- **Riesgo:** Usuarios con rol `VIEWER` o `MEMBER` ejecutan acciones reservadas a administradores (crear invitaciones, eliminar documentos, forzar reintentos).
- **Mitigación CDM:** Implementación rigurosa de la jerarquía de roles acordada en **ADR-0001**:
  $$\text{VIEWER} < \text{MEMBER} < \text{EDITOR} < \text{ADMIN} < \text{OWNER}$$
  - `VIEWER`: Solo lectura (consultar catálogo, detalle y descargar).
  - `MEMBER`: Sube documentos y consulta.
  - `EDITOR`: Puede eliminar documentos de forma lógica.
  - `ADMIN` / `OWNER`: Administran miembros y reintentos fallidos.
- **Verificación:** Validación forzosa en los casos de uso mediante `tenant.require_role(...)`.

### API6: Unrestricted Access to Sensitive Business Flows
- **Riesgo:** Evasión de la fase de verificación de subida o marcado arbitrario de documentos como listos.
- **Mitigación CDM:** Flujo de carga en dos fases con sesión efímera (`UploadSession`). El documento pasa a `UPLOADED` únicamente tras la reconciliación con S3 mediante `HeadObject`, y solo el Worker asíncrono o la canalización de procesamiento puede transicionarlo a `READY`.

### API7: Server Side Request Forgery (SSRF)
- **Riesgo:** La API descarga archivos desde URLs arbitrarias suministradas por usuarios.
- **Mitigación CDM:** CDM **nunca** realiza descargas salientes desde URLs provistas por el cliente. Las URLs son prefirmadas localmente con el SDK oficial de AWS (`boto3`) apuntando exclusivamente al bucket S3 privado del proyecto.

### API8: Security Misconfiguration
- **Riesgo:** Políticas CORS permisivas (`*`), buckets abiertos o exposición de trazas de error con datos internos.
- **Mitigación CDM:**
  - **S3 Block Public Access:** 4 directivas en `true`.
  - **CORS Estricto:** Orígenes parametrizados en backend y S3 (nunca `*` en producción).
  - **TLS Obligatorio:** Política de bucket `DenyInsecureTransport` (`aws:SecureTransport == false` denegado).
  - **Manejo Centralizado de Errores:** Errores mapeados a respuestas RFC 7807 sin stack traces (`cdm/adapters/inbound/http/errors.py`).

### API9: Improper Inventory Management
- **Riesgo:** Endpoints sin documentar o versiones obsoletas desprotegidas.
- **Mitigación CDM:** Especificación OpenAPI 3.1.0 versionada en `/api/v1/openapi.json`. Todos los routers están centralizados bajo `/api/v1` en `cdm/bootstrap/app.py`. Pruebas de contrato automatizadas verifican esquemas y respuestas.

### API10: Unsafe Consumption of APIs
- **Riesgo:** Dependencias inseguras de APIs de terceros o SDKs sin timeouts.
- **Mitigación CDM:** Integraciones externas acotadas a AWS Cognito y S3. Se usan timeouts explícitos y manejo robusto de excepciones de red con circuito de fallo controlado.

---

## 4. Matriz de Aislamiento Multi-Tenant

| Capa Arquitectural | Mecanismo de Aislamiento | Garantía de Seguridad |
|---|---|---|
| **Dominio** | `TenantContext(workspace_id, user_id, role)` inmutable | Ninguna regla de negocio se evalúa sin un tenant verificado. |
| **Casos de Uso** | Validación de roles (`require_role`) y pertenencia | Rechazo preventivo antes de tocar la base de datos o almacenamiento. |
| **Persistencia (SQL)** | Clave foránea `workspace_id` en todas las tablas (`documents`, `workspaces`, `memberships`, `upload_sessions`, `audit_events`) | Consultas filtradas por `workspace_id`. Índices compuestos en `(workspace_id, id)`. |
| **Almacenamiento (S3)** | Prefijos de objeto particionados: `workspaces/{workspace_id}/...` | Los objetos binarios quedan aislados bajo la clave del tenant. |
| **Mensajería (SQS)** | Eventos filtrados con `prefix = "workspaces/"` | El worker extrae el `storage_key` y verifica que pertenezca al workspace registrado. |

---

## 5. Menor Privilegio (IAM Least Privilege) y Políticas de S3

### 1. Rol IAM de la Lambda API (`lambda-api`)
```hcl
# Acciones permitidas acotadas estrictamente al bucket y prefijo de workspaces
actions = [
  "s3:GetObject",
  "s3:HeadObject",
  "s3:DeleteObject"
]
resources = [
  "${var.s3_bucket_arn}/workspaces/*"
]
```
- No tiene permisos de administración de buckets, ni acceso a otros buckets de la cuenta.
- El log group de CloudWatch tiene retención fijada (14 días en dev) para controlar costes.

### 2. Rol IAM del Lambda Worker (`lambda-worker`)
```hcl
# Consumo exclusivo de la cola SQS y lectura del bucket S3
statement {
  actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
  resources = [var.sqs_queue_arn]
}
statement {
  actions   = ["s3:GetObject", "s3:HeadObject"]
  resources = ["${var.s3_bucket_arn}/*"]
}
```

### 3. Política de Bucket S3 (`s3-document-store`)
- **BucketOwnerEnforced:** ACLs desactivadas; la cuenta es dueña absoluta de todos los objetos.
- **SSE-S3:** Cifrado en reposo AES256 por defecto con Bucket Key activado (sin costes por llamada de KMS).
- **DenyInsecureTransport:** Denegación explícita de cualquier petición HTTP en plano.

---

## 6. Higiene de Secretos y Sanitización de Logs

1. **Secretos Fuera de Git:**
   - `.gitignore` protege exhaustivamente `.env`, `*.pem`, `*.key`, `secrets/`, `*.tfstate`, `.terraform/`.
   - `.env.example` contiene únicamente nombres de variables con placeholders neutros.
2. **Filtro Sanitizador en Logging (`cdm/config/logging.py`):**
   - Intercepta y ofusca en tiempo real:
     - `Bearer [REDACTED]`
     - `[JWT_TOKEN_REDACTED]`
     - `https://[S3_PRESIGNED_URL_REDACTED]`
     - `password=[REDACTED]`, `secret=[REDACTED]`
   - Garantiza que URLs prefirmadas y firmas HMAC nunca se persistan en CloudWatch Logs.

---

## 7. Advertencia de Seguridad: Emuladores vs Nube Real (AGENTS.md §13)

> [!CAUTION]
> **Declaración Crítica sobre Emuladores y Entornos Locales:**
> 
> Los entornos locales basados en Docker Compose, SQLite, LocalStack o emuladores de S3 sirven exclusivamente para acelerar el ciclo de desarrollo y validar contratos de integración rápida.
> 
> **Un test aprobado contra un emulador local NO constituye prueba de seguridad en AWS real.**
> 
> Los emuladores locales:
> 1. No aplican el motor de políticas de IAM con evaluación de condiciones condicionales complejas (`aws:SecureTransport`, `aws:PrincipalArn`).
> 2. No validan la resolución DNS real de endpoints regionales ni la propagación de eventos S3/SQS con dead-letter queues.
> 3. No replican las restricciones de cuotas, latencias de red ni throttling de API Gateway.
> 
> Por ende, la validación de seguridad de CDM se apoya en:
> - Pruebas negativas unitarias con dobles de prueba deterministas.
> - Análisis estático y validación formal de configuración Terraform (`terraform validate`).
> - Verificación manual de políticas IAM y permisos antes de cualquier aplicación en la nube.

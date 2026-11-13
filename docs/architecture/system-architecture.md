# Arquitectura del Sistema — Cloud Document Manager (CDM)

> **Documento de Arquitectura de Alto Nivel**  
> **Versión:** 1.0 (MVP 0.1)  
> **Cumplimiento:** *AGENTS.md* (§1, §2, §5, §6, §8, §9, §12, §13, §14) · ADR-0001 a ADR-0008  

---

## 1. Visión General del Sistema

**Cloud Document Manager (CDM)** es una plataforma SaaS multi-tenant diseñada para el almacenamiento seguro, catalogación, procesamiento asíncrono y gestión de documentos corporativos en la nube.

La arquitectura garantiza:
1. **Aislamiento Multi-Tenant Estricto:** Particionamiento lógico en PostgreSQL mediante `workspace_id` indexado en todas las tablas operativas y particionamiento físico/lógico en Amazon S3 bajo prefijos seguros `workspaces/{workspace_id}/documents/{document_id}/...`.
2. **Carga Directa Optimizada:** La carga binaria se efectúa directamente desde el navegador (Angular SPA) hacia Amazon S3 mediante URLs prefirmadas de vida corta (15 minutos), evitando que los archivos saturen el backend o atraviesen API Gateway.
3. **Procesamiento Asíncrono Desacoplado:** Una vez confirmado el archivo, eventos de S3 (`s3:ObjectCreated:*`) son canalizados a través de Amazon SQS hacia una función AWS Lambda Worker con reintentos controlados y Dead Letter Queue (DLQ).
4. **Cero Costes Ocultos y Mínimo Privilegio:** Uso exclusivo de servicios Serverless (Lambda, API Gateway HTTP v2, S3, SQS, Cognito, CloudWatch), eliminando costes continuos como NAT Gateways o balanceadores dedicados (*AGENTS.md* §13).

---

## 2. Diagrama de Arquitectura Global (End-to-End)

```mermaid
flowchart TD
    subgraph CLIENT["Cliente (Navegador Web)"]
        SPA["Angular SPA (Signals, Zoneless, WCAG AA)"]
    end

    subgraph IDENTITY["Identidad y Autenticación"]
        COG["Amazon Cognito User Pool<br/>(JWT: ID Token & Access Token)"]
    end

    subgraph INGRESS["Capa de Entrada API"]
        APIGW["Amazon API Gateway (HTTP API v2)<br/>CORS Restringido · Throttling"]
    end

    subgraph COMPUTE_API["Backend Serverless (FastAPI)"]
        LAMBDA_API["AWS Lambda (API Handler)<br/>Python 3.12 · Mangum · FastAPI<br/>Arquitectura Hexagonal"]
    end

    subgraph DATA_PERSISTENCE["Capa de Datos"]
        PG[("PostgreSQL 16 (Local / RDS)<br/>Particionamiento por workspace_id<br/>Migraciones Alembic")]
    end

    subgraph STORAGE["Almacenamiento de Archivos"]
        S3[("Amazon S3 (Bucket Privado)<br/>Block Public Access · AES256<br/>workspaces/{ws_id}/documents/{doc_id}/")]
    end

    subgraph ASYNC_PROCESSING["Procesamiento Asíncrono de Eventos"]
        S3_EVENT["Notificación S3 Event<br/>(s3:ObjectCreated:*)"]
        SQS["Amazon SQS (Worker Queue)<br/>Visibility: 300s · maxReceive: 3"]
        DLQ["Amazon SQS (Dead Letter Queue)<br/>Retención: 14 días"]
        LAMBDA_WORKER["AWS Lambda (Worker Handler)<br/>Extracción Metadatos · Validación"]
    end

    subgraph OBSERVABILITY["Observabilidad y Alertas"]
        CW_LOGS["CloudWatch Logs<br/>(JSON Estructurado Sanitizado)"]
        CW_ALARMS["CloudWatch Alarms<br/>(Errores, Throttles, DLQ > 0)"]
        SNS["Amazon SNS (Alertas Operativas)"]
    end

    %% Relaciones de Flujo
    SPA -->|1. Autenticación / Refresh| COG
    SPA -->|2. HTTP + Bearer JWT| APIGW
    APIGW -->|Proxy ASGI| LAMBDA_API
    LAMBDA_API -->|Validación Token / JWKS| COG
    LAMBDA_API -->|Transacciones SQL / Tenancy| PG
    LAMBDA_API -->|3. Generar Presigned PUT URL| S3
    LAMBDA_API -->|Devuelve Presigned URL| SPA
    SPA -->|4. PUT Binario Directo| S3
    SPA -->|5. POST /complete| APIGW
    LAMBDA_API -->|HeadObject & Estado UPLOADED| S3
    LAMBDA_API -->|Actualiza Documento| PG

    %% Flujo Asíncrono
    S3 -->|ObjectCreated| S3_EVENT
    S3_EVENT -->|Encola evento| SQS
    SQS -->|Trigger por Lote| LAMBDA_WORKER
    LAMBDA_WORKER -->|Fallo tras 3 reintentos| DLQ
    LAMBDA_WORKER -->|HeadObject & Metadatos| S3
    LAMBDA_WORKER -->|Estado READY / FAILED| PG

    %% Trazabilidad y Telemetría
    LAMBDA_API -.->|Logs JSON + X-Request-ID| CW_LOGS
    LAMBDA_WORKER -.->|Logs JSON + SQS MessageId| CW_LOGS
    DLQ -.->|Métrica VisibleMessages| CW_ALARMS
    CW_ALARMS -.->|Notificación| SNS
```

---

## 3. Arquitectura del Backend (Hexagonal / Ports & Adapters)

El backend en Python 3.12 implementa estrictamente Arquitectura Hexagonal (*AGENTS.md* §2, §8):

```mermaid
flowchart TD
    subgraph INBOUND["Adaptadores de Entrada (Inbound)"]
        HTTP_ROUTERS["FastAPI Routers (/api/v1)<br/>auth, workspaces, documents, upload_sessions"]
        HTTP_MW["Middlewares<br/>CorrelationIdMiddleware · RateLimiter · ErrorHandlers"]
        SQS_HANDLER["Lambda SQS Worker Handler<br/>(Event deserialization)"]
    end

    subgraph APPLICATION["Capa de Aplicación (Casos de Uso)"]
        UC_AUTH["AuthenticateUser · ResolveTenantContext"]
        UC_WS["CreateWorkspace · ListWorkspaces · ManageMembers"]
        UC_DOC["CreateUploadSession · CompleteUpload · DownloadDocument · DeleteDocument"]
        UC_WORKER["ProcessDocumentAsync (SQS Event Processing)"]
        PORTS_IN["Interfaces / Puertos de Entrada"]
        PORTS_OUT["Interfaces / Puertos de Salida (Protocols)"]
    end

    subgraph DOMAIN["Capa de Dominio (Núcleo Puro)"]
        ENTITIES["Entidades:<br/>User · Workspace · Membership · Document · UploadSession"]
        VO["Value Objects & Enums:<br/>DocumentStatus · Role · ContentType · StorageKey"]
        RULES["Reglas de Invariantes:<br/>Transiciones de estado · Cuotas · Normalización"]
    end

    subgraph OUTBOUND["Adaptadores de Salida (Outbound)"]
        REPO_PG["PostgreSQL Repositories (SQLAlchemy 2.0)<br/>WorkspaceRepo · DocumentRepo · UserRepo"]
        S3_STORAGE["S3 Storage Service (Boto3)<br/>Presigned URLs · HeadObject · DeleteObject"]
        COGNITO_AUTH["Cognito JWKS Validator (Cache + Exp)"]
        METADATA_EXTRACTOR["Technical Metadata Extractor"]
    end

    %% Conexiones
    INBOUND --> PORTS_IN
    PORTS_IN --> APPLICATION
    APPLICATION --> DOMAIN
    APPLICATION --> PORTS_OUT
    PORTS_OUT --> OUTBOUND

    classDef pure fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef app fill:#e8f5e9,stroke:#388e3c,stroke-width:2px;
    classDef adapter fill:#fff3e0,stroke:#f57c00,stroke-width:2px;
    class DOMAIN pure;
    class APPLICATION app;
    class INBOUND,OUTBOUND adapter;
```

### Reglas de Dependencia
1. **El Dominio es completamente agnóstico:** Cero dependencias externas (`fastapi`, `sqlalchemy`, `pydantic`, `boto3`). Solo tipos estándar de Python (`dataclasses`, `enum`, `uuid`, `datetime`).
2. **Los Casos de Uso definen puertos:** Mediante `typing.Protocol`, desacoplándose de las implementaciones concretas de base de datos o almacenamiento en la nube.
3. **Persistencia aislada:** Los repositorios mapean modelos ORM a entidades de dominio inmutables antes de retornar hacia la aplicación.

---

## 4. Arquitectura del Frontend (Angular 22 Zoneless)

El cliente web está construido con Angular 22 bajo los lineamientos de accesibilidad WCAG AA y modularidad por características (*AGENTS.md* §9):

```mermaid
flowchart TD
    subgraph CORE["Capa Core"]
        AUTH_SVC["AuthService (Cognito / JWT / Session)"]
        TENANT_SVC["WorkspaceService (Tenant Activo / Contexto)"]
        HTTP_INTERCEPTOR["AuthInterceptor (Inyección Bearer JWT + X-Request-ID)"]
        ERROR_HANDLER["GlobalErrorHandler (Notificaciones accesibles)"]
    end

    subgraph STATE["Gestión de Estado Reactiva"]
        SIGNALS["Angular Signals (Zoneless Change Detection)<br/>currentWorkspace · activeDocuments · uploadProgress"]
    end

    subgraph FEATURES["Vistas y Componentes Autónomos"]
        AUTH_VIEWS["AuthFeature: Login / Registro"]
        WS_VIEWS["WorkspacesFeature: Selector · Creación · Administración de Miembros"]
        CATALOG_VIEWS["CatalogFeature: Tabla accesible · Filtros · Paginación · Detalle Modal"]
        UPLOAD_VIEWS["UploadFeature: Drag & Drop · Progreso reactivo · Cancelación"]
    end

    AUTH_SVC --> HTTP_INTERCEPTOR
    HTTP_INTERCEPTOR --> FEATURES
    FEATURES --> SIGNALS
    SIGNALS --> FEATURES
```

### Características Clave:
- **Signals Zoneless:** Operación sin `zone.js` (`provideZonelessChangeDetection()`), optimizando rendimiento, consumo de memoria y bundles compactos.
- **Validación Temprana y Accesible:** Validación previa en el navegador de tamaños y tipos MIME permitidos (PDF, PNG, JPEG, WEBP, TXT, CSV) antes de solicitar URLs prefirmadas.
- **Cero Lógica de Autorización Confiable en Cliente:** Las restricciones visuales mejoran la experiencia de usuario (UX), pero el backend valida de forma independiente e incondicional cada solicitud.

---

## 5. Matriz de Datos y Particionamiento Multi-Tenant

| Entidad | Clave Primaria (PK) | Tenant Isolation Key | Restricciones e Índices |
|---|---|---|---|
| `users` | `id` (UUID) | Global (N/A) | `cognito_sub` (UNIQUE), `email` |
| `workspaces` | `id` (UUID) | `id` | `slug` (UNIQUE), `created_by` (FK) |
| `workspace_memberships` | `id` (UUID) | `workspace_id` (FK) | `UNIQUE(workspace_id, user_id)`, `role`, `status` |
| `documents` | `id` (UUID) | `workspace_id` (FK) | INDEX en `(workspace_id, deleted_at, created_at)` |
| `upload_sessions` | `id` (UUID) | `workspace_id` (FK) | `expires_at`, `status`, `storage_key` |

### Particionamiento en S3:
```text
s3://<bucket-name>/
  └── workspaces/
      └── {workspace_id}/
          └── documents/
              └── {document_id}/
                  └── {sanitized_filename}
```
Ningún documento puede ser referenciado sin verificar que la membresía del usuario autenticado corresponda al `workspace_id` de la ruta.

---

## 6. Pipeline de Despliegue e Infraestructura como Código (IaC)

La infraestructura está declarada mediante módulos reutilizables de Terraform en `infrastructure/terraform/`:
- `modules/cognito`: User Pool, App Client y grupos de roles.
- `modules/s3-storage`: Bucket de documentos con bloqueo público, KMS/AES256, CORS y notificaciones de eventos S3.
- `modules/sqs-worker-queue`: Cola SQS de eventos, Dead Letter Queue (DLQ) y alarmas de mensajes visibles.
- `modules/lambda-api`: Función Lambda para FastAPI, integración con API Gateway HTTP v2 y roles IAM least-privilege.
- `modules/lambda-worker`: Función Lambda asíncrona disparada por SQS con políticas IAM de lectura/escritura acotadas.
- `modules/observability-cloudwatch`: Tópico SNS y alarmas CloudWatch para errores Lambda, throttles y mensajes encolados en DLQ.

Entornos independientes:
- `infrastructure/terraform/environments/dev`: Entorno de desarrollo / staging con costes bajo control.

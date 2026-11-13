# Política de Almacenamiento S3 y Seguridad — CDM

> Jira: **CDM-19** (subtarea **CDM-73**) · Fecha: 2026-11-12
> Regla rectora: [`AGENTS.md`](../../AGENTS.md) §12 (Flujo de carga y procesamiento de archivos).

Este documento formaliza el límite de seguridad, la estructura de claves y el control de acceso para el almacenamiento de archivos binarios en Amazon S3.

## 1. Esquema de Partición y Prefijos

Para garantizar el aislamiento estricto entre organizaciones (*tenants*), prevenir colisiones, sobreescrituras accidentales e inyecciones de ruta, se aplica un esquema de claves opacas y particionadas:

```text
s3://<bucket-name>/
├── tenants/
│   └── <tenant_id>/
│       └── documents/
│           └── <document_id>/
│               └── <storage_key>
└── temp/
    └── <upload_session_id>/
        └── <storage_key>
```

### Reglas de clave
1. **Opacidad obligatoria:** `<storage_key>` es un identificador aleatorio seguro generado por el backend (p. ej., UUID v4 o token hexadecimal criptográfico).
2. **Nombre original preservado en DB:** El nombre del archivo provisto por el usuario (`original_filename`) se sanea y almacena únicamente en PostgreSQL; **nunca se utiliza como clave ni prefijo en S3**.
3. **Aislamiento por prefijo:** Cada tenant solo tiene acceso lógico a su prefijo `tenants/<tenant_id>/`.

## 2. Controles de Seguridad del Bucket

El aprovisionamiento se gestiona mediante el módulo Terraform [`infrastructure/terraform/modules/s3-document-store`](../../infrastructure/terraform/modules/s3-document-store/):

* **S3 Block Public Access:** Activo al 100%. Ningún objeto es público ni accesible mediante URLs no firmadas.
* **Object Ownership:** `BucketOwnerEnforced`. Las ACLs de S3 quedan totalmente deshabilitadas.
* **Cifrado en reposo:** SSE-S3 (`AES256`) con Bucket Key activado por defecto. Cumple los requisitos de confidencialidad y tiene coste $0 en peticiones KMS, protegiendo los créditos de la cuenta Free Plan.
* **Cifrado en tránsito (TLS):** La política de bucket deniega explícitamente cualquier petición que no use HTTPS (`aws:SecureTransport = false`).
* **CORS para Single-Page Applications:** Configurado exclusivamente para orígenes autorizados (en dev: `http://localhost:4200`) con soporte para métodos `PUT`, `GET` y `HEAD`.

## 3. Matriz de Acceso IAM (Mínimo Privilegio)

El acceso al bucket se restringe estrictamente a tres actores:

| Actor | Alcance | Operaciones permitidas |
|---|---|---|
| **API Lambda (FastAPI)** | Global al bucket | Generar URLs prefirmadas (`PUT`/`GET`), `HeadObject` para verificar carga completada, y `DeleteObject` para eliminación física controlada. |
| **Worker Lambda** | `tenants/*` y `temp/*` | `GetObject` para análisis de metadatos/inspección técnica y `DeleteObject` de temporales. |
| **Frontend (Navegador)** | Exclusivamente el objeto exacto de la URL prefirmada | `PUT` durante la vigencia de la URL prefirmada (5–15 minutos) o `GET` para descarga autorizada temporal. |

*Nota:* Ningún usuario final ni el frontend de Angular reciben credenciales de AWS (IAM); interactúan con S3 exclusivamente a través de las URLs prefirmadas de vida corta generadas por el backend tras validar la membresía y el rol del usuario en el tenant.

## 4. Política de Ciclo de Vida (Lifecycle)

Para evitar acumulación de archivos huérfanos o cargas interrumpidas que consuman almacenamiento innecesario:
1. **Multipart uploads abortados:** Se cancelan y purgan automáticamente tras 7 días.
2. **Objetos en `temp/`:** Se eliminan automáticamente a las 24 horas si no son promovidos o confirmados por el usuario.
3. **Versiones no actuales:** Si el versionado se activa en producción, las versiones anteriores expiran tras 30 días.

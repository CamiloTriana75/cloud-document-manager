# Especificación Técnica: Validación de Contenido y Metadatos Técnicos (CDM-38)

> Jira: **CDM-38** · Fecha: 2026-11-12
> Reglas rectoras: [`AGENTS.md`](../../AGENTS.md) §2, §4, §10, §12.

Documento de arquitectura y especificación técnica que describe el proceso de extracción de metadatos, detección de tipos MIME por firmas binarias y validación de consistencia en el worker asíncrono de Cloud Document Manager (CDM).

---

## 1. Formatos Admitidos y Límites del MVP

El MVP de CDM implementa una política estricta de formatos permitidos para prevenir la ingesta de binarios ejecutables o scripts no autorizados:

| Formato | Extensión Normalizada | Tipo MIME Oficial | Firma Binaria (Magic Bytes) |
|---|---|---|---|
| **Documentos PDF** | `.pdf` | `application/pdf` | `%PDF-` (`0x25 0x50 0x44 0x46 0x2D`) |
| **Imágenes PNG** | `.png` | `image/png` | `\x89PNG\r\n\x1a\n` (`0x89 0x50 0x4E 0x47 0x0D 0x0A 0x1A 0x0A`) |
| **Imágenes JPEG** | `.jpg`, `.jpeg` | `image/jpeg` | `\xff\xd8\xff` (`0xFF 0xD8 0xFF`) |
| **Texto Plano** | `.txt` | `text/plain` | Caracteres UTF-8 válidos (sin bytes nulos `0x00`) |
| **Documentación Markdown** | `.md`, `.markdown` | `text/markdown` | Caracteres UTF-8 válidos |
| **Tablas CSV** | `.csv` | `text/csv` | Caracteres UTF-8 delimitados |
| **Datos JSON** | `.json` | `application/json` | Texto UTF-8 estructurado con raíz `{}` o `[]` |
| **Documentos Word** | `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Contenedor ZIP OpenXML (`PK\x03\x04`) |
| **Hojas de Cálculo Excel** | `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | Contenedor ZIP OpenXML (`PK\x03\x04`) |

### Límites de Tamaño
- **Tamaño mínimo:** 1 byte (los archivos vacíos de 0 bytes son rechazados como `FAILED`).
- **Tamaño máximo predeterminado:** 50 MB (`52,428,800` bytes), configurable vía `CDM_MAX_UPLOAD_SIZE_BYTES`.
- **Longitud máxima del nombre:** 255 caracteres, sin separadores de ruta (`/`, `\\`, `..`) ni caracteres de control.

---

## 2. Invariante de Seguridad: No Ejecución ni Renderizado

De acuerdo con `AGENTS.md` §4 y los criterios de aceptación de CDM-38:
1. **Inspección pasiva de cabeceras:** La identificación del formato se realiza leyendo únicamente el encabezado binario (primeros 512–8192 bytes) del objeto en Amazon S3.
2. **Cero ejecución de código:** No se utiliza ningún intérprete, shell, subproceso ni motor de renderizado para evaluar los archivos.
3. **Detección defensiva de ejecutables:** Se rechazan tajantemente firmas de ejecutables comunes, incluyendo:
   - Windows PE (`MZ`, `0x4D 0x5A`)
   - Linux ELF (`\x7fELF`, `0x7F 0x45 0x4C 0x46`)
   - macOS Mach-O (`0xFE 0xED 0xFA 0xCE`, etc.)
   - Shell scripts con Shebang (`#!`, `0x23 0x21`)
4. **Tratamiento de archivos no admitidos o corruptos:** Pasan inmediatamente al estado `FAILED` con una causa de fallo sanitizada (por ejemplo: *"Contenido ejecutable o script no permitido detectado en el archivo."*), sin arrojar excepciones de servidor no controladas que saturen la cola SQS ni la Dead Letter Queue (DLQ).

---

## 3. Estructura de Metadatos Técnicos en PostgreSQL (`JSONB`)

Los documentos procesados con éxito almacenan en su columna `technical_metadata` un diccionario estructurado que incluye:

```json
{
  "mime_detected": "application/pdf",
  "mime_declared": "application/pdf",
  "normalized_extension": ".pdf",
  "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "s3_size_bytes": 1048576,
  "s3_etag": "d41d8cd98f00b204e9800998ecf8427e",
  "s3_version_id": null,
  "s3_event_name": "ObjectCreated:Put",
  "s3_event_time": "2026-11-12T19:00:00Z",
  "processed_at": "2026-11-12T19:00:05.123456Z",
  "validation_status": "VALID"
}
```

En caso de fallo técnico (`FAILED`), el campo `failure_reason` conserva la causa sanitizada sin volcado de trazas:

```json
{
  "failure_reason": "Discrepancia de tipo de archivo: declarado 'application/pdf', pero el contenido real corresponde a 'application/x-dosexec'.",
  "mime_detected": "application/x-dosexec",
  "validation_status": "FAILED",
  "failed_at": "2026-11-12T19:00:05.123456Z"
}
```

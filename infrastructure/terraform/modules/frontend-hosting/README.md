# Módulo Terraform: Frontend Hosting en S3 + CloudFront (CDM-23)

Módulo reutilizable para alojar una aplicación Single-Page Application (SPA) construida con Angular sobre Amazon S3 y distribuirla globalmente mediante Amazon CloudFront.

## Características

- **Bucket Privado con OAC:** El bucket S3 tiene bloqueo público total (`Block Public Access`). CloudFront se autentica usando Origin Access Control (OAC) moderno con firma SigV4.
- **Enrutamiento SPA:** Respuestas de error personalizadas para códigos `403` y `404` que retornan `/index.html` con código HTTP `200`, permitiendo que el Angular Router maneje URLs profundas en el cliente.
- **Caché y Seguridad Optimizadas:** Utiliza las políticas administradas de AWS `Managed-CachingOptimized` (compresión automática Gzip/Brotli) y `Managed-SecurityHeadersPolicy` (HSTS, X-Frame-Options, X-Content-Type-Options).
- **Coste Cero:** Se mantiene bajo `PriceClass_100` y está completamente cubierto por el nivel **Siempre Gratis** de AWS (1 TB de transferencia de datos y 10,000,000 de peticiones al mes).

## Uso

```hcl
module "frontend_hosting" {
  source = "../../modules/frontend-hosting"

  project_name  = var.project_name
  environment   = var.environment
  force_destroy = true

  tags = local.tags
}
```

## Inputs

| Nombre | Tipo | Default | Descripción |
|---|---|---|---|
| `project_name` | `string` | `"cdm"` | Prefijo para los nombres de los recursos. |
| `environment` | `string` | N/A | Entorno de despliegue (`dev`, `prod`). |
| `price_class` | `string` | `"PriceClass_100"` | Clase de precio de CloudFront (`PriceClass_100` para Norteamérica y Europa). |
| `force_destroy` | `bool` | `true` | Permite destruir el bucket aunque contenga archivos. |
| `tags` | `map(string)` | `{}` | Etiquetas de infraestructura. |

## Outputs

| Nombre | Descripción |
|---|---|
| `bucket_name` | Nombre del bucket S3 de hosting. |
| `bucket_arn` | ARN del bucket S3. |
| `cloudfront_distribution_id` | ID de la distribución CloudFront para invalidaciones. |
| `cloudfront_domain_name` | Dominio CloudFront (ej. `d123.cloudfront.net`). |
| `cloudfront_url` | URL HTTPS completa para acceder a la aplicación. |

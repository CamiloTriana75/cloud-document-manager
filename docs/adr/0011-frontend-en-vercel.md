# ADR-0011: Hosting del frontend Angular en Vercel

- **Fecha:** 2026-11-15 · **Estado:** Aceptado · **Jira:** CDM-129, CDM-133
- **Relación:** resuelve la decisión pendiente “Hosting final del frontend y coste de CloudFront” (AGENTS.md §21).

## Contexto

Terraform creó un bucket S3 para el frontend (`module.frontend_hosting`), pero sin CloudFront (`enable_cloudfront = false`): CloudFront exige una verificación previa de la cuenta AWS y un bucket S3 privado no sirve una SPA por HTTPS por sí solo. El propietario pidió publicar el frontend en Vercel.

## Opciones consideradas

1. **S3 + CloudFront** — todo en AWS, pero requiere la verificación de la cuenta y una distribución adicional que mantener. Pendiente desde CDM-23.
2. **S3 website público** — sin HTTPS propio y obliga a desactivar Block Public Access. Descartado.
3. **Vercel (plan gratuito)** — HTTPS, CDN y despliegues por Git sin coste; build en Vercel con configuración versionada (`apps/web/vercel.json`).

## Decisión

- Proyecto Vercel `cloud-document-manager` (equipo del propietario) con `rootDirectory = apps/web`, Node 24.x. Producción: **https://cloud-document-manager.vercel.app**.
- Build: `npx --yes pnpm@12.14.0 install --frozen-lockfile` y `… exec ng build`, salida `dist/web/browser`. pnpm se fija con `npx` porque el pnpm por defecto de Vercel no lee el lockfile v9 multi-documento de pnpm 12, y corepack no se activó en el build.
- `.vercelignore` en la raíz: solo se sube `apps/web`.
- Fallback SPA (`rewrites` a `index.html`) y cabeceras de seguridad (`X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`); HSTS lo pone Vercel.
- El navegador llama directamente a API Gateway, Cognito y S3. El origen de Vercel se añade a `allowed_cors_origins` en Terraform (API Gateway, bucket S3 y FastAPI). La configuración pública del build (URL de la API e identificadores de Cognito) vive en `environment.prod.ts`.

## Consecuencias

- Coste USD 0 en el plan gratuito de Vercel; el bucket `frontend_hosting` queda sin uso (sin coste relevante) y puede retirarse en una tarea posterior.
- Las vistas previas de Vercel tienen otro dominio y no están en CORS: pueden navegar la UI, pero no llamar a la API. Solo producción está autorizada.
- Despliegue manual con `vercel deploy --prod` desde la raíz del repo (ver runbook). La conexión Git (despliegue automático desde `main`) se configura en el panel de Vercel.

## Riesgos

- **Dependencia de un proveedor externo** para el frontend: el build es estándar (`ng build`), así que volver a S3 + CloudFront solo requiere publicar `dist/web/browser`.
- **Sin Content-Security-Policy** todavía: añadirla tras validar los orígenes exactos (API Gateway, Cognito, bucket S3) y los estilos de Angular.

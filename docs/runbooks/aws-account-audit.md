# Auditoría de cuenta AWS — CDM-17

> Jira: **CDM-17** (épica CDM-3) · Fecha: 2026-11-12 · Fuente: datos reportados por el propietario + docs oficiales AWS (aws.amazon.com/free, FAQ Free Tier, pricing Cognito).
> Regla rectora: AGENTS.md §13 — nada con coste continuo sin estimación + aprobación.

## 1. Estado real de la cuenta

| Dato | Valor |
|---|---|
| Tipo de plan | **AWS Free Plan** (nuevo programa Free Tier) |
| Créditos restantes | **$100.00 USD** (de hasta $200; puede ganarse hasta $100 más — ver §2) |
| Caducidad del plan | **2027-05-12** (≈182 días) o al agotar créditos, lo que ocurra primero |
| Account ID | 1896-4874-1673 |
| Account name | Camilo Triana |
| Región activa | Por confirmar (propuesta: `us-east-1`, ver ADR-0007) |

### Reglas críticas del Free Plan (FAQ oficial)

1. La cuenta **se suspende** cuando se agotan los créditos **o** al cumplir 6 meses (2027-05-12). Hay **90 días** para hacer upgrade y recuperar los datos; después se borran definitivamente.
2. Al expirar el plan: **perder acceso a recursos y datos**. La estrategia de CDM es que el consumo quede dentro de los límites *always free* para que los créditos **no se toquen** (§4).
3. **No unirse a una AWS Organization ni activar "Advanced features"** hasta terminar de ganar los +$100 con el widget *Explore AWS* (actividades expiran inmediatamente al unirse). Además, "Advanced features" no permite volver al Free plan.
4. Upgrade a Paid es irreversible (no se puede bajar de vuelta al Free plan); los créditos sobreviven el upgrade hasta 12 meses desde la creación de la cuenta.
5. Créditos no transferibles y no acumulables con promocionales (no Activate).

## 2. Acción recomendada para el propietario: ganar +$100

En **https://console.aws.amazon.com/console/home** (home de la consola), widget **"Explore AWS"**, filtro **"Earn AWS credits"** — completar las actividades que enumera antes del 2027-05-12. Verificar llegada en Billing → Credits (puede tardar 30 min).

## 3. Servicios habilitados y límites *always free* (stack CDM)

Los límites siguientes son los límites de uso gratuito mensual vigentes en AWS (fuente: páginas de pricing/free de cada servicio); el Free Plan solo cubre los servicios elegibles y su consumo sobrante lo pagan los créditos automáticamente.

| Servicio | Disponible en Free Plan | Límite *always free* mensual | ¿Toca el stack CDM? |
|---|---|---|---|
| **Lambda** | Sí | 1M requests + 400,000 GB-s de cómputo | API + worker (distancia gigante del límite para MVP) |
| **API Gateway** (HTTP API) | Sí | 1M llamadas/mes | Entrada de la API |
| **SQS** | Sí | 1M requests/mes | Eventos S3 → worker |
| **S3** | Sí | 5 GB almacenamiento + 20K GET + 2K PUT | Documentos privados (MVP portafolio ≪ 5 GB) |
| **Cognito** (Lite/Essentials) | Sí | **10,000 MAU/mes** (signin directo/social, indefinido). SAML/OIDC federado: solo 50 MAU. M2M token: sin free tier | Auth del MVP; usar **Essentials** (default) o Lite; evitar SAML |
| **IAM / STS** | Sí | Gratis | Roles de Terraform y CI (OIDC) |
| **SSM Parameter Store** (parámetros Standard) | Sí | Gratis | Config no secreta |
| **CloudWatch** | Sí | Métricas/alarmas custom limitadas; **ingesta de logs se cobra** ≈$0.03-0.05/GB → retention corta (1-2 semanas) | Logs de API/worker |
| **Secrets Manager** | Sí (de pago) | **Sin free tier** ($0.40/secret/mes) | ❌ Evitar: usar Parameter Store SecureString / variables de entorno |
| **RDS PostgreSQL** | Sí (de pago) | **Sin free tier** → consume créditos: ≈$13-18/mes db.t4g.micro + ≈$2-3/mo 20GB gp3 | ❌ Ver ADR-0008: MVP con PostgreSQL local, RDS diferido |
| **Route 53** | Sí (de pago) | Hosted zone $0.50/mes + $0.40/dominio | ❌ Evitar en MVP: dominio deferido, usar URL `execute-api` |
| **CloudFront** | Sí (de pago) | 1TB/1M req free solo primeros 12 meses de cuenta antigua; en Free Plan consume créditos | ❌ Evitar en MVP: Angular en localhost/dev |
| **NAT Gateway** | Sí (de pago) | $0.045/h ≈ **$32/mes** | ❌ **PROHIBIDO** (AGENTS.md §13) |
| **Load Balancer (ALB)** | Sí (de pago) | ≈$16/mes | ❌ No necesario: API Gateway + Lambda |
| **VPC endpoints** | Sí (de pago) | ≈$7/mes por endpoint | ❌ No crear; Lambda con acceso público a S3/SQS vía endpoints AWS |

**Conclusión:** los 6 servicios del flujo MVP (S3, SQS, Lambda, API Gateway, Cognito, CloudWatch) están disponibles y quedan **dentro de los límites always free** para cargas de portafolio/MVP → consumo estimado de créditos **≈ $0-2/mes** (sobre todo logs). Proyección a 6 meses: **<$10** de los $100 disponibles.

## 4. Cuotas de servicio (defaults) relevantes

Revisadas como suficientes para MVP; ajustes solo si demostrada necesidad:

- **Lambda:** timeout máx 15 min, memoria 128 MB–10 GB, 1,024 ejecuciones concurrentes default, `/tmp` 512 MB–10 GB → worker simple: 128-256 MB, timeout ≤60 s.
- **SQS:** mensaje ≤256 KB (usar referencias, no payloads), ~120K mensajes en vuelo (Standard) → sobra.
- **S3:** 5 TB por objeto, Block Public Access on, bucket versioning opcional (política en ADR-0005/0006).
- **API Gateway HTTP API:** 10,000 RPS default, rutas ilimitadas → sobra.
- **Cognito:** límites de pools/RPS por API category default (ver *Cognito quotas* en pricing) → sobra para MVP.
- El propietario puede ver/crear límites en **Service Quotas** (consola); no se pidieron aumentos.

## 5. Presupuesto y alarmas

1. **Budget**: Billing → **Budgets** → *Create budget* → plantilla **"Monthly cost budget"**, monto **$5/mes** (fracción de los $100; da margen para logs), alerta email a 80%/100%. AWS Budgets es gratis para los 2 primeros budgets.
2. Alertas adicionales de Free Tier: Billing → **Free Tier usage alerts** (email al superar un límite always free).

## 6. Checklist de apagado/teardown (usar siempre al terminar una sesión de pruebas en AWS)

- [ ] `terraform destroy` del entorno temporal (o `terraform apply -destroy`) — revisar el plan antes.
- [ ] Vaciar y eliminar buckets S3 temporales (`aws s3 rm --recursive`, luego delete bucket).
- [ ] Vaciar y eliminar colas SQS temporales y sus DLQs.
- [ ] Eliminar logs de CloudWatch con retention ya creados si son de pruebas.
- [ ] Verificar que no queden funciones Lambda/HTTP APIs creadas a mano.
- [ ] Billing → Cost Explorer: costo del mes ≈ $0 (los *always free* no deben figurar como cargos).

## 7. Decisiones y pendientes

| Ítem | Estado |
|---|---|
| Región | **ADR-0007 propuesta `us-east-1`** — pendiente confirmación propietario |
| PostgreSQL | **ADR-0008 propuesta: local (Docker) para MVP, RDS diferido** — pendiente confirmación propietario |
| Budget $5/mes | Pendiente: crear en consola (pasos §5) |
| +$100 créditos (widget Explore AWS) | Pendiente: completar actividades antes de unirse a Organization |
| Región activa actual de la cuenta | Confirmar en consola (selector arriba derecha) |

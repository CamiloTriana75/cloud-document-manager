/**
 * Producción (build `ng build`, desplegado en Vercel): stack AWS `dev` de Terraform.
 *
 * Todos los valores son identificadores públicos (outputs de
 * `infrastructure/terraform/environments/dev`), no secretos: cualquier SPA los expone.
 * - apiBaseUrl: output `api_gateway_endpoint` (HTTP API → Lambda FastAPI).
 * - cognito: outputs `cognito_user_pool_id` y `cognito_client_id` (App Client SPA sin secreto).
 */
export const environment = {
  production: true,
  apiBaseUrl: 'https://5hjor3n08d.execute-api.us-east-1.amazonaws.com',
  cognito: {
    region: 'us-east-1',
    userPoolId: 'us-east-1_CHy8S2TKT',
    clientId: '2f0u5p9odjllof3jqs0ls54jpj',
    domain: '',
  },
};

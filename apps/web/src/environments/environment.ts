/**
 * Configuración por entorno. En desarrollo el dev-server proxiea /api y /health
 * al backend local (proxy.conf.json); en producción se define la URL real.
 */
export const environment = {
  production: false,
  apiBaseUrl: '',
};

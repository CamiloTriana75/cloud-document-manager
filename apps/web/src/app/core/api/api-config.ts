/** Configuración central del acceso a la API de CDM (AGENTS.md §9). */

import { InjectionToken } from '@angular/core';

import { environment } from '../../../environments/environment';

/**
 * URL base de la API (API Gateway en la nube), sin barra final.
 * Vacía en local: el dev-server proxiea `/api` y `/health` al backend (proxy.conf.json).
 */
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', {
  providedIn: 'root',
  factory: () => environment.apiBaseUrl.replace(/\/+$/, ''),
});

/** Rutas propias de la API de CDM. */
const API_PATH = /^\/(api\/|health(?:[/?]|$))/;

/** true si la URL es una ruta relativa de la API (`/api/...` o `/health`). */
export function isRelativeApiPath(url: string): boolean {
  return API_PATH.test(url);
}

/**
 * true si la petición va a la API de CDM: ruta relativa o URL absoluta bajo la URL base.
 * Las URLs prefirmadas de S3 y las llamadas a Cognito nunca cumplen esta condición.
 */
export function isApiRequestUrl(url: string, baseUrl: string): boolean {
  if (isRelativeApiPath(url)) {
    return true;
  }
  return baseUrl !== '' && url.startsWith(baseUrl) && isRelativeApiPath(url.slice(baseUrl.length));
}

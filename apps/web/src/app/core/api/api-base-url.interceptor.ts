import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { API_BASE_URL, isRelativeApiPath } from './api-config';

/**
 * Antepone la URL base de la API a las rutas relativas `/api` y `/health`.
 * Los servicios usan rutas relativas; en la nube apuntan a API Gateway y en local al proxy.
 */
export const apiBaseUrlInterceptor: HttpInterceptorFn = (req, next) => {
  const baseUrl = inject(API_BASE_URL);
  if (!baseUrl || !isRelativeApiPath(req.url)) {
    return next(req);
  }
  return next(req.clone({ url: `${baseUrl}${req.url}` }));
};

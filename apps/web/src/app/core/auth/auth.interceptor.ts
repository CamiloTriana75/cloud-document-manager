import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { API_BASE_URL, isApiRequestUrl } from '../api/api-config';
import { AuthService } from './auth.service';

/**
 * Adjunta el token Bearer solo a peticiones de la API de CDM (rutas relativas o la URL de
 * API Gateway configurada) y cierra la sesión ante un 401 de esa API. Nunca envía el token a
 * URLs prefirmadas de S3 ni a Cognito.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const isApiRequest = isApiRequestUrl(req.url, inject(API_BASE_URL));
  const token = isApiRequest ? authService.getIdToken() : null;

  const authReq = token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;

  return next(authReq).pipe(
    catchError((error) => {
      if (error.status === 401 && isApiRequest) {
        authService.logout();
        void router.navigate(['/auth/login']);
      }
      return throwError(() => error);
    }),
  );
};

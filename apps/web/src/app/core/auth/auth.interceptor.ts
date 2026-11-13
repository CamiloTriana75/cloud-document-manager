import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { AuthService } from './auth.service';

/**
 * Interceptor HTTP: adjunta Bearer token a peticiones de API y redirige ante 401.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const token = authService.getAccessToken();

  let authReq = req;
  // Solo adjuntar a endpoints de la API (no llamadas directas a Cognito ni transferencias directas a S3)
  const isExternalService =
    req.url.includes('cognito-idp.') ||
    req.url.includes('.amazonaws.com') ||
    req.url.includes('.s3.') ||
    req.url.includes('action=put');

  if (token && !isExternalService) {
    authReq = req.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`,
      },
    });
  }

  return next(authReq).pipe(
    catchError((error) => {
      if (
        error.status === 401 &&
        !isExternalService &&
        !req.url.includes('/auth/')
      ) {
        authService.logout();
        router.navigate(['/auth/login']);
      }
      return throwError(() => error);
    })
  );
};

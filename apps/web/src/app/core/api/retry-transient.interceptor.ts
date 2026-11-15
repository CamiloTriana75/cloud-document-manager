import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { retry, throwError, timer } from 'rxjs';

import { API_BASE_URL, isApiRequestUrl } from './api-config';

/** Estados transitorios: throttling de Lambda/API Gateway (503, 429) o fallos de pasarela. */
const TRANSIENT_STATUS = new Set([429, 502, 503, 504]);
const MAX_RETRIES = 2;
const BASE_DELAY_MS = 400;

/**
 * Reintenta con espera exponencial (400 ms, 1,2 s) las lecturas idempotentes (GET/HEAD) de la
 * API de CDM que fallan por saturación momentánea. Nunca reintenta escrituras ni peticiones a
 * S3 o Cognito, para no duplicar efectos.
 */
export const retryTransientInterceptor: HttpInterceptorFn = (req, next) => {
  const isIdempotent = req.method === 'GET' || req.method === 'HEAD';
  if (!isIdempotent || !isApiRequestUrl(req.url, inject(API_BASE_URL))) {
    return next(req);
  }

  return next(req).pipe(
    retry({
      count: MAX_RETRIES,
      delay: (error: unknown, retryCount: number) =>
        error instanceof HttpErrorResponse && TRANSIENT_STATUS.has(error.status)
          ? timer(BASE_DELAY_MS * 3 ** (retryCount - 1))
          : throwError(() => error),
    }),
  );
};

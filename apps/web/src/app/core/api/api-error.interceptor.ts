/** Interceptor central de errores de API: registro legible y re-lanzamiento.
 *
 * La presentación decide cómo mostrar el error; aquí se normaliza el log y se
 * evita filtrar detalles internos en producción.
 */

import {
  HttpErrorResponse,
  HttpInterceptorFn,
} from '@angular/common/http';
import { tap } from 'rxjs';

export const apiErrorInterceptor: HttpInterceptorFn = (req, next) => {
  return next(req).pipe(
    tap({
      error: (error: unknown) => {
        if (error instanceof HttpErrorResponse) {
          console.error(
            `[API] ${req.method} ${req.urlWithParams} → ${error.status}`,
          );
        }
      },
    }),
  );
};

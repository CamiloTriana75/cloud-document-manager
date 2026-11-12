import {
  HttpClient,
  HttpEvent,
  HttpHeaders,
  HttpEventType,
} from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { catchError, map, Observable, of, switchMap } from 'rxjs';

import {
  DocumentItem,
  DownloadUrlResponse,
  UploadProgressState,
  UploadSessionRequest,
  UploadSessionResponse,
} from './document.models';

interface ApiEnvelope<T> {
  data: T;
}

interface ApiListEnvelope<T> {
  data: T[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

@Injectable({
  providedIn: 'root',
})
export class DocumentService {
  private readonly http = inject(HttpClient);

  /**
   * Solicita una sesión de carga prefirmada directa a S3 (CDM-29).
   */
  requestUploadSession(
    workspaceId: string,
    payload: UploadSessionRequest
  ): Observable<UploadSessionResponse> {
    return this.http
      .post<ApiEnvelope<UploadSessionResponse>>(
        `/api/v1/workspaces/${workspaceId}/upload-sessions`,
        payload
      )
      .pipe(map((res) => res.data));
  }

  /**
   * Transmite el binario directamente desde el navegador a S3 vía PUT con progreso (CDM-31).
   * No pasa el binario por la API FastAPI.
   */
  uploadDirectToS3(
    uploadUrl: string,
    file: File,
    requiredHeaders?: Record<string, string>
  ): Observable<HttpEvent<unknown>> {
    let headers = new HttpHeaders();
    if (requiredHeaders) {
      Object.entries(requiredHeaders).forEach(([key, val]) => {
        headers = headers.set(key, val);
      });
    } else if (file.type) {
      headers = headers.set('Content-Type', file.type);
    }

    return this.http.put(uploadUrl, file, {
      headers,
      reportProgress: true,
      observe: 'events',
    });
  }

  /**
   * Confirma la carga completada y reconcilia presencia física en S3 (CDM-32).
   */
  completeUpload(
    workspaceId: string,
    documentId: string
  ): Observable<DocumentItem> {
    return this.http
      .post<ApiEnvelope<DocumentItem>>(
        `/api/v1/workspaces/${workspaceId}/documents/${documentId}/complete`,
        {}
      )
      .pipe(map((res) => res.data));
  }

  /**
   * Solicita una URL prefirmada temporal para la descarga de un documento autorizado (CDM-33).
   */
  getDownloadUrl(
    workspaceId: string,
    documentId: string,
    expiresInSeconds = 900
  ): Observable<DownloadUrlResponse> {
    return this.http
      .post<ApiEnvelope<DownloadUrlResponse>>(
        `/api/v1/workspaces/${workspaceId}/documents/${documentId}/download-url`,
        { expires_in_seconds: expiresInSeconds }
      )
      .pipe(map((res) => res.data));
  }

  /**
   * Orquesta el flujo completo de dos fases:
   * 1. Solicitud de sesión -> 2. PUT directo a S3 con progreso -> 3. Confirmación con backend.
   */
  uploadWithProgress(
    workspaceId: string,
    file: File,
    checksumSha256?: string | null
  ): Observable<UploadProgressState> {
    const totalBytes = file.size;

    return new Observable<UploadProgressState>((observer) => {
      // Notificar fase inicial
      observer.next({
        status: 'requesting',
        progressPercentage: 5,
        loadedBytes: 0,
        totalBytes,
      });

      const sessionReq: UploadSessionRequest = {
        original_filename: file.name,
        content_type: file.type || 'application/octet-stream',
        size_bytes: file.size,
        checksum_sha256: checksumSha256 ?? null,
      };

      const subscription = this.requestUploadSession(workspaceId, sessionReq)
        .pipe(
          switchMap((session) => {
            observer.next({
              status: 'uploading',
              progressPercentage: 10,
              loadedBytes: 0,
              totalBytes,
            });

            return this.uploadDirectToS3(
              session.upload_url,
              file,
              session.required_headers
            ).pipe(
              switchMap((event) => {
                if (event.type === HttpEventType.UploadProgress) {
                  const loaded = event.loaded;
                  const total = event.total || totalBytes;
                  // Progreso mapeado entre 10% y 90%
                  const percent = Math.min(
                    90,
                    10 + Math.round((loaded / total) * 80)
                  );
                  observer.next({
                    status: 'uploading',
                    progressPercentage: percent,
                    loadedBytes: loaded,
                    totalBytes: total,
                  });
                  return of(null);
                }

                if (event.type === HttpEventType.Response) {
                  observer.next({
                    status: 'completing',
                    progressPercentage: 95,
                    loadedBytes: totalBytes,
                    totalBytes,
                  });
                  return this.completeUpload(workspaceId, session.document_id);
                }

                return of(null);
              })
            );
          }),
          catchError((err) => {
            const errorMsg =
              err?.error?.error?.message ||
              err?.message ||
              'Error durante la transferencia del archivo.';
            observer.next({
              status: 'error',
              progressPercentage: 0,
              loadedBytes: 0,
              totalBytes,
              error: errorMsg,
            });
            observer.complete();
            return of(null);
          })
        )
        .subscribe({
          next: (doc) => {
            if (doc) {
              observer.next({
                status: 'completed',
                progressPercentage: 100,
                loadedBytes: totalBytes,
                totalBytes,
                document: doc,
              });
              observer.complete();
            }
          },
        });

      return () => {
        subscription.unsubscribe();
      };
    });
  }

  /**
   * Consulta el catálogo de documentos del workspace con paginación.
   */
  listDocuments(
    workspaceId: string,
    limit = 20,
    offset = 0
  ): Observable<{ items: DocumentItem[]; total: number }> {
    return this.http
      .get<ApiListEnvelope<DocumentItem>>(
        `/api/v1/workspaces/${workspaceId}/documents?limit=${limit}&offset=${offset}`
      )
      .pipe(
        map((res) => ({
          items: res.data,
          total: res.pagination.total,
        }))
      );
  }
}

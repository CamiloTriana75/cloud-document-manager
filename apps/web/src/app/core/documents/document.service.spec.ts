import { provideHttpClient } from '@angular/common/http';
import {
  HttpEventType,
  HttpProgressEvent,
  HttpResponse,
} from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import {
  DocumentItem,
  DownloadUrlResponse,
  UploadProgressState,
  UploadSessionRequest,
  UploadSessionResponse,
} from './document.models';
import { DocumentService } from './document.service';

describe('DocumentService', () => {
  let service: DocumentService;
  let http: HttpTestingController;

  const mockSession: UploadSessionResponse = {
    upload_session_id: 'sess-123',
    document_id: 'doc-456',
    upload_url:
      'https://cdm-test-bucket.s3.us-east-1.amazonaws.com/tenants/ws-1/doc-456.pdf?signature=test',
    storage_key: 'tenants/ws-1/documents/doc-456.pdf',
    expires_in_seconds: 900,
    required_headers: { 'Content-Type': 'application/pdf' },
  };

  const mockDocument: DocumentItem = {
    id: 'doc-456',
    workspace_id: 'ws-1',
    original_filename: 'reporte.pdf',
    storage_key: 'tenants/ws-1/documents/doc-456.pdf',
    content_type: 'application/pdf',
    size_bytes: 2048,
    status: 'UPLOADED',
    checksum_sha256: 'a'.repeat(64),
    technical_metadata: {},
    created_at: '2026-11-12T00:00:00Z',
    updated_at: '2026-11-12T00:00:00Z',
    uploaded_by: 'user-1',
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(DocumentService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  it('requestUploadSession envía POST con payload y desenvuelve data', () => {
    const payload: UploadSessionRequest = {
      original_filename: 'reporte.pdf',
      content_type: 'application/pdf',
      size_bytes: 2048,
    };

    service.requestUploadSession('ws-1', payload).subscribe((res) => {
      expect(res).toEqual(mockSession);
    });

    const req = http.expectOne('/api/v1/workspaces/ws-1/upload-sessions');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(payload);
    req.flush({ data: mockSession });
  });

  it('uploadDirectToS3 envía PUT al endpoint con observe=events y reportProgress=true', () => {
    const dummyFile = new File(['dummy content'], 'reporte.pdf', {
      type: 'application/pdf',
    });

    service
      .uploadDirectToS3(mockSession.upload_url, dummyFile, mockSession.required_headers)
      .subscribe((event) => {
        if (event.type === HttpEventType.Response) {
          expect((event as HttpResponse<unknown>).status).toBe(200);
        }
      });

    const req = http.expectOne(mockSession.upload_url);
    expect(req.request.method).toBe('PUT');
    expect(req.request.reportProgress).toBe(true);
    expect(req.request.headers.get('Content-Type')).toBe('application/pdf');
    req.flush({}, { status: 200, statusText: 'OK' });
  });

  it('completeUpload envía POST al endpoint de confirmación y retorna DocumentItem', () => {
    service.completeUpload('ws-1', 'doc-456').subscribe((doc) => {
      expect(doc).toEqual(mockDocument);
    });

    const req = http.expectOne(
      '/api/v1/workspaces/ws-1/documents/doc-456/complete'
    );
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    req.flush({ data: mockDocument });
  });

  it('getDownloadUrl envía POST al endpoint de download-url y retorna URL prefirmada', () => {
    const mockDownload: DownloadUrlResponse = {
      document_id: 'doc-456',
      original_filename: 'reporte.pdf',
      download_url: 'https://s3.amazonaws.com/test/reporte.pdf?signature=abc',
      expires_in_seconds: 600,
    };

    service.getDownloadUrl('ws-1', 'doc-456', 600).subscribe((res) => {
      expect(res).toEqual(mockDownload);
    });

    const req = http.expectOne(
      '/api/v1/workspaces/ws-1/documents/doc-456/download-url'
    );
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ expires_in_seconds: 600 });
    req.flush({ data: mockDownload });
  });

  it('listDocuments consulta catálogo con parámetros de paginación', () => {
    service.listDocuments('ws-1', 10, 20).subscribe((result) => {
      expect(result.items.length).toBe(1);
      expect(result.total).toBe(1);
    });

    const req = http.expectOne(
      '/api/v1/workspaces/ws-1/documents?limit=10&offset=20'
    );
    expect(req.request.method).toBe('GET');
    req.flush({
      data: [mockDocument],
      pagination: { total: 1, limit: 10, offset: 20, has_next: false, has_prev: true },
    });
  });

  it('uploadWithProgress orquesta el flujo completo de 3 pasos y reporta estados progresivos', () => {
    const dummyFile = new File(['dummy content'], 'reporte.pdf', {
      type: 'application/pdf',
    });

    const emittedStates: UploadProgressState[] = [];
    service.uploadWithProgress('ws-1', dummyFile).subscribe({
      next: (state) => emittedStates.push(state),
    });

    // 1. Estado inicial requesting
    expect(emittedStates.length).toBe(1);
    expect(emittedStates[0].status).toBe('requesting');

    // 2. Resolver sesión
    const sessionReq = http.expectOne('/api/v1/workspaces/ws-1/upload-sessions');
    expect(sessionReq.request.method).toBe('POST');
    sessionReq.flush({ data: mockSession });

    // Estado uploading inicial emitido
    expect(emittedStates.some((s) => s.status === 'uploading')).toBe(true);

    // 3. Simular PUT S3 con evento de progreso
    const s3Req = http.expectOne(mockSession.upload_url);
    expect(s3Req.request.method).toBe('PUT');

    const progressEvent: HttpProgressEvent = {
      type: HttpEventType.UploadProgress,
      loaded: 1024,
      total: 2048,
    };
    s3Req.event(progressEvent);

    const midState = emittedStates.find(
      (s) => s.status === 'uploading' && s.loadedBytes === 1024
    );
    expect(midState).toBeDefined();

    // Simular respuesta completa de S3
    s3Req.flush({}, { status: 200, statusText: 'OK' });

    // 4. Se debe haber disparado completeUpload
    const completeReq = http.expectOne(
      '/api/v1/workspaces/ws-1/documents/doc-456/complete'
    );
    expect(completeReq.request.method).toBe('POST');
    completeReq.flush({ data: mockDocument });

    // Estado final completed
    const finalState = emittedStates[emittedStates.length - 1];
    expect(finalState.status).toBe('completed');
    expect(finalState.progressPercentage).toBe(100);
    expect(finalState.document).toEqual(mockDocument);
  });

  it('uploadWithProgress maneja error de sesión y emite estado de error', () => {
    const dummyFile = new File(['dummy content'], 'reporte.pdf', {
      type: 'application/pdf',
    });

    const emittedStates: UploadProgressState[] = [];
    service.uploadWithProgress('ws-1', dummyFile).subscribe({
      next: (state) => emittedStates.push(state),
    });

    const sessionReq = http.expectOne('/api/v1/workspaces/ws-1/upload-sessions');
    sessionReq.flush(
      { error: { message: 'El archivo supera el tamaño máximo permitido' } },
      { status: 413, statusText: 'Content Too Large' }
    );

    const errorState = emittedStates[emittedStates.length - 1];
    expect(errorState.status).toBe('error');
    expect(errorState.error).toContain('supera el tamaño máximo');
  });

  it('listDocuments envía GET con parámetros de paginación y filtro de estado', () => {
    service.listDocuments('ws-1', 10, 20, 'READY').subscribe((res) => {
      expect(res.items.length).toBe(1);
      expect(res.total).toBe(1);
    });

    const req = http.expectOne('/api/v1/workspaces/ws-1/documents?limit=10&offset=20&status=READY');
    expect(req.request.method).toBe('GET');
    req.flush({
      data: [mockDocument],
      pagination: { total: 1, limit: 10, offset: 20, has_next: false, has_prev: false },
    });
  });

  it('getDocument envía GET por ID y retorna el documento', () => {
    service.getDocument('ws-1', 'doc-456').subscribe((doc) => {
      expect(doc.id).toBe('doc-456');
    });

    const req = http.expectOne('/api/v1/workspaces/ws-1/documents/doc-456');
    expect(req.request.method).toBe('GET');
    req.flush({ data: mockDocument });
  });

  it('deleteDocument envía DELETE y retorna mensaje de éxito', () => {
    service.deleteDocument('ws-1', 'doc-456').subscribe((res) => {
      expect(res.message).toBe('Documento eliminado');
    });

    const req = http.expectOne('/api/v1/workspaces/ws-1/documents/doc-456');
    expect(req.request.method).toBe('DELETE');
    req.flush({ data: { message: 'Documento eliminado' } });
  });

  it('retryDocument envía POST al endpoint de reintento y retorna DocumentItem actualizado (CDM-39)', () => {
    const retriedDoc = { ...mockDocument, status: 'PROCESSING' as const, retry_count: 1 };

    service.retryDocument('ws-1', 'doc-456').subscribe((doc) => {
      expect(doc.status).toBe('PROCESSING');
      expect(doc.retry_count).toBe(1);
    });

    const req = http.expectOne('/api/v1/workspaces/ws-1/documents/doc-456/retry');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    req.flush({ data: retriedDoc });
  });
});

import { TestBed } from '@angular/core/testing';
import { Observable, of, Subject } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DocumentItem, DocumentStatus, UploadProgressState } from './document.models';
import { DocumentService } from './document.service';
import { MAX_CONCURRENT_UPLOADS, UploadQueueService } from './upload-queue.service';

function file(name: string, content = 'contenido'): File {
  return new File([content], name, { type: 'application/pdf' });
}

function documentWith(status: DocumentStatus): DocumentItem {
  return {
    id: 'doc-1',
    workspace_id: 'ws-1',
    uploaded_by: 'u-1',
    original_filename: 'a.pdf',
    content_type: 'application/pdf',
    size_bytes: 9,
    status,
    technical_metadata: {},
    created_at: '2026-11-13T10:00:00Z',
    updated_at: '2026-11-13T10:00:00Z',
  };
}

describe('UploadQueueService', () => {
  let uploads: Subject<UploadProgressState>[];
  let uploadWithProgress: ReturnType<typeof vi.fn<(ws: string, f: File) => Observable<UploadProgressState>>>;
  let getDocument: ReturnType<typeof vi.fn<(ws: string, id: string) => Observable<DocumentItem>>>;
  let queue: UploadQueueService;

  beforeEach(() => {
    uploads = [];
    uploadWithProgress = vi.fn<(ws: string, f: File) => Observable<UploadProgressState>>(() => {
      const subject = new Subject<UploadProgressState>();
      uploads.push(subject);
      return subject;
    });
    getDocument = vi.fn<(ws: string, id: string) => Observable<DocumentItem>>(() =>
      of(documentWith('READY')),
    );
    TestBed.configureTestingModule({
      providers: [{ provide: DocumentService, useValue: { uploadWithProgress, getDocument } }],
    });
    queue = TestBed.inject(UploadQueueService);
  });

  afterEach(() => vi.useRealTimers());

  it(`sube como máximo ${MAX_CONCURRENT_UPLOADS} archivos a la vez`, () => {
    queue.enqueue('ws-1', [file('a.pdf'), file('b.pdf'), file('c.pdf')]);

    expect(uploadWithProgress).toHaveBeenCalledTimes(2);
    expect(queue.items().map((i) => i.phase)).toEqual(['requesting', 'requesting', 'queued']);
    expect(queue.activeCount()).toBe(2);
  });

  it('rechaza un archivo inválido con su motivo sin bloquear a los demás', () => {
    queue.enqueue('ws-1', [file('virus.exe'), file('a.pdf')]);

    const [rejected, valid] = queue.items();
    expect(rejected.phase).toBe('rejected');
    expect(rejected.error).toMatch(/no está permitido/);
    expect(valid.phase).toBe('requesting');
    expect(uploadWithProgress).toHaveBeenCalledTimes(1);
  });

  it('cancelar aborta la subida y arranca el siguiente de la cola', () => {
    queue.enqueue('ws-1', [file('a.pdf'), file('b.pdf'), file('c.pdf')]);
    const first = queue.items()[0];

    queue.cancel(first.id);

    expect(uploads[0].observed).toBe(false);
    expect(queue.items()[0].phase).toBe('cancelled');
    expect(queue.items()[2].phase).toBe('requesting');
    expect(uploadWithProgress).toHaveBeenCalledTimes(3);
  });

  it('reintentar vuelve a subir un archivo que falló', () => {
    queue.enqueue('ws-1', [file('a.pdf')]);
    const [item] = queue.items();
    uploads[0].next({ status: 'error', progressPercentage: 0, loadedBytes: 0, totalBytes: 9, error: 'Red caída' });
    uploads[0].complete();
    expect(queue.items()[0]).toMatchObject({ phase: 'error', error: 'Red caída' });

    queue.retry(item.id);

    expect(queue.items()[0].phase).toBe('requesting');
    expect(uploadWithProgress).toHaveBeenCalledTimes(2);
  });

  it('tras confirmar la carga sigue el estado del documento hasta que termina', () => {
    vi.useFakeTimers();
    const statuses: DocumentStatus[] = ['PROCESSING', 'READY'];
    getDocument.mockImplementation(() => of(documentWith(statuses.shift() ?? 'READY')));
    queue.enqueue('ws-1', [file('a.pdf')]);

    uploads[0].next({
      status: 'completed',
      progressPercentage: 100,
      loadedBytes: 9,
      totalBytes: 9,
      document: documentWith('UPLOADED'),
    });
    uploads[0].complete();
    expect(queue.items()[0]).toMatchObject({ phase: 'completed', documentId: 'doc-1', documentStatus: 'UPLOADED' });

    vi.advanceTimersByTime(2500);
    expect(queue.items()[0].documentStatus).toBe('PROCESSING');
    vi.advanceTimersByTime(2500);
    expect(queue.items()[0].documentStatus).toBe('READY');
    vi.advanceTimersByTime(10_000);
    expect(getDocument).toHaveBeenCalledTimes(2);
  });
});

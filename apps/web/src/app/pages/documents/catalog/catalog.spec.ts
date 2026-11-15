import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DocumentStats, DocumentStatsService } from '../../../core/documents/document-stats.service';
import { DocumentItem, DocumentListResult } from '../../../core/documents/document.models';
import { DocumentService } from '../../../core/documents/document.service';
import { UploadQueueService } from '../../../core/documents/upload-queue.service';
import { Workspace, WorkspaceRole } from '../../../core/workspaces/workspace.models';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';
import { DocumentCatalogComponent } from './catalog';
import { testDocument } from './components/test-documents';

const STATS: DocumentStats = {
  total: 14,
  byStatus: { READY: 7, PROCESSING: 2, UPLOADED: 1, PENDING_UPLOAD: 3, FAILED: 1 },
  lastWeek: 3,
  dailyUploads: [0, 0, 0, 1, 0, 0, 2],
};

const DOCS: DocumentItem[] = [
  testDocument('11111111-aaaa', 'READY', { original_filename: 'reporte.pdf' }),
  testDocument('22222222-bbbb', 'FAILED', { failure_reason: 'Contenido no admitido.' }),
];

function workspace(role: WorkspaceRole): Workspace {
  return {
    id: 'ws-1',
    name: 'Acme Legal',
    slug: 'acme-legal',
    role,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  };
}

describe('DocumentCatalogComponent (dashboard)', () => {
  let api: {
    listDocuments: ReturnType<typeof vi.fn>;
    getDownloadUrl: ReturnType<typeof vi.fn>;
    deleteDocument: ReturnType<typeof vi.fn>;
    retryDocument: ReturnType<typeof vi.fn>;
    getDocument: ReturnType<typeof vi.fn>;
  };
  let queue: { items: ReturnType<typeof signal>; enqueue: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    api = {
      listDocuments: vi.fn(() => of<DocumentListResult>({ items: DOCS, total: DOCS.length })),
      getDownloadUrl: vi.fn(() =>
        of({ document_id: 'x', original_filename: 'x', download_url: 'https://s3.example/x', expires_in_seconds: 900 }),
      ),
      deleteDocument: vi.fn(() => of({ message: 'ok' })),
      retryDocument: vi.fn((_ws: string, id: string) => of(testDocument(id, 'PROCESSING'))),
      getDocument: vi.fn(),
    };
    queue = { items: signal([]), enqueue: vi.fn() };
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: DocumentService, useValue: api },
        { provide: DocumentStatsService, useValue: { load: () => of(STATS) } },
        { provide: UploadQueueService, useValue: queue },
        {
          provide: ActivatedRoute,
          useValue: {
            paramMap: of(convertToParamMap({ id: 'ws-1' })),
            snapshot: { queryParamMap: convertToParamMap({}) },
          },
        },
      ],
    });
  });

  afterEach(() => vi.restoreAllMocks());

  async function render(role: WorkspaceRole = 'OWNER') {
    TestBed.inject(WorkspaceService).activeWorkspace.set(workspace(role));
    const fixture = TestBed.createComponent(DocumentCatalogComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const host = fixture.nativeElement as HTMLElement;
    const byText = (selector: string, text: string) =>
      Array.from(host.querySelectorAll<HTMLElement>(selector)).find((el) =>
        el.textContent?.includes(text),
      );
    return { fixture, host, byText };
  }

  it('muestra el workspace, las carpetas con conteos, los KPIs y el catálogo', async () => {
    const { host, byText } = await render();

    expect(host.querySelector('h1')?.textContent).toContain('Acme Legal');
    expect(host.querySelector('app-role-ladder')?.textContent).toContain('OWNER');
    expect(byText('[role="tab"]', 'Listos')?.textContent).toContain('7');
    expect(byText('app-kpi-card', 'Documentos')?.textContent).toContain('14');
    expect(byText('app-kpi-card', 'Documentos')?.textContent).toContain('+3 en 7 días');
    expect(byText('h2', 'Catálogo de documentos')).toBeTruthy();
    expect(host.querySelectorAll('tbody tr').length).toBe(2);
  });

  it('filtra por estado al elegir una carpeta', async () => {
    const { fixture, byText } = await render();
    api.listDocuments.mockClear();

    byText('[role="tab"]', 'Fallidos')?.click();
    fixture.detectChanges();

    expect(api.listDocuments).toHaveBeenCalledWith('ws-1', expect.objectContaining({ status: 'FAILED', offset: 0 }));
  });

  it('para VIEWER muestra el aviso de solo lectura y oculta carga y borrado', async () => {
    const { host } = await render('VIEWER');

    expect(host.textContent).toMatch(/Navegando con rol VIEWER/);
    expect(Array.from(host.querySelectorAll('a')).some((a) => a.textContent?.includes('Subir documento'))).toBe(false);
    expect(host.querySelector('button[aria-label="Eliminar documento"]')).toBeNull();
    expect(host.querySelector('.dropbar')).toBeNull();
  });

  it('muestra un estado vacío con la acción de subir cuando no hay documentos', async () => {
    api.listDocuments.mockReturnValue(of({ items: [], total: 0 }));
    const { host, byText } = await render('MEMBER');

    expect(host.textContent).toContain('Aún no hay documentos en este espacio');
    expect(byText('app-empty-state a', 'Subir documento')).toBeTruthy();
  });

  it('muestra el error de carga con opción de reintentar', async () => {
    api.listDocuments.mockReturnValue(throwError(() => new Error('caída')));
    const { byText } = await render();

    expect(byText('app-alert', 'No se pudieron cargar los documentos del espacio.')).toBeTruthy();
    expect(byText('button', 'Reintentar')).toBeTruthy();
  });

  it('confirma y ejecuta la eliminación lógica', async () => {
    const { fixture, host, byText } = await render();

    host.querySelector<HTMLButtonElement>('tbody button[aria-label="Eliminar documento"]')?.click();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(byText('h2', '¿Eliminar documento?')).toBeTruthy();

    byText('button', 'Sí, eliminar')?.click();
    fixture.detectChanges();
    await fixture.whenStable();

    expect(api.deleteDocument).toHaveBeenCalledWith('ws-1', '11111111-aaaa');
    expect(byText('h2', '¿Eliminar documento?')).toBeUndefined();
  });

  it('abre la URL de descarga en una pestaña nueva sin opener', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    const { host } = await render();

    host.querySelector<HTMLButtonElement>('tbody button[aria-label="Descargar archivo"]')?.click();

    expect(api.getDownloadUrl).toHaveBeenCalledWith('ws-1', '11111111-aaaa');
    expect(open).toHaveBeenCalledWith('https://s3.example/x', '_blank', 'noopener,noreferrer');
  });

  it('encola los archivos soltados en la Actividad', async () => {
    const { host } = await render();
    const file = new File(['x'], 'nuevo.pdf');
    const drop = new Event('drop', { bubbles: true, cancelable: true });
    Object.defineProperty(drop, 'dataTransfer', { value: { files: [file] } });

    host.querySelector('.dropbar')?.dispatchEvent(drop);

    expect(queue.enqueue).toHaveBeenCalledWith('ws-1', [file]);
  });
});

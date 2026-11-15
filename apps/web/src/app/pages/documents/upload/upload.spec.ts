import { signal, WritableSignal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { UploadQueueItem, UploadQueueService } from '../../../core/documents/upload-queue.service';
import { Workspace, WorkspaceRole } from '../../../core/workspaces/workspace.models';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';
import { DocumentUploadComponent } from './upload';

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

function queueItem(overrides: Partial<UploadQueueItem>): UploadQueueItem {
  return {
    id: 'upload-1',
    workspaceId: 'ws-1',
    file: new File(['contenido'], 'reporte.pdf', { type: 'application/pdf' }),
    phase: 'uploading',
    progress: 40,
    loadedBytes: 4,
    error: null,
    documentId: null,
    documentStatus: null,
    ...overrides,
  };
}

describe('DocumentUploadComponent', () => {
  let items: WritableSignal<UploadQueueItem[]>;
  let queue: {
    items: WritableSignal<UploadQueueItem[]>;
    enqueue: ReturnType<typeof vi.fn>;
    cancel: ReturnType<typeof vi.fn>;
    retry: ReturnType<typeof vi.fn>;
    remove: ReturnType<typeof vi.fn>;
    clearFinished: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    items = signal<UploadQueueItem[]>([]);
    queue = {
      items,
      enqueue: vi.fn(),
      cancel: vi.fn(),
      retry: vi.fn(),
      remove: vi.fn(),
      clearFinished: vi.fn(),
    };
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: UploadQueueService, useValue: queue },
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: 'ws-1' })) } },
      ],
    });
  });

  function render(role: WorkspaceRole = 'MEMBER') {
    TestBed.inject(WorkspaceService).activeWorkspace.set(workspace(role));
    const fixture = TestBed.createComponent(DocumentUploadComponent);
    fixture.detectChanges();
    const host = fixture.nativeElement as HTMLElement;
    const input = host.querySelector('#file-upload-input') as HTMLInputElement;
    const pick = (files: File[]) => {
      Object.defineProperty(input, 'files', { value: files, configurable: true });
      input.dispatchEvent(new Event('change'));
      fixture.detectChanges();
    };
    const button = (text: string) =>
      Array.from(host.querySelectorAll<HTMLButtonElement>('button')).find((b) =>
        b.textContent?.includes(text) || b.getAttribute('aria-label') === text,
      );
    return { fixture, host, input, pick, button };
  }

  it('muestra el título, la zona de carga accesible y la política de formatos', () => {
    const { host } = render();

    expect(host.querySelector('h1')?.textContent).toContain('Carga directa y segura a la nube');
    expect(host.querySelector('[role="region"]')?.getAttribute('aria-label')).toMatch(/Zona de carga/);
    expect(host.textContent).toContain('Formatos admitidos: PDF, PNG, JPG, TXT, MD, CSV, JSON, DOCX, XLSX');
    expect(host.querySelector('#file-upload-input')?.hasAttribute('multiple')).toBe(true);
  });

  it('prepara los archivos válidos y los encola al iniciar la carga', () => {
    const { pick, host, button } = render();
    const files = [new File(['a'], 'uno.pdf'), new File(['b'], 'dos.png')];

    pick(files);
    expect(host.textContent).toContain('uno.pdf');
    expect(host.textContent).toContain('dos.png');

    button('Iniciar carga segura a S3')?.click();
    expect(queue.enqueue).toHaveBeenCalledWith('ws-1', files);
  });

  it('rechaza formatos no permitidos con una alerta y no los prepara', () => {
    const { pick, host, button } = render();

    pick([new File(['x'], 'virus.exe')]);

    expect(host.querySelector('[role="alert"]')?.textContent).toMatch(/no está permitido/);
    expect(button('Iniciar carga segura a S3')).toBeUndefined();
  });

  it('para VIEWER muestra la advertencia y deshabilita la selección', () => {
    const { host, input } = render('VIEWER');

    expect(host.querySelector('[role="alert"]')?.textContent).toContain('Permiso insuficiente para carga');
    expect(input.disabled).toBe(true);
  });

  it('muestra el progreso por archivo y permite cancelar', () => {
    items.set([queueItem({ phase: 'uploading', progress: 40 })]);
    const { host, button } = render();

    expect(host.querySelector('[role="progressbar"]')?.getAttribute('aria-valuenow')).toBe('40');
    button('Cancelar carga de reporte.pdf')?.click();
    expect(queue.cancel).toHaveBeenCalledWith('upload-1');
  });

  it('confirma la carga completada con enlace al catálogo', () => {
    items.set([queueItem({ phase: 'completed', progress: 100, documentId: 'doc-9', documentStatus: 'PROCESSING' })]);
    const { host } = render();

    expect(host.querySelector('h2.summary__title')?.textContent).toContain('¡Documento cargado exitosamente!');
    const link = Array.from(host.querySelectorAll('a')).find((a) => a.textContent?.includes('Ver en el catálogo'));
    expect(link?.getAttribute('href')).toBe('/workspaces/ws-1/documents?docId=doc-9');
  });
});

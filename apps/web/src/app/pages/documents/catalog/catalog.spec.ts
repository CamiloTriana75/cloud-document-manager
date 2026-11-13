import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { describe, it, expect, beforeEach, vi } from 'vitest';

import { DocumentCatalogComponent } from './catalog';
import { DocumentService } from '../../../core/documents/document.service';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';
import { DocumentItem } from '../../../core/documents/document.models';

describe('DocumentCatalogComponent (CDM-37)', () => {
  let component: DocumentCatalogComponent;
  let fixture: ComponentFixture<DocumentCatalogComponent>;

  const mockDocuments: DocumentItem[] = [
    {
      id: 'doc-ready-1',
      workspace_id: 'ws-123',
      uploaded_by: 'user-1',
      original_filename: 'contrato.pdf',
      storage_key: 'tenants/ws-123/documents/doc-ready-1/contrato.pdf',
      content_type: 'application/pdf',
      size_bytes: 1048576, // 1 MB
      status: 'READY',
      technical_metadata: { s3_etag: 'etag-123' },
      created_at: '2026-11-12T18:00:00Z',
      updated_at: '2026-11-12T18:05:00Z',
      failure_reason: null,
    },
    {
      id: 'doc-proc-2',
      workspace_id: 'ws-123',
      uploaded_by: 'user-1',
      original_filename: 'video.mp4',
      storage_key: 'tenants/ws-123/documents/doc-proc-2/video.mp4',
      content_type: 'video/mp4',
      size_bytes: 5242880,
      status: 'PROCESSING',
      technical_metadata: {},
      created_at: '2026-11-12T19:00:00Z',
      updated_at: '2026-11-12T19:01:00Z',
      failure_reason: null,
    },
    {
      id: 'doc-failed-3',
      workspace_id: 'ws-123',
      uploaded_by: 'user-1',
      original_filename: 'corrupted.zip',
      storage_key: 'tenants/ws-123/documents/doc-failed-3/corrupted.zip',
      content_type: 'application/zip',
      size_bytes: 2048,
      status: 'FAILED',
      technical_metadata: { failed_at: '2026-11-12T19:10:00Z' },
      created_at: '2026-11-12T19:09:00Z',
      updated_at: '2026-11-12T19:10:00Z',
      failure_reason: 'Formato o contenido no admitido.',
    },
  ];

  const mockDocumentService = {
    listDocuments: vi.fn().mockReturnValue(
      of({
        items: mockDocuments,
        total: mockDocuments.length,
      })
    ),
    getDownloadUrl: vi.fn().mockReturnValue(
      of({
        document_id: 'doc-ready-1',
        original_filename: 'contrato.pdf',
        download_url: 'https://s3.amazonaws.com/test-url',
        expires_in_seconds: 900,
      })
    ),
    deleteDocument: vi.fn().mockReturnValue(of({ message: 'Deleted' })),
  };

  const mockWorkspaceService = {
    activeWorkspace: vi.fn().mockReturnValue({
      id: 'ws-123',
      name: 'Mi Workspace',
      slug: 'mi-workspace',
      role: 'ADMIN',
    }),
  };

  beforeEach(async () => {
    vi.clearAllMocks();

    await TestBed.configureTestingModule({
      imports: [DocumentCatalogComponent],
      providers: [
        provideRouter([]),
        { provide: DocumentService, useValue: mockDocumentService },
        { provide: WorkspaceService, useValue: mockWorkspaceService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(DocumentCatalogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('debe crearse correctamente y listar los documentos del espacio activo', () => {
    expect(component).toBeTruthy();
    expect(mockDocumentService.listDocuments).toHaveBeenCalledWith('ws-123', 50, 0);
    expect(component.documents().length).toBe(3);

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('contrato.pdf');
    expect(compiled.textContent).toContain('video.mp4');
    expect(compiled.textContent).toContain('corrupted.zip');
  });

  it('muestra los badges de estado correctamente (Listo, Procesando, Fallido)', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Listo');
    expect(compiled.textContent).toContain('Procesando');
    expect(compiled.textContent).toContain('Fallido');
  });

  it('muestra la razón segura de fallo para documentos en FAILED sin exponer stack traces', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Formato o contenido no admitido.');
    expect(compiled.textContent).not.toContain('Traceback');
  });

  it('permite filtrar por estado al interactuar con las píldoras de filtro', () => {
    // Filtrar solo READY
    component.setFilter('READY');
    fixture.detectChanges();
    expect(component.filteredDocuments().length).toBe(1);
    expect(component.filteredDocuments()[0].original_filename).toBe('contrato.pdf');

    // Filtrar solo FAILED
    component.setFilter('FAILED');
    fixture.detectChanges();
    expect(component.filteredDocuments().length).toBe(1);
    expect(component.filteredDocuments()[0].original_filename).toBe('corrupted.zip');

    // Volver a ALL
    component.setFilter('ALL');
    fixture.detectChanges();
    expect(component.filteredDocuments().length).toBe(3);
  });

  it('abre el modal de detalle técnico al invocar openDetail', () => {
    const doc = mockDocuments[0];
    component.openDetail(doc);
    fixture.detectChanges();

    expect(component.isDetailOpen()).toBe(true);
    expect(component.selectedDocument()?.id).toBe('doc-ready-1');

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Metadatos Técnicos (JSONB)');
    expect(compiled.textContent).toContain('s3_etag');
  });

  it('solicita la URL prefirmada al descargar un documento READY', () => {
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    const doc = mockDocuments[0];
    component.downloadDocument(doc);

    expect(mockDocumentService.getDownloadUrl).toHaveBeenCalledWith('ws-123', 'doc-ready-1');
    expect(windowOpenSpy).toHaveBeenCalledWith('https://s3.amazonaws.com/test-url', '_blank');
  });

  it('permite eliminar documentos para roles con permiso (ADMIN)', () => {
    const doc = mockDocuments[2];
    component.confirmDelete(doc);
    expect(component.documentToDelete()?.id).toBe('doc-failed-3');

    component.executeDelete();
    expect(mockDocumentService.deleteDocument).toHaveBeenCalledWith('ws-123', 'doc-failed-3');
  });
});

import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
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
    retryDocument: vi.fn().mockReturnValue(
      of({
        id: 'doc-failed-3',
        workspace_id: 'ws-123',
        uploaded_by: 'user-1',
        original_filename: 'corrupted.zip',
        storage_key: 'tenants/ws-123/documents/doc-failed-3/corrupted.zip',
        content_type: 'application/zip',
        size_bytes: 2048,
        status: 'PROCESSING',
        technical_metadata: { retry_count: 1 },
        created_at: '2026-11-12T19:09:00Z',
        updated_at: '2026-11-12T19:15:00Z',
        failure_reason: null,
        retry_count: 1,
      })
    ),
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
    expect(mockDocumentService.listDocuments).toHaveBeenCalledWith(
      'ws-123',
      expect.objectContaining({ limit: 50, offset: 0 })
    );
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

  it('permite reintentar documentos FAILED para usuarios ADMIN/OWNER (CDM-39)', () => {
    const failedDoc = mockDocuments[2];
    expect(component.canRetry()).toBe(true);

    component.retryDocument(failedDoc);
    expect(mockDocumentService.retryDocument).toHaveBeenCalledWith('ws-123', 'doc-failed-3');

    // El documento en la lista debe actualizarse a PROCESSING y retry_count=1
    const updated = component.documents().find((d) => d.id === 'doc-failed-3');
    expect(updated?.status).toBe('PROCESSING');
    expect(updated?.retry_count).toBe(1);
  });

  it('permite buscar documentos por término en nombre de archivo (CDM-42)', () => {
    // Búsqueda por término "contrato"
    component.searchTerm.set('contrato');
    fixture.detectChanges();
    expect(component.filteredDocuments().length).toBe(1);
    expect(component.filteredDocuments()[0].original_filename).toBe('contrato.pdf');

    // Limpiar búsqueda
    component.clearSearch();
    fixture.detectChanges();
    expect(component.filteredDocuments().length).toBe(3);
  });

  it('permite filtrar por tipo de formato MIME y resetear filtros (CDM-42)', () => {
    // Filtrar por application/pdf
    component.setMimeFilter('application/pdf');
    fixture.detectChanges();
    expect(component.filteredDocuments().length).toBe(1);
    expect(component.filteredDocuments()[0].content_type).toBe('application/pdf');

    // Resetear todos los filtros
    component.resetAllFilters();
    fixture.detectChanges();
    expect(component.activeFilter()).toBe('ALL');
    expect(component.searchTerm()).toBe('');
    expect(component.selectedMime()).toBe('ALL');
    expect(component.filteredDocuments().length).toBe(3);
  });

  it('calcula la paginación correctamente y permite navegar entre páginas (CDM-42)', () => {
    mockDocumentService.listDocuments.mockReturnValue(
      of({
        items: mockDocuments,
        total: 120,
      })
    );
    component.totalDocuments.set(120);
    component.pageSize.set(50);
    expect(component.totalPages()).toBe(3);
    expect(component.currentPage()).toBe(1);
    expect(component.hasPrevPage()).toBe(false);
    expect(component.hasNextPage()).toBe(true);
    expect(component.showingFrom()).toBe(1);
    expect(component.showingTo()).toBe(50);

    // Siguiente página
    component.nextPage();
    expect(component.currentPage()).toBe(2);
    expect(component.hasPrevPage()).toBe(true);
    expect(component.hasNextPage()).toBe(true);
    expect(component.showingFrom()).toBe(51);
    expect(component.showingTo()).toBe(100);

    // Página anterior
    component.prevPage();
    expect(component.currentPage()).toBe(1);

    // Cambiar tamaño de página
    component.setPageSize(25);
    expect(component.pageSize()).toBe(25);
    expect(component.totalPages()).toBe(5);
  });

  it('permite ordenar por columna (nombre, tamaño, fecha) en asc y desc (CDM-46)', () => {
    // Ordenar por nombre ascendente
    component.toggleSort('original_filename');
    expect(component.sortColumn()).toBe('original_filename');
    expect(component.sortDirection()).toBe('asc');
    expect(component.sortedDocuments()[0].original_filename).toBe('contrato.pdf');
    expect(component.sortedDocuments()[2].original_filename).toBe('video.mp4');

    // Toggle a descendente
    component.toggleSort('original_filename');
    expect(component.sortDirection()).toBe('desc');
    expect(component.sortedDocuments()[0].original_filename).toBe('video.mp4');
    expect(component.sortedDocuments()[2].original_filename).toBe('contrato.pdf');

    // Ordenar por tamaño
    component.toggleSort('size_bytes');
    expect(component.sortColumn()).toBe('size_bytes');
    expect(component.sortDirection()).toBe('asc');
    expect(component.sortedDocuments()[0].size_bytes).toBe(2048);
  });

  it('no muestra acciones no permitidas según el rol activo (ADR-0001 / CDM-46)', () => {
    // Para VIEWER: no puede subir, no puede eliminar, no puede reintentar
    mockWorkspaceService.activeWorkspace.mockReturnValue({
      id: 'ws-123',
      name: 'Mi Workspace',
      slug: 'mi-workspace',
      role: 'VIEWER',
    });

    const viewerFixture = TestBed.createComponent(DocumentCatalogComponent);
    viewerFixture.detectChanges();
    const viewerComp = viewerFixture.componentInstance;

    expect(viewerComp.canUpload()).toBe(false);
    expect(viewerComp.canDelete()).toBe(false);
    expect(viewerComp.canRetry()).toBe(false);
    expect(viewerFixture.nativeElement.querySelector('.role-notice-banner')).toBeTruthy();
    expect(viewerFixture.nativeElement.querySelector('.btn-delete')).toBeNull();

    // Para MEMBER: puede subir, pero no puede eliminar ni reintentar
    mockWorkspaceService.activeWorkspace.mockReturnValue({
      id: 'ws-123',
      name: 'Mi Workspace',
      slug: 'mi-workspace',
      role: 'MEMBER',
    });
    const memberFixture = TestBed.createComponent(DocumentCatalogComponent);
    memberFixture.detectChanges();
    const memberComp = memberFixture.componentInstance;

    expect(memberComp.canUpload()).toBe(true);
    expect(memberComp.canDelete()).toBe(false);
    expect(memberComp.canRetry()).toBe(false);

    // Para EDITOR: puede subir y eliminar, pero no reintentar
    mockWorkspaceService.activeWorkspace.mockReturnValue({
      id: 'ws-123',
      name: 'Mi Workspace',
      slug: 'mi-workspace',
      role: 'EDITOR',
    });
    const editorFixture = TestBed.createComponent(DocumentCatalogComponent);
    editorFixture.detectChanges();
    const editorComp = editorFixture.componentInstance;

    expect(editorComp.canUpload()).toBe(true);
    expect(editorComp.canDelete()).toBe(true);
    expect(editorComp.canRetry()).toBe(false);
  });
});

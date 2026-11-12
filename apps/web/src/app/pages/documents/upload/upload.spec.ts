import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, provideRouter } from '@angular/router';
import { Subject } from 'rxjs';

import {
  DocumentItem,
  UploadProgressState,
} from '../../../core/documents/document.models';
import { DocumentService } from '../../../core/documents/document.service';
import { Workspace } from '../../../core/workspaces/workspace.models';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';
import { DocumentUploadComponent } from './upload';

describe('DocumentUploadComponent', () => {
  let component: DocumentUploadComponent;
  let documentService: DocumentService;
  let workspaceService: WorkspaceService;
  let router: Router;

  const mockWorkspace: Workspace = {
    id: 'ws-test-123',
    name: 'Espacio Principal',
    slug: 'espacio-principal',
    role: 'ADMIN',
    created_at: '2026-11-12T00:00:00Z',
    updated_at: '2026-11-12T00:00:00Z',
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DocumentUploadComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: {
                get: (key: string) => (key === 'id' ? 'ws-test-123' : null),
              },
            },
          },
        },
      ],
    }).compileComponents();

    documentService = TestBed.inject(DocumentService);
    workspaceService = TestBed.inject(WorkspaceService);
    router = TestBed.inject(Router);

    workspaceService.activeWorkspace.set(mockWorkspace);

    const fixture = TestBed.createComponent(DocumentUploadComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('inicializa con el ID y nombre del workspace activo', () => {
    expect(component.workspaceId).toBe('ws-test-123');
    expect(component.workspaceName).toBe('Espacio Principal');
    expect(component.selectedFile).toBeNull();
    expect(component.uploadState.status).toBe('idle');
  });

  it('redirige a la raíz si no se proporciona el ID de workspace en la ruta', () => {
    const navigateSpy = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    const fixture = TestBed.createComponent(DocumentUploadComponent);
    const comp = fixture.componentInstance;
    comp.workspaceId = '';
    // Simulamos paramMap sin id
    const route = TestBed.inject(ActivatedRoute);
    route.snapshot.paramMap.get = () => null;

    comp.ngOnInit();

    expect(navigateSpy).toHaveBeenCalledWith(['/']);
  });

  it('valida y acepta un archivo válido con extensión permitida y tamaño correcto', () => {
    const validFile = new File(['hola mundo'], 'documento.pdf', {
      type: 'application/pdf',
    });

    component.handleFileSelected(validFile);

    expect(component.validationError).toBeNull();
    expect(component.selectedFile).toBe(validFile);
    expect(component.uploadState.totalBytes).toBe(validFile.size);
  });

  it('rechaza archivos con extensiones no permitidas (.exe)', () => {
    const invalidFile = new File(['binario'], 'malware.exe', {
      type: 'application/octet-stream',
    });

    component.handleFileSelected(invalidFile);

    expect(component.selectedFile).toBeNull();
    expect(component.validationError).toContain('no está permitido');
  });

  it('rechaza archivos vacíos de 0 bytes', () => {
    const emptyFile = new File([], 'vacio.txt', { type: 'text/plain' });

    component.handleFileSelected(emptyFile);

    expect(component.selectedFile).toBeNull();
    expect(component.validationError).toContain('está vacío');
  });

  it('rechaza archivos que exceden los 50 MB', () => {
    const bigFile = new File(['x'], 'gigante.pdf', { type: 'application/pdf' });
    Object.defineProperty(bigFile, 'size', { value: 55 * 1024 * 1024 });

    component.handleFileSelected(bigFile);

    expect(component.selectedFile).toBeNull();
    expect(component.validationError).toContain('supera el tamaño máximo');
  });

  it('maneja eventos drag & drop actualizando isDragging', () => {
    const mockEvent = {
      preventDefault: vi.fn(),
      stopPropagation: vi.fn(),
    } as unknown as DragEvent;

    component.onDragOver(mockEvent);
    expect(component.isDragging).toBe(true);

    component.onDragLeave(mockEvent);
    expect(component.isDragging).toBe(false);
  });

  it('onDrop extrae el archivo y lo valida', () => {
    const validFile = new File(['pdf data'], 'balance.pdf', {
      type: 'application/pdf',
    });
    const mockDropEvent = {
      preventDefault: vi.fn(),
      stopPropagation: vi.fn(),
      dataTransfer: {
        files: [validFile],
      },
    } as unknown as DragEvent;

    component.onDrop(mockDropEvent);

    expect(component.isDragging).toBe(false);
    expect(component.selectedFile).toBe(validFile);
  });

  it('inicia la carga y actualiza reactivamente uploadState', () => {
    const validFile = new File(['pdf data'], 'balance.pdf', {
      type: 'application/pdf',
    });
    component.handleFileSelected(validFile);

    const progressSubject = new Subject<UploadProgressState>();
    vi.spyOn(documentService, 'uploadWithProgress').mockReturnValue(
      progressSubject.asObservable()
    );

    component.startUpload();

    // Emite estado de progreso
    progressSubject.next({
      status: 'uploading',
      progressPercentage: 50,
      loadedBytes: 512,
      totalBytes: 1024,
    });

    expect(component.uploadState.status).toBe('uploading');
    expect(component.uploadState.progressPercentage).toBe(50);

    // Emite estado final
    const mockDoc: DocumentItem = {
      id: 'doc-1',
      workspace_id: 'ws-test-123',
      original_filename: 'balance.pdf',
      storage_key: 'key',
      content_type: 'application/pdf',
      size_bytes: 1024,
      status: 'UPLOADED',
      checksum_sha256: null,
      technical_metadata: {},
      created_at: '',
      updated_at: '',
      uploaded_by: '',
    };

    progressSubject.next({
      status: 'completed',
      progressPercentage: 100,
      loadedBytes: 1024,
      totalBytes: 1024,
      document: mockDoc,
    });

    expect(component.uploadState.status).toBe('completed');
    expect(component.uploadState.progressPercentage).toBe(100);
  });

  it('permite cancelar la carga en curso interrumpiendo la suscripción', () => {
    const validFile = new File(['pdf data'], 'balance.pdf', {
      type: 'application/pdf',
    });
    component.handleFileSelected(validFile);

    const progressSubject = new Subject<UploadProgressState>();
    vi.spyOn(documentService, 'uploadWithProgress').mockReturnValue(
      progressSubject.asObservable()
    );

    component.startUpload();
    progressSubject.next({
      status: 'uploading',
      progressPercentage: 40,
      loadedBytes: 400,
      totalBytes: 1000,
    });

    component.cancelUpload();

    expect(component.uploadState.status).toBe('cancelled');
    expect(component.uploadState.error).toContain('cancelada');
  });

  it('resetForm limpia el estado completo de carga y archivo seleccionado', () => {
    const validFile = new File(['pdf data'], 'balance.pdf', {
      type: 'application/pdf',
    });
    component.handleFileSelected(validFile);

    component.resetForm();

    expect(component.selectedFile).toBeNull();
    expect(component.validationError).toBeNull();
    expect(component.uploadState.status).toBe('idle');
  });

  it('formatBytes formatea tamaños legibles correctamente', () => {
    expect(component.formatBytes(0)).toBe('0 B');
    expect(component.formatBytes(1024)).toBe('1 KB');
    expect(component.formatBytes(5 * 1024 * 1024)).toBe('5 MB');
  });
});

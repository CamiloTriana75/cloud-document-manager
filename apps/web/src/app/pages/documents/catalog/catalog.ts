import {
  Component,
  computed,
  DestroyRef,
  HostListener,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { Subject, takeUntil } from 'rxjs';

import {
  DocumentFilterOptions,
  DocumentItem,
  DocumentStatus,
} from '../../../core/documents/document.models';
import { DocumentService } from '../../../core/documents/document.service';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';

export type StatusFilterOption = 'ALL' | DocumentStatus;

export type SortColumn =
  | 'original_filename'
  | 'content_type'
  | 'size_bytes'
  | 'created_at'
  | 'status';
export type SortDirection = 'asc' | 'desc';

export interface MimeOption {
  label: string;
  value: string;
}

export const MIME_OPTIONS: MimeOption[] = [
  { label: 'Todos los tipos', value: 'ALL' },
  { label: 'PDFs (.pdf)', value: 'application/pdf' },
  { label: 'Imágenes (PNG/JPG)', value: 'image/' },
  { label: 'Documentos Word/Excel', value: 'application/vnd' },
  { label: 'Texto y Markdown', value: 'text/' },
];

@Component({
  selector: 'app-document-catalog',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  templateUrl: './catalog.html',
  styleUrl: './catalog.css',
})
export class DocumentCatalogComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly documentService = inject(DocumentService);
  readonly workspaceService = inject(WorkspaceService);
  private readonly destroyRef = inject(DestroyRef);

  private readonly destroy$ = new Subject<void>();

  readonly workspaceId = signal<string>('');
  readonly documents = signal<DocumentItem[]>([]);
  readonly isLoading = signal<boolean>(true);
  readonly isRefreshing = signal<boolean>(false);
  readonly errorMessage = signal<string | null>(null);

  // Filtros interactivos (CDM-42)
  readonly activeFilter = signal<StatusFilterOption>('ALL');
  readonly searchTerm = signal<string>('');
  readonly selectedMime = signal<string>('ALL');
  readonly mimeOptions = MIME_OPTIONS;

  // Paginación server-side (CDM-42)
  readonly currentPage = signal<number>(1);
  readonly pageSize = signal<number>(50);
  readonly totalDocuments = signal<number>(0);

  readonly totalPages = computed(() =>
    Math.max(1, Math.ceil(this.totalDocuments() / this.pageSize()))
  );

  readonly hasNextPage = computed(() => this.currentPage() < this.totalPages());
  readonly hasPrevPage = computed(() => this.currentPage() > 1);

  readonly showingFrom = computed(() =>
    this.totalDocuments() === 0
      ? 0
      : (this.currentPage() - 1) * this.pageSize() + 1
  );

  readonly showingTo = computed(() =>
    Math.min(this.currentPage() * this.pageSize(), this.totalDocuments())
  );

  // Modal / Detalle de documento seleccionado
  readonly selectedDocument = signal<DocumentItem | null>(null);
  readonly isDetailOpen = signal<boolean>(false);

  // Modal de confirmación de eliminación
  readonly documentToDelete = signal<DocumentItem | null>(null);
  readonly isDeleting = signal<boolean>(false);

  // Acción de descarga en progreso
  readonly downloadingDocId = signal<string | null>(null);
  readonly actionErrorMessage = signal<string | null>(null);

  readonly canDelete = computed(() => {
    const role = this.workspaceService.activeWorkspace()?.role;
    return role === 'OWNER' || role === 'ADMIN' || role === 'EDITOR';
  });

  readonly canUpload = computed(() => {
    const role = this.workspaceService.activeWorkspace()?.role;
    return (
      role === 'OWNER' ||
      role === 'ADMIN' ||
      role === 'EDITOR' ||
      role === 'MEMBER'
    );
  });

  readonly canRetry = computed(() => {
    const role = this.workspaceService.activeWorkspace()?.role;
    return role === 'OWNER' || role === 'ADMIN';
  });

  readonly retryingDocId = signal<string | null>(null);

  readonly filteredDocuments = computed(() => {
    const statusFilter = this.activeFilter();
    const search = this.searchTerm().trim().toLowerCase();
    const mime = this.selectedMime();
    let result = this.documents();

    // 1. Filtro por estado
    if (statusFilter !== 'ALL') {
      result = result.filter((doc) => doc.status === statusFilter);
    }

    // 2. Filtro por término en nombre
    if (search) {
      result = result.filter((doc) =>
        doc.original_filename.toLowerCase().includes(search)
      );
    }

    // 3. Filtro por MIME type
    if (mime !== 'ALL') {
      result = result.filter((doc) =>
        doc.content_type.toLowerCase().startsWith(mime.toLowerCase())
      );
    }

    return result;
  });

  // Ordenamiento interactivo por columna (CDM-46)
  readonly sortColumn = signal<SortColumn>('created_at');
  readonly sortDirection = signal<SortDirection>('desc');

  toggleSort(column: SortColumn): void {
    if (this.sortColumn() === column) {
      this.sortDirection.update((dir) => (dir === 'asc' ? 'desc' : 'asc'));
    } else {
      this.sortColumn.set(column);
      this.sortDirection.set('asc');
    }
  }

  readonly sortedDocuments = computed(() => {
    const list = [...this.filteredDocuments()];
    const col = this.sortColumn();
    const dir = this.sortDirection();

    return list.sort((a, b) => {
      let cmp = 0;
      switch (col) {
        case 'original_filename':
          cmp = a.original_filename.localeCompare(b.original_filename);
          break;
        case 'content_type':
          cmp = a.content_type.localeCompare(b.content_type);
          break;
        case 'size_bytes':
          cmp = a.size_bytes - b.size_bytes;
          break;
        case 'created_at':
          cmp =
            new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
        case 'status':
          cmp = a.status.localeCompare(b.status);
          break;
      }
      return dir === 'asc' ? cmp : -cmp;
    });
  });

  readonly hasActiveFilters = computed(
    () =>
      this.activeFilter() !== 'ALL' ||
      this.searchTerm().trim().length > 0 ||
      this.selectedMime() !== 'ALL'
  );

  readonly hasProcessingDocuments = computed(() => {
    return this.documents().some(
      (doc) => doc.status === 'PROCESSING' || doc.status === 'UPLOADED'
    );
  });

  ngOnInit(): void {
    this.destroyRef.onDestroy(() => {
      this.destroy$.next();
      this.destroy$.complete();
    });

    const routeId = this.route.snapshot.paramMap.get('id');
    const targetWsId =
      routeId || this.workspaceService.activeWorkspace()?.id || '';

    if (!targetWsId) {
      this.errorMessage.set('No se ha seleccionado ningún espacio de trabajo.');
      this.isLoading.set(false);
      return;
    }

    this.workspaceId.set(targetWsId);
    this.loadDocuments();

    const targetDocId = this.route.snapshot.queryParamMap.get('docId');
    if (targetDocId) {
      this.documentService
        .getDocument(targetWsId, targetDocId)
        .pipe(takeUntil(this.destroy$))
        .subscribe({
          next: (doc) => this.openDetail(doc),
          error: () => {
            // Documento no encontrado o no accesible
          },
        });
    }

    // Auto-polling cada 5 segundos si hay documentos en procesamiento
    const intervalId = setInterval(() => {
      if (this.hasProcessingDocuments() && !this.isLoading()) {
        this.refreshDocuments(true);
      }
    }, 5000);

    this.destroyRef.onDestroy(() => {
      clearInterval(intervalId);
    });
  }

  loadDocuments(): void {
    const wsId = this.workspaceId();
    if (!wsId) return;

    this.isLoading.set(true);
    this.errorMessage.set(null);

    const offset = (this.currentPage() - 1) * this.pageSize();
    const filterOptions: DocumentFilterOptions = {
      limit: this.pageSize(),
      offset,
      status: this.activeFilter() === 'ALL' ? undefined : this.activeFilter(),
      search: this.searchTerm().trim() || undefined,
      content_type:
        this.selectedMime() === 'ALL' ? undefined : this.selectedMime(),
    };

    this.documentService
      .listDocuments(wsId, filterOptions)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (res) => {
          this.documents.set(res.items);
          this.totalDocuments.set(res.total);
          this.isLoading.set(false);
          this.isRefreshing.set(false);
        },
        error: (err) => {
          this.errorMessage.set(
            err?.error?.error?.message ||
              'No se pudieron cargar los documentos del espacio.'
          );
          this.isLoading.set(false);
          this.isRefreshing.set(false);
        },
      });
  }

  refreshDocuments(silent = false): void {
    const wsId = this.workspaceId();
    if (!wsId) return;

    if (!silent) {
      this.isRefreshing.set(true);
    }

    const offset = (this.currentPage() - 1) * this.pageSize();
    const filterOptions: DocumentFilterOptions = {
      limit: this.pageSize(),
      offset,
      status: this.activeFilter() === 'ALL' ? undefined : this.activeFilter(),
      search: this.searchTerm().trim() || undefined,
      content_type:
        this.selectedMime() === 'ALL' ? undefined : this.selectedMime(),
    };

    this.documentService
      .listDocuments(wsId, filterOptions)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (res) => {
          this.documents.set(res.items);
          this.totalDocuments.set(res.total);
          this.isRefreshing.set(false);
        },
        error: () => {
          this.isRefreshing.set(false);
        },
      });
  }

  setFilter(filter: StatusFilterOption): void {
    this.activeFilter.set(filter);
    this.currentPage.set(1);
    this.loadDocuments();
  }

  onSearchChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.searchTerm.set(input.value || '');
    this.currentPage.set(1);
    this.loadDocuments();
  }

  clearSearch(): void {
    this.searchTerm.set('');
    this.currentPage.set(1);
    this.loadDocuments();
  }

  setMimeFilter(mime: string): void {
    this.selectedMime.set(mime);
    this.currentPage.set(1);
    this.loadDocuments();
  }

  resetAllFilters(): void {
    this.activeFilter.set('ALL');
    this.searchTerm.set('');
    this.selectedMime.set('ALL');
    this.currentPage.set(1);
    this.loadDocuments();
  }

  nextPage(): void {
    if (this.hasNextPage()) {
      this.currentPage.update((p) => p + 1);
      this.loadDocuments();
    }
  }

  prevPage(): void {
    if (this.hasPrevPage()) {
      this.currentPage.update((p) => p - 1);
      this.loadDocuments();
    }
  }

  goToPage(page: number): void {
    if (page >= 1 && page <= this.totalPages() && page !== this.currentPage()) {
      this.currentPage.set(page);
      this.loadDocuments();
    }
  }

  setPageSize(size: number): void {
    this.pageSize.set(size);
    this.currentPage.set(1);
    this.loadDocuments();
  }

  openDetail(doc: DocumentItem): void {
    this.selectedDocument.set(doc);
    this.isDetailOpen.set(true);
  }

  closeDetail(): void {
    this.selectedDocument.set(null);
    this.isDetailOpen.set(false);
  }

  downloadDocument(doc: DocumentItem): void {
    if (doc.status !== 'READY') return;

    this.downloadingDocId.set(doc.id);
    this.documentService
      .getDownloadUrl(this.workspaceId(), doc.id)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (res) => {
          this.downloadingDocId.set(null);
          // Redirigir a URL prefirmada temporal para descarga
          window.open(res.download_url, '_blank');
        },
        error: (err) => {
          this.downloadingDocId.set(null);
          this.actionErrorMessage.set(
            err?.error?.error?.message ||
              'No se pudo generar la URL de descarga del documento.'
          );
        },
      });
  }

  retryDocument(doc: DocumentItem): void {
    if (doc.status !== 'FAILED') return;

    this.retryingDocId.set(doc.id);
    this.actionErrorMessage.set(null);
    this.documentService
      .retryDocument(this.workspaceId(), doc.id)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (updatedDoc) => {
          this.retryingDocId.set(null);
          this.documents.update((docs) =>
            docs.map((d) => (d.id === updatedDoc.id ? updatedDoc : d))
          );
          if (this.selectedDocument()?.id === doc.id) {
            this.selectedDocument.set(updatedDoc);
          }
        },
        error: (err) => {
          this.retryingDocId.set(null);
          this.actionErrorMessage.set(
            err?.error?.error?.message ||
              'No se pudo reintentar el procesamiento del documento.'
          );
        },
      });
  }

  confirmDelete(doc: DocumentItem): void {
    this.actionErrorMessage.set(null);
    this.documentToDelete.set(doc);
  }

  confirmDeleteFromDetail(doc: DocumentItem): void {
    this.closeDetail();
    this.confirmDelete(doc);
  }

  cancelDelete(): void {
    this.documentToDelete.set(null);
  }

  executeDelete(): void {
    const doc = this.documentToDelete();
    if (!doc) return;

    this.isDeleting.set(true);
    this.actionErrorMessage.set(null);
    this.documentService
      .deleteDocument(this.workspaceId(), doc.id)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.isDeleting.set(false);
          this.documentToDelete.set(null);
          if (this.selectedDocument()?.id === doc.id) {
            this.closeDetail();
          }
          this.refreshDocuments(true);
        },
        error: (err) => {
          this.isDeleting.set(false);
          this.actionErrorMessage.set(
            err?.error?.error?.message ||
              'No se pudo eliminar el documento seleccionado.'
          );
        },
      });
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.documentToDelete()) {
      this.cancelDelete();
    } else if (this.isDetailOpen()) {
      this.closeDetail();
    }
  }

  formatBytes(bytes: number): string {
    if (bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  }

  formatDate(dateStr: string): string {
    try {
      const date = new Date(dateStr);
      return new Intl.DateTimeFormat('es-CO', {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(date);
    } catch {
      return dateStr;
    }
  }

  getStatusLabel(status: StatusFilterOption): string {
    switch (status) {
      case 'ALL':
        return 'Todos';
      case 'READY':
        return 'Listo';
      case 'PROCESSING':
        return 'Procesando';
      case 'UPLOADED':
        return 'Subido';
      case 'PENDING_UPLOAD':
        return 'Pendiente';
      case 'FAILED':
        return 'Fallido';
      case 'DELETED':
        return 'Eliminado';
      default:
        return status;
    }
  }

  getStatusClass(status: DocumentStatus): string {
    switch (status) {
      case 'READY':
        return 'doc-status-ready';
      case 'PROCESSING':
        return 'doc-status-processing';
      case 'UPLOADED':
        return 'doc-status-uploaded';
      case 'PENDING_UPLOAD':
        return 'doc-status-pending';
      case 'FAILED':
        return 'doc-status-failed';
      case 'DELETED':
        return 'doc-status-deleted';
      default:
        return '';
    }
  }
}

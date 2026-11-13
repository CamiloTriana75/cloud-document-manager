import {
  Component,
  computed,
  DestroyRef,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { Subject, takeUntil } from 'rxjs';

import {
  DocumentItem,
  DocumentStatus,
} from '../../../core/documents/document.models';
import { DocumentService } from '../../../core/documents/document.service';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';

export type StatusFilterOption = 'ALL' | DocumentStatus;

@Component({
  selector: 'app-document-catalog',
  standalone: true,
  imports: [CommonModule, RouterModule],
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
  readonly activeFilter = signal<StatusFilterOption>('ALL');

  // Modal / Detalle de documento seleccionado
  readonly selectedDocument = signal<DocumentItem | null>(null);
  readonly isDetailOpen = signal<boolean>(false);

  // Modal de confirmación de eliminación
  readonly documentToDelete = signal<DocumentItem | null>(null);
  readonly isDeleting = signal<boolean>(false);

  // Acción de descarga en progreso
  readonly downloadingDocId = signal<string | null>(null);

  readonly canDelete = computed(() => {
    const role = this.workspaceService.activeWorkspace()?.role;
    return role === 'OWNER' || role === 'ADMIN' || role === 'EDITOR';
  });

  readonly canUpload = computed(() => {
    const role = this.workspaceService.activeWorkspace()?.role;
    return role === 'OWNER' || role === 'ADMIN' || role === 'EDITOR' || role === 'MEMBER';
  });

  readonly canRetry = computed(() => {
    const role = this.workspaceService.activeWorkspace()?.role;
    return role === 'OWNER' || role === 'ADMIN';
  });

  readonly retryingDocId = signal<string | null>(null);

  readonly filteredDocuments = computed(() => {
    const filter = this.activeFilter();
    const all = this.documents();
    if (filter === 'ALL') {
      return all;
    }
    return all.filter((doc) => doc.status === filter);
  });

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
    const targetWsId = routeId || this.workspaceService.activeWorkspace()?.id || '';

    if (!targetWsId) {
      this.errorMessage.set('No se ha seleccionado ningún espacio de trabajo.');
      this.isLoading.set(false);
      return;
    }

    this.workspaceId.set(targetWsId);
    this.loadDocuments();

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

    this.documentService
      .listDocuments(wsId, 50, 0)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (res) => {
          this.documents.set(res.items);
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

    this.documentService
      .listDocuments(wsId, 50, 0)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (res) => {
          this.documents.set(res.items);
          this.isRefreshing.set(false);
        },
        error: () => {
          this.isRefreshing.set(false);
        },
      });
  }

  setFilter(filter: StatusFilterOption): void {
    this.activeFilter.set(filter);
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
          alert(
            err?.error?.error?.message ||
              'No se pudo generar la URL de descarga del documento.'
          );
        },
      });
  }

  retryDocument(doc: DocumentItem): void {
    if (doc.status !== 'FAILED') return;

    this.retryingDocId.set(doc.id);
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
          alert(
            err?.error?.error?.message ||
              'No se pudo reintentar el procesamiento del documento.'
          );
        },
      });
  }

  confirmDelete(doc: DocumentItem): void {
    this.documentToDelete.set(doc);
  }

  cancelDelete(): void {
    this.documentToDelete.set(null);
  }

  executeDelete(): void {
    const doc = this.documentToDelete();
    if (!doc) return;

    this.isDeleting.set(true);
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
          alert(
            err?.error?.error?.message ||
              'No se pudo eliminar el documento seleccionado.'
          );
        },
      });
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

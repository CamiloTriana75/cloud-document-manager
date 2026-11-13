import { CommonModule } from '@angular/common';
import {
  Component,
  computed,
  inject,
  OnDestroy,
  OnInit,
  signal,
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { interval, Subscription, switchMap, take } from 'rxjs';

import {
  ALLOWED_UPLOAD_EXTENSIONS,
  DocumentStatus,
  MAX_UPLOAD_SIZE_BYTES,
  UploadProgressState,
} from '../../../core/documents/document.models';
import { DocumentService } from '../../../core/documents/document.service';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';

@Component({
  selector: 'app-document-upload',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './upload.html',
  styleUrl: './upload.css',
})
export class DocumentUploadComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly documentService = inject(DocumentService);
  readonly workspaceService = inject(WorkspaceService);

  workspaceId = '';
  workspaceName = '';
  selectedFile: File | null = null;
  isDragging = false;
  validationError: string | null = null;
  readonly uploadState = signal<UploadProgressState>({
    status: 'idle',
    progressPercentage: 0,
    loadedBytes: 0,
    totalBytes: 0,
  });

  readonly currentDocumentStatus = signal<DocumentStatus | null>(null);
  readonly isPollingStatus = signal<boolean>(false);

  private uploadSub?: Subscription;
  private pollSub?: Subscription;

  readonly allowedExtensions = ALLOWED_UPLOAD_EXTENSIONS;
  readonly maxSizeBytes = MAX_UPLOAD_SIZE_BYTES;

  /**
   * Comprueba si el usuario tiene permisos de edición (ADR-0001: VIEWER es solo lectura).
   */
  readonly canUpload = computed(() => {
    const role = this.workspaceService.activeWorkspace()?.role;
    return role !== 'VIEWER';
  });

  ngOnInit(): void {
    this.workspaceId = this.route.snapshot.paramMap.get('id') || '';
    if (!this.workspaceId) {
      this.router.navigate(['/']);
      return;
    }

    const activeWs = this.workspaceService.activeWorkspace();
    if (activeWs && activeWs.id === this.workspaceId) {
      this.workspaceName = activeWs.name;
    }
  }

  ngOnDestroy(): void {
    this.cancelUpload();
    this.stopStatusPolling();
  }

  onDragOver(event: DragEvent): void {
    if (!this.canUpload()) return;
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = true;
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
  }

  onDrop(event: DragEvent): void {
    if (!this.canUpload()) return;
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;

    if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
      this.handleFileSelected(event.dataTransfer.files[0]);
    }
  }

  onFileInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFileSelected(input.files[0]);
    }
  }

  triggerFileInput(fileInput: HTMLInputElement): void {
    if (this.canUpload()) {
      fileInput.click();
    }
  }

  handleFileSelected(file: File): void {
    this.validationError = null;
    this.selectedFile = null;

    if (!this.canUpload()) {
      this.validationError =
        'No tienes permisos para subir archivos en este espacio (rol VIEWER).';
      return;
    }

    // Validación de extensión
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!this.allowedExtensions.includes(ext)) {
      this.validationError = `El formato "${ext}" no está permitido. Formatos admitidos: ${this.allowedExtensions.join(', ')}.`;
      return;
    }

    // Validación de tamaño
    if (file.size <= 0) {
      this.validationError = 'El archivo seleccionado está vacío (0 bytes).';
      return;
    }

    if (file.size > this.maxSizeBytes) {
      const maxMb = Math.round(this.maxSizeBytes / (1024 * 1024));
      this.validationError = `El archivo supera el tamaño máximo permitido de ${maxMb} MB.`;
      return;
    }

    this.selectedFile = file;
    this.uploadState.set({
      status: 'idle',
      progressPercentage: 0,
      loadedBytes: 0,
      totalBytes: file.size,
    });
  }

  startUpload(): void {
    if (!this.selectedFile || !this.workspaceId || !this.canUpload()) {
      return;
    }

    this.stopStatusPolling();
    this.currentDocumentStatus.set(null);

    this.uploadSub = this.documentService
      .uploadWithProgress(this.workspaceId, this.selectedFile)
      .subscribe({
        next: (state) => {
          this.uploadState.set(state);
          if (state.status === 'completed' && state.document) {
            this.currentDocumentStatus.set(state.document.status);
            this.startStatusPolling(state.document.id);
          }
        },
      });
  }

  cancelUpload(): void {
    if (this.uploadSub && !this.uploadSub.closed) {
      this.uploadSub.unsubscribe();
      this.uploadState.set({
        status: 'cancelled',
        progressPercentage: 0,
        loadedBytes: 0,
        totalBytes: this.selectedFile?.size || 0,
        error: 'Carga cancelada por el usuario.',
      });
    }
    this.stopStatusPolling();
  }

  resetForm(): void {
    this.cancelUpload();
    this.stopStatusPolling();
    this.selectedFile = null;
    this.validationError = null;
    this.currentDocumentStatus.set(null);
    this.uploadState.set({
      status: 'idle',
      progressPercentage: 0,
      loadedBytes: 0,
      totalBytes: 0,
    });
  }

  startStatusPolling(documentId: string): void {
    this.stopStatusPolling();
    this.isPollingStatus.set(true);

    this.pollSub = interval(2500)
      .pipe(
        take(8),
        switchMap(() =>
          this.documentService.getDocument(this.workspaceId, documentId)
        )
      )
      .subscribe({
        next: (doc) => {
          this.currentDocumentStatus.set(doc.status);
          if (doc.status === 'READY' || doc.status === 'FAILED') {
            this.stopStatusPolling();
          }
        },
        error: () => {
          this.stopStatusPolling();
        },
        complete: () => {
          this.isPollingStatus.set(false);
        },
      });
  }

  stopStatusPolling(): void {
    if (this.pollSub && !this.pollSub.closed) {
      this.pollSub.unsubscribe();
    }
    this.isPollingStatus.set(false);
  }

  formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
}

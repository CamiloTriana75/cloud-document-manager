import { CommonModule } from '@angular/common';
import { Component, inject, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import {
  ALLOWED_UPLOAD_EXTENSIONS,
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
  private readonly workspaceService = inject(WorkspaceService);

  workspaceId = '';
  workspaceName = '';
  selectedFile: File | null = null;
  isDragging = false;
  validationError: string | null = null;
  uploadState: UploadProgressState = {
    status: 'idle',
    progressPercentage: 0,
    loadedBytes: 0,
    totalBytes: 0,
  };

  private uploadSub?: Subscription;

  readonly allowedExtensions = ALLOWED_UPLOAD_EXTENSIONS;
  readonly maxSizeBytes = MAX_UPLOAD_SIZE_BYTES;

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
  }

  onDragOver(event: DragEvent): void {
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

  handleFileSelected(file: File): void {
    this.validationError = null;
    this.selectedFile = null;

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
    this.uploadState = {
      status: 'idle',
      progressPercentage: 0,
      loadedBytes: 0,
      totalBytes: file.size,
    };
  }

  startUpload(): void {
    if (!this.selectedFile || !this.workspaceId) {
      return;
    }

    this.uploadSub = this.documentService
      .uploadWithProgress(this.workspaceId, this.selectedFile)
      .subscribe({
        next: (state) => {
          this.uploadState = state;
        },
      });
  }

  cancelUpload(): void {
    if (this.uploadSub && !this.uploadSub.closed) {
      this.uploadSub.unsubscribe();
      this.uploadState = {
        status: 'cancelled',
        progressPercentage: 0,
        loadedBytes: 0,
        totalBytes: this.selectedFile?.size || 0,
        error: 'Carga cancelada por el usuario.',
      };
    }
  }

  resetForm(): void {
    this.cancelUpload();
    this.selectedFile = null;
    this.validationError = null;
    this.uploadState = {
      status: 'idle',
      progressPercentage: 0,
      loadedBytes: 0,
      totalBytes: 0,
    };
  }

  formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
}

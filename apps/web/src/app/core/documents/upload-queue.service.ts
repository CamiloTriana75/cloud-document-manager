import { computed, inject, Injectable, Signal, signal } from '@angular/core';
import { interval, Subscription, switchMap, take, takeWhile } from 'rxjs';

import { DocumentStatus, UploadPhase } from './document.models';
import { DocumentService } from './document.service';
import { validateUploadFile } from './upload-policy';

/** Fase de un archivo en la cola: espera, rechazo previo o una fase del flujo de carga. */
export type QueuePhase = 'queued' | 'rejected' | Exclude<UploadPhase, 'idle'>;

export interface UploadQueueItem {
  readonly id: string;
  readonly workspaceId: string;
  readonly file: File;
  readonly phase: QueuePhase;
  /** 0–100, como lo reporta DocumentService.uploadWithProgress. */
  readonly progress: number;
  readonly loadedBytes: number;
  readonly error: string | null;
  readonly documentId: string | null;
  /** Estado del documento en el pipeline asíncrono tras confirmar la carga. */
  readonly documentStatus: DocumentStatus | null;
}

export const MAX_CONCURRENT_UPLOADS = 2;
const STATUS_POLL_INTERVAL_MS = 2500;
const STATUS_POLL_ATTEMPTS = 8;

const ACTIVE_PHASES: ReadonlySet<QueuePhase> = new Set(['requesting', 'uploading', 'completing']);
const FINISHED_PHASES: ReadonlySet<QueuePhase> = new Set([
  'completed',
  'error',
  'cancelled',
  'rejected',
]);

function isFinalStatus(status: DocumentStatus): boolean {
  return status === 'READY' || status === 'FAILED' || status === 'DELETED';
}

/**
 * Cola de carga global (sobrevive a la navegación): valida cada archivo, sube como máximo
 * MAX_CONCURRENT_UPLOADS a la vez con el flujo de URL prefirmada y sigue el estado del
 * documento hasta que el procesamiento asíncrono termina.
 */
@Injectable({ providedIn: 'root' })
export class UploadQueueService {
  private readonly documents = inject(DocumentService);

  private readonly state = signal<readonly UploadQueueItem[]>([]);
  readonly items = this.state.asReadonly();
  readonly activeCount = computed(
    () => this.items().filter((item) => ACTIVE_PHASES.has(item.phase)).length,
  );

  private readonly uploads = new Map<string, Subscription>();
  private readonly statusWatches = new Map<string, Subscription>();
  private sequence = 0;

  /** Vista de la cola de un workspace; crearla una vez por consumidor. */
  itemsFor(workspaceId: string): Signal<readonly UploadQueueItem[]> {
    return computed(() => this.items().filter((item) => item.workspaceId === workspaceId));
  }

  enqueue(workspaceId: string, files: readonly File[]): void {
    const added = files.map((file): UploadQueueItem => {
      const error = validateUploadFile(file);
      return {
        id: `upload-${++this.sequence}`,
        workspaceId,
        file,
        phase: error ? 'rejected' : 'queued',
        progress: 0,
        loadedBytes: 0,
        error,
        documentId: null,
        documentStatus: null,
      };
    });
    this.state.update((items) => [...items, ...added]);
    this.pump();
  }

  cancel(id: string): void {
    const item = this.find(id);
    if (!item || (item.phase !== 'queued' && !ACTIVE_PHASES.has(item.phase))) {
      return;
    }
    this.stopUpload(id);
    this.patch(id, { phase: 'cancelled', progress: 0, loadedBytes: 0, error: 'Carga cancelada.' });
    this.pump();
  }

  retry(id: string): void {
    const item = this.find(id);
    if (!item || (item.phase !== 'error' && item.phase !== 'cancelled')) {
      return;
    }
    this.patch(id, { phase: 'queued', progress: 0, loadedBytes: 0, error: null });
    this.pump();
  }

  remove(id: string): void {
    this.stopUpload(id);
    this.stopWatch(id);
    this.state.update((items) => items.filter((item) => item.id !== id));
    this.pump();
  }

  /** Retira de la vista los archivos terminados (subidos, rechazados, fallidos o cancelados). */
  clearFinished(workspaceId: string): void {
    for (const item of this.items()) {
      if (item.workspaceId === workspaceId && FINISHED_PHASES.has(item.phase)) {
        this.stopWatch(item.id);
      }
    }
    this.state.update((items) =>
      items.filter((item) => item.workspaceId !== workspaceId || !FINISHED_PHASES.has(item.phase)),
    );
  }

  private pump(): void {
    while (this.activeCount() < MAX_CONCURRENT_UPLOADS) {
      const next = this.items().find((item) => item.phase === 'queued');
      if (!next) {
        return;
      }
      this.start(next);
    }
  }

  private start(item: UploadQueueItem): void {
    this.patch(item.id, { phase: 'requesting', progress: 5, error: null });
    const subscription = this.documents.uploadWithProgress(item.workspaceId, item.file).subscribe({
      next: (progress) => {
        this.patch(item.id, {
          phase: progress.status === 'idle' ? 'requesting' : progress.status,
          progress: progress.progressPercentage,
          loadedBytes: progress.loadedBytes,
          error: progress.error ?? null,
        });
        if (progress.status === 'completed' && progress.document) {
          this.patch(item.id, {
            documentId: progress.document.id,
            documentStatus: progress.document.status,
          });
          this.watchStatus(item.id, item.workspaceId, progress.document.id, progress.document.status);
        }
      },
      complete: () => {
        this.uploads.delete(item.id);
        this.pump();
      },
    });
    if (!subscription.closed) {
      this.uploads.set(item.id, subscription);
    }
  }

  private watchStatus(id: string, workspaceId: string, documentId: string, current: DocumentStatus): void {
    this.stopWatch(id);
    if (isFinalStatus(current)) {
      return;
    }
    const subscription = interval(STATUS_POLL_INTERVAL_MS)
      .pipe(
        take(STATUS_POLL_ATTEMPTS),
        switchMap(() => this.documents.getDocument(workspaceId, documentId)),
        takeWhile((document) => !isFinalStatus(document.status), true),
      )
      .subscribe({
        next: (document) => this.patch(id, { documentStatus: document.status }),
        error: () => this.statusWatches.delete(id),
        complete: () => this.statusWatches.delete(id),
      });
    if (!subscription.closed) {
      this.statusWatches.set(id, subscription);
    }
  }

  private stopUpload(id: string): void {
    this.uploads.get(id)?.unsubscribe();
    this.uploads.delete(id);
  }

  private stopWatch(id: string): void {
    this.statusWatches.get(id)?.unsubscribe();
    this.statusWatches.delete(id);
  }

  private find(id: string): UploadQueueItem | undefined {
    return this.items().find((item) => item.id === id);
  }

  private patch(id: string, changes: Partial<UploadQueueItem>): void {
    this.state.update((items) =>
      items.map((item) => (item.id === id ? { ...item, ...changes } : item)),
    );
  }
}

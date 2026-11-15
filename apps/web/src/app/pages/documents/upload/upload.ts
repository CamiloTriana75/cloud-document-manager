import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { DOCUMENT_STATUS_META } from '../../../core/documents/document-status';
import { ALLOWED_UPLOAD_EXTENSIONS } from '../../../core/documents/document.models';
import { FILE_KIND_ICON, fileKind } from '../../../core/documents/file-kind';
import { validateUploadFile } from '../../../core/documents/upload-policy';
import { UploadQueueItem, UploadQueueService } from '../../../core/documents/upload-queue.service';
import { hasRoleAtLeast } from '../../../core/workspaces/workspace-roles';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';
import { BytesPipe } from '../../../shared/format/bytes.pipe';
import { AlertComponent } from '../../../shared/ui/alert/alert';
import { CoilSceneComponent } from '../../../shared/ui/coil-scene/coil-scene';
import { IconComponent } from '../../../shared/ui/icon/icon';
import { IconName } from '../../../shared/ui/icon/icons';

interface Rejection {
  readonly name: string;
  readonly reason: string;
}

const ACTIVE = new Set(['queued', 'requesting', 'uploading', 'completing']);
const FINISHED = new Set(['completed', 'error', 'cancelled', 'rejected']);

/** Carga multi-archivo directa a S3 (`/workspaces/:id/upload`) sobre la cola global. */
@Component({
  selector: 'app-document-upload',
  imports: [RouterLink, AlertComponent, BytesPipe, CoilSceneComponent, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './upload.html',
  styleUrl: './upload.css',
})
export class DocumentUploadComponent {
  private readonly route = inject(ActivatedRoute);
  protected readonly workspaceService = inject(WorkspaceService);
  private readonly queue = inject(UploadQueueService);

  protected readonly accept = ALLOWED_UPLOAD_EXTENSIONS.join(',');

  protected readonly workspaceId = signal('');
  protected readonly workspace = computed(() => {
    const id = this.workspaceId();
    const active = this.workspaceService.activeWorkspace();
    return active?.id === id
      ? active
      : (this.workspaceService.workspaces().find((ws) => ws.id === id) ?? null);
  });
  protected readonly canUpload = computed(() =>
    hasRoleAtLeast(this.workspace()?.role, 'MEMBER'),
  );

  protected readonly staged = signal<File[]>([]);
  protected readonly rejected = signal<Rejection[]>([]);
  protected readonly dragging = signal(false);

  protected readonly items = computed(() =>
    this.queue.items().filter((item) => item.workspaceId === this.workspaceId()),
  );
  protected readonly hasActive = computed(() => this.items().some((i) => ACTIVE.has(i.phase)));
  protected readonly hasFinished = computed(() => this.items().some((i) => FINISHED.has(i.phase)));
  protected readonly completed = computed(() =>
    this.items().filter((item) => item.phase === 'completed'),
  );
  protected readonly lastCompleted = computed(() => this.completed().at(-1) ?? null);
  protected readonly stagedBytes = computed(() =>
    this.staged().reduce((sum, file) => sum + file.size, 0),
  );

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      this.workspaceId.set(params.get('id') ?? '');
      this.staged.set([]);
      this.rejected.set([]);
    });
  }

  protected onInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.addFiles(Array.from(input.files ?? []));
    input.value = '';
  }

  protected onDragOver(event: DragEvent): void {
    if (!this.canUpload()) {
      return;
    }
    event.preventDefault();
    this.dragging.set(true);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    if (this.canUpload()) {
      this.addFiles(Array.from(event.dataTransfer?.files ?? []));
    }
  }

  protected removeStaged(index: number): void {
    this.staged.update((files) => files.filter((_, i) => i !== index));
  }

  protected startUpload(): void {
    const files = this.staged();
    if (files.length === 0 || !this.canUpload()) {
      return;
    }
    this.queue.enqueue(this.workspaceId(), files);
    this.staged.set([]);
    this.rejected.set([]);
  }

  protected cancel(item: UploadQueueItem): void {
    this.queue.cancel(item.id);
  }

  protected retry(item: UploadQueueItem): void {
    this.queue.retry(item.id);
  }

  protected remove(item: UploadQueueItem): void {
    this.queue.remove(item.id);
  }

  protected clearFinished(): void {
    this.queue.clearFinished(this.workspaceId());
  }

  protected icon(file: File): IconName {
    return FILE_KIND_ICON[fileKind(file.type)];
  }

  protected isActive(item: UploadQueueItem): boolean {
    return ACTIVE.has(item.phase);
  }

  protected phaseLabel(item: UploadQueueItem): string {
    switch (item.phase) {
      case 'queued':
        return 'En cola';
      case 'requesting':
        return 'Preparando URL prefirmada…';
      case 'uploading':
        return `Subiendo a S3 · ${item.progress}%`;
      case 'completing':
        return 'Verificando el archivo en S3…';
      case 'completed':
        return item.documentStatus
          ? `Subido · ${DOCUMENT_STATUS_META[item.documentStatus].label}`
          : 'Subido';
      case 'cancelled':
        return 'Carga cancelada';
      default:
        return item.error ?? 'No se pudo subir el archivo.';
    }
  }

  private addFiles(files: File[]): void {
    if (!this.canUpload() || files.length === 0) {
      return;
    }
    const accepted: File[] = [];
    const rejected: Rejection[] = [];
    for (const file of files) {
      const reason = validateUploadFile(file);
      if (reason) {
        rejected.push({ name: file.name, reason });
      } else {
        accepted.push(file);
      }
    }
    this.staged.update((current) => [...current, ...accepted]);
    this.rejected.set(rejected);
  }
}

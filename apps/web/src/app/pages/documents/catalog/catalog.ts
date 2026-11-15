import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { interval } from 'rxjs';

import { PageVisibilityService } from '../../../core/browser/page-visibility.service';
import { CountedStatus } from '../../../core/documents/document-stats.service';
import {
  DOCUMENT_TYPE_OPTIONS,
  STATUS_FOLDERS,
  StatusFilter,
} from '../../../core/documents/document-status';
import { DocumentItem } from '../../../core/documents/document.models';
import { DocumentService } from '../../../core/documents/document.service';
import { UploadQueueService } from '../../../core/documents/upload-queue.service';
import { hasRoleAtLeast } from '../../../core/workspaces/workspace-roles';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';
import { shortId } from '../../../shared/format/format-id';
import { AlertComponent } from '../../../shared/ui/alert/alert';
import { CoilSceneComponent } from '../../../shared/ui/coil-scene/coil-scene';
import { DialogComponent } from '../../../shared/ui/dialog/dialog';
import { EmptyStateComponent } from '../../../shared/ui/empty-state/empty-state';
import { FolderTab, FolderTabsComponent } from '../../../shared/ui/folder-tabs/folder-tabs';
import { IconComponent } from '../../../shared/ui/icon/icon';
import { KpiCardComponent } from '../../../shared/ui/kpi-card/kpi-card';
import { RoleLadderComponent } from '../../../shared/ui/role-ladder/role-ladder';
import { BarSegment, SegmentedBarComponent } from '../../../shared/ui/segmented-bar/segmented-bar';
import { SparklineComponent } from '../../../shared/ui/sparkline/sparkline';
import { CatalogStore, PAGE_SIZE_OPTIONS } from './catalog.store';
import { ActivityPanelComponent } from './components/activity-panel/activity-panel';
import { DocumentDetailComponent } from './components/document-detail/document-detail';
import { DocumentTableComponent } from './components/document-table/document-table';

const POLL_INTERVAL_MS = 5000;

function percent(part: number, total: number): number {
  return total > 0 ? Math.round((part / total) * 100) : 0;
}

function apiMessage(error: unknown, fallback: string): string {
  const message = (error as { error?: { error?: { message?: string } } } | null)?.error?.error
    ?.message;
  return message || fallback;
}

/** Dashboard de documentos del workspace (`/workspaces/:id/documents`). */
@Component({
  selector: 'app-document-catalog',
  imports: [
    RouterLink,
    ActivityPanelComponent,
    AlertComponent,
    CoilSceneComponent,
    DialogComponent,
    DocumentDetailComponent,
    DocumentTableComponent,
    EmptyStateComponent,
    FolderTabsComponent,
    IconComponent,
    KpiCardComponent,
    RoleLadderComponent,
    SegmentedBarComponent,
    SparklineComponent,
  ],
  providers: [CatalogStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './catalog.html',
  styleUrl: './catalog.css',
})
export class DocumentCatalogComponent {
  protected readonly store = inject(CatalogStore);
  protected readonly workspaceService = inject(WorkspaceService);
  private readonly route = inject(ActivatedRoute);
  private readonly documentsApi = inject(DocumentService);
  private readonly uploadQueue = inject(UploadQueueService);
  private readonly visibility = inject(PageVisibilityService);

  protected readonly typeOptions = DOCUMENT_TYPE_OPTIONS;
  protected readonly pageSizes = PAGE_SIZE_OPTIONS;
  protected readonly shortId = shortId;

  protected readonly workspaceId = signal('');
  protected readonly workspace = computed(() => {
    const id = this.workspaceId();
    const active = this.workspaceService.activeWorkspace();
    return active?.id === id
      ? active
      : (this.workspaceService.workspaces().find((ws) => ws.id === id) ?? null);
  });
  protected readonly role = computed(() => this.workspace()?.role ?? null);
  protected readonly canUpload = computed(() => hasRoleAtLeast(this.role(), 'MEMBER'));
  protected readonly canDelete = computed(() => hasRoleAtLeast(this.role(), 'EDITOR'));
  protected readonly canRetry = computed(() => hasRoleAtLeast(this.role(), 'ADMIN'));

  protected readonly uploads = computed(() =>
    this.uploadQueue
      .items()
      .filter(
        (item) =>
          item.workspaceId === this.workspaceId() &&
          (item.phase === 'queued' ||
            item.phase === 'requesting' ||
            item.phase === 'uploading' ||
            item.phase === 'completing'),
      ),
  );

  protected readonly folders = computed<FolderTab[]>(() => {
    const stats = this.store.stats();
    return STATUS_FOLDERS.map((folder) => ({
      id: folder.id,
      label: folder.label,
      count: stats
        ? folder.id === 'ALL'
          ? stats.total
          : (stats.byStatus[folder.id as CountedStatus] ?? 0)
        : null,
    }));
  });

  protected readonly readyPercent = computed(() => {
    const stats = this.store.stats();
    return stats ? percent(stats.byStatus.READY, stats.total) : 0;
  });

  protected readonly pipeline = computed(() => {
    const stats = this.store.stats();
    const counts = stats?.byStatus;
    const total = stats?.total ?? 0;
    const inProgress = counts ? counts.UPLOADED + counts.PROCESSING : 0;
    const segments: BarSegment[] = [
      { value: counts?.READY ?? 0, tone: 'positive', label: 'Listos' },
      { value: inProgress, tone: 'accent', label: 'En curso' },
      { value: counts?.PENDING_UPLOAD ?? 0, tone: 'neutral', label: 'Pendientes' },
      { value: counts?.FAILED ?? 0, tone: 'danger', label: 'Fallidos' },
    ];
    return {
      segments,
      ready: percent(counts?.READY ?? 0, total),
      inProgress: percent(inProgress, total),
      failed: percent(counts?.FAILED ?? 0, total),
    };
  });

  protected readonly sparkLabel = computed(() => {
    const series = this.store.stats()?.dailyUploads;
    return series
      ? `Documentos cargados por día en los últimos 7 días: ${series.join(', ')}`
      : '';
  });

  protected readonly selected = signal<DocumentItem | null>(null);
  protected readonly toDelete = signal<DocumentItem | null>(null);
  protected readonly busyId = signal<string | null>(null);
  protected readonly deleting = signal(false);
  protected readonly actionError = signal<string | null>(null);

  private completedUploads = 0;

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const id = params.get('id') ?? this.workspaceService.activeWorkspace()?.id ?? '';
      this.workspaceId.set(id);
      this.closeDetail();
      this.toDelete.set(null);
      if (id) {
        this.store.init(id);
        this.openFromQuery(id);
      } else {
        this.store.loading.set(false);
        this.store.error.set('No se ha seleccionado ningún espacio de trabajo.');
      }
    });

    interval(POLL_INTERVAL_MS)
      .pipe(takeUntilDestroyed())
      .subscribe(() => {
        if (this.visibility.visible() && this.store.inFlight() && !this.store.loading()) {
          this.store.poll();
        }
      });

    // Cuando termina una carga de este workspace, refresca tabla, actividad y métricas.
    effect(() => {
      const completed = this.uploadQueue
        .items()
        .filter((item) => item.workspaceId === this.workspaceId() && item.phase === 'completed')
        .length;
      untracked(() => {
        if (completed > this.completedUploads) {
          this.store.poll();
        }
        this.completedUploads = completed;
      });
    });
  }

  protected onFolder(id: string): void {
    this.store.setStatus(id as StatusFilter);
  }

  protected onSearch(event: Event): void {
    this.store.setSearch((event.target as HTMLInputElement).value);
  }

  protected onType(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.store.setContentType(value === '' ? null : value);
  }

  protected onPageSize(event: Event): void {
    this.store.setPageSize(Number((event.target as HTMLSelectElement).value));
  }

  protected onFilesDropped(files: File[]): void {
    this.uploadQueue.enqueue(this.workspaceId(), files);
  }

  protected openDetail(doc: DocumentItem): void {
    this.selected.set(doc);
  }

  protected closeDetail(): void {
    this.selected.set(null);
  }

  protected download(doc: DocumentItem): void {
    if (doc.status !== 'READY') {
      return;
    }
    this.busyId.set(doc.id);
    this.actionError.set(null);
    this.documentsApi.getDownloadUrl(this.workspaceId(), doc.id).subscribe({
      next: (res) => {
        this.busyId.set(null);
        window.open(res.download_url, '_blank', 'noopener,noreferrer');
      },
      error: (err) => {
        this.busyId.set(null);
        this.actionError.set(
          apiMessage(err, 'No se pudo generar la URL de descarga del documento.'),
        );
      },
    });
  }

  protected retry(doc: DocumentItem): void {
    this.busyId.set(doc.id);
    this.actionError.set(null);
    this.documentsApi.retryDocument(this.workspaceId(), doc.id).subscribe({
      next: (updated) => {
        this.busyId.set(null);
        this.store.upsert(updated);
        if (this.selected()?.id === updated.id) {
          this.selected.set(updated);
        }
      },
      error: (err) => {
        this.busyId.set(null);
        this.actionError.set(
          apiMessage(err, 'No se pudo reintentar el procesamiento del documento.'),
        );
      },
    });
  }

  protected askDelete(doc: DocumentItem): void {
    this.actionError.set(null);
    this.closeDetail();
    this.toDelete.set(doc);
  }

  protected cancelDelete(): void {
    if (!this.deleting()) {
      this.toDelete.set(null);
    }
  }

  protected confirmDelete(): void {
    const doc = this.toDelete();
    if (!doc) {
      return;
    }
    this.deleting.set(true);
    this.documentsApi.deleteDocument(this.workspaceId(), doc.id).subscribe({
      next: () => {
        this.deleting.set(false);
        this.toDelete.set(null);
        this.store.remove(doc.id);
      },
      error: (err) => {
        this.deleting.set(false);
        this.toDelete.set(null);
        this.actionError.set(apiMessage(err, 'No se pudo eliminar el documento seleccionado.'));
      },
    });
  }

  private openFromQuery(workspaceId: string): void {
    const docId = this.route.snapshot.queryParamMap.get('docId');
    if (!docId) {
      return;
    }
    this.documentsApi.getDocument(workspaceId, docId).subscribe({
      next: (doc) => this.openDetail(doc),
      error: () => undefined,
    });
  }
}

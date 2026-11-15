import { computed, DestroyRef, inject, Injectable, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { catchError, debounceTime, distinctUntilChanged, map, of, Subject, switchMap } from 'rxjs';

import { DocumentStats, DocumentStatsService } from '../../../core/documents/document-stats.service';
import { isInFlight, StatusFilter } from '../../../core/documents/document-status';
import { DocumentItem, DocumentListResult } from '../../../core/documents/document.models';
import { DocumentService } from '../../../core/documents/document.service';

export type SortColumn = 'original_filename' | 'content_type' | 'size_bytes' | 'created_at' | 'status';

export interface CatalogSort {
  readonly column: SortColumn;
  readonly direction: 'asc' | 'desc';
}

export const PAGE_SIZE_OPTIONS = [10, 25, 50] as const;

const SEARCH_DEBOUNCE_MS = 300;
const STATS_REFRESH_DEBOUNCE_MS = 400;
const RECENT_LIMIT = 8;

type LoadMode = 'load' | 'refresh' | 'silent';
type LoadResult =
  | { readonly mode: LoadMode; readonly page: DocumentListResult }
  | { readonly mode: LoadMode; readonly error: unknown };

function apiMessage(error: unknown, fallback: string): string {
  const message = (error as { error?: { error?: { message?: string } } } | null)?.error?.error
    ?.message;
  return message || fallback;
}

function compare(a: DocumentItem, b: DocumentItem, column: SortColumn): number {
  switch (column) {
    case 'size_bytes':
      return a.size_bytes - b.size_bytes;
    case 'created_at':
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    default:
      return a[column].localeCompare(b[column], 'es');
  }
}

/**
 * Estado del dashboard de documentos (provisto por la página). Las consultas pasan por
 * `switchMap`: una respuesta de un filtro anterior nunca pisa la del filtro actual.
 */
@Injectable()
export class CatalogStore {
  private readonly documentsApi = inject(DocumentService);
  private readonly statsApi = inject(DocumentStatsService);
  private readonly destroyRef = inject(DestroyRef);

  readonly workspaceId = signal('');
  readonly documents = signal<DocumentItem[]>([]);
  readonly total = signal(0);
  readonly loading = signal(true);
  readonly refreshing = signal(false);
  readonly error = signal<string | null>(null);

  readonly status = signal<StatusFilter>('ALL');
  readonly contentType = signal<string | null>(null);
  /** Texto tal como lo escribe el usuario; la consulta usa la versión con debounce. */
  readonly searchInput = signal('');
  private readonly appliedSearch = signal('');
  readonly page = signal(1);
  readonly pageSize = signal<number>(25);
  readonly sort = signal<CatalogSort>({ column: 'created_at', direction: 'desc' });

  readonly stats = signal<DocumentStats | null>(null);
  readonly statsLoading = signal(true);
  readonly recent = signal<DocumentItem[]>([]);

  readonly totalPages = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize())));
  readonly hasNext = computed(() => this.page() < this.totalPages());
  readonly hasPrev = computed(() => this.page() > 1);
  readonly rangeStart = computed(() =>
    this.total() === 0 ? 0 : (this.page() - 1) * this.pageSize() + 1,
  );
  readonly rangeEnd = computed(() => Math.min(this.page() * this.pageSize(), this.total()));
  readonly hasActiveFilters = computed(
    () => this.status() !== 'ALL' || this.contentType() !== null || this.appliedSearch() !== '',
  );

  /** Orden aplicado a la página actual (la API ordena por fecha de creación descendente). */
  readonly sortedDocuments = computed(() => {
    const { column, direction } = this.sort();
    const factor = direction === 'asc' ? 1 : -1;
    return [...this.documents()].sort((a, b) => compare(a, b, column) * factor);
  });

  /** Hay trabajo del backend en curso: justifica refrescar periódicamente. */
  readonly inFlight = computed(() => {
    const visible = [...this.recent(), ...this.documents()].some((d) => isInFlight(d.status));
    const counts = this.stats()?.byStatus;
    return visible || (counts ? counts.PROCESSING + counts.UPLOADED > 0 : false);
  });

  private readonly pageLoads = new Subject<LoadMode>();
  private readonly recentLoads = new Subject<LoadMode>();
  private readonly statsLoads = new Subject<void>();
  private readonly statsTransitions = new Subject<void>();
  private readonly searches = new Subject<string>();
  private lastSignature = '';

  constructor() {
    this.pageLoads
      .pipe(
        switchMap((mode) =>
          this.documentsApi.listDocuments(this.workspaceId(), this.queryOptions()).pipe(
            map((page): LoadResult => ({ mode, page })),
            catchError((error: unknown) => of<LoadResult>({ mode, error })),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => this.applyPage(result));

    this.recentLoads
      .pipe(
        switchMap((mode) =>
          this.documentsApi.listDocuments(this.workspaceId(), { limit: RECENT_LIMIT }).pipe(
            map((page) => ({ mode, items: page.items })),
            catchError(() => of(null)),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        if (result) {
          this.recent.set(result.items);
          this.trackTransitions(result.mode);
        }
      });

    this.statsLoads
      .pipe(
        switchMap(() =>
          this.statsApi.load(this.workspaceId()).pipe(catchError(() => of(null))),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((stats) => {
        if (stats) {
          this.stats.set(stats);
        }
        this.statsLoading.set(false);
      });

    this.statsTransitions
      .pipe(debounceTime(STATS_REFRESH_DEBOUNCE_MS), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.statsLoads.next());

    this.searches
      .pipe(
        debounceTime(SEARCH_DEBOUNCE_MS),
        distinctUntilChanged(),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((term) => {
        this.appliedSearch.set(term);
        this.page.set(1);
        this.load();
      });
  }

  init(workspaceId: string): void {
    this.workspaceId.set(workspaceId);
    this.lastSignature = '';
    this.load();
    this.recentLoads.next('load');
    this.statsLoading.set(true);
    this.statsLoads.next();
  }

  setStatus(status: StatusFilter): void {
    this.status.set(status);
    this.page.set(1);
    this.load();
  }

  setContentType(contentType: string | null): void {
    this.contentType.set(contentType);
    this.page.set(1);
    this.load();
  }

  setSearch(term: string): void {
    this.searchInput.set(term);
    this.searches.next(term.trim());
  }

  clearSearch(): void {
    this.searchInput.set('');
    this.searches.next('');
    this.appliedSearch.set('');
    this.page.set(1);
    this.load();
  }

  resetFilters(): void {
    this.status.set('ALL');
    this.contentType.set(null);
    this.searchInput.set('');
    this.searches.next('');
    this.appliedSearch.set('');
    this.page.set(1);
    this.load();
  }

  setPage(page: number): void {
    if (page < 1 || page > this.totalPages() || page === this.page()) {
      return;
    }
    this.page.set(page);
    this.load();
  }

  setPageSize(size: number): void {
    this.pageSize.set(size);
    this.page.set(1);
    this.load();
  }

  toggleSort(column: SortColumn): void {
    this.sort.update((current) =>
      current.column === column
        ? { column, direction: current.direction === 'asc' ? 'desc' : 'asc' }
        : { column, direction: 'asc' },
    );
  }

  /** Refresco manual (muestra indicador) o silencioso (polling). */
  refresh(options: { silent?: boolean } = {}): void {
    if (!this.workspaceId()) {
      return;
    }
    if (!options.silent) {
      this.refreshing.set(true);
    }
    this.pageLoads.next(options.silent ? 'silent' : 'refresh');
  }

  /** Ciclo de polling: página + recientes en silencio; las estadísticas siguen a los cambios. */
  poll(): void {
    if (!this.workspaceId()) {
      return;
    }
    this.pageLoads.next('silent');
    this.recentLoads.next('silent');
  }

  /** Sustituye un documento actualizado (p. ej. tras reintentar) en tabla y actividad. */
  upsert(document: DocumentItem): void {
    const replace = (list: DocumentItem[]) =>
      list.map((item) => (item.id === document.id ? document : item));
    this.documents.update(replace);
    this.recent.update(replace);
    this.statsTransitions.next();
  }

  /** Retira un documento eliminado y resincroniza página, actividad y métricas. */
  remove(documentId: string): void {
    this.documents.update((list) => list.filter((item) => item.id !== documentId));
    this.recent.update((list) => list.filter((item) => item.id !== documentId));
    this.total.update((total) => Math.max(0, total - 1));
    this.pageLoads.next('silent');
    this.recentLoads.next('silent');
    this.statsLoads.next();
  }

  /** Recarga tras cambiar consulta, página o tamaño (muestra skeleton). */
  private load(): void {
    if (!this.workspaceId()) {
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.pageLoads.next('load');
  }

  private queryOptions() {
    return {
      limit: this.pageSize(),
      offset: (this.page() - 1) * this.pageSize(),
      status: this.status() === 'ALL' ? undefined : this.status(),
      search: this.appliedSearch() || undefined,
      content_type: this.contentType() ?? undefined,
    };
  }

  private applyPage(result: LoadResult): void {
    this.loading.set(false);
    this.refreshing.set(false);
    if ('error' in result) {
      if (result.mode !== 'silent') {
        this.error.set(
          apiMessage(result.error, 'No se pudieron cargar los documentos del espacio.'),
        );
      }
      return;
    }
    this.error.set(null);
    this.documents.set(result.page.items);
    this.total.set(result.page.total);
    this.trackTransitions(result.mode);
  }

  /** En refrescos silenciosos, un cambio de estado visible dispara la recarga de métricas. */
  private trackTransitions(mode: LoadMode): void {
    const signature = [...this.recent(), ...this.documents()]
      .map((item) => `${item.id}:${item.status}`)
      .sort()
      .join('|');
    if (mode === 'silent' && this.lastSignature && signature !== this.lastSignature) {
      this.statsTransitions.next();
    }
    this.lastSignature = signature;
  }
}

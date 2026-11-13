import { TestBed } from '@angular/core/testing';
import { Observable, of, Subject } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DocumentStats, DocumentStatsService } from '../../../core/documents/document-stats.service';
import {
  DocumentFilterOptions,
  DocumentItem,
  DocumentListResult,
  DocumentStatus,
} from '../../../core/documents/document.models';
import { DocumentService } from '../../../core/documents/document.service';
import { CatalogStore } from './catalog.store';

function doc(id: string, status: DocumentStatus = 'READY'): DocumentItem {
  return {
    id,
    workspace_id: 'ws-1',
    uploaded_by: 'u-1',
    original_filename: `${id}.pdf`,
    content_type: 'application/pdf',
    size_bytes: 100,
    status,
    technical_metadata: {},
    created_at: '2026-11-10T10:00:00Z',
    updated_at: '2026-11-10T10:00:00Z',
  };
}

const STATS: DocumentStats = {
  total: 1,
  byStatus: { READY: 1, PROCESSING: 0, UPLOADED: 0, PENDING_UPLOAD: 0, FAILED: 0 },
  lastWeek: 1,
  dailyUploads: [0, 0, 0, 0, 0, 0, 1],
};

function page(items: DocumentItem[]): DocumentListResult {
  return { items, total: items.length };
}

describe('CatalogStore', () => {
  let listDocuments: ReturnType<typeof vi.fn<(ws: string, opts: DocumentFilterOptions) => Observable<DocumentListResult>>>;
  let loadStats: ReturnType<typeof vi.fn<(ws: string) => Observable<DocumentStats>>>;
  let store: CatalogStore;

  /** Llamadas de la tabla (las de "recientes" usan limit 8). */
  const tableCalls = () => listDocuments.mock.calls.filter(([, opts]) => opts.limit !== 8);

  beforeEach(() => {
    vi.useFakeTimers();
    listDocuments = vi.fn<(ws: string, opts: DocumentFilterOptions) => Observable<DocumentListResult>>(
      () => of(page([doc('a')])),
    );
    loadStats = vi.fn<(ws: string) => Observable<DocumentStats>>(() => of(STATS));
    TestBed.configureTestingModule({
      providers: [
        CatalogStore,
        { provide: DocumentService, useValue: { listDocuments } },
        { provide: DocumentStatsService, useValue: { load: loadStats } },
      ],
    });
    store = TestBed.inject(CatalogStore);
  });

  afterEach(() => vi.useRealTimers());

  it('carga página, recientes y estadísticas al iniciar', () => {
    store.init('ws-1');

    expect(tableCalls()[0][1]).toMatchObject({ limit: 25, offset: 0 });
    expect(listDocuments.mock.calls.some(([, opts]) => opts.limit === 8)).toBe(true);
    expect(loadStats).toHaveBeenCalledWith('ws-1');
    expect(store.documents().map((d) => d.id)).toEqual(['a']);
    expect(store.loading()).toBe(false);
  });

  it('aplica la búsqueda con debounce y solo consulta el último término', () => {
    store.init('ws-1');
    listDocuments.mockClear();

    store.setSearch('re');
    vi.advanceTimersByTime(100);
    store.setSearch('reporte');
    vi.advanceTimersByTime(300);

    expect(tableCalls().length).toBe(1);
    expect(tableCalls()[0][1].search).toBe('reporte');
  });

  it('descarta la respuesta tardía de una consulta reemplazada', () => {
    const first = new Subject<DocumentListResult>();
    const second = new Subject<DocumentListResult>();
    listDocuments.mockImplementation((_ws, opts) =>
      opts.limit === 8 ? of(page([])) : opts.status === 'READY' ? second : first,
    );
    store.init('ws-1');

    store.setStatus('READY');
    second.next(page([doc('nuevo')]));
    first.next(page([doc('viejo')]));

    expect(store.documents().map((d) => d.id)).toEqual(['nuevo']);
  });

  it('vuelve a la página 1 al cambiar un filtro', () => {
    listDocuments.mockImplementation((_ws, opts) =>
      of({ items: [doc('a')], total: opts.limit === 8 ? 1 : 200 }),
    );
    store.init('ws-1');
    store.setPage(3);
    expect(tableCalls().at(-1)?.[1].offset).toBe(50);

    store.setStatus('FAILED');

    expect(store.page()).toBe(1);
    expect(tableCalls().at(-1)?.[1]).toMatchObject({ offset: 0, status: 'FAILED' });
  });

  it('el polling recarga estadísticas solo si algún documento cambió de estado', () => {
    let status: DocumentStatus = 'PROCESSING';
    listDocuments.mockImplementation(() => of(page([doc('a', status)])));
    store.init('ws-1');
    expect(loadStats).toHaveBeenCalledTimes(1);
    expect(store.inFlight()).toBe(true);

    store.poll();
    vi.advanceTimersByTime(500);
    expect(loadStats).toHaveBeenCalledTimes(1);

    status = 'READY';
    store.poll();
    vi.advanceTimersByTime(500);
    expect(loadStats).toHaveBeenCalledTimes(2);
    expect(store.inFlight()).toBe(false);
  });
});

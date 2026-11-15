import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, TestRequest } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { DocumentItem } from './document.models';
import { bucketByDay, DocumentStats, DocumentStatsService } from './document-stats.service';

const WS = 'ws-1';
const NOW = new Date(2026, 10, 13, 15, 0, 0);

function doc(createdAt: Date): DocumentItem {
  return {
    id: crypto.randomUUID(),
    workspace_id: WS,
    uploaded_by: 'u-1',
    original_filename: 'a.pdf',
    content_type: 'application/pdf',
    size_bytes: 10,
    status: 'READY',
    technical_metadata: {},
    created_at: createdAt.toISOString(),
    updated_at: createdAt.toISOString(),
  };
}

function flushList(req: TestRequest, total: number, items: DocumentItem[] = []): void {
  req.flush({ data: items, pagination: { total, limit: Number(req.request.params.get('limit')), offset: 0 } });
}

describe('DocumentStatsService', () => {
  let service: DocumentStatsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(DocumentStatsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  /**
   * Las consultas se sirven de una en una: la cuenta AWS tiene un límite bajo de
   * ejecuciones concurrentes de Lambda y una ráfaga de 6 peticiones provocaba 503 (CDM-133).
   */
  async function load(respond: (status: string | null, req: TestRequest) => void): Promise<DocumentStats> {
    const result = firstValueFrom(service.load(WS, NOW));
    let served = 0;
    for (;;) {
      const pending = http.match((r) => r.url === `/api/v1/workspaces/${WS}/documents`);
      if (pending.length === 0) {
        break;
      }
      expect(pending.length).toBe(1);
      respond(pending[0].request.params.get('status'), pending[0]);
      served++;
    }
    expect(served).toBe(6);
    return result;
  }

  it('cuenta por estado con limit=1 y la ventana de 7 días con created_after', async () => {
    const counts: Record<string, number> = { READY: 7, PROCESSING: 2, UPLOADED: 1, PENDING_UPLOAD: 3, FAILED: 1 };
    const seen: string[] = [];

    const stats = await load((status, req) => {
      if (status) {
        expect(req.request.params.get('limit')).toBe('1');
        seen.push(status);
        flushList(req, counts[status]);
      } else {
        expect(req.request.params.get('limit')).toBe('100');
        expect(req.request.params.get('created_after')).toBe(new Date(2026, 10, 7).toISOString());
        flushList(req, 3, [doc(new Date(2026, 10, 13, 9)), doc(new Date(2026, 10, 13, 10)), doc(new Date(2026, 10, 10, 8))]);
      }
    });

    expect(seen.sort()).toEqual(['FAILED', 'PENDING_UPLOAD', 'PROCESSING', 'READY', 'UPLOADED']);
    expect(stats.total).toBe(14);
    expect(stats.byStatus.READY).toBe(7);
    expect(stats.lastWeek).toBe(3);
    expect(stats.dailyUploads).toEqual([0, 0, 0, 1, 0, 0, 2]);
  });

  it('oculta la serie diaria si la ventana supera las 100 cargas', async () => {
    const stats = await load((status, req) => flushList(req, status ? 0 : 101));

    expect(stats.lastWeek).toBe(101);
    expect(stats.dailyUploads).toBeNull();
  });

  it('devuelve ceros para un workspace vacío', async () => {
    const stats = await load((_status, req) => flushList(req, 0));

    expect(stats.total).toBe(0);
    expect(stats.lastWeek).toBe(0);
    expect(stats.dailyUploads).toEqual([0, 0, 0, 0, 0, 0, 0]);
  });
});

describe('bucketByDay', () => {
  it('agrupa por día local del más antiguo a hoy e ignora lo que queda fuera', () => {
    const dates = [
      new Date(2026, 10, 13, 1),
      new Date(2026, 10, 12, 23),
      new Date(2026, 10, 7, 0, 5),
      new Date(2026, 10, 6, 23, 59),
      new Date(2026, 10, 14, 9),
    ].map((d) => d.toISOString());

    expect(bucketByDay(dates, NOW, 7)).toEqual([1, 0, 0, 0, 0, 1, 1]);
  });
});

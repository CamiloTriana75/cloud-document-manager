import { inject, Injectable } from '@angular/core';
import { concatMap, from, map, Observable, toArray } from 'rxjs';

import { DocumentService } from './document.service';

/** Estados que lista la API (los borrados lógicos nunca se devuelven). */
export type CountedStatus = 'READY' | 'PROCESSING' | 'UPLOADED' | 'PENDING_UPLOAD' | 'FAILED';

export const COUNTED_STATUSES: readonly CountedStatus[] = [
  'READY',
  'PROCESSING',
  'UPLOADED',
  'PENDING_UPLOAD',
  'FAILED',
];

export interface DocumentStats {
  readonly total: number;
  readonly byStatus: Readonly<Record<CountedStatus, number>>;
  /** Documentos creados en los últimos `STATS_WINDOW_DAYS` días (incluido hoy). */
  readonly lastWeek: number;
  /** Cargas por día, del más antiguo a hoy; `null` si la ventana supera la página máxima. */
  readonly dailyUploads: readonly number[] | null;
}

export const STATS_WINDOW_DAYS = 7;
/** Página máxima de la API (pagination.py `_MAX_LIMIT`). */
const WINDOW_LIMIT = 100;
const DAY_MS = 86_400_000;

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/** Cuenta fechas por día local en una ventana de `days` días que termina hoy. */
export function bucketByDay(createdAt: readonly string[], now: Date, days = STATS_WINDOW_DAYS): number[] {
  const buckets = new Array<number>(days).fill(0);
  const today = startOfDay(now).getTime();
  for (const iso of createdAt) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) {
      continue;
    }
    const daysAgo = Math.round((today - startOfDay(date).getTime()) / DAY_MS);
    if (daysAgo >= 0 && daysAgo < days) {
      buckets[days - 1 - daysAgo]++;
    }
  }
  return buckets;
}

/**
 * Métricas del workspace calculadas solo con `GET /documents` (no hay endpoint de
 * estadísticas): un conteo `limit=1` por estado y una ventana de 7 días.
 */
@Injectable({ providedIn: 'root' })
export class DocumentStatsService {
  private readonly documents = inject(DocumentService);

  load(workspaceId: string, now: Date = new Date()): Observable<DocumentStats> {
    const windowStart = startOfDay(now);
    windowStart.setDate(windowStart.getDate() - (STATS_WINDOW_DAYS - 1));

    // Consultas en serie, no en paralelo: la cuenta AWS limita las ejecuciones
    // concurrentes de Lambda y una ráfaga de 6 peticiones provocaba 503 (CDM-133).
    const counts = COUNTED_STATUSES.map((status) =>
      this.documents.listDocuments(workspaceId, { limit: 1, status }).pipe(map((r) => r.total)),
    );
    const recentWindow = this.documents.listDocuments(workspaceId, {
      limit: WINDOW_LIMIT,
      created_after: windowStart.toISOString(),
    });

    return from(counts).pipe(
      concatMap((count) => count),
      toArray(),
      concatMap((totals) => recentWindow.pipe(map((window) => ({ totals, window })))),
      map(({ totals, window }) => {
        const byStatus = Object.fromEntries(
          COUNTED_STATUSES.map((status, index) => [status, totals[index]]),
        ) as Record<CountedStatus, number>;
        return {
          total: totals.reduce((sum, value) => sum + value, 0),
          byStatus,
          lastWeek: window.total,
          dailyUploads:
            window.total > WINDOW_LIMIT
              ? null
              : bucketByDay(
                  window.items.map((item) => item.created_at),
                  now,
                ),
        };
      }),
    );
  }
}

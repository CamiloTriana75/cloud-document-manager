const LOCALE = 'es-CO';

const RELATIVE_FORMAT = new Intl.RelativeTimeFormat('es', { numeric: 'auto' });

const RELATIVE_STEPS: readonly [limitSeconds: number, unit: Intl.RelativeTimeFormatUnit, seconds: number][] = [
  [60, 'second', 1],
  [3600, 'minute', 60],
  [86_400, 'hour', 3600],
  [604_800, 'day', 86_400],
  [2_629_800, 'week', 604_800],
  [31_557_600, 'month', 2_629_800],
  [Number.POSITIVE_INFINITY, 'year', 31_557_600],
];

function parse(iso: string): Date | null {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Fecha y hora media en español ("10 nov 2026, 10:00 a. m."); conserva el texto si no es fecha. */
export function formatDateTime(iso: string, timeZone?: string): string {
  const date = parse(iso);
  if (!date) {
    return iso;
  }
  return new Intl.DateTimeFormat(LOCALE, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone,
  }).format(date);
}

/** Fecha corta en español ("10 nov 2026"). */
export function formatDate(iso: string, timeZone?: string): string {
  const date = parse(iso);
  if (!date) {
    return iso;
  }
  return new Intl.DateTimeFormat(LOCALE, { day: 'numeric', month: 'short', year: 'numeric', timeZone }).format(
    date,
  );
}

/** Tiempo relativo ("ahora", "hace 5 minutos", "ayer"). */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const date = parse(iso);
  if (!date) {
    return iso;
  }
  const diffSeconds = (date.getTime() - now.getTime()) / 1000;
  const absolute = Math.abs(diffSeconds);
  if (absolute < 60) {
    return RELATIVE_FORMAT.format(0, 'second');
  }
  for (const [limit, unit, seconds] of RELATIVE_STEPS) {
    if (absolute < limit) {
      return RELATIVE_FORMAT.format(Math.round(diffSeconds / seconds), unit);
    }
  }
  return iso;
}

const UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const;
const NUMBER_FORMAT = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 1 });

/** Tamaño legible en unidades binarias (1 KB = 1024 B) con formato numérico es-CO. */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 B';
  }
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), UNITS.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${NUMBER_FORMAT.format(exponent === 0 ? Math.round(value) : value)} ${UNITS[exponent]}`;
}

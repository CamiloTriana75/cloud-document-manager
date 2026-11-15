import { describe, expect, it } from 'vitest';

import { BytesPipe } from './bytes.pipe';
import { formatBytes } from './format-bytes';
import { formatDateTime, formatRelativeTime } from './format-date';
import { shortId } from './format-id';
import { RelativeTimePipe } from './relative-time.pipe';

describe('formatBytes', () => {
  it('formatea cero y bytes sueltos', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(512)).toBe('512 B');
  });

  it('usa unidades binarias con un decimal y coma decimal', () => {
    expect(formatBytes(1536)).toBe('1,5 KB');
    expect(formatBytes(52428800)).toBe('50 MB');
    expect(formatBytes(1073741824)).toBe('1 GB');
  });

  it('trata valores negativos o inválidos como cero', () => {
    expect(formatBytes(-10)).toBe('0 B');
    expect(formatBytes(Number.NaN)).toBe('0 B');
  });
});

describe('formatDateTime', () => {
  it('formatea fecha y hora en español', () => {
    const text = formatDateTime('2026-11-10T10:00:00Z', 'UTC');
    expect(text).toContain('2026');
    expect(text).toContain('nov');
    expect(text).toContain('10:00');
  });

  it('devuelve el texto original si la fecha es inválida', () => {
    expect(formatDateTime('no-es-fecha')).toBe('no-es-fecha');
  });
});

describe('formatRelativeTime', () => {
  const now = new Date('2026-11-13T12:00:00Z');

  it('dice "ahora" para menos de un minuto', () => {
    expect(formatRelativeTime('2026-11-13T11:59:40Z', now)).toBe('ahora');
  });

  it('usa minutos, horas y días', () => {
    expect(formatRelativeTime('2026-11-13T11:55:00Z', now)).toBe('hace 5 minutos');
    expect(formatRelativeTime('2026-11-13T09:00:00Z', now)).toBe('hace 3 horas');
    expect(formatRelativeTime('2026-11-12T12:00:00Z', now)).toBe('ayer');
  });
});

describe('shortId', () => {
  it('devuelve los primeros 8 caracteres del UUID', () => {
    expect(shortId('11111111-1111-4000-a000-000000000001')).toBe('11111111');
  });
});

describe('pipes de formato', () => {
  it('bytes delega en formatBytes', () => {
    expect(new BytesPipe().transform(1536)).toBe('1,5 KB');
  });

  it('relativeTime tolera valores vacíos', () => {
    expect(new RelativeTimePipe().transform(null)).toBe('');
  });
});

import { describe, expect, it } from 'vitest';

import {
  DOCUMENT_STATUS_META,
  DOCUMENT_TYPE_OPTIONS,
  isInFlight,
  STATUS_FOLDERS,
} from './document-status';
import { FILE_KIND_ICON, fileKind } from './file-kind';
import { validateUploadFile } from './upload-policy';

describe('metadatos de estado de documento', () => {
  it('define etiqueta, tono y paso de cada estado', () => {
    expect(DOCUMENT_STATUS_META.READY).toEqual({
      label: 'Listo',
      tone: 'positive',
      step: 3,
      inFlight: false,
    });
    expect(DOCUMENT_STATUS_META.PROCESSING.label).toBe('Procesando');
    expect(DOCUMENT_STATUS_META.FAILED.tone).toBe('danger');
    expect(DOCUMENT_STATUS_META.PENDING_UPLOAD.step).toBe(0);
  });

  it('considera en curso solo UPLOADED y PROCESSING', () => {
    expect(isInFlight('UPLOADED')).toBe(true);
    expect(isInFlight('PROCESSING')).toBe(true);
    expect(isInFlight('READY')).toBe(false);
    expect(isInFlight('PENDING_UPLOAD')).toBe(false);
    expect(isInFlight('FAILED')).toBe(false);
  });

  it('expone las cinco carpetas de estado en orden', () => {
    expect(STATUS_FOLDERS.map((f) => f.id)).toEqual([
      'ALL',
      'READY',
      'PROCESSING',
      'PENDING_UPLOAD',
      'FAILED',
    ]);
    expect(STATUS_FOLDERS.map((f) => f.label)).toEqual([
      'Todos',
      'Listos',
      'Procesando',
      'Pendientes',
      'Fallidos',
    ]);
  });

  it('ofrece solo tipos MIME exactos (sin prefijos) para el filtro', () => {
    expect(DOCUMENT_TYPE_OPTIONS[0]).toEqual({ label: 'Todos los tipos', value: null });
    const values = DOCUMENT_TYPE_OPTIONS.map((o) => o.value).filter((v) => v !== null);
    expect(values).toContain('application/pdf');
    expect(values).toContain('image/jpeg');
    expect(values).toContain('text/markdown');
    for (const value of values) {
      expect(value).toMatch(/^[a-z]+\/[a-z0-9.+-]+$/);
    }
  });
});

describe('fileKind', () => {
  it('clasifica los tipos permitidos', () => {
    expect(fileKind('application/pdf')).toBe('pdf');
    expect(fileKind('image/png')).toBe('image');
    expect(fileKind('application/vnd.openxmlformats-officedocument.wordprocessingml.document')).toBe(
      'document',
    );
    expect(fileKind('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')).toBe(
      'spreadsheet',
    );
    expect(fileKind('text/csv')).toBe('spreadsheet');
    expect(fileKind('text/markdown')).toBe('text');
    expect(fileKind('application/json')).toBe('data');
    expect(fileKind('application/octet-stream')).toBe('other');
  });

  it('asigna un icono a cada tipo', () => {
    expect(FILE_KIND_ICON.pdf).toBe('file-pdf');
    expect(FILE_KIND_ICON.data).toBe('braces');
    expect(FILE_KIND_ICON.other).toBe('file');
  });
});

describe('validateUploadFile', () => {
  it('acepta formatos permitidos sin importar mayúsculas', () => {
    expect(validateUploadFile({ name: 'REPORTE.PDF', size: 2048 })).toBeNull();
    expect(validateUploadFile({ name: 'notas.markdown', size: 10 })).toBeNull();
  });

  it('rechaza extensiones no permitidas o ausentes', () => {
    expect(validateUploadFile({ name: 'virus.exe', size: 10 })).toMatch(/no está permitido/);
    expect(validateUploadFile({ name: 'README', size: 10 })).toMatch(/no tiene extensión/);
  });

  it('rechaza archivos vacíos y mayores a 50 MB', () => {
    expect(validateUploadFile({ name: 'vacio.pdf', size: 0 })).toMatch(/vacío/);
    expect(validateUploadFile({ name: 'grande.pdf', size: 50 * 1024 * 1024 + 1 })).toMatch(/50 MB/);
  });
});

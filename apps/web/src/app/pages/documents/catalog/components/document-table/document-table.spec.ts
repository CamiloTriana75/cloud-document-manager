import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import { testDocument } from '../test-documents';
import { DocumentTableComponent } from './document-table';

function setup(inputs: Record<string, unknown> = {}) {
  const fixture = TestBed.createComponent(DocumentTableComponent);
  fixture.componentRef.setInput('documents', [
    testDocument('11111111-aaaa', 'READY', { original_filename: 'reporte.pdf' }),
    testDocument('22222222-bbbb', 'FAILED', { failure_reason: 'Contenido no admitido.' }),
  ]);
  fixture.componentRef.setInput('sort', { column: 'created_at', direction: 'desc' });
  for (const [key, value] of Object.entries(inputs)) {
    fixture.componentRef.setInput(key, value);
  }
  fixture.detectChanges();
  const host = fixture.nativeElement as HTMLElement;
  const rows = Array.from(host.querySelectorAll('tbody tr'));
  const button = (row: Element, name: string) =>
    row.querySelector<HTMLButtonElement>(`button[aria-label="${name}"]`);
  return { fixture, host, rows, button };
}

describe('DocumentTableComponent', () => {
  it('lista documentos con ID corto, nombre, estado y motivo de fallo', () => {
    const { host, rows } = setup();

    expect(host.querySelector('table')?.getAttribute('aria-label')).toBe(
      'Lista de documentos del espacio',
    );
    expect(rows.length).toBe(2);
    expect(rows[0].textContent).toContain('11111111');
    expect(rows[0].textContent).toContain('reporte.pdf');
    expect(rows[0].querySelector('.doc-status-ready')).toBeTruthy();
    expect(rows[1].textContent).toContain('Contenido no admitido.');
  });

  it('ofrece acciones según estado y permisos', () => {
    const { fixture, rows, button } = setup({ canDelete: false, canRetry: true });
    const download = vi.fn();
    const retry = vi.fn();
    const detail = vi.fn();
    fixture.componentInstance.download.subscribe(download);
    fixture.componentInstance.retry.subscribe(retry);
    fixture.componentInstance.openDetail.subscribe(detail);

    button(rows[0], 'Descargar archivo')?.click();
    button(rows[1], 'Reintentar procesamiento')?.click();
    button(rows[0], 'Ver detalle técnico del documento')?.click();

    expect(download).toHaveBeenCalledTimes(1);
    expect(retry).toHaveBeenCalledTimes(1);
    expect(detail).toHaveBeenCalledTimes(1);
    expect(button(rows[1], 'Descargar archivo')).toBeNull();
    expect(button(rows[0], 'Eliminar documento')).toBeNull();
  });

  it('expone el orden en los encabezados y emite el cambio de columna', () => {
    const { fixture, host } = setup();
    const spy = vi.fn();
    fixture.componentInstance.sortChange.subscribe(spy);

    const dateHeader = Array.from(host.querySelectorAll('th')).find((th) =>
      th.textContent?.includes('Fecha'),
    );
    expect(dateHeader?.getAttribute('aria-sort')).toBe('descending');

    const nameSort = Array.from(host.querySelectorAll<HTMLButtonElement>('th button')).find((b) =>
      b.textContent?.includes('Nombre'),
    );
    nameSort?.click();
    expect(spy).toHaveBeenCalledWith('original_filename');
  });
});

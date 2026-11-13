import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import { DocumentItem } from '../../../../../core/documents/document.models';
import { testDocument } from '../test-documents';
import { DocumentDetailComponent } from './document-detail';

function setup(document: DocumentItem, inputs: Record<string, unknown> = {}) {
  const fixture = TestBed.createComponent(DocumentDetailComponent);
  fixture.componentRef.setInput('document', document);
  for (const [key, value] of Object.entries(inputs)) {
    fixture.componentRef.setInput(key, value);
  }
  fixture.detectChanges();
  const host = fixture.nativeElement as HTMLElement;
  const button = (name: string) =>
    Array.from(host.querySelectorAll<HTMLButtonElement>('button')).find(
      (b) => b.getAttribute('aria-label') === name || b.textContent?.trim() === name,
    );
  return { fixture, host, button };
}

describe('DocumentDetailComponent', () => {
  it('muestra título, metadatos técnicos y cierra con un botón accesible', () => {
    const { fixture, host, button } = setup(
      testDocument('a', 'READY', { original_filename: 'reporte.pdf' }),
    );
    const close = vi.fn();
    fixture.componentInstance.closed.subscribe(close);

    expect(host.querySelector('h2#detail-title')?.textContent).toContain('reporte.pdf');
    expect(host.textContent).toContain('Metadatos Técnicos (JSONB)');
    expect(host.textContent).toContain('paginas');
    button('Cerrar detalle')?.click();
    expect(close).toHaveBeenCalledTimes(1);
  });

  it('ofrece descargar si está listo y eliminar si el rol lo permite', () => {
    const { fixture, button } = setup(testDocument('a', 'READY'), { canDelete: true });
    const download = vi.fn();
    const remove = vi.fn();
    fixture.componentInstance.download.subscribe(download);
    fixture.componentInstance.remove.subscribe(remove);

    button('Descargar archivo')?.click();
    button('Eliminar documento')?.click();

    expect(download).toHaveBeenCalledTimes(1);
    expect(remove).toHaveBeenCalledTimes(1);
  });

  it('explica el fallo y marca la línea de tiempo hasta el paso final', () => {
    const { host, button } = setup(
      testDocument('a', 'FAILED', { failure_reason: 'Contenido no admitido.' }),
      { canRetry: true },
    );

    expect(host.querySelector('[role="alert"]')?.textContent).toContain('Contenido no admitido.');
    expect(host.querySelectorAll('.timeline__step.is-done').length).toBe(3);
    expect(host.querySelector('.timeline__step.is-failed')).toBeTruthy();
    expect(button('Reintentar procesamiento')).toBeTruthy();
    expect(button('Descargar archivo')).toBeUndefined();
  });
});

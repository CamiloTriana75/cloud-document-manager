import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import { KpiCardComponent } from './kpi-card';

function create(inputs: Record<string, unknown>) {
  const fixture = TestBed.createComponent(KpiCardComponent);
  for (const [key, value] of Object.entries(inputs)) {
    fixture.componentRef.setInput(key, value);
  }
  fixture.detectChanges();
  return fixture;
}

describe('KpiCardComponent', () => {
  it('muestra etiqueta, valor, unidad y leyenda', () => {
    const host = create({
      label: 'Listos',
      value: 87,
      unit: '%',
      caption: '96 de 110 documentos',
    }).nativeElement as HTMLElement;

    expect(host.querySelector('.kpi__label')?.textContent?.trim()).toBe('Listos');
    expect(host.querySelector('.kpi__value')?.textContent).toContain('87');
    expect(host.querySelector('.kpi__unit')?.textContent).toBe('%');
    expect(host.querySelector('.kpi__caption')?.textContent?.trim()).toBe('96 de 110 documentos');
  });

  it('muestra un skeleton y oculta el valor mientras carga', () => {
    const host = create({ label: 'Documentos', value: 12, loading: true }).nativeElement as HTMLElement;

    expect(host.querySelector('.skeleton')).toBeTruthy();
    expect(host.querySelector('.kpi__value')).toBeNull();
    expect(host.querySelector('.kpi')?.getAttribute('aria-busy')).toBe('true');
  });

  it('emite la acción del botón con nombre accesible', () => {
    const fixture = create({ label: 'Listos', value: 3, actionLabel: 'Ver documentos listos' });
    const spy = vi.fn();
    fixture.componentInstance.action.subscribe(spy);

    const button = (fixture.nativeElement as HTMLElement).querySelector('button');
    expect(button?.getAttribute('aria-label')).toBe('Ver documentos listos');
    button?.click();
    expect(spy).toHaveBeenCalledTimes(1);
  });
});

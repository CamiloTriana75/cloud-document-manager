import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { StatusBadgeComponent } from './status-badge';

describe('StatusBadgeComponent (CDM-48)', () => {
  it('renderiza badge y etiqueta accesible para estado READY', () => {
    const fixture = TestBed.createComponent(StatusBadgeComponent);
    fixture.componentRef.setInput('status', 'READY');
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const badge = el.querySelector('.doc-status-badge');
    expect(badge).toBeTruthy();
    expect(badge?.classList.contains('doc-status-ready')).toBe(true);
    expect(badge?.textContent?.trim()).toBe('Listo');
    expect(badge?.getAttribute('aria-label')).toBe('Estado del documento: Listo');
    expect(el.querySelector('.pulse-indicator')).toBeNull();
  });

  it('muestra indicador de pulso en estado PROCESSING', () => {
    const fixture = TestBed.createComponent(StatusBadgeComponent);
    fixture.componentRef.setInput('status', 'PROCESSING');
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.pulse-indicator')).toBeTruthy();
    expect(el.textContent).toContain('Procesando');
  });

  it('renderiza correctamente el estado FAILED', () => {
    const fixture = TestBed.createComponent(StatusBadgeComponent);
    fixture.componentRef.setInput('status', 'FAILED');
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const badge = el.querySelector('.doc-status-badge');
    expect(badge?.classList.contains('doc-status-failed')).toBe(true);
    expect(badge?.textContent?.trim()).toBe('Fallido');
  });
});

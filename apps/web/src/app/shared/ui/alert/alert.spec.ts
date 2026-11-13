import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import { AlertComponent } from './alert';

describe('AlertComponent (CDM-48)', () => {
  it('renderiza alerta informativa con rol status por defecto', () => {
    const fixture = TestBed.createComponent(AlertComponent);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const alert = el.querySelector('.alert');
    expect(alert).toBeTruthy();
    expect(alert?.classList.contains('alert-info')).toBe(true);
    expect(alert?.getAttribute('role')).toBe('status');
  });

  it('asigna rol alert y aria-live assertive en alertas de peligro', () => {
    const fixture = TestBed.createComponent(AlertComponent);
    fixture.componentRef.setInput('type', 'danger');
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const alert = el.querySelector('.alert');
    expect(alert?.classList.contains('alert-danger')).toBe(true);
    expect(alert?.getAttribute('role')).toBe('alert');
    expect(alert?.getAttribute('aria-live')).toBe('assertive');
  });

  it('emite evento dismiss al presionar el botón de cierre cuando es dismissible', () => {
    const fixture = TestBed.createComponent(AlertComponent);
    fixture.componentRef.setInput('dismissible', true);
    fixture.detectChanges();

    const dismissSpy = vi.fn();
    fixture.componentInstance.dismiss.subscribe(dismissSpy);

    const closeBtn = fixture.nativeElement.querySelector('.alert-close-btn') as HTMLButtonElement;
    expect(closeBtn).toBeTruthy();
    closeBtn.click();

    expect(dismissSpy).toHaveBeenCalled();
  });
});

import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { SpinnerComponent } from './spinner';

describe('SpinnerComponent (CDM-48)', () => {
  it('renderiza con tamaño y etiqueta accesible por defecto', () => {
    const fixture = TestBed.createComponent(SpinnerComponent);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const spinner = el.querySelector('.spinner');
    expect(spinner).toBeTruthy();
    expect(spinner?.classList.contains('spinner-md')).toBe(true);
    expect(spinner?.getAttribute('role')).toBe('status');
    expect(spinner?.getAttribute('aria-label')).toBe('Cargando contenido...');
    expect(el.querySelector('.sr-only')?.textContent).toBe('Cargando contenido...');
  });

  it('permite personalizar el tamaño y la etiqueta ARIA', () => {
    const fixture = TestBed.createComponent(SpinnerComponent);
    fixture.componentRef.setInput('size', 'lg');
    fixture.componentRef.setInput('label', 'Guardando cambios...');
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const spinner = el.querySelector('.spinner');
    expect(spinner?.classList.contains('spinner-lg')).toBe(true);
    expect(spinner?.getAttribute('aria-label')).toBe('Guardando cambios...');
  });
});

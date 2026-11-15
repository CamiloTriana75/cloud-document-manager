import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { EmptyStateComponent } from './empty-state';

@Component({
  imports: [EmptyStateComponent],
  template: `
    <app-empty-state
      icon="inbox"
      title="Aún no hay documentos"
      description="Sube el primero para empezar."
    >
      <a href="/subir" class="btn btn--primary">Subir documento</a>
    </app-empty-state>
  `,
})
class HostComponent {}

describe('EmptyStateComponent', () => {
  it('muestra icono, título como encabezado, descripción y acciones proyectadas', () => {
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('app-icon')).toBeTruthy();
    expect(el.querySelector('h3')?.textContent?.trim()).toBe('Aún no hay documentos');
    expect(el.textContent).toContain('Sube el primero para empezar.');
    expect(el.querySelector('a.btn')?.textContent?.trim()).toBe('Subir documento');
  });
});

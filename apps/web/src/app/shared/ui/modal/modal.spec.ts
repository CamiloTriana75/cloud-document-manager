import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import { ModalComponent } from './modal';

@Component({
  standalone: true,
  imports: [ModalComponent],
  template: `
    <app-modal [isOpen]="isOpen" [title]="title" (modalClose)="onClose()">
      <p>Contenido del modal</p>
      <button modal-footer type="button" class="btn-confirm">Aceptar</button>
    </app-modal>
  `,
})
class TestHostComponent {
  isOpen = false;
  title = 'Título de prueba';
  onClose = vi.fn();
}

describe('ModalComponent (CDM-48)', () => {
  it('no renderiza contenido cuando isOpen es false', () => {
    const fixture = TestBed.createComponent(TestHostComponent);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.modal-backdrop')).toBeNull();
  });

  it('renderiza diálogo accesible con título y roles cuando isOpen es true', () => {
    const fixture = TestBed.createComponent(TestHostComponent);
    fixture.componentInstance.isOpen = true;
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const backdrop = el.querySelector('.modal-backdrop');
    expect(backdrop).toBeTruthy();
    expect(backdrop?.getAttribute('role')).toBe('dialog');
    expect(backdrop?.getAttribute('aria-modal')).toBe('true');
    expect(el.querySelector('.modal-title')?.textContent).toBe('Título de prueba');
    expect(el.textContent).toContain('Contenido del modal');
    expect(el.querySelector('.btn-confirm')).toBeTruthy();
  });

  it('cierra el modal al pulsar la tecla Escape o el botón de cierre', () => {
    const fixture = TestBed.createComponent(TestHostComponent);
    fixture.componentInstance.isOpen = true;
    fixture.detectChanges();

    const closeBtn = fixture.nativeElement.querySelector('.modal-close-btn') as HTMLButtonElement;
    closeBtn.click();
    expect(fixture.componentInstance.onClose).toHaveBeenCalled();

    // Pulso de Escape
    const modalComp = fixture.debugElement.children[0].componentInstance as ModalComponent;
    modalComp.onEscape();
    expect(fixture.componentInstance.onClose).toHaveBeenCalledTimes(2);
  });
});

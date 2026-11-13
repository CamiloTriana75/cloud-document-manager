import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { DialogComponent } from './dialog';

@Component({
  imports: [DialogComponent],
  template: `
    <button id="opener" type="button">Abrir</button>
    <app-dialog [open]="open()" label="Detalle" (closed)="closedCount = closedCount + 1">
      <button id="inside" type="button">Dentro</button>
    </app-dialog>
  `,
})
class HostComponent {
  readonly open = signal(false);
  closedCount = 0;
}

async function setup() {
  const fixture = TestBed.createComponent(HostComponent);
  fixture.detectChanges();
  await fixture.whenStable();
  const host = fixture.nativeElement as HTMLElement;
  return { fixture, host, dialog: host.querySelector('dialog') as HTMLDialogElement };
}

describe('DialogComponent', () => {
  it('abre y cierra el <dialog> nativo según la entrada open', async () => {
    const { fixture, dialog } = await setup();
    expect(dialog.hasAttribute('open')).toBe(false);
    expect(dialog.getAttribute('aria-label')).toBe('Detalle');

    fixture.componentInstance.open.set(true);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(dialog.hasAttribute('open')).toBe(true);

    fixture.componentInstance.open.set(false);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(dialog.hasAttribute('open')).toBe(false);
  });

  it('emite closed con Escape (evento cancel) sin cerrarse por su cuenta', async () => {
    const { fixture, dialog } = await setup();
    fixture.componentInstance.open.set(true);
    fixture.detectChanges();
    await fixture.whenStable();

    const cancel = new Event('cancel', { cancelable: true });
    dialog.dispatchEvent(cancel);

    expect(cancel.defaultPrevented).toBe(true);
    expect(fixture.componentInstance.closedCount).toBe(1);
  });

  it('emite closed al hacer clic en el fondo, no en el contenido', async () => {
    const { fixture, host, dialog } = await setup();
    fixture.componentInstance.open.set(true);
    fixture.detectChanges();
    await fixture.whenStable();

    (host.querySelector('#inside') as HTMLButtonElement).click();
    expect(fixture.componentInstance.closedCount).toBe(0);

    dialog.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(fixture.componentInstance.closedCount).toBe(1);
  });

  it('devuelve el foco al elemento que lo abrió', async () => {
    const { fixture, host } = await setup();
    const opener = host.querySelector('#opener') as HTMLButtonElement;
    opener.focus();

    fixture.componentInstance.open.set(true);
    fixture.detectChanges();
    await fixture.whenStable();
    (host.querySelector('#inside') as HTMLButtonElement).focus();

    fixture.componentInstance.open.set(false);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(document.activeElement).toBe(opener);
  });
});

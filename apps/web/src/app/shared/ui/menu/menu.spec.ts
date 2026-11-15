import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { MenuComponent, MenuItemDirective } from './menu';

@Component({
  imports: [MenuComponent, MenuItemDirective],
  template: `
    <button id="outside" type="button">Fuera</button>
    <app-menu label="Opciones del documento">
      <span menuTrigger>Más</span>
      <button appMenuItem type="button" id="first" (click)="last = 'first'">Ver detalle</button>
      <button appMenuItem type="button" id="second" (click)="last = 'second'">Descargar</button>
      <button appMenuItem type="button" id="third" (click)="last = 'third'">Eliminar</button>
    </app-menu>
  `,
})
class HostComponent {
  last = '';
}

async function setup() {
  const fixture = TestBed.createComponent(HostComponent);
  fixture.detectChanges();
  await fixture.whenStable();
  const host = fixture.nativeElement as HTMLElement;
  const trigger = host.querySelector('[aria-haspopup="menu"]') as HTMLButtonElement;
  const panel = host.querySelector('[role="menu"]') as HTMLElement;
  const item = (id: string) => host.querySelector(`#${id}`) as HTMLButtonElement;
  const open = async () => {
    trigger.click();
    fixture.detectChanges();
    await fixture.whenStable();
  };
  const key = async (target: HTMLElement, name: string) => {
    target.dispatchEvent(new KeyboardEvent('keydown', { key: name, bubbles: true }));
    fixture.detectChanges();
    await fixture.whenStable();
  };
  return { fixture, host, trigger, panel, item, open, key };
}

describe('MenuComponent', () => {
  it('abre con el disparador, anuncia el estado y enfoca el primer ítem', async () => {
    const { trigger, panel, item, open } = await setup();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(trigger.getAttribute('aria-label')).toBe('Opciones del documento');
    expect(panel.hidden).toBe(true);

    await open();

    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(panel.hidden).toBe(false);
    expect(item('first').getAttribute('role')).toBe('menuitem');
    expect(document.activeElement).toBe(item('first'));
  });

  it('mueve el foco con flechas de forma cíclica, Home y End', async () => {
    const { item, open, key } = await setup();
    await open();

    await key(item('first'), 'ArrowDown');
    expect(document.activeElement).toBe(item('second'));
    await key(item('second'), 'End');
    expect(document.activeElement).toBe(item('third'));
    await key(item('third'), 'ArrowDown');
    expect(document.activeElement).toBe(item('first'));
    await key(item('first'), 'ArrowUp');
    expect(document.activeElement).toBe(item('third'));
    await key(item('third'), 'Home');
    expect(document.activeElement).toBe(item('first'));
  });

  it('cierra con Escape y devuelve el foco al disparador', async () => {
    const { trigger, panel, item, open, key } = await setup();
    await open();

    await key(item('first'), 'Escape');

    expect(panel.hidden).toBe(true);
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(trigger);
  });

  it('ejecuta la acción del ítem y cierra el menú', async () => {
    const { fixture, panel, item, open } = await setup();
    await open();

    item('second').click();
    fixture.detectChanges();
    await fixture.whenStable();

    expect(fixture.componentInstance.last).toBe('second');
    expect(panel.hidden).toBe(true);
  });

  it('cierra al hacer clic fuera', async () => {
    const { fixture, host, panel, open } = await setup();
    await open();

    (host.querySelector('#outside') as HTMLButtonElement).click();
    fixture.detectChanges();
    await fixture.whenStable();

    expect(panel.hidden).toBe(true);
  });
});

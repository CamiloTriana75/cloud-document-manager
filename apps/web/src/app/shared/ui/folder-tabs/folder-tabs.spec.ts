import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import { FolderTabsComponent } from './folder-tabs';

const TABS = [
  { id: 'ALL', label: 'Todos', count: 12 },
  { id: 'READY', label: 'Listos', count: 9 },
  { id: 'FAILED', label: 'Fallidos', count: null },
];

async function setup(active = 'ALL') {
  const fixture = TestBed.createComponent(FolderTabsComponent);
  fixture.componentRef.setInput('tabs', TABS);
  fixture.componentRef.setInput('active', active);
  fixture.componentRef.setInput('controls', 'catalog-panel');
  fixture.componentRef.setInput('label', 'Carpetas por estado');
  fixture.detectChanges();
  await fixture.whenStable();
  const host = fixture.nativeElement as HTMLElement;
  const tabs = Array.from(host.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
  return { fixture, host, tabs };
}

describe('FolderTabsComponent', () => {
  it('expone el patrón tablist con la carpeta activa seleccionada', async () => {
    const { host, tabs } = await setup('READY');

    expect(host.querySelector('[role="tablist"]')?.getAttribute('aria-label')).toBe(
      'Carpetas por estado',
    );
    expect(tabs.length).toBe(3);
    expect(tabs[1].getAttribute('aria-selected')).toBe('true');
    expect(tabs[0].getAttribute('aria-selected')).toBe('false');
    expect(tabs[1].getAttribute('aria-controls')).toBe('catalog-panel');
    expect(tabs[1].tabIndex).toBe(0);
    expect(tabs[0].tabIndex).toBe(-1);
  });

  it('muestra el conteo solo cuando existe', async () => {
    const { tabs } = await setup();

    expect(tabs[0].textContent).toContain('12');
    expect(tabs[2].querySelector('.folder__count')).toBeNull();
  });

  it('mueve el foco con flechas, Home y End sin activar', async () => {
    const { fixture, tabs } = await setup();
    const spy = vi.fn();
    fixture.componentInstance.activeChange.subscribe(spy);
    tabs[0].focus();

    tabs[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    expect(document.activeElement).toBe(tabs[1]);
    tabs[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }));
    expect(document.activeElement).toBe(tabs[2]);
    tabs[2].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    expect(document.activeElement).toBe(tabs[0]);
    tabs[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }));
    expect(document.activeElement).toBe(tabs[2]);
    expect(spy).not.toHaveBeenCalled();
  });

  it('emite la carpeta elegida al activarla', async () => {
    const { fixture, tabs } = await setup();
    const spy = vi.fn();
    fixture.componentInstance.activeChange.subscribe(spy);

    tabs[2].click();

    expect(spy).toHaveBeenCalledWith('FAILED');
  });
});

import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { IconComponent } from './icon';
import { ICONS, IconName } from './icons';

function render(name: IconName, size?: number) {
  const fixture = TestBed.createComponent(IconComponent);
  fixture.componentRef.setInput('name', name);
  if (size !== undefined) {
    fixture.componentRef.setInput('size', size);
  }
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('IconComponent (CDM-108)', () => {
  it('dibuja un elemento SVG por cada nodo del registro', () => {
    const host = render('upload');
    const svg = host.querySelector('svg');

    expect(svg).toBeTruthy();
    expect(svg?.children.length).toBe(ICONS.upload.length);
    expect(svg?.querySelector('polyline')?.getAttribute('points')).toBe('17 8 12 3 7 8');
  });

  it('aplica el tamaño al ancho y alto del SVG', () => {
    const svg = render('search', 24).querySelector('svg');

    expect(svg?.getAttribute('width')).toBe('24');
    expect(svg?.getAttribute('height')).toBe('24');
  });

  it('es decorativo para tecnologías de asistencia', () => {
    const host = render('download');

    expect(host.getAttribute('aria-hidden')).toBe('true');
    expect(host.querySelector('svg')?.getAttribute('focusable')).toBe('false');
  });

  it('cada icono del registro tiene al menos un trazo', () => {
    for (const [name, nodes] of Object.entries(ICONS)) {
      expect(nodes.length, name).toBeGreaterThan(0);
    }
  });
});

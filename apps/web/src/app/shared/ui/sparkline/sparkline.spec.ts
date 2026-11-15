import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { SparklineComponent } from './sparkline';

function render(points: number[]) {
  const fixture = TestBed.createComponent(SparklineComponent);
  fixture.componentRef.setInput('points', points);
  fixture.componentRef.setInput('label', 'Cargas por día');
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

function vertices(d: string | null | undefined): number[][] {
  return (d ?? '')
    .split(/[ML]/)
    .map((pair) => pair.trim())
    .filter(Boolean)
    .map((pair) => pair.split(',').map(Number));
}

describe('SparklineComponent', () => {
  it('traza un vértice por punto con la etiqueta accesible', () => {
    const host = render([0, 2, 1, 4, 3, 5, 2]);
    const svg = host.querySelector('svg');
    const line = host.querySelector('.sparkline__line');

    expect(svg?.getAttribute('role')).toBe('img');
    expect(svg?.getAttribute('aria-label')).toBe('Cargas por día');
    expect(vertices(line?.getAttribute('d')).length).toBe(7);
  });

  it('dibuja una línea plana en la base cuando todos los valores son cero', () => {
    const host = render([0, 0, 0]);
    const ys = vertices(host.querySelector('.sparkline__line')?.getAttribute('d')).map((v) => v[1]);

    expect(new Set(ys).size).toBe(1);
    expect(ys[0]).toBeGreaterThan(16);
  });
});

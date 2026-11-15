import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { SegmentedBarComponent } from './segmented-bar';

function render(segments: { value: number; tone: 'positive' | 'accent' | 'danger'; label: string }[]) {
  const fixture = TestBed.createComponent(SegmentedBarComponent);
  fixture.componentRef.setInput('label', 'Pipeline');
  fixture.componentRef.setInput('segments', segments);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('SegmentedBarComponent', () => {
  it('reparte el ancho en proporción a cada valor y lo anuncia en porcentajes', () => {
    const host = render([
      { value: 1, tone: 'positive', label: 'Listos' },
      { value: 1, tone: 'accent', label: 'En curso' },
      { value: 2, tone: 'danger', label: 'Fallidos' },
    ]);

    const parts = host.querySelectorAll<HTMLElement>('.segment');
    expect(parts.length).toBe(3);
    expect(parts[2].style.flexGrow).toBe('2');
    expect(host.getAttribute('role')).toBe('img');
    expect(host.getAttribute('aria-label')).toBe('Pipeline: Listos 25 %, En curso 25 %, Fallidos 50 %');
  });

  it('omite segmentos en cero y muestra solo la pista sin datos', () => {
    const host = render([
      { value: 0, tone: 'positive', label: 'Listos' },
      { value: 0, tone: 'danger', label: 'Fallidos' },
    ]);

    expect(host.querySelectorAll('.segment').length).toBe(0);
    expect(host.getAttribute('aria-label')).toBe('Pipeline: sin datos');
  });
});

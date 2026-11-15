import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { CoilSceneComponent } from './coil-scene';

describe('CoilSceneComponent', () => {
  it('usa el fondo CSS de respaldo cuando no hay WebGL (jsdom)', async () => {
    const fixture = TestBed.createComponent(CoilSceneComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    const host = fixture.nativeElement as HTMLElement;

    expect(host.getAttribute('aria-hidden')).toBe('true');
    expect(host.getAttribute('data-state')).toBe('fallback');
    expect(host.querySelector('.coil-fallback')).toBeTruthy();
  });
});

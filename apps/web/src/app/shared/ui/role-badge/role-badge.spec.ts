import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { RoleBadgeComponent } from './role-badge';

describe('RoleBadgeComponent (CDM-48)', () => {
  it('renderiza clase y texto para el rol OWNER', () => {
    const fixture = TestBed.createComponent(RoleBadgeComponent);
    fixture.componentRef.setInput('role', 'OWNER');
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const badge = el.querySelector('.role-badge');
    expect(badge?.classList.contains('role-owner')).toBe(true);
    expect(badge?.textContent?.trim()).toBe('OWNER');
    expect(badge?.getAttribute('aria-label')).toBe('Rol de usuario: OWNER');
  });

  it('renderiza clase y texto para el rol VIEWER', () => {
    const fixture = TestBed.createComponent(RoleBadgeComponent);
    fixture.componentRef.setInput('role', 'VIEWER');
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const badge = el.querySelector('.role-badge');
    expect(badge?.classList.contains('role-viewer')).toBe(true);
    expect(badge?.textContent?.trim()).toBe('VIEWER');
  });
});

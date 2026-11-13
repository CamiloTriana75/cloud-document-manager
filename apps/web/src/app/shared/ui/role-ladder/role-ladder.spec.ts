import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { RoleLadderComponent } from './role-ladder';

describe('RoleLadderComponent', () => {
  it('llena los peldaños hasta el nivel del rol y marca el actual', () => {
    const fixture = TestBed.createComponent(RoleLadderComponent);
    fixture.componentRef.setInput('role', 'EDITOR');
    fixture.detectChanges();
    const host = fixture.nativeElement as HTMLElement;

    const steps = host.querySelectorAll('.ladder__step');
    expect(steps.length).toBe(5);
    expect(host.querySelectorAll('.ladder__step.is-filled').length).toBe(3);
    expect(steps[2].classList.contains('is-current')).toBe(true);
    expect(host.querySelector('[role="img"]')?.getAttribute('aria-label')).toBe(
      'Rol EDITOR, nivel 3 de 5',
    );
    expect(host.textContent).toContain('EDITOR');
  });
});

import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { FormErrorComponent } from './form-error';

describe('FormErrorComponent (CDM-48)', () => {
  it('no renderiza mensaje cuando message es null', () => {
    const fixture = TestBed.createComponent(FormErrorComponent);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.form-error-msg')).toBeNull();
  });

  it('renderiza mensaje de error con rol alert e id asociado para accesibilidad', () => {
    const fixture = TestBed.createComponent(FormErrorComponent);
    fixture.componentRef.setInput('message', 'El correo es obligatorio');
    fixture.componentRef.setInput('id', 'email-error');
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const msg = el.querySelector('.form-error-msg');
    expect(msg).toBeTruthy();
    expect(msg?.getAttribute('id')).toBe('email-error');
    expect(msg?.getAttribute('role')).toBe('alert');
    expect(msg?.textContent).toContain('El correo es obligatorio');
  });
});

import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import { UserMenuComponent } from './user-menu';

describe('UserMenuComponent', () => {
  it('muestra la identidad y el rol activo y emite logout', () => {
    const fixture = TestBed.createComponent(UserMenuComponent);
    fixture.componentRef.setInput('user', {
      sub: 'u-1',
      email: 'admin@empresa.com',
      name: 'Admin Empresa',
      emailVerified: true,
    });
    fixture.componentRef.setInput('role', 'ADMIN');
    fixture.componentRef.setInput('workspaceName', 'Espacio Principal');
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    const spy = vi.fn();
    fixture.componentInstance.logout.subscribe(spy);

    expect(el.querySelector('[aria-haspopup="menu"]')?.getAttribute('aria-label')).toBe(
      'Menú de usuario',
    );
    expect(el.querySelector('.user-name')?.textContent).toContain('Admin Empresa');
    expect(el.querySelector('.user-email')?.textContent).toContain('admin@empresa.com');
    expect(el.querySelector('.role-admin')?.textContent).toContain('ADMIN');

    const logout = Array.from(el.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Cerrar sesión'),
    );
    logout?.click();
    expect(spy).toHaveBeenCalledTimes(1);
  });
});

import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Workspace } from '../../core/workspaces/workspace.models';
import { WorkspaceService } from '../../core/workspaces/workspace.service';
import { WorkspaceSwitcherComponent } from './workspace-switcher';

const WS_A: Workspace = {
  id: 'ws-1',
  name: 'Espacio Demo',
  slug: 'espacio-demo',
  role: 'OWNER',
  created_at: '2026-11-12T00:00:00Z',
  updated_at: '2026-11-12T00:00:00Z',
};
const WS_B: Workspace = { ...WS_A, id: 'ws-2', name: 'Nuevo Espacio', role: 'VIEWER' };

describe('WorkspaceSwitcherComponent', () => {
  let service: WorkspaceService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    service = TestBed.inject(WorkspaceService);
  });

  it('muestra el workspace activo en el disparador y lista los demás como opciones', () => {
    service.workspaces.set([WS_A, WS_B]);
    service.activeWorkspace.set(WS_A);
    const fixture = TestBed.createComponent(WorkspaceSwitcherComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('[aria-haspopup="menu"]')?.textContent).toContain('Espacio Demo');
    const options = el.querySelectorAll('[role="menuitemradio"]');
    expect(options.length).toBe(2);
    expect(options[0].getAttribute('aria-checked')).toBe('true');
    expect(options[1].getAttribute('aria-checked')).toBe('false');
    expect(el.querySelector('.role-viewer')?.textContent).toContain('VIEWER');
  });

  it('ofrece crear un espacio cuando no hay workspace activo', () => {
    service.activeWorkspace.set(null);
    const fixture = TestBed.createComponent(WorkspaceSwitcherComponent);
    fixture.detectChanges();
    const link = (fixture.nativeElement as HTMLElement).querySelector('a[href="/workspaces/new"]');

    expect(link?.textContent).toContain('Crear espacio');
  });

  it('cambia el workspace activo y conserva la sección actual', () => {
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    Object.defineProperty(router, 'url', { value: '/workspaces/ws-1/members', configurable: true });
    service.workspaces.set([WS_A, WS_B]);
    service.activeWorkspace.set(WS_A);
    const fixture = TestBed.createComponent(WorkspaceSwitcherComponent);
    fixture.detectChanges();

    const options = (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>(
      '[role="menuitemradio"]',
    );
    options[1].click();

    expect(service.activeWorkspace()?.id).toBe('ws-2');
    expect(navigate).toHaveBeenCalledWith(['/workspaces', 'ws-2', 'members']);
  });
});

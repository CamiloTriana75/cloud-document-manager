import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthService } from '../../core/auth/auth.service';
import { Workspace } from '../../core/workspaces/workspace.models';
import { WorkspaceService } from '../../core/workspaces/workspace.service';
import { Home } from './home';

const WORKSPACES: Workspace[] = [
  {
    id: 'ws-1',
    name: 'Acme Legal',
    slug: 'acme-legal',
    role: 'OWNER',
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  },
  {
    id: 'ws-2',
    name: 'Finanzas',
    slug: 'finanzas',
    role: 'VIEWER',
    created_at: '2026-11-05T00:00:00Z',
    updated_at: '2026-11-05T00:00:00Z',
  },
];

describe('Home', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Home],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function flushHealthOk(): void {
    http.expectOne('/health').flush({ status: 'ok', service: 'cdm-api', version: '0.1.0' });
  }

  it('muestra estado operativa cuando la API responde', async () => {
    const fixture = TestBed.createComponent(Home);
    fixture.detectChanges();

    flushHealthOk();
    fixture.detectChanges();
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.status-ok')).toBeTruthy();
    expect(el.textContent).toContain('Operativa');
    expect(el.textContent).toContain('cdm-api');
  });

  it('muestra error y botón de reintento cuando la API falla', async () => {
    const fixture = TestBed.createComponent(Home);
    fixture.detectChanges();

    http.expectOne('/health').flush('no disponible', { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.status-error')).toBeTruthy();
    const retry = el.querySelector<HTMLButtonElement>('.btn-retry');
    expect(retry?.textContent).toContain('Reintentar');
  });

  it('sin sesión presenta el producto con accesos a crear cuenta e iniciar sesión', () => {
    TestBed.inject(AuthService).currentUser.set(null);
    const fixture = TestBed.createComponent(Home);
    fixture.detectChanges();
    flushHealthOk();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('h1')?.textContent?.trim().length).toBeGreaterThan(0);
    expect(el.querySelector('a[href="/auth/register"]')?.textContent).toContain('Crear cuenta');
    expect(el.querySelector('a[href="/auth/login"]')?.textContent).toContain('Iniciar sesión');
  });

  it('con sesión saluda y lista los workspaces; elegir uno lo activa y abre sus documentos', () => {
    TestBed.inject(AuthService).currentUser.set({
      sub: 'u-1',
      email: 'ana@empresa.com',
      name: 'Ana',
      emailVerified: true,
    });
    const workspaces = TestBed.inject(WorkspaceService);
    workspaces.workspaces.set(WORKSPACES);
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const fixture = TestBed.createComponent(Home);
    fixture.detectChanges();
    flushHealthOk();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('h1')?.textContent).toContain('Ana');
    const cards = el.querySelectorAll<HTMLButtonElement>('button.workspace-card');
    expect(cards.length).toBe(2);
    expect(cards[1].textContent).toContain('Finanzas');

    cards[1].click();
    expect(workspaces.activeWorkspace()?.id).toBe('ws-2');
    expect(navigate).toHaveBeenCalledWith(['/workspaces', 'ws-2', 'documents']);
  });

  it('con sesión y sin workspaces invita a crear el primero', () => {
    TestBed.inject(AuthService).currentUser.set({
      sub: 'u-1',
      email: 'ana@empresa.com',
      emailVerified: true,
    });
    TestBed.inject(WorkspaceService).workspaces.set([]);
    const fixture = TestBed.createComponent(Home);
    fixture.detectChanges();
    flushHealthOk();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('a[href="/workspaces/new"]')?.textContent).toMatch(/Crear/);
  });
});

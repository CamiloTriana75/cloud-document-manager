import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import { App } from './app';
import { routes } from './app.routes';
import { AuthService } from './core/auth/auth.service';
import { Workspace } from './core/workspaces/workspace.models';
import { WorkspaceService } from './core/workspaces/workspace.service';

describe('App (shell y navegación CDM-44)', () => {
  let authService: AuthService;
  let workspaceService: WorkspaceService;
  let router: Router;

  const mockWs: Workspace = {
    id: 'ws-test-123',
    name: 'Espacio Principal',
    slug: 'espacio-principal',
    role: 'ADMIN',
    created_at: '2026-11-12T00:00:00Z',
    updated_at: '2026-11-12T00:00:00Z',
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter(routes),
      ],
    }).compileComponents();

    authService = TestBed.inject(AuthService);
    workspaceService = TestBed.inject(WorkspaceService);
    router = TestBed.inject(Router);
  });

  it('renderiza header con marca y skip link accesible', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.brand')?.textContent).toContain(
      'Cloud Document Manager',
    );
    const skip = el.querySelector<HTMLAnchorElement>('.skip-link');
    expect(skip?.getAttribute('href')).toBe('#main');
    expect(el.querySelector('main#main')).toBeTruthy();
  });

  it('muestra enlaces de autenticación cuando el usuario no está autenticado', () => {
    authService.currentUser.set(null);
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.desktop-nav')).toBeNull();
    const loginLink = el.querySelector('a[routerLink="/auth/login"]');
    expect(loginLink?.textContent).toContain('Iniciar sesión');
    const registerLink = el.querySelector('a[routerLink="/auth/register"]');
    expect(registerLink?.textContent).toContain('Crear cuenta');
  });

  it('muestra navegación principal, selector y estado de sesión cuando está autenticado', () => {
    authService.currentUser.set({
      sub: 'usr-1',
      email: 'admin@empresa.com',
      name: 'Admin Empresa',
      emailVerified: true,
    });
    workspaceService.activeWorkspace.set(mockWs);

    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    // Navegación principal en escritorio
    const desktopNav = el.querySelector('.desktop-nav');
    expect(desktopNav).toBeTruthy();
    expect(desktopNav?.textContent).toContain('Inicio');
    expect(desktopNav?.textContent).toContain('Documentos');
    expect(desktopNav?.textContent).toContain('Cargar');
    expect(desktopNav?.textContent).toContain('Miembros');

    // Estado de sesión
    expect(el.querySelector('.user-name')?.textContent).toContain('Admin Empresa');
    expect(el.querySelector('.role-admin')?.textContent).toContain('ADMIN');
    expect(el.querySelector('.btn-logout')).toBeTruthy();
  });

  it('ejecuta cierre de sesión y redirige a login', () => {
    authService.currentUser.set({
      sub: 'usr-1',
      email: 'admin@empresa.com',
      emailVerified: true,
    });
    workspaceService.activeWorkspace.set(mockWs);

    const navigateSpy = vi.spyOn(router, 'navigate');
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const logoutBtn = fixture.nativeElement.querySelector('.btn-logout') as HTMLButtonElement;
    logoutBtn.click();
    fixture.detectChanges();

    expect(authService.currentUser()).toBeNull();
    expect(workspaceService.activeWorkspace()).toBeNull();
    expect(navigateSpy).toHaveBeenCalledWith(['/auth/login']);
  });

  it('controla la apertura, cierre y tecla escape del menú móvil', () => {
    authService.currentUser.set({
      sub: 'usr-1',
      email: 'admin@empresa.com',
      emailVerified: true,
    });
    workspaceService.activeWorkspace.set(mockWs);

    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    expect(fixture.componentInstance.isMobileMenuOpen()).toBe(false);
    expect(fixture.nativeElement.querySelector('.mobile-drawer')).toBeNull();

    // Abrir menú móvil
    fixture.componentInstance.toggleMobileMenu();
    fixture.detectChanges();

    expect(fixture.componentInstance.isMobileMenuOpen()).toBe(true);
    expect(fixture.nativeElement.querySelector('.mobile-drawer')).toBeTruthy();

    // Escape cierra el menú móvil
    fixture.componentInstance.onEscape();
    fixture.detectChanges();

    expect(fixture.componentInstance.isMobileMenuOpen()).toBe(false);
    expect(fixture.nativeElement.querySelector('.mobile-drawer')).toBeNull();
  });
});

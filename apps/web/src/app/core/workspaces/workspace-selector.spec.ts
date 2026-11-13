import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import { Workspace } from './workspace.models';
import { WorkspaceSelectorComponent } from './workspace-selector';
import { WorkspaceService } from './workspace.service';

describe('WorkspaceSelectorComponent', () => {
  let workspaceService: WorkspaceService;

  const mockWs: Workspace = {
    id: 'ws-1',
    name: 'Espacio Demo',
    slug: 'espacio-demo',
    role: 'OWNER',
    created_at: '2026-11-12T00:00:00Z',
    updated_at: '2026-11-12T00:00:00Z',
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [WorkspaceSelectorComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    }).compileComponents();

    workspaceService = TestBed.inject(WorkspaceService);
  });

  it('muestra el nombre del workspace activo y su badge de rol', () => {
    workspaceService.activeWorkspace.set(mockWs);
    const fixture = TestBed.createComponent(WorkspaceSelectorComponent);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.active-name')?.textContent).toContain('Espacio Demo');
    expect(el.querySelector('.role-owner')?.textContent).toContain('OWNER');
  });

  it('abre y cierra el menú desplegable al hacer clic y con la tecla escape', () => {
    workspaceService.activeWorkspace.set(mockWs);
    workspaceService.workspaces.set([mockWs]);
    const fixture = TestBed.createComponent(WorkspaceSelectorComponent);
    fixture.detectChanges();

    const trigger = fixture.nativeElement.querySelector('.selector-trigger') as HTMLButtonElement;
    expect(fixture.componentInstance.isOpen()).toBe(false);

    trigger.click();
    fixture.detectChanges();
    expect(fixture.componentInstance.isOpen()).toBe(true);
    expect(fixture.nativeElement.querySelector('.dropdown-menu')).toBeTruthy();

    // Escape cierra el dropdown
    fixture.componentInstance.onEscape();
    fixture.detectChanges();
    expect(fixture.componentInstance.isOpen()).toBe(false);
  });

  it('muestra botón de crear espacio cuando no hay workspace activo', () => {
    workspaceService.activeWorkspace.set(null);
    const fixture = TestBed.createComponent(WorkspaceSelectorComponent);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.empty-state-trigger')?.textContent).toContain('+ Crear espacio');
  });

  it('sincroniza y navega a la ruta equivalente al seleccionar un nuevo workspace', () => {
    const router = TestBed.inject(Router);
    const navigateSpy = vi.spyOn(router, 'navigate');
    Object.defineProperty(router, 'url', { value: '/workspaces/ws-1/documents', configurable: true });

    const newWs: Workspace = { ...mockWs, id: 'ws-2', name: 'Nuevo Espacio' };
    const fixture = TestBed.createComponent(WorkspaceSelectorComponent);
    fixture.componentInstance.selectWorkspace(newWs);

    expect(workspaceService.activeWorkspace()?.id).toBe('ws-2');
    expect(navigateSpy).toHaveBeenCalledWith(['/workspaces', 'ws-2', 'documents']);
  });
});

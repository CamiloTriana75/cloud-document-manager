import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { Workspace, WorkspaceMember } from './workspace.models';
import { WorkspaceService } from './workspace.service';

describe('WorkspaceService', () => {
  let service: WorkspaceService;
  let http: HttpTestingController;

  const mockWorkspaces: Workspace[] = [
    {
      id: 'ws-1',
      name: 'Equipo Alfa',
      slug: 'equipo-alfa',
      role: 'OWNER',
      created_at: '2026-11-12T00:00:00Z',
      updated_at: '2026-11-12T00:00:00Z',
    },
    {
      id: 'ws-2',
      name: 'Equipo Beta',
      slug: 'equipo-beta',
      role: 'MEMBER',
      created_at: '2026-11-12T00:00:00Z',
      updated_at: '2026-11-12T00:00:00Z',
    },
  ];

  const mockMembers: WorkspaceMember[] = [
    {
      membership_id: 'm-1',
      user_id: 'u-1',
      email: 'owner@test.com',
      display_name: 'Owner',
      role: 'OWNER',
      status: 'ACTIVE',
      created_at: '2026-11-12T00:00:00Z',
    },
    {
      membership_id: 'm-2',
      user_id: 'u-2',
      email: 'member@test.com',
      display_name: 'Member',
      role: 'MEMBER',
      status: 'ACTIVE',
      created_at: '2026-11-12T00:00:00Z',
    },
  ];

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(WorkspaceService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    sessionStorage.clear();
  });

  it('carga workspaces y selecciona el primero como activo por defecto', () => {
    service.loadWorkspaces().subscribe((workspaces) => {
      expect(workspaces.length).toBe(2);
    });

    const req = http.expectOne('/api/v1/workspaces');
    expect(req.request.method).toBe('GET');
    req.flush({ data: mockWorkspaces });

    expect(service.workspaces().length).toBe(2);
    expect(service.activeWorkspace()?.id).toBe('ws-1');
    expect(service.hasWorkspaces()).toBe(true);
    expect(service.canManageMembers()).toBe(true);
  });

  it('permite cambiar el workspace activo y persiste el ID en sessionStorage', () => {
    service.setActiveWorkspace(mockWorkspaces[1]);
    expect(service.activeWorkspace()?.id).toBe('ws-2');
    expect(sessionStorage.getItem('cdm_active_workspace_id')).toBe('ws-2');
    expect(service.canManageMembers()).toBe(false); // MEMBER no puede administrar miembros
  });

  it('crea un nuevo workspace y lo coloca como activo', () => {
    const newWs: Workspace = {
      id: 'ws-3',
      name: 'Equipo Gamma',
      slug: 'equipo-gamma',
      role: 'OWNER',
      created_at: '2026-11-12T00:00:00Z',
      updated_at: '2026-11-12T00:00:00Z',
    };

    service.createWorkspace({ name: 'Equipo Gamma', slug: 'equipo-gamma' }).subscribe((ws) => {
      expect(ws.name).toBe('Equipo Gamma');
    });

    const req = http.expectOne('/api/v1/workspaces');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ name: 'Equipo Gamma', slug: 'equipo-gamma' });
    req.flush({ data: newWs });

    expect(service.workspaces()).toContainEqual(newWs);
    expect(service.activeWorkspace()?.id).toBe('ws-3');
  });

  it('carga los miembros de un workspace y actualiza el signal', () => {
    service.loadMembers('ws-1').subscribe((members) => {
      expect(members.length).toBe(2);
    });

    const req = http.expectOne('/api/v1/workspaces/ws-1/members');
    expect(req.request.method).toBe('GET');
    req.flush({ data: mockMembers });

    expect(service.members().length).toBe(2);
  });

  it('agrega un miembro y lo inserta al principio de la lista', () => {
    const newMember: WorkspaceMember = {
      membership_id: 'm-3',
      user_id: 'u-3',
      email: 'admin@test.com',
      display_name: null,
      role: 'ADMIN',
      status: 'ACTIVE',
      created_at: '2026-11-12T00:00:00Z',
    };

    service.addMember('ws-1', { email: 'admin@test.com', role: 'ADMIN' }).subscribe((m) => {
      expect(m.email).toBe('admin@test.com');
    });

    const req = http.expectOne('/api/v1/workspaces/ws-1/members');
    expect(req.request.method).toBe('POST');
    req.flush({ data: newMember });

    expect(service.members()[0].email).toBe('admin@test.com');
  });
});

import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { WorkspaceMember } from '../../../core/workspaces/workspace.models';
import { WorkspaceMembersComponent } from './members';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';

describe('WorkspaceMembersComponent', () => {
  let component: WorkspaceMembersComponent;
  let workspaceService: WorkspaceService;

  const mockMembers: WorkspaceMember[] = [
    {
      membership_id: 'm-1',
      user_id: 'u-1',
      email: 'owner@test.com',
      display_name: 'Owner User',
      role: 'OWNER',
      status: 'ACTIVE',
      created_at: '2026-11-12T00:00:00Z',
    },
  ];

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [WorkspaceMembersComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: {
                get: (key: string) => (key === 'id' ? 'ws-test-id' : null),
              },
            },
          },
        },
      ],
    }).compileComponents();

    workspaceService = TestBed.inject(WorkspaceService);
    vi.spyOn(workspaceService, 'loadMembers').mockReturnValue(of(mockMembers));
    workspaceService.activeWorkspace.set({
      id: 'ws-test-id',
      name: 'Espacio Prueba',
      slug: 'espacio-prueba',
      role: 'OWNER',
      created_at: '',
      updated_at: '',
    });

    const fixture = TestBed.createComponent(WorkspaceMembersComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('carga los miembros al inicializar', () => {
    expect(workspaceService.loadMembers).toHaveBeenCalledWith('ws-test-id');
    expect(component.workspaceId()).toBe('ws-test-id');
  });

  it('permite invitar a un miembro cuando el usuario es OWNER', () => {
    const newMember: WorkspaceMember = {
      membership_id: 'm-2',
      user_id: 'u-2',
      email: 'nuevo@test.com',
      display_name: null,
      role: 'MEMBER',
      status: 'ACTIVE',
      created_at: '',
    };
    vi.spyOn(workspaceService, 'addMember').mockReturnValue(of(newMember));

    component.form.controls.email.setValue('nuevo@test.com');
    component.form.controls.role.setValue('MEMBER');
    component.onInvite();

    expect(workspaceService.addMember).toHaveBeenCalledWith('ws-test-id', {
      email: 'nuevo@test.com',
      role: 'MEMBER',
    });
    expect(component.inviteSuccess()).toContain('nuevo@test.com');
    expect(component.form.controls.email.value).toBe('');
  });

  it('muestra error cuando la invitación falla', () => {
    vi.spyOn(workspaceService, 'addMember').mockReturnValue(
      throwError(() => ({
        error: {
          error: {
            message: 'El usuario ya es miembro.',
          },
        },
      }))
    );

    component.form.controls.email.setValue('existente@test.com');
    component.form.controls.role.setValue('MEMBER');
    component.onInvite();

    expect(component.inviteError()).toBe('El usuario ya es miembro.');
    expect(component.isSubmitting()).toBe(false);
  });
});

import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import {
  FormBuilder,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { WorkspaceMember, WorkspaceRole } from '../../../core/workspaces/workspace.models';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';
import { formatDate } from '../../../shared/format/format-date';
import { AlertComponent } from '../../../shared/ui/alert/alert';
import { AvatarComponent } from '../../../shared/ui/avatar/avatar';
import { EmptyStateComponent } from '../../../shared/ui/empty-state/empty-state';
import { IconComponent } from '../../../shared/ui/icon/icon';
import { RoleBadgeComponent } from '../../../shared/ui/role-badge/role-badge';
import { RoleLadderComponent } from '../../../shared/ui/role-ladder/role-ladder';

interface InviteMemberForm {
  email: FormControl<string>;
  role: FormControl<WorkspaceRole>;
}

/** Roles asignables por invitación: OWNER no se asigna desde aquí (ADR-0001). */
const ASSIGNABLE_ROLES: readonly WorkspaceRole[] = ['ADMIN', 'EDITOR', 'MEMBER', 'VIEWER'];

const STATUS_LABEL: Readonly<Record<WorkspaceMember['status'], string>> = {
  ACTIVE: 'Activo',
  INVITED: 'Invitado',
  SUSPENDED: 'Suspendido',
};

/** Miembros y roles del workspace (`/workspaces/:id/members`). */
@Component({
  selector: 'app-workspace-members',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    AlertComponent,
    AvatarComponent,
    EmptyStateComponent,
    IconComponent,
    RoleBadgeComponent,
    RoleLadderComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './members.html',
  styleUrl: './members.css',
})
export class WorkspaceMembersComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);
  readonly workspaceService = inject(WorkspaceService);

  readonly workspaceId = signal<string>('');
  readonly isSubmitting = signal<boolean>(false);
  readonly inviteError = signal<string | null>(null);
  readonly inviteSuccess = signal<string | null>(null);

  readonly availableRoles = ASSIGNABLE_ROLES;

  readonly form: FormGroup<InviteMemberForm> = this.fb.group<InviteMemberForm>({
    email: this.fb.control('', {
      nonNullable: true,
      validators: [Validators.required, Validators.email],
    }),
    role: this.fb.control('MEMBER' as WorkspaceRole, {
      nonNullable: true,
      validators: [Validators.required],
    }),
  });

  protected readonly summary = computed(() => {
    const members = this.workspaceService.members();
    return {
      total: members.length,
      admins: members.filter((m) => m.role === 'OWNER' || m.role === 'ADMIN').length,
      active: members.filter((m) => m.status === 'ACTIVE').length,
    };
  });

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.workspaceId.set(id);
      this.loadMembers();
    }
  }

  loadMembers(): void {
    const id = this.workspaceId();
    if (!id) return;
    this.workspaceService.loadMembers(id).subscribe({
      error: () => {
        // El error se expone mediante workspaceService.error
      },
    });
  }

  onInvite(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    const id = this.workspaceId();
    if (!id) return;

    this.isSubmitting.set(true);
    this.inviteError.set(null);
    this.inviteSuccess.set(null);

    const raw = this.form.getRawValue();
    const payload = {
      email: raw.email.trim().toLowerCase(),
      role: raw.role,
    };

    this.workspaceService.addMember(id, payload).subscribe({
      next: (member) => {
        this.isSubmitting.set(false);
        this.inviteSuccess.set(`Se agregó a ${member.email} con rol ${member.role}.`);
        this.form.reset({ email: '', role: 'MEMBER' });
      },
      error: (err) => {
        this.isSubmitting.set(false);
        const msg =
          err?.error?.error?.message ||
          'Error al agregar el miembro. Verifica los permisos o si el usuario ya existe.';
        this.inviteError.set(msg);
      },
    });
  }

  protected statusLabel(member: WorkspaceMember): string {
    return STATUS_LABEL[member.status] ?? member.status;
  }

  protected joined(member: WorkspaceMember): string {
    return formatDate(member.created_at);
  }

  protected emailInvalid(): boolean {
    const control = this.form.controls.email;
    return control.invalid && control.touched;
  }
}

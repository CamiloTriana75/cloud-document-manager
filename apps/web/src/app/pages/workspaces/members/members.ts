import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import {
  FormBuilder,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { WorkspaceRole } from '../../../core/workspaces/workspace.models';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';

interface InviteMemberForm {
  email: FormControl<string>;
  role: FormControl<WorkspaceRole>;
}

@Component({
  selector: 'app-workspace-members',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
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

  readonly availableRoles = computed<WorkspaceRole[]>(() => {
    const callerRole = this.workspaceService.activeWorkspace()?.role;
    if (callerRole === 'OWNER') {
      return ['ADMIN', 'EDITOR', 'MEMBER', 'VIEWER'];
    }
    // Un ADMIN no puede nombrar un OWNER
    return ['ADMIN', 'EDITOR', 'MEMBER', 'VIEWER'];
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
        // El error ya lo maneja el signal workspaceService.error
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
}

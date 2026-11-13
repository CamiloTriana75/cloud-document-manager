import { CommonModule } from '@angular/common';
import { Component, input } from '@angular/core';

import { WorkspaceRole } from '../../../core/workspaces/workspace.models';

@Component({
  selector: 'app-role-badge',
  standalone: true,
  imports: [CommonModule],
  template: `
    <span
      class="role-badge"
      [ngClass]="'role-' + role().toLowerCase()"
      [attr.aria-label]="'Rol de usuario: ' + role()"
    >
      {{ role() }}
    </span>
  `,
  styles: [
    `
      :host {
        display: inline-block;
      }
    `,
  ],
})
export class RoleBadgeComponent {
  readonly role = input.required<WorkspaceRole>();
}

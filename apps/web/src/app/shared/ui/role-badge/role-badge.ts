import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { WorkspaceRole } from '../../../core/workspaces/workspace.models';

/** Rol del usuario en un workspace (ADR-0001). Conserva las clases `role-<rol>`. */
@Component({
  selector: 'app-role-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span
      class="role-badge role-{{ role().toLowerCase() }}"
      [attr.aria-label]="'Rol de usuario: ' + role()"
    >
      {{ role() }}
    </span>
  `,
  styles: `
    :host {
      display: inline-flex;
    }
    .role-badge {
      display: inline-flex;
      align-items: center;
      min-height: 1.5rem;
      padding: 0 var(--space-2);
      border: 1px solid var(--color-border-strong);
      border-radius: var(--radius-xs);
      background: var(--color-neutral-soft);
      color: var(--color-text-secondary);
      font-size: var(--text-xs);
      font-weight: var(--weight-medium);
      letter-spacing: 0.06em;
    }
    .role-owner,
    .role-admin {
      border-color: color-mix(in srgb, var(--color-accent) 35%, transparent);
      background: var(--color-accent-soft);
      color: var(--color-accent-text);
    }
    .role-editor {
      border-color: color-mix(in srgb, var(--color-info) 30%, transparent);
      background: var(--color-info-soft);
      color: var(--color-info);
    }
    .role-member {
      border-color: color-mix(in srgb, var(--color-positive) 28%, transparent);
      background: var(--color-positive-soft);
      color: var(--color-positive);
    }
  `,
})
export class RoleBadgeComponent {
  readonly role = input.required<WorkspaceRole>();
}

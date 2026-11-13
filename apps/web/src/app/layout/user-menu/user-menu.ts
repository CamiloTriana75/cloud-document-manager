import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

import { UserSession } from '../../core/auth/auth.models';
import { WorkspaceRole } from '../../core/workspaces/workspace.models';
import { AvatarComponent } from '../../shared/ui/avatar/avatar';
import { IconComponent } from '../../shared/ui/icon/icon';
import { MenuComponent, MenuItemDirective } from '../../shared/ui/menu/menu';
import { RoleBadgeComponent } from '../../shared/ui/role-badge/role-badge';

/** Avatar con menú: identidad, rol en el workspace activo y cierre de sesión. */
@Component({
  selector: 'app-user-menu',
  imports: [AvatarComponent, IconComponent, MenuComponent, MenuItemDirective, RoleBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-menu label="Menú de usuario" triggerClass="btn btn--icon avatar-trigger">
      <app-avatar menuTrigger [name]="displayName()" [size]="38" />

      <div class="menu__header user-card" role="presentation">
        <span class="user-name">{{ displayName() }}</span>
        <span class="user-email">{{ user().email }}</span>
        @if (role(); as activeRole) {
          <span class="user-role">
            <app-role-badge [role]="activeRole" />
            @if (workspaceName(); as name) {
              <span class="user-role__workspace">en {{ name }}</span>
            }
          </span>
        }
      </div>
      <div class="menu__separator" role="separator"></div>
      <button type="button" appMenuItem class="btn-logout" (click)="logout.emit()">
        <app-icon name="log-out" [size]="16" />
        Cerrar sesión
      </button>
    </app-menu>
  `,
  styles: `
    :host {
      display: inline-flex;
    }
    .user-card {
      display: grid;
      gap: 2px;
      min-width: 15rem;
    }
    .user-name {
      font-size: var(--text-md);
      color: var(--color-text);
    }
    .user-email {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .user-role {
      display: flex;
      align-items: center;
      gap: var(--space-2);
      margin-top: var(--space-2);
    }
    .user-role__workspace {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  `,
})
export class UserMenuComponent {
  readonly user = input.required<UserSession>();
  readonly role = input<WorkspaceRole | null>(null);
  readonly workspaceName = input<string | null>(null);

  readonly logout = output<void>();

  protected readonly displayName = computed(() => this.user().name || this.user().email);
}

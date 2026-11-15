import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { Workspace } from '../../core/workspaces/workspace.models';
import { WorkspaceService } from '../../core/workspaces/workspace.service';
import { IconComponent } from '../../shared/ui/icon/icon';
import { MenuComponent, MenuItemDirective } from '../../shared/ui/menu/menu';
import { RoleBadgeComponent } from '../../shared/ui/role-badge/role-badge';

/**
 * Selector del workspace activo. La selección del cliente solo cambia la vista: el backend
 * vuelve a verificar la membresía en cada petición (AGENTS.md §3.2).
 */
@Component({
  selector: 'app-workspace-switcher',
  imports: [RouterLink, IconComponent, MenuComponent, MenuItemDirective, RoleBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (workspaceService.activeWorkspace(); as active) {
      <app-menu
        [label]="'Espacio de trabajo: ' + active.name + '. Cambiar de espacio'"
        triggerClass="btn btn--secondary ws-trigger"
        align="end"
      >
        <span menuTrigger class="ws-trigger__content">
          <span class="ws-trigger__dot" aria-hidden="true"></span>
          <span class="ws-trigger__name">{{ active.name }}</span>
          <app-icon name="chevrons-up-down" [size]="16" />
        </span>

        <div class="menu__header" role="presentation">Tus espacios de trabajo</div>
        @for (workspace of workspaceService.workspaces(); track workspace.id) {
          <button
            type="button"
            appMenuItem
            menuRole="menuitemradio"
            [menuChecked]="workspace.id === active.id"
            (click)="select(workspace)"
          >
            <span class="ws-option__name">{{ workspace.name }}</span>
            <app-role-badge [role]="workspace.role" />
            <span class="ws-option__check">
              @if (workspace.id === active.id) {
                <app-icon name="check" [size]="16" />
              }
            </span>
          </button>
        }
        <div class="menu__separator" role="separator"></div>
        <button type="button" appMenuItem (click)="goTo(['/workspaces', active.id, 'members'])">
          <app-icon name="users" [size]="16" />
          Miembros y roles
        </button>
        <button type="button" appMenuItem (click)="goTo(['/workspaces/new'])">
          <app-icon name="plus" [size]="16" />
          Nuevo espacio de trabajo
        </button>
      </app-menu>
    } @else {
      <a routerLink="/workspaces/new" class="btn btn--secondary btn--sm">
        <app-icon name="plus" [size]="16" />
        Crear espacio
      </a>
    }
  `,
  styles: `
    :host {
      display: inline-flex;
      min-width: 0;
    }
    .ws-trigger__content {
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      min-width: 0;
    }
    .ws-trigger__dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--color-positive);
      box-shadow: 0 0 0 3px var(--color-positive-soft);
    }
    .ws-trigger__name {
      max-width: 11rem;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .ws-option__name {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .ws-option__check {
      display: inline-flex;
      width: 16px;
      color: var(--color-accent-text);
    }
  `,
})
export class WorkspaceSwitcherComponent {
  protected readonly workspaceService = inject(WorkspaceService);
  private readonly router = inject(Router);

  select(workspace: Workspace): void {
    this.workspaceService.setActiveWorkspace(workspace);
    const url = this.router.url;
    if (url.includes('/workspaces/')) {
      const section = url.includes('/members')
        ? 'members'
        : url.includes('/upload')
          ? 'upload'
          : 'documents';
      void this.router.navigate(['/workspaces', workspace.id, section]);
    }
  }

  protected goTo(commands: string[]): void {
    void this.router.navigate(commands);
  }
}

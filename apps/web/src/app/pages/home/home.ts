import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { HealthStatus } from '../../core/api/health';
import { HealthService } from '../../core/api/health.service';
import { AuthService } from '../../core/auth/auth.service';
import { Workspace } from '../../core/workspaces/workspace.models';
import { WorkspaceService } from '../../core/workspaces/workspace.service';
import { formatDate } from '../../shared/format/format-date';
import { CoilSceneComponent } from '../../shared/ui/coil-scene/coil-scene';
import { IconComponent } from '../../shared/ui/icon/icon';
import { RoleLadderComponent } from '../../shared/ui/role-ladder/role-ladder';
import { StatusBadgeComponent } from '../../shared/ui/status-badge/status-badge';

type HealthState = { kind: 'loading' } | { kind: 'ok'; data: HealthStatus } | { kind: 'error' };

/** Inicio: presentación del producto sin sesión; lanzador de workspaces con sesión. */
@Component({
  selector: 'app-home',
  imports: [RouterLink, CoilSceneComponent, IconComponent, RoleLadderComponent, StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './home.html',
  styleUrl: './home.css',
})
export class Home {
  private readonly healthService = inject(HealthService);
  private readonly router = inject(Router);
  protected readonly authService = inject(AuthService);
  protected readonly workspaceService = inject(WorkspaceService);

  protected readonly health = signal<HealthState>({ kind: 'loading' });
  protected readonly status = computed(() => {
    const state = this.health();
    return state.kind === 'ok' ? state.data : null;
  });
  protected readonly firstName = computed(() => {
    const user = this.authService.currentUser();
    const name = user?.name || user?.email.split('@')[0] || '';
    return name.split(/\s+/)[0];
  });

  constructor() {
    this.refresh();
  }

  refresh(): void {
    this.health.set({ kind: 'loading' });
    this.healthService.getStatus().subscribe({
      next: (data) => this.health.set({ kind: 'ok', data }),
      error: (error: unknown) => {
        if (error instanceof HttpErrorResponse) {
          this.health.set({ kind: 'error' });
        } else {
          throw error;
        }
      },
    });
  }

  protected since(workspace: Workspace): string {
    return formatDate(workspace.created_at);
  }

  protected open(workspace: Workspace): void {
    this.workspaceService.setActiveWorkspace(workspace);
    void this.router.navigate(['/workspaces', workspace.id, 'documents']);
  }
}

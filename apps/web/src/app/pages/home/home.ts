import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { RouterLink } from '@angular/router';

import { HealthService } from '../../core/api/health.service';
import { HealthStatus } from '../../core/api/health';
import { AuthService } from '../../core/auth/auth.service';
import { WorkspaceService } from '../../core/workspaces/workspace.service';

type HomeState =
  | { kind: 'loading' }
  | { kind: 'ok'; data: HealthStatus }
  | { kind: 'error' };

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './home.html',
  styleUrl: './home.css',
})
export class Home {
  private readonly healthService = inject(HealthService);
  readonly authService = inject(AuthService);
  readonly workspaceService = inject(WorkspaceService);

  readonly state = signal<HomeState>({ kind: 'loading' });
  readonly isLoading = computed(() => this.state().kind === 'loading');
  readonly isOk = computed(() => this.state().kind === 'ok');
  readonly isError = computed(() => this.state().kind === 'error');
  readonly status = computed(() => {
    const current = this.state();
    return current.kind === 'ok' ? current.data : null;
  });

  constructor() {
    this.refresh();
  }

  refresh(): void {
    this.state.set({ kind: 'loading' });
    this.healthService.getStatus().subscribe({
      next: (data) => this.state.set({ kind: 'ok', data }),
      error: (error: unknown) => {
        if (error instanceof HttpErrorResponse) {
          this.state.set({ kind: 'error' });
        } else {
          throw error;
        }
      },
    });
  }
}

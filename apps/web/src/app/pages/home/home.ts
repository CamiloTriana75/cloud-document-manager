import { Component, computed, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';

import { HealthService } from '../../core/api/health.service';
import { HealthStatus } from '../../core/api/health';

type HomeState =
  | { kind: 'loading' }
  | { kind: 'ok'; data: HealthStatus }
  | { kind: 'error' };

@Component({
  selector: 'app-home',
  templateUrl: './home.html',
  styleUrl: './home.css',
})
export class Home {
  private readonly healthService = inject(HealthService);

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

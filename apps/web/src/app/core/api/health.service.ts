/** Servicio de acceso a la API centralizado (AGENTS.md §9). */

import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

import { HealthStatus } from './health';

@Injectable({ providedIn: 'root' })
export class HealthService {
  private readonly http = inject(HttpClient);
  getStatus() {
    return this.http.get<HealthStatus>('/health');
  }
}

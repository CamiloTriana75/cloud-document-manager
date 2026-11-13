import { CommonModule } from '@angular/common';
import { Component, input } from '@angular/core';

import { DocumentStatus } from '../../../core/documents/document.models';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  imports: [CommonModule],
  template: `
    <span
      class="doc-status-badge"
      [ngClass]="'doc-status-' + status().toLowerCase()"
      [attr.aria-label]="'Estado del documento: ' + getLabel()"
    >
      @if (status() === 'PROCESSING' || (showPulse() && status() === 'UPLOADED')) {
        <span class="pulse-indicator" aria-hidden="true"></span>
      }
      {{ getLabel() }}
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
export class StatusBadgeComponent {
  readonly status = input.required<DocumentStatus>();
  readonly showPulse = input<boolean>(true);

  getLabel(): string {
    switch (this.status()) {
      case 'READY':
        return 'Listo';
      case 'PROCESSING':
        return 'Procesando';
      case 'UPLOADED':
        return 'Subido';
      case 'PENDING_UPLOAD':
        return 'Pendiente';
      case 'FAILED':
        return 'Fallido';
      case 'DELETED':
        return 'Eliminado';
      default:
        return this.status();
    }
  }
}

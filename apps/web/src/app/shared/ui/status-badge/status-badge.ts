import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { DOCUMENT_STATUS_META } from '../../../core/documents/document-status';
import { DocumentStatus } from '../../../core/documents/document.models';

const DOTS = [0, 1, 2] as const;

/**
 * Estado de procesamiento como tres puntos de avance (pendiente → subido/procesando → final)
 * más la etiqueta. Los estados en curso animan los puntos. Conserva las clases
 * `doc-status-<estado>` que usan las pruebas E2E.
 */
@Component({
  selector: 'app-status-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span
      class="doc-status-badge doc-status-{{ cssStatus() }}"
      [attr.data-tone]="meta().tone"
      [attr.aria-label]="'Estado del documento: ' + meta().label"
    >
      <span class="status-dots" [class.is-live]="meta().inFlight" aria-hidden="true">
        @for (dot of dots; track dot) {
          <i [class.is-on]="dot < filled()"></i>
        }
      </span>
      {{ meta().label }}
    </span>
  `,
  styles: `
    :host {
      display: inline-flex;
    }
    .doc-status-badge {
      --tone: var(--color-text-secondary);
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      font-size: var(--text-md);
      color: var(--color-text);
      white-space: nowrap;
    }
    .doc-status-badge[data-tone='positive'] {
      --tone: var(--color-positive);
    }
    .doc-status-badge[data-tone='accent'] {
      --tone: var(--color-accent);
    }
    .doc-status-badge[data-tone='info'] {
      --tone: var(--color-info);
    }
    .doc-status-badge[data-tone='warning'] {
      --tone: var(--color-warning);
    }
    .doc-status-badge[data-tone='danger'] {
      --tone: var(--color-danger);
    }
    .status-dots {
      display: inline-flex;
      gap: 3px;
    }
    .status-dots i {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.18);
    }
    .status-dots i.is-on {
      background: var(--tone);
    }
    .status-dots.is-live i.is-on:last-of-type,
    .status-dots.is-live i.is-on + i:not(.is-on) {
      animation: status-live 1.2s var(--ease-in-out) infinite;
    }
    @keyframes status-live {
      50% {
        opacity: 0.35;
      }
    }
  `,
})
export class StatusBadgeComponent {
  readonly status = input.required<DocumentStatus>();

  protected readonly dots = DOTS;
  protected readonly meta = computed(() => DOCUMENT_STATUS_META[this.status()]);
  protected readonly cssStatus = computed(() =>
    this.status() === 'PENDING_UPLOAD' ? 'pending' : this.status().toLowerCase(),
  );
  /** Pendiente 1 · Subido/Procesando 2 · Listo/Fallido 3 · Eliminado 0. */
  protected readonly filled = computed(() => {
    if (this.status() === 'DELETED') return 0;
    const step = this.meta().step;
    return step === 3 ? 3 : Math.min(step + 1, 2);
  });
}

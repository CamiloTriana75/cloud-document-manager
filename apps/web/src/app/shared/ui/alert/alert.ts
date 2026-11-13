import { CommonModule } from '@angular/common';
import { Component, input, output } from '@angular/core';

export type AlertType = 'info' | 'success' | 'warning' | 'danger';

@Component({
  selector: 'app-alert',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div
      class="alert alert-{{ type() }}"
      [attr.role]="type() === 'danger' || type() === 'warning' ? 'alert' : 'status'"
      [attr.aria-live]="type() === 'danger' ? 'assertive' : 'polite'"
    >
      <div class="alert-icon" aria-hidden="true">
        @switch (type()) {
          @case ('success') {
            ✓
          }
          @case ('danger') {
            ✕
          }
          @case ('warning') {
            ⚠
          }
          @default {
            ℹ
          }
        }
      </div>
      <div class="alert-content">
        <ng-content />
      </div>
      @if (dismissible()) {
        <button
          type="button"
          class="alert-close-btn"
          (click)="onDismiss()"
          aria-label="Cerrar notificación"
        >
          ✕
        </button>
      }
    </div>
  `,
  styles: [
    `
      .alert {
        display: flex;
        align-items: flex-start;
        gap: var(--space-3);
        padding: var(--space-3) var(--space-4);
        border-radius: var(--radius-sm);
        border: 1px solid transparent;
        font-size: var(--font-size-sm);
        line-height: 1.5;
        margin-bottom: var(--space-4);
      }
      .alert-icon {
        font-weight: 700;
        flex-shrink: 0;
        margin-top: 1px;
      }
      .alert-content {
        flex: 1;
      }
      .alert-close-btn {
        background: transparent;
        border: none;
        font-size: 1rem;
        cursor: pointer;
        padding: 0 4px;
        color: inherit;
        opacity: 0.7;
        margin-left: var(--space-2);
        border-radius: var(--radius-sm);
      }
      .alert-close-btn:hover {
        opacity: 1;
      }
      .alert-info {
        background-color: #eff6ff;
        border-color: #bfdbfe;
        color: #1e40af;
      }
      .alert-success {
        background-color: var(--color-success-bg);
        border-color: #86efac;
        color: var(--color-success);
      }
      .alert-warning {
        background-color: #fefce8;
        border-color: #fef08a;
        color: #854d0e;
      }
      .alert-danger {
        background-color: var(--color-danger-bg);
        border-color: #fca5a5;
        color: var(--color-danger);
      }
    `,
  ],
})
export class AlertComponent {
  readonly type = input<AlertType>('info');
  readonly dismissible = input<boolean>(false);
  readonly dismiss = output<void>();

  onDismiss(): void {
    this.dismiss.emit();
  }
}

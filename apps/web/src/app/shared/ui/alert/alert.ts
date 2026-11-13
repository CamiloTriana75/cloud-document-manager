import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

import { IconComponent } from '../icon/icon';
import { IconName } from '../icon/icons';

export type AlertType = 'info' | 'success' | 'warning' | 'danger';

const ALERT_ICON: Readonly<Record<AlertType, IconName>> = {
  info: 'info',
  success: 'check-circle',
  warning: 'alert-triangle',
  danger: 'alert-circle',
};

/** Mensaje en línea: `status` para información, `alert` para avisos y errores. */
@Component({
  selector: 'app-alert',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="alert alert-{{ type() }}"
      [attr.role]="type() === 'danger' || type() === 'warning' ? 'alert' : 'status'"
      [attr.aria-live]="type() === 'danger' ? 'assertive' : 'polite'"
    >
      <span class="alert-icon"><app-icon [name]="icon()" [size]="18" /></span>
      <div class="alert-content">
        <ng-content />
      </div>
      @if (dismissible()) {
        <button
          type="button"
          class="alert-close-btn btn btn--icon btn--sm"
          (click)="dismiss.emit()"
          aria-label="Cerrar notificación"
        >
          <app-icon name="x" [size]="16" />
        </button>
      }
    </div>
  `,
  styles: `
    :host {
      display: block;
    }
    .alert {
      --alert-tone: var(--color-info);
      --alert-soft: var(--color-info-soft);
      display: flex;
      align-items: flex-start;
      gap: var(--space-3);
      padding: var(--space-3) var(--space-4);
      border: 1px solid color-mix(in srgb, var(--alert-tone) 28%, transparent);
      border-radius: var(--radius-md);
      background: var(--alert-soft);
      color: var(--color-text);
      font-size: var(--text-md);
    }
    .alert-success {
      --alert-tone: var(--color-positive);
      --alert-soft: var(--color-positive-soft);
    }
    .alert-warning {
      --alert-tone: var(--color-warning);
      --alert-soft: var(--color-warning-soft);
    }
    .alert-danger {
      --alert-tone: var(--color-danger);
      --alert-soft: var(--color-danger-soft);
    }
    .alert-icon {
      display: inline-flex;
      margin-top: 1px;
      color: var(--alert-tone);
    }
    .alert-content {
      flex: 1;
      min-width: 0;
      line-height: var(--leading-normal);
    }
    .alert-close-btn {
      margin: -4px -6px -4px 0;
    }
  `,
})
export class AlertComponent {
  readonly type = input<AlertType>('info');
  readonly dismissible = input<boolean>(false);
  readonly dismiss = output<void>();

  protected readonly icon = computed(() => ALERT_ICON[this.type()]);
}

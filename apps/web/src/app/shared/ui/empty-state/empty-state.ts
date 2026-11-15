import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { IconComponent } from '../icon/icon';
import { IconName } from '../icon/icons';

/** Estado vacío que explica qué falta y ofrece la siguiente acción (proyectada). */
@Component({
  selector: 'app-empty-state',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="empty">
      <span class="empty__icon"><app-icon [name]="icon()" [size]="26" /></span>
      <h3 class="empty__title">{{ title() }}</h3>
      @if (description()) {
        <p class="empty__description">{{ description() }}</p>
      }
      <div class="empty__actions"><ng-content /></div>
    </div>
  `,
  styles: `
    :host {
      display: block;
    }
    .empty {
      display: grid;
      justify-items: center;
      gap: var(--space-3);
      padding: var(--space-12) var(--space-6);
      text-align: center;
    }
    .empty__icon {
      display: grid;
      place-items: center;
      width: 3.5rem;
      height: 3.5rem;
      margin-bottom: var(--space-1);
      border: 1px solid var(--color-border-strong);
      border-radius: var(--radius-md);
      background: var(--color-neutral-soft);
      color: var(--color-accent-text);
    }
    .empty__title {
      font-size: var(--text-lg);
      font-weight: var(--weight-regular);
    }
    .empty__description {
      max-width: 40ch;
      color: var(--color-text-secondary);
    }
    .empty__actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: var(--space-3);
      margin-top: var(--space-2);
    }
    .empty__actions:empty {
      display: none;
    }
  `,
})
export class EmptyStateComponent {
  readonly icon = input<IconName>('inbox');
  readonly title = input.required<string>();
  readonly description = input<string | null>(null);
}

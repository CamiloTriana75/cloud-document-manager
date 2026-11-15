import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

import { IconComponent } from '../icon/icon';

/** Métrica del dashboard: etiqueta, cifra, leyenda y una visualización proyectada (`[kpiVisual]`). */
@Component({
  selector: 'app-kpi-card',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <article class="kpi" [class.kpi--highlighted]="highlighted()" [attr.aria-busy]="loading()">
      <header class="kpi__header">
        <h3 class="kpi__label">{{ label() }}</h3>
        @if (actionLabel(); as actionText) {
          <button
            type="button"
            class="btn btn--icon btn--sm kpi__action"
            [attr.aria-label]="actionText"
            (click)="action.emit()"
          >
            <app-icon name="arrow-up-right" [size]="16" />
          </button>
        }
      </header>
      @if (loading() || value() !== null) {
        <div class="kpi__body">
          <div class="kpi__figure">
            @if (loading()) {
              <span class="skeleton kpi__skeleton"></span>
              <span class="skeleton kpi__skeleton kpi__skeleton--short"></span>
            } @else {
              <p class="kpi__value tabular">
                {{ value() }}@if (unit()) {<span class="kpi__unit">{{ unit() }}</span>}
              </p>
              @if (caption()) {
                <p class="kpi__caption" [class.kpi__caption--positive]="captionTone() === 'positive'">
                  {{ caption() }}
                </p>
              }
            }
          </div>
          <div class="kpi__visual"><ng-content select="[kpiVisual]" /></div>
        </div>
      }
      <div class="kpi__detail"><ng-content select="[kpiDetail]" /></div>
    </article>
  `,
  styles: `
    :host {
      display: block;
      min-width: 0;
    }
    .kpi {
      display: grid;
      gap: var(--space-3);
      height: 100%;
      padding: var(--space-4) var(--space-5) var(--space-5);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      background: var(--color-card);
      box-shadow: var(--shadow-card), var(--inset-highlight);
      transition: background-color var(--duration-base) var(--ease-out);
    }
    .kpi--highlighted {
      background: var(--color-card-raised);
      border-color: var(--color-border-strong);
    }
    .kpi__header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-2);
      min-height: 2rem;
    }
    .kpi__label {
      font-size: var(--text-base);
      font-weight: var(--weight-regular);
      color: var(--color-text);
    }
    .kpi__action {
      margin-right: calc(var(--space-2) * -1);
    }
    .kpi__body {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: var(--space-3);
    }
    .kpi__figure {
      display: grid;
      gap: var(--space-1);
      min-width: 0;
    }
    .kpi__value {
      font-size: var(--text-metric);
      font-weight: var(--weight-light);
      line-height: 1;
      letter-spacing: var(--tracking-metric);
    }
    .kpi__unit {
      margin-left: 2px;
      font-size: 0.45em;
      font-weight: var(--weight-regular);
      letter-spacing: 0;
      color: var(--color-text-secondary);
    }
    .kpi__caption {
      font-size: var(--text-sm);
      color: var(--color-text-secondary);
    }
    .kpi__caption--positive {
      color: var(--color-positive);
    }
    .kpi__skeleton {
      width: 5.5rem;
      height: 2.5rem;
    }
    .kpi__skeleton--short {
      width: 8rem;
      height: 0.875rem;
    }
    .kpi__visual:empty,
    .kpi__detail:empty {
      display: none;
    }
  `,
})
export class KpiCardComponent {
  readonly label = input.required<string>();
  readonly value = input<string | number | null>(null);
  readonly unit = input<string | null>(null);
  readonly caption = input<string | null>(null);
  readonly captionTone = input<'positive' | 'neutral'>('neutral');
  readonly highlighted = input(false);
  readonly loading = input(false);
  readonly actionLabel = input<string | null>(null);

  readonly action = output<void>();
}

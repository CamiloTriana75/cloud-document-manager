import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { StatusTone } from '../../../core/documents/document-status';

export interface BarSegment {
  readonly value: number;
  readonly tone: StatusTone;
  readonly label: string;
}

/** Barra proporcional segmentada; el desglose completo va en el nombre accesible. */
@Component({
  selector: 'app-segmented-bar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    role: 'img',
    '[attr.aria-label]': 'ariaLabel()',
  },
  template: `
    @for (part of parts(); track part.label) {
      <span class="segment" [attr.data-tone]="part.tone" [style.flex-grow]="part.value"></span>
    }
  `,
  styles: `
    :host {
      display: flex;
      gap: 3px;
      height: 8px;
      border-radius: var(--radius-pill);
      background: var(--color-track);
      overflow: hidden;
    }
    .segment {
      flex-basis: 0;
      min-width: 6px;
      border-radius: var(--radius-pill);
      background: var(--color-track);
      transition: flex-grow var(--duration-slow) var(--ease-out);
    }
    .segment[data-tone='positive'] {
      background: var(--color-positive);
    }
    .segment[data-tone='accent'] {
      background: var(--color-accent);
    }
    .segment[data-tone='warning'] {
      background: var(--color-warning);
    }
    .segment[data-tone='danger'] {
      background: var(--color-danger);
    }
    .segment[data-tone='info'] {
      background: var(--color-info);
    }
    .segment[data-tone='neutral'] {
      background: rgba(255, 255, 255, 0.22);
    }
  `,
})
export class SegmentedBarComponent {
  readonly segments = input.required<readonly BarSegment[]>();
  readonly label = input.required<string>();

  protected readonly parts = computed(() => this.segments().filter((s) => s.value > 0));

  protected readonly ariaLabel = computed(() => {
    const parts = this.parts();
    const total = parts.reduce((sum, part) => sum + part.value, 0);
    if (total === 0) {
      return `${this.label()}: sin datos`;
    }
    const detail = parts
      .map((part) => `${part.label} ${Math.round((part.value / total) * 100)} %`)
      .join(', ');
    return `${this.label()}: ${detail}`;
  });
}

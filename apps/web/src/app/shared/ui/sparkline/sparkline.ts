import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

const WIDTH = 100;
const HEIGHT = 32;
const PADDING = 3;

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

/**
 * Serie temporal mínima (p. ej. cargas por día). Sin gradientes con `url(#id)`:
 * con `<base href>` esas referencias se rompen al cambiar de ruta.
 */
@Component({
  selector: 'app-sparkline',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[attr.data-tone]': 'tone()' },
  template: `
    <svg
      [attr.viewBox]="viewBox"
      preserveAspectRatio="none"
      role="img"
      [attr.aria-label]="label()"
      focusable="false"
    >
      <path class="sparkline__area" [attr.d]="areaPath()" />
      <path class="sparkline__line" [attr.d]="linePath()" vector-effect="non-scaling-stroke" />
    </svg>
  `,
  styles: `
    :host {
      --spark: var(--color-positive);
      display: block;
      width: 5.5rem;
      height: 2rem;
    }
    :host([data-tone='accent']) {
      --spark: var(--color-accent);
    }
    :host([data-tone='neutral']) {
      --spark: var(--color-text-tertiary);
    }
    svg {
      width: 100%;
      height: 100%;
      overflow: visible;
    }
    .sparkline__area {
      fill: var(--spark);
      fill-opacity: 0.12;
      stroke: none;
    }
    .sparkline__line {
      fill: none;
      stroke: var(--spark);
      stroke-width: 1.5;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
  `,
})
export class SparklineComponent {
  readonly points = input.required<readonly number[]>();
  readonly label = input.required<string>();
  readonly tone = input<'positive' | 'accent' | 'neutral'>('positive');

  protected readonly viewBox = `0 0 ${WIDTH} ${HEIGHT}`;

  private readonly coordinates = computed<[number, number][]>(() => {
    const values = this.points().length > 0 ? [...this.points()] : [0];
    const series = values.length === 1 ? [values[0], values[0]] : values;
    const min = Math.min(...series);
    const max = Math.max(...series);
    const span = max - min;
    const step = WIDTH / (series.length - 1);
    return series.map((value, index) => {
      const ratio = span === 0 ? 0 : (value - min) / span;
      return [round(index * step), round(HEIGHT - PADDING - ratio * (HEIGHT - PADDING * 2))];
    });
  });

  protected readonly linePath = computed(() =>
    this.coordinates()
      .map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${x},${y}`)
      .join(' '),
  );

  protected readonly areaPath = computed(
    () => `${this.linePath()} L${WIDTH},${HEIGHT} L0,${HEIGHT} Z`,
  );
}

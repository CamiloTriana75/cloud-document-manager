import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { ICONS, IconName, IconNode } from './icons';

/**
 * Icono de trazo decorativo. El significado accesible lo aporta siempre el control
 * o el texto que lo acompaña; el icono queda oculto para lectores de pantalla.
 * Renderiza nodos SVG tipados (sin innerHTML).
 */
@Component({
  selector: 'app-icon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'icon',
    'aria-hidden': 'true',
  },
  template: `
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-linecap="round"
      stroke-linejoin="round"
      focusable="false"
      [attr.width]="size()"
      [attr.height]="size()"
      [attr.stroke-width]="strokeWidth()"
    >
      @for (node of nodes(); track $index) {
        @switch (node[0]) {
          @case ('path') {
            <svg:path [attr.d]="node[1]['d']" />
          }
          @case ('circle') {
            <svg:circle [attr.cx]="node[1]['cx']" [attr.cy]="node[1]['cy']" [attr.r]="node[1]['r']" />
          }
          @case ('line') {
            <svg:line
              [attr.x1]="node[1]['x1']"
              [attr.y1]="node[1]['y1']"
              [attr.x2]="node[1]['x2']"
              [attr.y2]="node[1]['y2']"
            />
          }
          @case ('polyline') {
            <svg:polyline [attr.points]="node[1]['points']" />
          }
          @case ('rect') {
            <svg:rect
              [attr.x]="node[1]['x']"
              [attr.y]="node[1]['y']"
              [attr.width]="node[1]['width']"
              [attr.height]="node[1]['height']"
              [attr.rx]="node[1]['rx']"
              [attr.ry]="node[1]['ry']"
            />
          }
        }
      }
    </svg>
  `,
  styles: `
    :host {
      display: inline-flex;
      flex-shrink: 0;
      line-height: 0;
    }
  `,
})
export class IconComponent {
  readonly name = input.required<IconName>();
  readonly size = input(18);
  readonly strokeWidth = input(1.75);

  protected readonly nodes = computed<readonly IconNode[]>(() => ICONS[this.name()]);
}

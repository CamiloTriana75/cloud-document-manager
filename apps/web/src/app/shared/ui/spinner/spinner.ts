import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Indicador de actividad breve (botones, acciones). Para contenido que carga, usar `.skeleton`. */
@Component({
  selector: 'app-spinner',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="spinner spinner-{{ size() }}" role="status" [attr.aria-label]="label()">
      <span class="sr-only">{{ label() }}</span>
    </span>
  `,
  styles: `
    :host {
      display: inline-flex;
    }
    .spinner {
      display: inline-block;
      border-radius: 50%;
      border: 2px solid rgba(255, 255, 255, 0.16);
      border-top-color: currentColor;
      animation: spin 0.8s linear infinite;
    }
    .spinner-sm {
      width: 14px;
      height: 14px;
    }
    .spinner-md {
      width: 20px;
      height: 20px;
    }
    .spinner-lg {
      width: 32px;
      height: 32px;
      border-width: 3px;
    }
    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }
  `,
})
export class SpinnerComponent {
  readonly size = input<'sm' | 'md' | 'lg'>('md');
  readonly label = input<string>('Cargando contenido...');
}

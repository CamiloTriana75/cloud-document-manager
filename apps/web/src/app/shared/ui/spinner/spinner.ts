import { CommonModule } from '@angular/common';
import { Component, input } from '@angular/core';

@Component({
  selector: 'app-spinner',
  standalone: true,
  imports: [CommonModule],
  template: `
    <span
      class="spinner spinner-{{ size() }}"
      role="status"
      [attr.aria-label]="label()"
    >
      <span class="sr-only">{{ label() }}</span>
    </span>
  `,
  styles: [
    `
      .spinner {
        display: inline-block;
        border-radius: 50%;
        border: 2px solid var(--color-border);
        border-top-color: var(--color-primary);
        animation: spin 0.8s linear infinite;
        vertical-align: middle;
      }
      .spinner-sm {
        width: 16px;
        height: 16px;
        border-width: 2px;
      }
      .spinner-md {
        width: 24px;
        height: 24px;
        border-width: 2.5px;
      }
      .spinner-lg {
        width: 36px;
        height: 36px;
        border-width: 3px;
      }
      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }
    `,
  ],
})
export class SpinnerComponent {
  readonly size = input<'sm' | 'md' | 'lg'>('md');
  readonly label = input<string>('Cargando contenido...');
}

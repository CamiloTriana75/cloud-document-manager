import { CommonModule } from '@angular/common';
import { Component, input } from '@angular/core';

@Component({
  selector: 'app-form-error',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (message()) {
      <p class="form-error-msg" [id]="id()" role="alert" aria-live="polite">
        <span class="error-bullet" aria-hidden="true">⚠</span>
        <span>{{ message() }}</span>
      </p>
    }
  `,
  styles: [
    `
      .form-error-msg {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        margin: var(--space-1) 0 0 0;
        font-size: var(--font-size-sm);
        color: var(--color-danger);
      }
      .error-bullet {
        font-size: 0.875rem;
      }
    `,
  ],
})
export class FormErrorComponent {
  readonly message = input<string | null>(null);
  readonly id = input<string>('');
}

import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { IconComponent } from '../icon/icon';

/** Error de campo asociado por `id` (el control lo referencia con aria-describedby). */
@Component({
  selector: 'app-form-error',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (message()) {
      <p class="form-error-msg field__error" [id]="id()" role="alert" aria-live="polite">
        <app-icon name="alert-circle" [size]="15" />
        <span>{{ message() }}</span>
      </p>
    }
  `,
  styles: `
    :host {
      display: block;
    }
    .form-error-msg {
      margin: 0;
    }
  `,
})
export class FormErrorComponent {
  readonly message = input<string | null>(null);
  readonly id = input<string>('');
}

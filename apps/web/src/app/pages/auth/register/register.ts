import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  ValidatorFn,
  Validators,
} from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../../core/auth/auth.service';
import { AlertComponent } from '../../../shared/ui/alert/alert';
import { IconComponent } from '../../../shared/ui/icon/icon';
import { AuthLayoutComponent } from '../auth-layout/auth-layout';

const passwordMatchValidator: ValidatorFn = (control: AbstractControl): ValidationErrors | null => {
  const password = control.get('password');
  const confirmPassword = control.get('confirmPassword');

  if (password && confirmPassword && password.value !== confirmPassword.value) {
    return { passwordMismatch: true };
  }
  return null;
};

/** Requisitos de contraseña de la política de Cognito, mostrados en vivo. */
const PASSWORD_RULES: readonly { readonly label: string; readonly test: (value: string) => boolean }[] = [
  { label: 'Al menos 8 caracteres', test: (value) => value.length >= 8 },
  { label: 'Una letra minúscula', test: (value) => /[a-z]/.test(value) },
  { label: 'Una letra mayúscula', test: (value) => /[A-Z]/.test(value) },
  { label: 'Un número', test: (value) => /\d/.test(value) },
  { label: 'Un símbolo', test: (value) => /[\W_]/.test(value) },
];

@Component({
  selector: 'app-register',
  imports: [ReactiveFormsModule, RouterLink, AlertComponent, AuthLayoutComponent, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './register.html',
  styleUrls: ['../auth-form.css', './register.css'],
})
export class RegisterComponent {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  readonly errorMessage = signal<string | null>(null);
  readonly isSubmitting = signal<boolean>(false);
  readonly showPassword = signal(false);

  readonly form = this.fb.group(
    {
      name: ['', [Validators.required, Validators.minLength(2)]],
      email: ['', [Validators.required, Validators.email]],
      password: [
        '',
        [
          Validators.required,
          Validators.minLength(8),
          Validators.pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).+$/),
        ],
      ],
      confirmPassword: ['', [Validators.required]],
    },
    { validators: passwordMatchValidator },
  );

  private readonly password = toSignal(this.form.controls.password.valueChanges, {
    initialValue: '',
  });

  protected readonly rules = computed(() => {
    const value = this.password() ?? '';
    return PASSWORD_RULES.map((rule) => ({ label: rule.label, met: rule.test(value) }));
  });

  togglePassword(): void {
    this.showPassword.update((visible) => !visible);
  }

  invalid(control: 'name' | 'email' | 'password' | 'confirmPassword'): boolean {
    const field = this.form.controls[control];
    return field.invalid && field.touched;
  }

  mismatch(): boolean {
    return this.form.hasError('passwordMismatch') && !!this.form.controls.confirmPassword.touched;
  }

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.errorMessage.set(null);
    this.isSubmitting.set(true);

    const { name, email, password } = this.form.getRawValue();

    this.authService.register({ name: name!, email: email!, password: password! }).subscribe({
      next: ({ userConfirmed }) => {
        if (!userConfirmed) {
          // Cognito envió un código al correo: la cuenta se activa al confirmarlo (CDM-133)
          this.isSubmitting.set(false);
          void this.router.navigate(['/auth/confirm'], { queryParams: { email } });
          return;
        }
        this.authService.login({ email: email!, password: password! }).subscribe({
          next: () => {
            this.isSubmitting.set(false);
            void this.router.navigate(['/']);
          },
          error: () => {
            this.isSubmitting.set(false);
            void this.router.navigate(['/auth/login'], {
              queryParams: { registered: 'true', email },
            });
          },
        });
      },
      error: (err) => {
        this.isSubmitting.set(false);
        this.errorMessage.set(err.message || 'Error al registrar usuario.');
      },
    });
  }
}

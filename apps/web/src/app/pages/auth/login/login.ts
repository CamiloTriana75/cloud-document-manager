import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AuthError } from '../../../core/auth/auth-errors';
import { AuthService } from '../../../core/auth/auth.service';
import { AlertComponent } from '../../../shared/ui/alert/alert';
import { IconComponent } from '../../../shared/ui/icon/icon';
import { AuthLayoutComponent } from '../auth-layout/auth-layout';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, RouterLink, AlertComponent, AuthLayoutComponent, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login.html',
  styleUrls: ['../auth-form.css'],
})
export class LoginComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly errorMessage = signal<string | null>(null);
  readonly successMessage = signal<string | null>(null);
  readonly isSubmitting = signal<boolean>(false);
  readonly showPassword = signal(false);

  readonly form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(6)]],
  });

  ngOnInit(): void {
    const { registered, confirmed, email } = this.route.snapshot.queryParams;
    if (confirmed === 'true') {
      this.successMessage.set('Cuenta confirmada. Ya puedes iniciar sesión.');
    } else if (registered === 'true') {
      this.successMessage.set('¡Cuenta creada exitosamente! Ya puedes iniciar sesión.');
    }
    if (email && (confirmed === 'true' || registered === 'true')) {
      this.form.patchValue({ email });
    }
  }

  togglePassword(): void {
    this.showPassword.update((visible) => !visible);
  }

  invalid(control: 'email' | 'password'): boolean {
    const field = this.form.controls[control];
    return field.invalid && field.touched;
  }

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.errorMessage.set(null);
    this.isSubmitting.set(true);

    const { email, password } = this.form.getRawValue();

    this.authService.login({ email: email!, password: password! }).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        const returnUrl = this.route.snapshot.queryParams['returnUrl'] || '/';
        void this.router.navigateByUrl(returnUrl);
      },
      error: (err: unknown) => {
        this.isSubmitting.set(false);
        if (err instanceof AuthError && err.code === 'user-not-confirmed') {
          void this.router.navigate(['/auth/confirm'], { queryParams: { email } });
          return;
        }
        this.errorMessage.set(err instanceof Error ? err.message : 'Error al iniciar sesión.');
      },
    });
  }
}

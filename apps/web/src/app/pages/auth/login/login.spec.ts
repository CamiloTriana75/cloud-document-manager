import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter, Router } from '@angular/router';
import { throwError } from 'rxjs';
import { describe, expect, it, beforeEach, vi } from 'vitest';

import { AuthError } from '../../../core/auth/auth-errors';
import { AuthService } from '../../../core/auth/auth.service';
import { LoginComponent } from './login';

describe('LoginComponent', () => {
  let component: LoginComponent;
  let fixture: ComponentFixture<LoginComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(LoginComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('debe crearse correctamente con formulario vacío', () => {
    expect(component).toBeTruthy();
    expect(component.form.valid).toBe(false);
  });

  it('debe validar correo electrónico', () => {
    const emailCtrl = component.form.get('email');
    emailCtrl?.setValue('invalido');
    expect(emailCtrl?.valid).toBe(false);

    emailCtrl?.setValue('usuario@cdm.com');
    expect(emailCtrl?.valid).toBe(true);
  });

  it('no debe enviar el formulario si es inválido', () => {
    component.onSubmit();
    expect(component.isSubmitting()).toBe(false);
  });

  it('permite mostrar y ocultar la contraseña sin nombre ambiguo (CDM-127)', () => {
    const el = fixture.nativeElement as HTMLElement;
    const input = el.querySelector('#password') as HTMLInputElement;
    const toggle = el.querySelector('button[aria-controls="password"]') as HTMLButtonElement;

    expect(input.type).toBe('password');
    expect(toggle.getAttribute('aria-label')).toBeNull();
    toggle.click();
    fixture.detectChanges();
    expect(input.type).toBe('text');
    expect(toggle.getAttribute('aria-pressed')).toBe('true');
  });

  it('no anida un <main> dentro del shell (CDM-127)', () => {
    expect((fixture.nativeElement as HTMLElement).querySelector('main')).toBeNull();
  });

  it('si la cuenta no está confirmada, lleva a la pantalla de código (CDM-133)', () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    vi.spyOn(TestBed.inject(AuthService), 'login').mockReturnValue(
      throwError(() => new AuthError('user-not-confirmed', 'Tu cuenta aún no ha sido confirmada.')),
    );
    component.form.setValue({ email: 'ana@empresa.com', password: 'Segura123!' });

    component.onSubmit();

    expect(navigate).toHaveBeenCalledWith(['/auth/confirm'], {
      queryParams: { email: 'ana@empresa.com' },
    });
  });

  it('tras confirmar la cuenta muestra el aviso y precarga el correo (CDM-133)', () => {
    const route = TestBed.inject(ActivatedRoute);
    route.snapshot.queryParams = { confirmed: 'true', email: 'ana@empresa.com' };

    component.ngOnInit();

    expect(component.successMessage()).toContain('confirmada');
    expect(component.form.controls.email.value).toBe('ana@empresa.com');
  });
});

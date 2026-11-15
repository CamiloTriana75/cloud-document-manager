import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { describe, expect, it, beforeEach, vi } from 'vitest';

import { AuthService } from '../../../core/auth/auth.service';
import { ConfirmComponent } from './confirm';

describe('ConfirmComponent', () => {
  let component: ConfirmComponent;
  let fixture: ComponentFixture<ConfirmComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ConfirmComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(ConfirmComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('debe crearse correctamente con formulario vacío', () => {
    expect(component).toBeTruthy();
    expect(component.form.valid).toBe(false);
  });

  it('debe validar código de 6 dígitos numéricos', () => {
    const codeCtrl = component.form.get('code');
    codeCtrl?.setValue('123');
    expect(codeCtrl?.valid).toBe(false);

    codeCtrl?.setValue('12345a');
    expect(codeCtrl?.valid).toBe(false);

    codeCtrl?.setValue('123456');
    expect(codeCtrl?.valid).toBe(true);
  });

  it('reenvía el código al correo indicado (CDM-133)', () => {
    const resend = vi
      .spyOn(TestBed.inject(AuthService), 'resendConfirmationCode')
      .mockReturnValue(of(void 0));
    component.form.controls.email.setValue('ana@empresa.com');

    component.resendCode();

    expect(resend).toHaveBeenCalledWith('ana@empresa.com');
    expect(component.successMessage()).toContain('nuevo código');
  });

  it('tras confirmar vuelve al login con el correo precargado (CDM-133)', () => {
    vi.useFakeTimers();
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    vi.spyOn(TestBed.inject(AuthService), 'confirmRegistration').mockReturnValue(of(void 0));
    component.form.setValue({ email: 'ana@empresa.com', code: '123456' });

    component.onSubmit();
    vi.runAllTimers();
    vi.useRealTimers();

    expect(navigate).toHaveBeenCalledWith(['/auth/login'], {
      queryParams: { confirmed: 'true', email: 'ana@empresa.com' },
    });
  });
});

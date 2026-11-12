import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it, beforeEach } from 'vitest';

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
});

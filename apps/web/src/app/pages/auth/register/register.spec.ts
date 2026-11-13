import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it, beforeEach } from 'vitest';

import { RegisterComponent } from './register';

describe('RegisterComponent', () => {
  let component: RegisterComponent;
  let fixture: ComponentFixture<RegisterComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RegisterComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(RegisterComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('debe crearse correctamente con formulario vacío', () => {
    expect(component).toBeTruthy();
    expect(component.form.valid).toBe(false);
  });

  it('debe validar coincidencia de contraseñas', () => {
    component.form.patchValue({
      name: 'Test',
      email: 'test@example.com',
      password: 'Password123!',
      confirmPassword: 'DiferentePassword!',
    });

    expect(component.form.hasError('passwordMismatch')).toBe(true);

    component.form.patchValue({ confirmPassword: 'Password123!' });
    expect(component.form.hasError('passwordMismatch')).toBe(false);
  });
});

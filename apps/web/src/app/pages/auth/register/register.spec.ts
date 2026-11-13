import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { describe, expect, it, beforeEach, vi } from 'vitest';

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

  it('marca en vivo los requisitos de contraseña cumplidos (CDM-127)', () => {
    const el = fixture.nativeElement as HTMLElement;
    const input = el.querySelector('#password') as HTMLInputElement;
    input.value = 'abc1';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const met = Array.from(el.querySelectorAll('.rules li.is-met')).map((li) => li.textContent?.trim());
    expect(met).toEqual(expect.arrayContaining([expect.stringContaining('minúscula'), expect.stringContaining('número')]));
    expect(el.querySelectorAll('.rules li:not(.is-met)').length).toBe(3);
  });

  it('tras registrarse e iniciar sesión vuelve al inicio (CDM-127)', () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    component.form.setValue({
      name: 'Ana Pérez',
      email: 'ana@empresa.com',
      password: 'Segura123!',
      confirmPassword: 'Segura123!',
    });

    component.onSubmit();

    expect(navigate).toHaveBeenCalledWith(['/']);
  });
});

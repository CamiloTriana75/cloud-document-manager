import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it, beforeEach } from 'vitest';

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
});

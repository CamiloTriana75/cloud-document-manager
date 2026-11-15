import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { AuthLayoutComponent } from './auth-layout';

@Component({
  imports: [AuthLayoutComponent],
  template: `<app-auth-layout><h1>Iniciar sesión</h1></app-auth-layout>`,
})
class HostComponent {}

describe('AuthLayoutComponent', () => {
  it('proyecta el formulario junto al panel visual sin crear un <main>', () => {
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('.auth__form h1')?.textContent).toBe('Iniciar sesión');
    expect(el.querySelector('app-coil-scene')).toBeTruthy();
    expect(el.querySelector('main')).toBeNull();
  });
});

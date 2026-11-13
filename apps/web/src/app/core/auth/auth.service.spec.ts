import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { describe, expect, it, beforeEach } from 'vitest';

import { AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), AuthService],
    });
    service = TestBed.inject(AuthService);
  });

  it('debe iniciar sin usuario autenticado', () => {
    expect(service.currentUser()).toBeNull();
    expect(service.isAuthenticated()).toBe(false);
  });

  it('debe iniciar sesión exitosamente en modo mock y persistir tokens', async () => {
    const authResponse = await firstValueFrom(
      service.login({ email: 'test@example.com', password: 'Password123!' })
    );

    expect(authResponse.user.email).toBe('test@example.com');
    expect(service.isAuthenticated()).toBe(true);
    expect(service.currentUser()?.email).toBe('test@example.com');
    expect(service.getAccessToken()).toContain('mock-access-token');
  });

  it('debe rechazar credenciales inválidas sin revelar existencia de usuario', async () => {
    let errorMessage = '';
    try {
      await firstValueFrom(service.login({ email: 'bad-email', password: '123' }));
    } catch (err: unknown) {
      errorMessage = (err as Error).message;
    }

    expect(errorMessage).toBe('Correo electrónico o contraseña incorrectos.');
    expect(service.isAuthenticated()).toBe(false);
  });

  it('debe registrar un nuevo usuario con éxito', async () => {
    await expect(
      firstValueFrom(
        service.register({
          email: 'nuevo@example.com',
          password: 'Password123!',
          name: 'Nuevo Usuario',
        })
      )
    ).resolves.toBeUndefined();
  });

  it('debe confirmar el código de verificación de 6 dígitos', async () => {
    await expect(
      firstValueFrom(
        service.confirmRegistration({ email: 'nuevo@example.com', code: '123456' })
      )
    ).resolves.toBeUndefined();
  });

  it('debe cerrar sesión y limpiar storage', async () => {
    await firstValueFrom(
      service.login({ email: 'test@example.com', password: 'Password123!' })
    );
    expect(service.isAuthenticated()).toBe(true);

    service.logout();
    expect(service.isAuthenticated()).toBe(false);
    expect(service.currentUser()).toBeNull();
    expect(service.getAccessToken()).toBeNull();
  });
});

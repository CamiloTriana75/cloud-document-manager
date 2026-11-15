import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { COGNITO_CONFIG } from './auth-config';
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
    expect(service.getIdToken()).toContain('mock-id-token');
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
    ).resolves.toEqual({ userConfirmed: true });
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
    expect(service.getIdToken()).toBeNull();
  });
});

/** JWT de prueba con payload base64url y UTF-8, como los emite Cognito. */
function cognitoLikeJwt(payload: Record<string, unknown>): string {
  const base64Url = (value: string) =>
    btoa(String.fromCharCode(...new TextEncoder().encode(value)))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
  return `${base64Url(JSON.stringify({ alg: 'RS256', kid: 'k1' }))}.${base64Url(JSON.stringify(payload))}.firma`;
}

describe('AuthService con Cognito configurado (CDM-133)', () => {
  const COGNITO_URL = 'https://cognito-idp.us-east-1.amazonaws.com/';
  let service: AuthService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        AuthService,
        {
          provide: COGNITO_CONFIG,
          useValue: { region: 'us-east-1', userPoolId: 'us-east-1_Pool', clientId: 'client-123', domain: '' },
        },
      ],
    });
    service = TestBed.inject(AuthService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpTesting.verify());

  it('el registro informa si Cognito exige confirmar la cuenta', async () => {
    const result = firstValueFrom(
      service.register({ email: 'ana@empresa.com', password: 'Segura123!', name: 'Ana' }),
    );

    const req = httpTesting.expectOne(COGNITO_URL);
    expect(req.request.headers.get('X-Amz-Target')).toBe('AWSCognitoIdentityProviderService.SignUp');
    req.flush({ UserConfirmed: false, UserSub: 'sub-1' });

    await expect(result).resolves.toEqual({ userConfirmed: false });
  });

  it('el login de una cuenta sin confirmar devuelve un error tipado', async () => {
    const result = firstValueFrom(service.login({ email: 'ana@empresa.com', password: 'Segura123!' }));

    httpTesting
      .expectOne(COGNITO_URL)
      .flush(
        { __type: 'UserNotConfirmedException', message: 'User is not confirmed.' },
        { status: 400, statusText: 'Bad Request' },
      );

    await expect(result).rejects.toMatchObject({ code: 'user-not-confirmed' });
  });

  it('usa el ID token para la API y decodifica claims base64url con UTF-8', async () => {
    const idToken = cognitoLikeJwt({
      sub: 'sub-123',
      email: 'ana.pena@empresa.com',
      name: 'Ana Peña ¿?',
      email_verified: true,
      token_use: 'id',
    });
    const result = firstValueFrom(service.login({ email: 'ana.pena@empresa.com', password: 'Segura123!' }));

    httpTesting.expectOne(COGNITO_URL).flush({
      AuthenticationResult: { AccessToken: 'access-jwt', IdToken: idToken, RefreshToken: 'r', ExpiresIn: 3600 },
    });
    const response = await result;

    expect(service.getIdToken()).toBe(idToken);
    expect(response.user).toEqual({
      sub: 'sub-123',
      email: 'ana.pena@empresa.com',
      name: 'Ana Peña ¿?',
      emailVerified: true,
    });
  });

  it('reenvía el código de confirmación', async () => {
    const result = firstValueFrom(service.resendConfirmationCode('ana@empresa.com'));

    const req = httpTesting.expectOne(COGNITO_URL);
    expect(req.request.headers.get('X-Amz-Target')).toBe(
      'AWSCognitoIdentityProviderService.ResendConfirmationCode',
    );
    expect(req.request.body).toEqual({ ClientId: 'client-123', Username: 'ana@empresa.com' });
    req.flush({ CodeDeliveryDetails: { DeliveryMedium: 'EMAIL' } });

    await expect(result).resolves.toBeUndefined();
  });
});

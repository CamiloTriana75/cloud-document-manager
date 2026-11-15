import { HttpClient, HttpHeaders } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { finalize, map, Observable, of, catchError, tap, throwError } from 'rxjs';

import { COGNITO_CONFIG } from './auth-config';
import { AuthError } from './auth-errors';
import {
  AuthResponse,
  AuthTokens,
  ConfirmRegistrationData,
  LoginCredentials,
  RegisterData,
  RegisterResult,
  UserSession,
} from './auth.models';
import { decodeJwtPayload } from './jwt';

const STORAGE_KEY = 'cdm_auth_tokens';

interface CognitoAuthResult {
  AccessToken: string;
  IdToken: string;
  RefreshToken?: string;
  ExpiresIn?: number;
}

interface CognitoInitiateAuthResponse {
  AuthenticationResult?: CognitoAuthResult;
}

interface CognitoSignUpResponse {
  UserConfirmed?: boolean;
}

/**
 * Autenticación contra Amazon Cognito (User Pool, flujo USER_PASSWORD_AUTH) y sesión local.
 *
 * Sin `clientId` configurado funciona en modo de desarrollo local con tokens sin firma,
 * que el backend solo acepta con CDM_AUTH_MOCK_ENABLED=true y sin User Pool (CDM-130).
 */
@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly cognito = inject(COGNITO_CONFIG);

  readonly currentUser = signal<UserSession | null>(null);
  readonly isLoading = signal<boolean>(false);
  readonly isAuthenticated = computed(() => this.currentUser() !== null);

  constructor() {
    this.restoreSession();
  }

  private get usesCognito(): boolean {
    return Boolean(this.cognito.clientId);
  }

  /** Inicia sesión con correo y contraseña. */
  login(credentials: LoginCredentials): Observable<AuthResponse> {
    this.isLoading.set(true);

    if (!this.usesCognito) {
      return this.mockLogin(credentials);
    }

    return this.callCognito<CognitoInitiateAuthResponse>('InitiateAuth', {
      AuthFlow: 'USER_PASSWORD_AUTH',
      ClientId: this.cognito.clientId,
      AuthParameters: {
        USERNAME: credentials.email,
        PASSWORD: credentials.password,
      },
    }).pipe(
      map((res) => {
        const result = res.AuthenticationResult;
        if (!result) {
          throw new AuthError('unknown', 'Respuesta de autenticación incompleta de Cognito.');
        }

        const tokens: AuthTokens = {
          accessToken: result.AccessToken,
          idToken: result.IdToken,
          refreshToken: result.RefreshToken || '',
          expiresAt: Date.now() + (result.ExpiresIn || 3600) * 1000,
        };
        return { tokens, user: this.decodeUserFromToken(tokens.idToken, credentials.email) };
      }),
      tap((authResponse) => {
        this.saveTokens(authResponse.tokens);
        this.currentUser.set(authResponse.user);
      }),
      finalize(() => this.isLoading.set(false)),
    );
  }

  /** Registra una cuenta. Indica si Cognito exige confirmarla con el código enviado por correo. */
  register(data: RegisterData): Observable<RegisterResult> {
    this.isLoading.set(true);

    if (!this.usesCognito) {
      return this.mockRegister(data);
    }

    const userAttributes = [{ Name: 'email', Value: data.email }];
    if (data.name) {
      userAttributes.push({ Name: 'name', Value: data.name });
    }

    return this.callCognito<CognitoSignUpResponse>('SignUp', {
      ClientId: this.cognito.clientId,
      Username: data.email,
      Password: data.password,
      UserAttributes: userAttributes,
    }).pipe(
      map((res) => ({ userConfirmed: Boolean(res.UserConfirmed) })),
      finalize(() => this.isLoading.set(false)),
    );
  }

  /** Confirma la cuenta con el código de 6 dígitos enviado por correo. */
  confirmRegistration(data: ConfirmRegistrationData): Observable<void> {
    this.isLoading.set(true);

    if (!this.usesCognito) {
      return this.mockConfirm(data);
    }

    return this.callCognito<unknown>('ConfirmSignUp', {
      ClientId: this.cognito.clientId,
      Username: data.email,
      ConfirmationCode: data.code,
    }).pipe(
      map(() => void 0),
      finalize(() => this.isLoading.set(false)),
    );
  }

  /** Envía de nuevo el código de confirmación al correo de la cuenta. */
  resendConfirmationCode(email: string): Observable<void> {
    if (!this.usesCognito) {
      return of(void 0);
    }

    return this.callCognito<unknown>('ResendConfirmationCode', {
      ClientId: this.cognito.clientId,
      Username: email,
    }).pipe(map(() => void 0));
  }

  /** Cierre de sesión y limpieza local de tokens. */
  logout(): void {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // Ignorar si sessionStorage no está disponible
    }
    this.currentUser.set(null);
  }

  /**
   * ID token vigente para autenticar las peticiones a la API de CDM.
   * Se usa el ID token (y no el access token) porque incluye `email` y `email_verified`,
   * que el backend necesita para identificar al usuario y vincular invitaciones.
   */
  getIdToken(): string | null {
    const tokens = this.getStoredTokens();
    if (!tokens || this.isTokenExpired(tokens)) {
      return null;
    }
    return tokens.idToken;
  }

  /** Comprueba si el token almacenado ha caducado (con 30 s de margen). */
  isTokenExpired(tokens?: AuthTokens | null): boolean {
    const t = tokens ?? this.getStoredTokens();
    if (!t) return true;
    return Date.now() >= t.expiresAt - 30_000;
  }

  // --- Soporte de sesión ---

  private callCognito<T>(action: string, body: object): Observable<T> {
    const endpoint = `https://cognito-idp.${this.cognito.region}.amazonaws.com/`;
    const headers = new HttpHeaders({
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': `AWSCognitoIdentityProviderService.${action}`,
    });
    return this.http
      .post<T>(endpoint, body, { headers })
      .pipe(catchError((error: unknown) => throwError(() => this.toAuthError(error))));
  }

  private restoreSession(): void {
    const tokens = this.getStoredTokens();
    if (tokens && !this.isTokenExpired(tokens)) {
      this.currentUser.set(this.decodeUserFromToken(tokens.idToken, ''));
    } else if (tokens) {
      this.logout();
    }
  }

  private saveTokens(tokens: AuthTokens): void {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
    } catch {
      // Manejo seguro en caso de cuota de storage superada
    }
  }

  private getStoredTokens(): AuthTokens | null {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw) as AuthTokens;
    } catch {
      return null;
    }
  }

  private decodeUserFromToken(idToken: string, fallbackEmail: string): UserSession {
    const payload = decodeJwtPayload(idToken);
    const email = typeof payload?.['email'] === 'string' ? payload['email'] : fallbackEmail;
    const name = typeof payload?.['name'] === 'string' ? payload['name'] : undefined;
    return {
      sub: typeof payload?.['sub'] === 'string' ? payload['sub'] : '',
      email,
      name: name || undefined,
      emailVerified: payload?.['email_verified'] === true,
    };
  }

  private toAuthError(error: unknown): AuthError {
    if (error instanceof AuthError) {
      return error;
    }
    const err = error as { error?: { __type?: string; code?: string; message?: string } };
    const errorType = err?.error?.__type || err?.error?.code || '';
    const message = err?.error?.message || '';

    // Prevención de enumeración de cuentas: mensajes genéricos y seguros
    if (
      errorType.includes('NotAuthorizedException') ||
      errorType.includes('UserNotFoundException') ||
      message.includes('Incorrect username or password')
    ) {
      return new AuthError('invalid-credentials', 'Correo electrónico o contraseña incorrectos.');
    }
    if (errorType.includes('UserNotConfirmedException')) {
      return new AuthError(
        'user-not-confirmed',
        'Tu cuenta aún no ha sido confirmada. Ingresa el código que enviamos a tu correo.',
      );
    }
    if (errorType.includes('UsernameExistsException')) {
      return new AuthError(
        'username-exists',
        'Ya existe una cuenta con este correo electrónico o está pendiente de confirmación.',
      );
    }
    if (errorType.includes('InvalidPasswordException')) {
      return new AuthError(
        'invalid-password',
        'La contraseña no cumple los requisitos: mínimo 8 caracteres, mayúsculas, minúsculas, números y símbolos.',
      );
    }
    if (errorType.includes('CodeMismatchException') || errorType.includes('ExpiredCodeException')) {
      return new AuthError('code-mismatch', 'El código de verificación es incorrecto o ha caducado.');
    }
    if (errorType.includes('LimitExceededException') || errorType.includes('TooManyRequestsException')) {
      return new AuthError(
        'too-many-attempts',
        'Demasiados intentos. Espera unos minutos antes de volver a intentarlo.',
      );
    }
    return new AuthError('unknown', 'Ocurrió un error al procesar la solicitud. Por favor intenta de nuevo.');
  }

  // --- Modo de desarrollo local sin Cognito ---

  private createMockJwt(prefix: string, payload: Record<string, unknown>): string {
    const b64 = (str: string) => btoa(String.fromCharCode(...new TextEncoder().encode(str)));
    const header = b64(JSON.stringify({ alg: 'none', typ: 'JWT' }));
    const body = b64(JSON.stringify(payload));
    return `${prefix}.${header}.${body}.mock-signature`;
  }

  private mockLogin(credentials: LoginCredentials): Observable<AuthResponse> {
    this.isLoading.set(false);
    if (!credentials.email.includes('@') || credentials.password.length < 6) {
      return throwError(
        () => new AuthError('invalid-credentials', 'Correo electrónico o contraseña incorrectos.'),
      );
    }

    const user: UserSession = {
      sub: 'mock-sub-' + credentials.email.replace(/[^a-zA-Z0-9]/g, ''),
      email: credentials.email,
      name: credentials.email.split('@')[0],
      emailVerified: true,
    };
    const now = Math.floor(Date.now() / 1000);
    const claims = {
      sub: user.sub,
      email: user.email,
      name: user.name,
      email_verified: true,
      iat: now,
      exp: now + 3600,
    };
    const tokens: AuthTokens = {
      accessToken: this.createMockJwt('mock-access-token-' + Date.now(), { ...claims, token_use: 'access' }),
      idToken: this.createMockJwt('mock-id-token-' + Date.now(), { ...claims, token_use: 'id' }),
      refreshToken: 'mock-refresh-token-' + Date.now(),
      expiresAt: Date.now() + 3600 * 1000,
    };

    this.saveTokens(tokens);
    this.currentUser.set(user);
    return of({ tokens, user });
  }

  private mockRegister(data: RegisterData): Observable<RegisterResult> {
    this.isLoading.set(false);
    if (!data.email.includes('@') || data.password.length < 8) {
      return throwError(
        () => new AuthError('invalid-password', 'La contraseña debe tener mínimo 8 caracteres.'),
      );
    }
    return of({ userConfirmed: true });
  }

  private mockConfirm(data: ConfirmRegistrationData): Observable<void> {
    this.isLoading.set(false);
    if (!/^\d{6}$/.test(data.code)) {
      return throwError(
        () => new AuthError('code-mismatch', 'El código de verificación es incorrecto.'),
      );
    }
    return of(void 0);
  }
}

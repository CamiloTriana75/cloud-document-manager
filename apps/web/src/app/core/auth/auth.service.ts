import { HttpClient, HttpHeaders } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { catchError, map, Observable, of, tap, throwError } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AuthResponse,
  AuthTokens,
  ConfirmRegistrationData,
  LoginCredentials,
  RegisterData,
  UserSession,
} from './auth.models';

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

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);

  readonly currentUser = signal<UserSession | null>(null);
  readonly isLoading = signal<boolean>(false);
  readonly isAuthenticated = computed(() => this.currentUser() !== null);

  constructor() {
    this.restoreSession();
  }

  /**
   * Inicia sesión con correo y contraseña contra Amazon Cognito.
   */
  login(credentials: LoginCredentials): Observable<AuthResponse> {
    this.isLoading.set(true);

    if (!environment.cognito.clientId) {
      return this.mockLogin(credentials);
    }

    const endpoint = `https://cognito-idp.${environment.cognito.region}.amazonaws.com/`;
    const headers = new HttpHeaders({
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
    });

    const body = {
      AuthFlow: 'USER_PASSWORD_AUTH',
      ClientId: environment.cognito.clientId,
      AuthParameters: {
        USERNAME: credentials.email,
        PASSWORD: credentials.password,
      },
    };

    return this.http.post<CognitoInitiateAuthResponse>(endpoint, body, { headers }).pipe(
      map((res) => {
        const result = res.AuthenticationResult;
        if (!result) {
          throw new Error('Respuesta de autenticación incompleta de Cognito.');
        }

        const expiresInMs = (result.ExpiresIn || 3600) * 1000;
        const tokens: AuthTokens = {
          accessToken: result.AccessToken,
          idToken: result.IdToken,
          refreshToken: result.RefreshToken || '',
          expiresAt: Date.now() + expiresInMs,
        };

        const user = this.decodeUserFromToken(tokens.idToken, credentials.email);
        return { tokens, user };
      }),
      tap((authResponse) => {
        this.saveTokens(authResponse.tokens);
        this.currentUser.set(authResponse.user);
        this.isLoading.set(false);
      }),
      catchError((error) => {
        this.isLoading.set(false);
        const userMessage = this.normalizeCognitoError(error);
        return throwError(() => new Error(userMessage));
      })
    );
  }

  /**
   * Registro de un nuevo usuario en Amazon Cognito.
   */
  register(data: RegisterData): Observable<void> {
    this.isLoading.set(true);

    if (!environment.cognito.clientId) {
      return this.mockRegister(data);
    }

    const endpoint = `https://cognito-idp.${environment.cognito.region}.amazonaws.com/`;
    const headers = new HttpHeaders({
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': 'AWSCognitoIdentityProviderService.SignUp',
    });

    const userAttributes = [{ Name: 'email', Value: data.email }];
    if (data.name) {
      userAttributes.push({ Name: 'name', Value: data.name });
    }

    const body = {
      ClientId: environment.cognito.clientId,
      Username: data.email,
      Password: data.password,
      UserAttributes: userAttributes,
    };

    return this.http.post<unknown>(endpoint, body, { headers }).pipe(
      map(() => void 0),
      tap(() => this.isLoading.set(false)),
      catchError((error) => {
        this.isLoading.set(false);
        const userMessage = this.normalizeCognitoError(error);
        return throwError(() => new Error(userMessage));
      })
    );
  }

  /**
   * Confirmación del código de 6 dígitos enviado por correo.
   */
  confirmRegistration(data: ConfirmRegistrationData): Observable<void> {
    this.isLoading.set(true);

    if (!environment.cognito.clientId) {
      return this.mockConfirm(data);
    }

    const endpoint = `https://cognito-idp.${environment.cognito.region}.amazonaws.com/`;
    const headers = new HttpHeaders({
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': 'AWSCognitoIdentityProviderService.ConfirmSignUp',
    });

    const body = {
      ClientId: environment.cognito.clientId,
      Username: data.email,
      ConfirmationCode: data.code,
    };

    return this.http.post<unknown>(endpoint, body, { headers }).pipe(
      map(() => void 0),
      tap(() => this.isLoading.set(false)),
      catchError((error) => {
        this.isLoading.set(false);
        const userMessage = this.normalizeCognitoError(error);
        return throwError(() => new Error(userMessage));
      })
    );
  }

  /**
   * Cierre de sesión y revocación local de tokens.
   */
  logout(): void {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // Ignorar si sessionStorage no está disponible
    }
    this.currentUser.set(null);
  }

  /**
   * Retorna el Access Token actual si no ha expirado.
   */
  getAccessToken(): string | null {
    const tokens = this.getStoredTokens();
    if (!tokens || this.isTokenExpired(tokens)) {
      return null;
    }
    return tokens.accessToken;
  }

  /**
   * Comprueba si el token almacenado ha caducado.
   */
  isTokenExpired(tokens?: AuthTokens | null): boolean {
    const t = tokens ?? this.getStoredTokens();
    if (!t) return true;
    // Margen de seguridad de 30 segundos
    return Date.now() >= t.expiresAt - 30_000;
  }

  // --- Métodos privados de soporte y sesión ---

  private restoreSession(): void {
    const tokens = this.getStoredTokens();
    if (tokens && !this.isTokenExpired(tokens)) {
      const user = this.decodeUserFromToken(tokens.idToken, 'usuario@cdm.local');
      this.currentUser.set(user);
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
    try {
      const parts = idToken.split('.');
      if (parts.length >= 2) {
        const payload = JSON.parse(atob(parts[1]));
        return {
          sub: payload.sub || 'mock-sub',
          email: payload.email || fallbackEmail,
          name: payload.name || undefined,
          emailVerified: Boolean(payload.email_verified),
        };
      }
    } catch {
      // Si el token no es un JWT estándar (mock), usar fallback
    }

    return {
      sub: 'user-' + Math.random().toString(36).substring(2, 9),
      email: fallbackEmail,
      name: fallbackEmail.split('@')[0],
      emailVerified: true,
    };
  }

  private normalizeCognitoError(error: unknown): string {
    const err = error as {
      error?: { __type?: string; code?: string; message?: string };
      message?: string;
    };
    const errorType = err?.error?.__type || err?.error?.code || '';
    const message = err?.error?.message || err?.message || '';

    // Prevención de enumeración de cuentas: mensajes genéricos y seguros
    if (
      errorType.includes('NotAuthorizedException') ||
      errorType.includes('UserNotFoundException') ||
      message.includes('Incorrect username or password')
    ) {
      return 'Correo electrónico o contraseña incorrectos.';
    }

    if (errorType.includes('UserNotConfirmedException')) {
      return 'Tu cuenta aún no ha sido confirmada. Revisa tu correo electrónico para ingresar el código.';
    }

    if (errorType.includes('UsernameExistsException')) {
      return 'Ya existe una cuenta con este correo electrónico o está pendiente de confirmación.';
    }

    if (errorType.includes('InvalidPasswordException')) {
      return 'La contraseña no cumple los requisitos: mínimo 8 caracteres, mayúsculas, minúsculas, números y símbolos.';
    }

    if (errorType.includes('CodeMismatchException')) {
      return 'El código de verificación es incorrecto o ha caducado.';
    }

    return 'Ocurrió un error al procesar la solicitud. Por favor intenta de nuevo.';
  }

  // --- Emuladores para desarrollo local offline ---

  private mockLogin(credentials: LoginCredentials): Observable<AuthResponse> {
    if (!credentials.email.includes('@') || credentials.password.length < 6) {
      this.isLoading.set(false);
      return throwError(() => new Error('Correo electrónico o contraseña incorrectos.'));
    }

    const tokens: AuthTokens = {
      accessToken: 'mock-access-token-' + Date.now(),
      idToken: 'mock-id-token-' + Date.now(),
      refreshToken: 'mock-refresh-token-' + Date.now(),
      expiresAt: Date.now() + 3600 * 1000,
    };

    const user: UserSession = {
      sub: 'mock-sub-' + credentials.email.replace(/[^a-zA-Z0-9]/g, ''),
      email: credentials.email,
      name: credentials.email.split('@')[0],
      emailVerified: true,
    };

    this.saveTokens(tokens);
    this.currentUser.set(user);
    this.isLoading.set(false);

    return of({ tokens, user });
  }

  private mockRegister(data: RegisterData): Observable<void> {
    this.isLoading.set(false);
    if (!data.email.includes('@') || data.password.length < 8) {
      return throwError(
        () => new Error('La contraseña debe tener mínimo 8 caracteres.')
      );
    }
    return of(void 0);
  }

  private mockConfirm(data: ConfirmRegistrationData): Observable<void> {
    this.isLoading.set(false);
    if (data.code !== '123456' && data.code.length !== 6) {
      return throwError(() => new Error('El código de verificación es incorrecto.'));
    }
    return of(void 0);
  }
}

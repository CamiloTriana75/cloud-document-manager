/**
 * Modelos de autenticación e identidad para Cloud Document Manager (CDM-24).
 */

export interface UserSession {
  sub: string;
  email: string;
  name?: string;
  emailVerified: boolean;
}

export interface AuthTokens {
  accessToken: string;
  idToken: string;
  refreshToken: string;
  expiresAt: number; // Unix timestamp en milisegundos
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  name?: string;
}

export interface ConfirmRegistrationData {
  email: string;
  code: string;
}

export interface AuthResponse {
  tokens: AuthTokens;
  user: UserSession;
}

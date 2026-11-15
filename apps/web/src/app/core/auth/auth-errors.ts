/** Errores de autenticación tipados para que las pantallas reaccionen sin comparar textos. */

export type AuthErrorCode =
  | 'invalid-credentials'
  | 'user-not-confirmed'
  | 'username-exists'
  | 'invalid-password'
  | 'code-mismatch'
  | 'too-many-attempts'
  | 'unknown';

export class AuthError extends Error {
  constructor(
    readonly code: AuthErrorCode,
    message: string,
  ) {
    super(message);
    this.name = 'AuthError';
  }
}

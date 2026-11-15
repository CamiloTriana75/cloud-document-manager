import { InjectionToken } from '@angular/core';

import { environment } from '../../../environments/environment';

/** Identificadores públicos del User Pool y App Client de Cognito (no son secretos). */
export interface CognitoConfig {
  region: string;
  userPoolId: string;
  clientId: string;
  domain: string;
}

/** Sin `clientId`, la app usa el modo de desarrollo local sin Cognito (tokens sin firma). */
export const COGNITO_CONFIG = new InjectionToken<CognitoConfig>('COGNITO_CONFIG', {
  providedIn: 'root',
  factory: () => environment.cognito,
});

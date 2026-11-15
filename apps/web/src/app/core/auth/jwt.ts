/**
 * Lectura de claims de un JWT solo para presentación (nombre, correo).
 * No verifica la firma: la autenticidad del token la decide siempre el backend.
 */

/** Decodifica base64url (sin relleno) a texto UTF-8. */
function decodeBase64Url(segment: string): string {
  const base64 = segment.replace(/-/g, '+').replace(/_/g, '/');
  const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
  const binary = atob(padded);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

/**
 * Devuelve el payload de un JWT (`header.payload.signature`). Admite también los tokens
 * del modo de desarrollo local, que llevan un prefijo antes del header.
 */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split('.');
  if (parts.length < 3) {
    return null;
  }
  const payloadSegment = parts.length >= 4 ? parts[2] : parts[1];
  try {
    const payload: unknown = JSON.parse(decodeBase64Url(payloadSegment));
    return payload !== null && typeof payload === 'object' ? (payload as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

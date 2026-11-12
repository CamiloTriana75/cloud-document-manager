"""Adaptador outbound: Verificador de tokens JWT de Amazon Cognito (CDM-25 / CDM-81).

Valida criptográficamente la firma con la clave pública de Cognito (JWKS),
maneja rotación de claves, comprueba issuer (iss), vigencia (exp),
token_use ('id' o 'access') y audience/client_id.
"""

from __future__ import annotations

import jwt
from jwt import ExpiredSignatureError, PyJWKClient, PyJWKClientError
from jwt.exceptions import InvalidTokenError as JwtInvalidTokenError

from cdm.application.ports.auth import TokenVerifierPort
from cdm.domain.errors import ExpiredTokenError, InvalidTokenError
from cdm.domain.identity import AuthenticatedUser


class CognitoJwtVerifier(TokenVerifierPort):
    """Verificador de tokens JWT emitidos por Amazon Cognito User Pools."""

    def __init__(
        self,
        user_pool_id: str,
        client_id: str = "",
        aws_region: str = "us-east-1",
        jwks_client: PyJWKClient | None = None,
    ) -> None:
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.aws_region = aws_region
        self.issuer = f"https://cognito-idp.{aws_region}.amazonaws.com/{user_pool_id}"

        self._jwks_client: PyJWKClient | None
        if jwks_client is not None:
            self._jwks_client = jwks_client
        elif user_pool_id:
            jwks_url = f"{self.issuer}/.well-known/jwks.json"
            # Cache automático con soporte para rotación de claves
            self._jwks_client = PyJWKClient(
                jwks_url,
                cache_jwk_set=True,
                max_cached_keys=16,
                lifespan=3600,
            )
        else:
            self._jwks_client = None

    def verify_token(self, token: str) -> AuthenticatedUser:
        """Verifica la firma y claims del token según los estándares de Cognito."""
        if not token or not token.strip():
            raise InvalidTokenError("El token no puede estar vacío.")

        clean_token = token.strip()

        # Si no hay user_pool_id configurado (desarrollo local sin Cognito), emular validación
        if not self.user_pool_id or self._jwks_client is None:
            return self._verify_mock_token(clean_token)

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(clean_token)
        except PyJWKClientError as exc:
            raise InvalidTokenError(
                f"No se pudo resolver la clave pública para el token: {exc}"
            ) from exc
        except Exception as exc:
            raise InvalidTokenError(f"Formato de token no compatible con JWKS: {exc}") from exc

        try:
            payload: dict[str, object] = jwt.decode(
                clean_token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iss": True,
                    "verify_aud": False,  # Verificación manual abajo según token_use
                },
            )
        except ExpiredSignatureError as exc:
            raise ExpiredTokenError("El token ha expirado.") from exc
        except JwtInvalidTokenError as exc:
            raise InvalidTokenError(f"Token inválido: {exc}") from exc
        except Exception as exc:
            raise InvalidTokenError(f"Fallo en la verificación criptográfica: {exc}") from exc

        return self._build_authenticated_user(payload)

    def _build_authenticated_user(self, payload: dict[str, object]) -> AuthenticatedUser:
        """Valida claims obligatorios de Cognito y construye la entidad de dominio."""
        token_use = str(payload.get("token_use", ""))
        if token_use not in ("id", "access"):
            raise InvalidTokenError(f"Claim 'token_use' no válido: '{token_use}'.")

        # Validación de audiencia / client_id según el tipo de token
        if self.client_id:
            if token_use == "id":
                aud = payload.get("aud")
                if aud != self.client_id:
                    raise InvalidTokenError(
                        "La audiencia (aud) del ID token no coincide con el Client ID esperado."
                    )
            elif token_use == "access":
                client_id_claim = payload.get("client_id")
                if client_id_claim != self.client_id:
                    raise InvalidTokenError(
                        "El client_id del Access token no coincide con el esperado."
                    )

        sub = payload.get("sub")
        if not sub or not isinstance(sub, str):
            raise InvalidTokenError("El token no contiene un claim 'sub' válido.")

        email = str(payload.get("email") or payload.get("username") or f"{sub}@cognito.local")
        name = str(payload.get("name")) if payload.get("name") else None
        email_verified = bool(payload.get("email_verified", False))

        return AuthenticatedUser(
            cognito_sub=sub,
            email=email,
            name=name,
            email_verified=email_verified,
            token_use=token_use,
        )

    def _verify_mock_token(self, token: str) -> AuthenticatedUser:
        """Modo offline de desarrollo para validar tokens locales sin dependencias de red."""
        if token.startswith("expired_"):
            raise ExpiredTokenError("El token ha expirado (mock).")
        if token.startswith("invalid_") or "." not in token:
            raise InvalidTokenError("Token manipulado o con formato inválido (mock).")

        # Extraer claims de prueba si es un JWT válido o mock
        try:
            unverified: dict[str, object] = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False},
            )
            sub = str(unverified.get("sub", "mock-sub-12345"))
            email = str(unverified.get("email", "dev@cdm.local"))
            name = str(unverified.get("name", "Usuario Dev")) if unverified.get("name") else None
            return AuthenticatedUser(
                cognito_sub=sub,
                email=email,
                name=name,
                email_verified=True,
                token_use="access",
            )
        except Exception:
            # Fallback simple para tokens opacos de prueba
            return AuthenticatedUser(
                cognito_sub=f"mock-{token[:8]}",
                email="dev@cdm.local",
                name="Usuario Dev",
                email_verified=True,
                token_use="access",
            )

"""Adaptador inbound HTTP: dependencias de autenticación y endpoint /api/v1/me (CDM-25 / CDM-82).

Extrae el Bearer token del header Authorization, delega la verificación
al TokenVerifierPort inyectado y provee el AuthenticatedUser tipado.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from cdm.adapters.outbound.auth.cognito_verifier import CognitoJwtVerifier
from cdm.application.ports.auth import TokenVerifierPort
from cdm.config.settings import Settings, load_settings
from cdm.domain.errors import MissingTokenError
from cdm.domain.identity import AuthenticatedUser

# auto_error=False para que nuestro middleware capture el fallo y devuelva el envelope CDM estándar
security_scheme = HTTPBearer(auto_error=False)


def get_token_verifier(
    settings: Annotated[Settings, Depends(load_settings)],
) -> TokenVerifierPort:
    """Fábrica de dependencias para el verificador de tokens JWT."""
    return CognitoJwtVerifier(
        user_pool_id=settings.cognito_user_pool_id,
        client_id=settings.cognito_client_id,
        aws_region=settings.cognito_region,
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(security_scheme)],
    verifier: Annotated[TokenVerifierPort, Depends(get_token_verifier)],
) -> AuthenticatedUser:
    """Dependencia principal: extrae y valida el token Bearer, devolviendo el usuario tipado.

    Lanza:
        MissingTokenError (401): si no se proveyó encabezado Bearer.
        ExpiredTokenError (401): si el token expiró.
        InvalidTokenError (401): si la firma o claims no son válidos.
    """
    if credentials is None or not credentials.credentials:
        raise MissingTokenError("Se requiere encabezado Authorization: Bearer <token>.")

    return verifier.verify_token(credentials.credentials)


class UserProfileResponse(BaseModel):
    """Schema de respuesta para el perfil de usuario autenticado."""

    sub: str
    email: str
    name: str | None = None
    email_verified: bool = False
    token_use: str = "access"


class EnvelopeUserProfile(BaseModel):
    """Envelope estándar de datos para /api/v1/me."""

    data: UserProfileResponse


router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.get(
    "/me",
    response_model=EnvelopeUserProfile,
    summary="Obtener perfil del usuario autenticado",
    description=(
        "Retorna la identidad y contexto del usuario resuelto desde el token JWT de Cognito."
    ),
    responses={
        401: {
            "description": "Token ausente, inválido o expirado",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "missing_token",
                            "message": "Se requiere encabezado Authorization: Bearer <token>.",
                            "details": None,
                        }
                    }
                }
            },
        }
    },
)
def get_me(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> EnvelopeUserProfile:
    """Endpoint /api/v1/me: contexto y perfil del usuario autenticado (AGENTS.md §11)."""
    return EnvelopeUserProfile(
        data=UserProfileResponse(
            sub=current_user.cognito_sub,
            email=current_user.email,
            name=current_user.name,
            email_verified=current_user.email_verified,
            token_use=current_user.token_use,
        )
    )

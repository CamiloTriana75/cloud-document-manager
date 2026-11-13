"""Puertos de autenticación (capa de aplicación, CDM-25).

Define la interfaz que cualquier adaptador de verificación de tokens debe cumplir.
Los casos de uso dependen de este contrato, nunca de PyJWT ni de Cognito directamente.
"""

from typing import Protocol

from cdm.domain.identity import AuthenticatedUser


class TokenVerifierPort(Protocol):
    """Contrato para la verificación criptográfica de tokens JWT."""

    def verify_token(self, token: str) -> AuthenticatedUser:
        """Verifica la firma, emisor, audiencia y vigencia del token.

        Retorna:
            AuthenticatedUser con la identidad verificada.

        Lanza:
            UnauthenticatedError: Ante cualquier fallo criptográfico o de vigencia.
        """
        ...

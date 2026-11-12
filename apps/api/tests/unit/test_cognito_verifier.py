"""Pruebas unitarias para la verificación criptográfica de JWT Cognito (CDM-25 / CDM-81).

Valida firma RS256, rotación de claves, issuer, audience/client_id,
expiración (exp), token_use y claim 'sub'.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClient, PyJWKClientError

from cdm.adapters.outbound.auth.cognito_verifier import CognitoJwtVerifier
from cdm.domain.errors import ExpiredTokenError, InvalidTokenError

USER_POOL_ID = "us-east-1_TestPool123"
CLIENT_ID = "test-spa-client-id-456"
AWS_REGION = "us-east-1"
ISSUER = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}"


@pytest.fixture
def rsa_keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, str]:
    """Genera par de claves RSA para pruebas criptográficas RS256."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    kid = "test-key-id-1"
    return private_key, public_key, kid


@pytest.fixture
def mock_jwks_client(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, str],
) -> PyJWKClient:
    """Mock de PyJWKClient que devuelve la clave pública correspondiente."""
    _, public_key, _ = rsa_keypair
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key

    mock_client = MagicMock(spec=PyJWKClient)
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
    return mock_client


@pytest.fixture
def verifier(mock_jwks_client: PyJWKClient) -> CognitoJwtVerifier:
    return CognitoJwtVerifier(
        user_pool_id=USER_POOL_ID,
        client_id=CLIENT_ID,
        aws_region=AWS_REGION,
        jwks_client=mock_jwks_client,
    )


def test_verify_valid_id_token(
    verifier: CognitoJwtVerifier,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, str],
) -> None:
    private_key, _, kid = rsa_keypair
    now = int(time.time())
    payload = {
        "sub": "user-uuid-123",
        "email": "persona@cdm.local",
        "name": "Persona Prueba",
        "email_verified": True,
        "token_use": "id",
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "exp": now + 3600,
        "iat": now,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})

    user = verifier.verify_token(token)

    assert user.cognito_sub == "user-uuid-123"
    assert user.email == "persona@cdm.local"
    assert user.name == "Persona Prueba"
    assert user.email_verified is True
    assert user.token_use == "id"


def test_verify_valid_access_token(
    verifier: CognitoJwtVerifier,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, str],
) -> None:
    private_key, _, kid = rsa_keypair
    now = int(time.time())
    payload = {
        "sub": "access-user-456",
        "username": "usuario_acceso",
        "token_use": "access",
        "client_id": CLIENT_ID,
        "iss": ISSUER,
        "exp": now + 3600,
        "iat": now,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})

    user = verifier.verify_token(token)

    assert user.cognito_sub == "access-user-456"
    assert user.token_use == "access"


def test_reject_expired_token(
    verifier: CognitoJwtVerifier,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, str],
) -> None:
    private_key, _, kid = rsa_keypair
    now = int(time.time())
    payload = {
        "sub": "expired-user-789",
        "token_use": "id",
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "exp": now - 60,  # Expirado hace un minuto
        "iat": now - 3600,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})

    with pytest.raises(ExpiredTokenError, match="El token ha expirado"):
        verifier.verify_token(token)


def test_reject_tampered_signature(
    verifier: CognitoJwtVerifier,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, str],
) -> None:
    # Firmar con una clave privada distinta a la registrada en JWKS
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    payload = {
        "sub": "tampered-user",
        "token_use": "id",
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "exp": now + 3600,
    }
    token = jwt.encode(payload, other_key, algorithm="RS256", headers={"kid": "other-kid"})

    with pytest.raises(InvalidTokenError):
        verifier.verify_token(token)


def test_reject_incorrect_issuer(
    verifier: CognitoJwtVerifier,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, str],
) -> None:
    private_key, _, kid = rsa_keypair
    now = int(time.time())
    payload = {
        "sub": "bad-iss-user",
        "token_use": "id",
        "iss": "https://cognito-idp.us-east-1.amazonaws.com/OTRO_POOL_MALICIOSO",
        "aud": CLIENT_ID,
        "exp": now + 3600,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})

    with pytest.raises(InvalidTokenError, match="Token inválido"):
        verifier.verify_token(token)


def test_reject_incorrect_audience_for_id_token(
    verifier: CognitoJwtVerifier,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, str],
) -> None:
    private_key, _, kid = rsa_keypair
    now = int(time.time())
    payload = {
        "sub": "bad-aud-user",
        "token_use": "id",
        "iss": ISSUER,
        "aud": "cliente-ajeno-no-autorizado",
        "exp": now + 3600,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})

    with pytest.raises(InvalidTokenError, match="audiencia"):
        verifier.verify_token(token)


def test_reject_missing_sub(
    verifier: CognitoJwtVerifier,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, str],
) -> None:
    private_key, _, kid = rsa_keypair
    now = int(time.time())
    payload = {
        "token_use": "id",
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "exp": now + 3600,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})

    with pytest.raises(InvalidTokenError, match="'sub'"):
        verifier.verify_token(token)


def test_key_rotation_failure_handled(
    verifier: CognitoJwtVerifier,
    mock_jwks_client: MagicMock,
) -> None:
    mock_jwks_client.get_signing_key_from_jwt.side_effect = PyJWKClientError("Clave no encontrada")

    with pytest.raises(InvalidTokenError, match="No se pudo resolver la clave pública"):
        verifier.verify_token("header.payload.signature")

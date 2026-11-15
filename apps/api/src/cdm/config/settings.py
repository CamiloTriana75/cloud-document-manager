"""Ajustes de la aplicación, validados al arrancar con pydantic-settings.

Solo variables con prefijo ``CDM_`` (ver ``.env.example`` en la raíz).
No incluye secretos: los valores sensibles llegan por entorno/secrets manager.

El archivo ``.env`` se busca en el directorio de trabajo y en la raíz del
repositorio (``../../.env`` al ejecutar desde ``apps/api``); en Lambda no
existe y toda la configuración llega por variables de entorno.
"""

from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CDM_",
        env_file=("../../.env", ".env"),
        extra="ignore",
    )

    env: str = "dev"
    database_url: str = "postgresql+psycopg://cdm:cdm@localhost:5432/cdm"
    cors_origins: str = "http://localhost:4200"
    log_level: str = "INFO"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "us-east-1"
    # Modo de desarrollo local sin Cognito: acepta tokens sin firma. Solo se activa de
    # forma explícita (CDM_AUTH_MOCK_ENABLED=true) y nunca con CDM_ENV=prod (CDM-130).
    auth_mock_enabled: bool = False
    s3_bucket_name: str = "cdm-documents-dev"
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    max_upload_size_bytes: int = 52428800  # 50 MB
    upload_url_expires_in_seconds: int = 900  # 15 min

    @model_validator(mode="after")
    def _forbid_mock_auth_in_prod(self) -> Self:
        if self.auth_mock_enabled and self.env == "prod":
            raise ValueError("CDM_AUTH_MOCK_ENABLED no puede activarse con CDM_ENV=prod.")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        """Orígenes CORS separados por coma, sin espacios ni vacíos."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cognito_issuer_url(self) -> str:
        """URL del emisor JWT de Cognito (iss)."""
        if not self.cognito_user_pool_id:
            return ""
        return (
            f"https://cognito-idp.{self.cognito_region}.amazonaws.com/{self.cognito_user_pool_id}"
        )


def load_settings() -> Settings:
    """Punto único de construcción de Settings (inyección en bootstrap)."""
    return Settings()

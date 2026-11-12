"""Ajustes de la aplicación, validados al arrancar con pydantic-settings.

Solo variables con prefijo ``CDM_`` (ver ``.env.example`` en la raíz).
No incluye secretos: los valores sensibles llegan por entorno/secrets manager.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CDM_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://cdm:cdm@localhost:5432/cdm"
    cors_origins: str = "http://localhost:4200"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        """Orígenes CORS separados por coma, sin espacios ni vacíos."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def load_settings() -> Settings:
    """Punto único de construcción de Settings (inyección en bootstrap)."""
    return Settings()

"""Pruebas unitarias de la configuración (validación en el borde)."""

import pytest
from pydantic import ValidationError

from cdm.config.settings import Settings


def test_cors_origins_se_parsean_como_lista() -> None:
    settings = Settings(cors_origins="http://a.test, http://b.test, ,http://c.test")

    assert settings.cors_origin_list == [
        "http://a.test",
        "http://b.test",
        "http://c.test",
    ]


def test_cors_origins_vacio_devuelve_lista_vacia() -> None:
    settings = Settings(cors_origins="")

    assert settings.cors_origin_list == []


def test_modo_mock_de_autenticacion_desactivado_por_defecto() -> None:
    assert Settings().auth_mock_enabled is False


def test_modo_mock_de_autenticacion_prohibido_en_produccion() -> None:
    with pytest.raises(ValidationError):
        Settings(env="prod", auth_mock_enabled=True)

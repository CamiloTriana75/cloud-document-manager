"""Pruebas unitarias de la configuración (validación en el borde)."""

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

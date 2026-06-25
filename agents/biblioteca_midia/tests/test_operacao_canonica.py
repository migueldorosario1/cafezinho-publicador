from agents.biblioteca_midia.config import CANONICAL_PRODUCTION_DB_PATH
from agents.biblioteca_midia.legacy_sources import LEGACY_SOURCES, is_legacy_path


def test_path_canonico_producao_e_unico():
    assert CANONICAL_PRODUCTION_DB_PATH == "/root/agent_data/acervo_midia/acervo.db"
    assert not is_legacy_path(CANONICAL_PRODUCTION_DB_PATH)


def test_fontes_legadas_sao_read_only_import():
    assert LEGACY_SOURCES
    for source in LEGACY_SOURCES:
        assert source.allowed_mode == "read_only_import"
        assert source.path.endswith(".db")
        assert source.path != CANONICAL_PRODUCTION_DB_PATH


def test_is_legacy_path_reconhece_inventario():
    for source in LEGACY_SOURCES:
        assert is_legacy_path(source.path)

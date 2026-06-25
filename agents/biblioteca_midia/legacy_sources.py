"""Inventario de fontes legadas de midia.

Regra operacional: estes bancos podem ser lidos por importadores e auditores,
mas nao sao fonte canonica e nao devem receber novas escritas.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import CANONICAL_PRODUCTION_DB_PATH


@dataclass(frozen=True)
class LegacySource:
    path: str
    owner: str
    purpose: str
    allowed_mode: str = "read_only_import"


LEGACY_SOURCES: tuple[LegacySource, ...] = (
    LegacySource(
        path="/root/agent_data/banco_midia/banco_imagens_reais.db",
        owner="legado",
        purpose="Banco bruto historico de imagens coletadas antes do Acervo Editorial de Midia.",
    ),
    LegacySource(
        path="/root/agent_data/banco_midia/banco_imagens_curadas_v3.db",
        owner="v3",
        purpose="Banco curado antigo do V3. Deve virar fonte de importacao, nao destino.",
    ),
    LegacySource(
        path="/root/agent_data/banco_midia/banco_indice_r2_midia_v3.db",
        owner="v3",
        purpose="Indice antigo de objetos R2. Usar para reconciliacao/inventario.",
    ),
    LegacySource(
        path="/root/V3/banco_catalogo_midia_r2_v3.db",
        owner="v3",
        purpose="Catalogo R2 antigo com metadados parciais. Usar para backfill controlado.",
    ),
    LegacySource(
        path="/root/agent_data/banco_midia/banco_fontes_externas_midia_v3.db",
        owner="v3",
        purpose="Fontes externas antigas. Usar para dedupe e auditoria.",
    ),
    LegacySource(
        path="/root/agent_data/banco_midia/banco_wp_media_index_v4.db",
        owner="wordpress",
        purpose="Indice antigo da biblioteca WordPress. Usar apenas para reconciliacao.",
    ),
)


def is_legacy_path(path: str) -> bool:
    return path in {source.path for source in LEGACY_SOURCES}


__all__ = [
    "CANONICAL_PRODUCTION_DB_PATH",
    "LEGACY_SOURCES",
    "LegacySource",
    "is_legacy_path",
]

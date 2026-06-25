"""config.py — Configuração do Acervo Editorial de Mídia.

Centraliza paths defaults e env vars. **NÃO contém credenciais** —
todas as credenciais (Flickr, R2, WP, etc) vivem em GitHub Secrets e
são lidas em runtime pelos agentes especializados (flickr_harvester,
r2_uploader, etc), não pelo acervo.

O acervo só precisa saber onde está seu DB SQLite.
"""

from __future__ import annotations

import os
from pathlib import Path

# ============================================================
# DB PATH — override via env
# ============================================================

DEFAULT_DB_FILENAME = "acervo.db"
CANONICAL_PRODUCTION_DB_PATH = "/root/agent_data/acervo_midia/acervo.db"

def default_db_path() -> Path:
    """Path default: ``agents/biblioteca_midia/data/acervo.db``.

    Override via ``ACERVO_MIDIA_DB_PATH`` env var.
    """
    env = os.environ.get("ACERVO_MIDIA_DB_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "data" / DEFAULT_DB_FILENAME


def canonical_production_db_path() -> Path:
    """Path canônico do acervo em produção Tencent.

    Bancos legados não devem receber novas escritas. Em produção, serviços
    permanentes devem setar ``ACERVO_MIDIA_DB_PATH`` para este caminho.
    """
    return Path(CANONICAL_PRODUCTION_DB_PATH)


# ============================================================
# LIMITES OPERACIONAIS
# ============================================================

MAX_SEARCH_LIMIT = 500
DEFAULT_SEARCH_LIMIT = 50

MAX_TITLE_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 5000
MAX_CREDIT_LENGTH = 500
MAX_BYTES_SIZE = 10_000_000_000  # 10 GB


# ============================================================
# ENV VARS CONHECIDAS (documentação, não validação)
# ============================================================

ENV_VARS = {
    "ACERVO_MIDIA_DB_PATH": (
        "Override do path do SQLite. Default: "
        "agents/biblioteca_midia/data/acervo.db. Em produção Tencent, usar "
        f"{CANONICAL_PRODUCTION_DB_PATH}"
    ),
}

__all__ = [
    "DEFAULT_DB_FILENAME",
    "CANONICAL_PRODUCTION_DB_PATH",
    "default_db_path",
    "canonical_production_db_path",
    "MAX_SEARCH_LIMIT",
    "DEFAULT_SEARCH_LIMIT",
    "MAX_TITLE_LENGTH",
    "MAX_DESCRIPTION_LENGTH",
    "MAX_CREDIT_LENGTH",
    "MAX_BYTES_SIZE",
    "ENV_VARS",
]

"""schema.py — SQLite DDL do Acervo Editorial de Mídia.

ESPELHO do contrato Pydantic em ``contracts.py``. O schema IMPLEMENTA o
contrato; não o substitui. Mudou contrato -> bump CONTRACT_VERSION + nova
migração versionada aqui.

Tabelas (5):
  - ``midia``: 1 linha por ``MidiaRecord`` (campos flatten)
  - ``midia_entity``: N entidades por mídia (busca eficiente)
  - ``midia_tag``: N tags por mídia (busca eficiente)
  - ``operators``: catálogo de operators vistos (cache/dedup)
  - ``schema_version``: controle de migrations futuras

Convenções:
  - UUID armazenado como ``TEXT`` (36 chars, formato canônico).
  - Datetime armazenado como ``TEXT`` ISO 8601 UTC com timezone.
  - Enums armazenados como ``TEXT`` (valor string do enum Pydantic).
  - ``external_id`` + ``source`` formam chave de dedupe (UNIQUE INDEX).
  - ``sha256`` tem índice UNIQUE parcial (só quando presente) — dedupe
    por conteúdo.
  - ``contract_version`` é coluna da linha, não do schema — permite
    conviver com registros de versões diferentes durante migração.

Compatibilidade:
  - SQLite >= 3.38 (FTS5 disponível). Para SQLite < 3.38, FTS5 cai para
    LIKE em ``entities``/``tags`` (degraded mas funcional).
  - ``PRAGMA foreign_keys = ON`` habilitado em runtime pela API.
  - ``PRAGMA journal_mode = WAL`` habilitado em runtime pela API para
    concorrência leitora.
"""

from __future__ import annotations

from .contracts import CONTRACT_VERSION

SCHEMA_VERSION = 1


def schema_ddl() -> str:
    """Retorna DDL completo do schema V1.

    Pode ser passado direto a ``conn.executescript(schema_ddl())``. É
    idempotente (``CREATE TABLE IF NOT EXISTS``).
    """
    return f"""
-- ============================================================
-- ACERVO EDITORIAL DE MÍDIA — SCHEMA V{SCHEMA_VERSION}
-- Contrato Pydantic: v{CONTRACT_VERSION}
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA encoding = 'UTF-8';

-- ------------------------------------------------------------
-- Tabela principal: midia
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS midia (
    -- Identificação
    id                  TEXT    PRIMARY KEY,          -- UUID canônico (36 chars)
    external_id         TEXT,                         -- ID na fonte origem (até 256)
    source              TEXT    NOT NULL,             -- FonteMidia.value

    -- Técnico
    mime_type           TEXT    NOT NULL,
    width               INTEGER NOT NULL CHECK (width  BETWEEN 1 AND 65535),
    height              INTEGER NOT NULL CHECK (height BETWEEN 1 AND 65535),
    bytes_size          INTEGER NOT NULL CHECK (bytes_size BETWEEN 0 AND 10000000000),
    sha256              TEXT    CHECK (length(sha256) = 64 OR sha256 IS NULL),

    -- Armazenamento (StorageRef flattenned)
    storage_kind        TEXT    NOT NULL,             -- StorageKind.value
    storage_provider    TEXT    NOT NULL,             -- StorageProvider.value
    storage_bucket      TEXT,
    storage_key         TEXT,
    storage_url         TEXT,

    -- Editorial
    title               TEXT    NOT NULL CHECK (length(title)  BETWEEN 1 AND 500),
    description         TEXT    CHECK (length(description) <= 5000 OR description IS NULL),
    alt_text            TEXT    CHECK (length(alt_text) <= 500 OR alt_text IS NULL),
    credit              TEXT    NOT NULL CHECK (length(credit)  BETWEEN 1 AND 500),
    license             TEXT    NOT NULL,             -- LicencaMidia.value
    license_url         TEXT,
    source_url          TEXT,

    -- Proveniência
    collected_at        TEXT    NOT NULL,             -- ISO 8601 UTC
    collected_by        TEXT    NOT NULL,             -- operator_id

    -- Validação
    validation_status   TEXT    NOT NULL DEFAULT 'pending',  -- StatusValidacao.value
    validation_reason   TEXT    CHECK (length(validation_reason) <= 2000 OR validation_reason IS NULL),
    validated_at        TEXT,
    validated_by        TEXT,                          -- operator_id ou NULL

    -- Versionamento do contrato
    contract_version    TEXT    NOT NULL,             -- SemVer (ex: '1.0.0')

    -- Timestamps internos (não no contrato Pydantic)
    _created_at         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    _updated_at         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ------------------------------------------------------------
-- Tabela auxiliar: midia_entity (N entidades por mídia)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS midia_entity (
    midia_id    TEXT    NOT NULL,
    entity      TEXT    NOT NULL,
    position    INTEGER NOT NULL DEFAULT 0,           -- preserva ordem da lista
    PRIMARY KEY (midia_id, entity),
    FOREIGN KEY (midia_id) REFERENCES midia(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_midia_entity_entity ON midia_entity(entity);

-- ------------------------------------------------------------
-- Tabela auxiliar: midia_tag (N tags por mídia)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS midia_tag (
    midia_id    TEXT    NOT NULL,
    tag         TEXT    NOT NULL,
    position    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (midia_id, tag),
    FOREIGN KEY (midia_id) REFERENCES midia(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_midia_tag_tag ON midia_tag(tag);

-- ------------------------------------------------------------
-- Tabela: operators (catálogo de operators vistos)
-- ------------------------------------------------------------
-- Permite dedupe e metadados de "quem" tocou registros. Não é origem
-- de verdade (operators podem aparecer em midia sem estarem catalogados
-- aqui primeiro), mas a API populará esta tabela como efeito colateral.
CREATE TABLE IF NOT EXISTS operators (
    operator_id      TEXT    PRIMARY KEY,
    description      TEXT,
    first_seen_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_seen_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (length(operator_id) BETWEEN 1 AND 128)
);

-- ------------------------------------------------------------
-- Tabela: schema_version (controle de migrations futuras)
-- ------------------------------------------------------------
-- Cada linha = 1 migration aplicada. A API sempre checa o MAX(version)
-- antes de operar, e roda migrations pendentes se houver.
CREATE TABLE IF NOT EXISTS schema_version (
    version         INTEGER PRIMARY KEY,
    applied_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    description     TEXT
);

-- Registra versão atual (idempotente)
INSERT OR IGNORE INTO schema_version (version, description)
VALUES ({SCHEMA_VERSION}, 'Schema inicial — Acervo Editorial de Mídia v{CONTRACT_VERSION}');

-- ------------------------------------------------------------
-- Índices para queries comuns (MidiaQuery)
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_midia_source         ON midia(source);
CREATE INDEX IF NOT EXISTS idx_midia_license        ON midia(license);
CREATE INDEX IF NOT EXISTS idx_midia_status         ON midia(validation_status);
CREATE INDEX IF NOT EXISTS idx_midia_storage_kind   ON midia(storage_kind);
CREATE INDEX IF NOT EXISTS idx_midia_collected_at   ON midia(collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_midia_collected_by   ON midia(collected_by);

-- Dedupe: external_id único por source
CREATE UNIQUE INDEX IF NOT EXISTS uq_midia_external_id_source
    ON midia(source, external_id) WHERE external_id IS NOT NULL;

-- Dedupe: sha256 único quando presente
CREATE UNIQUE INDEX IF NOT EXISTS uq_midia_sha256
    ON midia(sha256) WHERE sha256 IS NOT NULL;
"""


__all__ = ["SCHEMA_VERSION", "schema_ddl"]

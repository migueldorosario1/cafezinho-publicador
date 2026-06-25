"""api.py — API operacional do Acervo Editorial de Mídia.

Esta é a **fachada canônica** para todos os produtores, consumidores e
validadores que usam o acervo. Qualquer acesso direto às tabelas SQLite
fora deste módulo é desencorajado — o contrato Pydantic é a fonte de
verdade e a API é o único gargalo de I/O.

Princípios (regra de ouro do GPT):
  1. Contrato válido para qualquer produtor/consumidor, atual ou futuro.
  2. Nenhum conhecimento de domínio específico (Flickr, Wikimedia, V3)
     vive aqui — apenas CRUD genérico sobre MidiaRecord.
  3. Erros de contrato viram ``ContratoInvalidoError``; erros de negócio
     viram suas exceções específicas (ver ``contracts.py``).
  4. Thread-safe: cada chamada abre sua própria conexão (SQLite WAL).

Operações expostas:
  - ``register_midia(MidiaRecord) -> MidiaRecord`` — insere, dedupe
  - ``get_midia(UUID) -> MidiaRecord`` — leitura por id
  - ``search_midia(MidiaQuery) -> MidiaPage`` — busca paginada
  - ``update_validation(UUID, ResultadoValidacao) -> MidiaRecord``
  - ``delete_midia(UUID) -> None`` — remove do acervo
  - ``stats() -> AcervoStats`` — agregados

Configuração:
  - DB path default: ``agents/biblioteca_midia/data/acervo.db``
  - Override via env ``ACERVO_MIDIA_DB_PATH`` (testes, CI).
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional
from uuid import UUID

from .contracts import (
    CONTRACT_VERSION,
    AcervoStats,
    ContratoInvalidoError,
    FonteMidia,
    LicencaMidia,
    MidiaDuplicadaError,
    MidiaNaoEncontradaError,
    MidiaPage,
    MidiaQuery,
    MidiaRecord,
    OperatorRef,
    ResultadoValidacao,
    StatusValidacao,
    StorageKind,
    StorageProvider,
)
from .schema import SCHEMA_VERSION, schema_ddl


# ============================================================
# CONFIG — DB path resolvível
# ============================================================

_DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent / "data" / "acervo.db"
)


def _resolve_db_path(override: Optional[str | Path] = None) -> str:
    """Resolve path do DB: override > env > default."""
    if override is not None:
        return str(override)
    env = os.environ.get("ACERVO_MIDIA_DB_PATH")
    if env:
        return env
    return str(_DEFAULT_DB_PATH)


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 tolerante a sufixo 'Z' (Python < 3.11)."""
    if s is None:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ============================================================
# CONEXÃO — factory com PRAGMAsseguro
# ============================================================

@contextmanager
def _connect(db_path: str) -> Iterator[sqlite3.Connection]:
    """Abre conexão com PRAGMAs e fecha ao final."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)  # autocommit
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA encoding = 'UTF-8'")
        yield conn
    finally:
        conn.close()


# ============================================================
# INIT — bootstrap do schema
# ============================================================

def init_db(db_path: Optional[str | Path] = None) -> None:
    """Cria schema se não existir. Idempotente."""
    path = _resolve_db_path(db_path)
    with _connect(path) as conn:
        conn.executescript(schema_ddl())
        applied = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0]
        if applied is None or applied < SCHEMA_VERSION:
            raise RuntimeError(
                f"Schema version mismatch: expected >= {SCHEMA_VERSION}, "
                f"got {applied}"
            )


# ============================================================
# SERIALIZAÇÃO — Pydantic <-> SQLite row
# ============================================================

def _row_to_record(row: sqlite3.Row) -> MidiaRecord:
    """Converte linha SQLite em MidiaRecord (com entidades/tags)."""
    d = dict(row)
    entities_json = d.pop("_entities_json", "[]")
    tags_json = d.pop("_tags_json", "[]")
    entities = json.loads(entities_json) if entities_json else []
    tags = json.loads(tags_json) if tags_json else []
    storage_url = d.pop("storage_url", None)
    return MidiaRecord(
        id=UUID(d["id"]),
        external_id=d["external_id"],
        source=FonteMidia(d["source"]),
        mime_type=d["mime_type"],
        width=d["width"],
        height=d["height"],
        bytes_size=d["bytes_size"],
        sha256=d["sha256"],
        storage={
            "kind": StorageKind(d["storage_kind"]),
            "provider": StorageProvider(d["storage_provider"]),
            "bucket": d["storage_bucket"],
            "key": d["storage_key"],
            "url": storage_url,
        },
        title=d["title"],
        description=d["description"],
        alt_text=d["alt_text"],
        credit=d["credit"],
        license=LicencaMidia(d["license"]),
        license_url=d["license_url"],
        source_url=d["source_url"],
        entities=entities,
        tags=tags,
        collected_at=_parse_iso(d["collected_at"]),
        collected_by=OperatorRef(operator_id=d["collected_by"]),
        validation_status=StatusValidacao(d["validation_status"]),
        validation_reason=d["validation_reason"],
        validated_at=_parse_iso(d["validated_at"]),
        validated_by=(
            OperatorRef(operator_id=d["validated_by"])
            if d["validated_by"]
            else None
        ),
        contract_version=d["contract_version"],
    )


def _record_to_row(r: MidiaRecord) -> dict:
    """Converte MidiaRecord em dict de colunas SQLite."""
    storage = r.storage
    return {
        "id": str(r.id),
        "external_id": r.external_id,
        "source": r.source.value,
        "mime_type": r.mime_type,
        "width": r.width,
        "height": r.height,
        "bytes_size": r.bytes_size,
        "sha256": r.sha256,
        "storage_kind": storage.kind.value,
        "storage_provider": storage.provider.value,
        "storage_bucket": storage.bucket,
        "storage_key": storage.key,
        "storage_url": str(storage.url) if storage.url else None,
        "title": r.title,
        "description": r.description,
        "alt_text": r.alt_text,
        "credit": r.credit,
        "license": r.license.value,
        "license_url": str(r.license_url) if r.license_url else None,
        "source_url": str(r.source_url) if r.source_url else None,
        "collected_at": r.collected_at.isoformat(),
        "collected_by": r.collected_by.operator_id,
        "validation_status": r.validation_status.value,
        "validation_reason": r.validation_reason,
        "validated_at": r.validated_at.isoformat() if r.validated_at else None,
        "validated_by": r.validated_by.operator_id if r.validated_by else None,
        "contract_version": r.contract_version,
    }


# ============================================================
# API — operações públicas
# ============================================================

class AcervoEditorialAPI:
    """Fachada de acesso ao Acervo Editorial de Mídia.

    Instancie uma vez por processo; thread-safe via conexões curtas.
    """

    def __init__(self, db_path: Optional[str | Path] = None):
        self.db_path = _resolve_db_path(db_path)
        init_db(self.db_path)

    # ----- PRODUÇÃO (write) -----

    def register_midia(self, record: MidiaRecord) -> MidiaRecord:
        """Insere mídia. Levanta ``MidiaDuplicadaError`` se conflitar.

        Dedupe por:
          - (source, external_id) quando external_id presente
          - sha256 quando presente
        """
        row = _record_to_row(record)
        with _connect(self.db_path) as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO midia (
                        id, external_id, source, mime_type, width, height,
                        bytes_size, sha256, storage_kind, storage_provider,
                        storage_bucket, storage_key, storage_url,
                        title, description, alt_text, credit, license,
                        license_url, source_url, collected_at, collected_by,
                        validation_status, validation_reason, validated_at,
                        validated_by, contract_version
                    ) VALUES (
                        :id, :external_id, :source, :mime_type, :width, :height,
                        :bytes_size, :sha256, :storage_kind, :storage_provider,
                        :storage_bucket, :storage_key, :storage_url,
                        :title, :description, :alt_text, :credit, :license,
                        :license_url, :source_url, :collected_at, :collected_by,
                        :validation_status, :validation_reason, :validated_at,
                        :validated_by, :contract_version
                    )
                    """,
                    row,
                )
            except sqlite3.IntegrityError as e:
                msg = str(e).lower()
                # SQLite frequentemente não menciona o nome do índice UNIQUE
                # parcial; checamos por substring da coluna envolvida.
                if "external_id" in msg:
                    raise MidiaDuplicadaError(
                        f"Mídia duplicada: source={record.source.value} "
                        f"external_id={record.external_id!r}"
                    ) from e
                if "sha256" in msg:
                    raise MidiaDuplicadaError(
                        f"Mídia duplicada por sha256: {record.sha256}"
                    ) from e
                if "primary key" in msg:
                    raise MidiaDuplicadaError(
                        f"Mídia duplicada por id: {record.id}"
                    ) from e
                raise ContratoInvalidoError(f"Integrity: {msg}") from e

            # Catálogo de operator (efeito colateral)
            conn.execute(
                """
                INSERT INTO operators (operator_id, description)
                VALUES (:oid, :desc)
                ON CONFLICT(operator_id) DO UPDATE SET
                    last_seen_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                {
                    "oid": record.collected_by.operator_id,
                    "desc": record.collected_by.description,
                },
            )

            # Entidades
            for pos, entity in enumerate(record.entities):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO midia_entity (midia_id, entity, position)
                    VALUES (?, ?, ?)
                    """,
                    (str(record.id), entity, pos),
                )

            # Tags
            for pos, tag in enumerate(record.tags):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO midia_tag (midia_id, tag, position)
                    VALUES (?, ?, ?)
                    """,
                    (str(record.id), tag, pos),
                )

        return self.get_midia(record.id)

    # ----- LEITURA -----

    def get_midia(self, midia_id: UUID | str) -> MidiaRecord:
        """Recupera mídia por id. ``MidiaNaoEncontradaError`` se ausente."""
        midia_id_str = str(midia_id) if isinstance(midia_id, UUID) else midia_id
        with _connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT m.*,
                    (SELECT json_group_array(entity) FROM (
                        SELECT entity FROM midia_entity
                        WHERE midia_id = m.id ORDER BY position
                    )) AS _entities_json,
                    (SELECT json_group_array(tag) FROM (
                        SELECT tag FROM midia_tag
                        WHERE midia_id = m.id ORDER BY position
                    )) AS _tags_json
                FROM midia m
                WHERE m.id = ?
                """,
                (midia_id_str,),
            ).fetchone()
            if row is None:
                raise MidiaNaoEncontradaError(
                    f"Mídia não encontrada: id={midia_id_str}"
                )
            return _row_to_record(row)

    def search_midia(self, query: MidiaQuery) -> MidiaPage:
        """Busca paginada. Filtros AND entre campos; OR dentro de listas."""
        sql = ["SELECT DISTINCT m.id FROM midia m"]
        params: list = []
        clauses: list[str] = []

        if query.entities:
            placeholders = ",".join("?" * len(query.entities))
            clauses.append(
                f"""
                m.id IN (
                    SELECT me.midia_id FROM midia_entity me
                    WHERE me.entity IN ({placeholders})
                )
                """
            )
            params.extend(query.entities)

        if query.source is not None:
            clauses.append("m.source = ?")
            params.append(query.source.value)

        if query.license is not None:
            clauses.append("m.license = ?")
            params.append(query.license.value)

        if query.licenses_allowed:
            placeholders = ",".join("?" * len(query.licenses_allowed))
            clauses.append(f"m.license IN ({placeholders})")
            params.extend(l.value for l in query.licenses_allowed)

        if query.validation_status is not None:
            clauses.append("m.validation_status = ?")
            params.append(query.validation_status.value)

        if query.storage_kind is not None:
            clauses.append("m.storage_kind = ?")
            params.append(query.storage_kind.value)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql.append(where)

        # Conta total
        count_sql = f"SELECT COUNT(*) FROM ({' '.join(sql)})"
        with _connect(self.db_path) as conn:
            total = conn.execute(count_sql, params).fetchone()[0]

        # Pagina
        sql.append("ORDER BY m.collected_at DESC")
        sql.append("LIMIT ? OFFSET ?")
        params.extend([query.limit, query.offset])

        with _connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            ids = [
                r[0]
                for r in conn.execute(" ".join(sql), params).fetchall()
            ]

        items = [self.get_midia(i) for i in ids]
        has_more = (query.offset + len(items)) < total

        return MidiaPage(
            items=items,
            total=total,
            offset=query.offset,
            limit=query.limit,
            has_more=has_more,
        )

    # ----- VALIDAÇÃO -----

    def update_validation(
        self,
        midia_id: UUID | str,
        resultado: ResultadoValidacao,
    ) -> MidiaRecord:
        """Atualiza estado de validação. Não mexe em outros campos."""
        midia_id_str = str(midia_id) if isinstance(midia_id, UUID) else midia_id
        if str(resultado.midia_id) != midia_id_str:
            raise ContratoInvalidoError(
                f"midia_id mismatch: path={midia_id_str} "
                f"resultado={resultado.midia_id}"
            )
        with _connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE midia SET
                    validation_status = ?,
                    validation_reason = ?,
                    validated_at = ?,
                    validated_by = ?,
                    _updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (
                    resultado.status.value,
                    resultado.reason,
                    resultado.validated_at.isoformat(),
                    resultado.validated_by.operator_id,
                    midia_id_str,
                ),
            )
            if cur.rowcount == 0:
                raise MidiaNaoEncontradaError(
                    f"Mídia não encontrada: id={midia_id_str}"
                )
        return self.get_midia(midia_id_str)

    # ----- REMOÇÃO -----

    def delete_midia(self, midia_id: UUID | str) -> None:
        """Remove mídia. Cascade limpa entidades/tags."""
        midia_id_str = str(midia_id) if isinstance(midia_id, UUID) else midia_id
        with _connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM midia WHERE id = ?", (midia_id_str,))
            if cur.rowcount == 0:
                raise MidiaNaoEncontradaError(
                    f"Mídia não encontrada: id={midia_id_str}"
                )

    # ----- ESTATÍSTICAS -----

    def stats(self) -> AcervoStats:
        """Agregados do acervo para dashboard / monitoramento."""
        with _connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM midia").fetchone()[0]
            by_source = dict(
                conn.execute(
                    "SELECT source, COUNT(*) FROM midia GROUP BY source"
                ).fetchall()
            )
            by_license = dict(
                conn.execute(
                    "SELECT license, COUNT(*) FROM midia GROUP BY license"
                ).fetchall()
            )
            by_status = dict(
                conn.execute(
                    "SELECT validation_status, COUNT(*) FROM midia "
                    "GROUP BY validation_status"
                ).fetchall()
            )
            by_collected_by = dict(
                conn.execute(
                    "SELECT collected_by, COUNT(*) FROM midia "
                    "GROUP BY collected_by"
                ).fetchall()
            )
            last_row = conn.execute(
                "SELECT MAX(_updated_at) FROM midia"
            ).fetchone()
            last_updated_str = last_row[0] if last_row else None
            last_updated = _parse_iso(last_updated_str)

        return AcervoStats(
            total_midia=total,
            by_source=by_source,
            by_license=by_license,
            by_validation_status=by_status,
            by_collected_by=by_collected_by,
            last_updated=last_updated,
        )


# ============================================================
# FACTORY — instância singleton para processo
# ============================================================

_default_api: Optional[AcervoEditorialAPI] = None


def get_api(db_path: Optional[str | Path] = None) -> AcervoEditorialAPI:
    """Retorna singleton da API. Cria DB se não existir."""
    global _default_api
    if _default_api is None or db_path is not None:
        _default_api = AcervoEditorialAPI(db_path=db_path)
    return _default_api


__all__ = [
    "AcervoEditorialAPI",
    "init_db",
    "get_api",
]

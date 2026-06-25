"""contracts.py — Contratos Pydantic do Acervo Editorial de Mídia.

CONTRATOS CANÔNICOS. Estáveis para todos os produtores e consumidores,
atuais e futuros:

- Produtores (gravam no acervo):
  - flickr_harvester
  - wikimedia_harvester
  - r2_uploader
  - futuro: agency_harvester, user_upload, ...

- Consumidores (lêem do acervo):
  - wordpress_publisher
  - vision_cataloger (atualiza estado de validação)
  - embedding_cataloger (lê para vetorizar)
  - V3 pipeline (substitui banco_midia_cafezinho.db)
  - futuro: search_service, media_promoter, novos portais

REGRAS DE EVOLUÇÃO (backwards-compatible):
  1. Nunca remover campo existente — marcar deprecated se preciso.
  2. Adicionar novos campos sempre com default.
  3. Novos valores de enum só podem ser adicionados (nunca removidos).
  4. Bump em ``CONTRACT_VERSION`` (SemVer) quando houver mudança.
  5. Sempre que mudar, atualizar ``CONTRATOS.md`` com data e justificativa.

Mantenedor atual: GLM (Ming).
Homologado por: GPT (Arquiteto-chefe), Codex (coordenador),
                Claude Code (auditor), Miguel (homologação).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


# ============================================================
# CONSTANTES DE VERSIONAMENTO
# ============================================================

CONTRACT_VERSION = "1.0.0"


# ============================================================
# ENUMS — listas só crescem, nunca removem valores
# ============================================================

class FonteMidia(str, Enum):
    """Fonte origem da mídia (quem produziu/colheu o registro)."""

    FLICKR = "flickr"
    WIKIMEDIA_COMMONS = "wikimedia_commons"
    R2_UPLOADED = "r2_uploaded"
    LEGACY_BANCO_MIDIA = "legacy_banco_midia"
    MANUAL = "manual"
    EXTERNAL_URL = "external_url"


class LicencaMidia(str, Enum):
    """Licença editorial da mídia (vocabulário Creative Commons + PD + especiais).

    Todas as licenças podem ser REGISTRADAS no acervo. A política editorial
    do Cafezinho definirá em runtime quais são publicáveis.
    """

    CC0 = "CC0"
    PDM = "PDM"
    CC_BY = "CC-BY"
    CC_BY_SA = "CC-BY-SA"
    CC_BY_ND = "CC-BY-ND"
    CC_BY_NC = "CC-BY-NC"
    CC_BY_NC_SA = "CC-BY-NC-SA"
    CC_BY_NC_ND = "CC-BY-NC-ND"
    RIGHTS_RESERVED = "RIGHTS_RESERVED"
    UNKNOWN = "UNKNOWN"


class StatusValidacao(str, Enum):
    """Estado editorial da mídia — pode ser publicada?"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    QUARANTINE = "quarantine"


class StorageKind(str, Enum):
    """Tipo lógico de armazenamento do binário."""

    R2 = "r2"
    S3 = "s3"
    LOCAL_FILE = "local_file"
    EXTERNAL_URL = "external_url"


class StorageProvider(str, Enum):
    """Provider físico de armazenamento. Complementa ``StorageKind``."""

    CLOUDFLARE_R2 = "cloudflare_r2"
    BACKBLAZE_B2 = "backblaze_b2"
    AWS_S3 = "aws_s3"
    LOCAL_DISK = "local_disk"
    EXTERNAL = "external"


# ============================================================
# OPERATOR — quem/qual agente tocou o registro
# ============================================================

class OperatorRef(BaseModel):
    """Referência a um operador (agente ou humano) que produziu/curou o registro.

    ``operator_id`` é string livre, permitindo futuros agentes sem mudar
    contrato. Exemplos canônicos:
      - "flickr_harvester"
      - "wikimedia_harvester"
      - "r2_uploader"
      - "vision_cataloger"
      - "v3_pipeline"
      - "manual:miguel"
      - "legacy_migration"
    """

    operator_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Identificador do operador (ex: 'flickr_harvester').",
    )
    description: Optional[str] = Field(
        None,
        description="Descrição humanamente legível do operador (opcional).",
    )


# ============================================================
# STORAGE REFERENCE — onde está o binário
# ============================================================

class StorageRef(BaseModel):
    """Referência ao binário físico da mídia.

    O binário NÃO precisa estar hospedado por nós — basta saber onde está.

    Exemplos:
      - R2:        kind=r2, provider=cloudflare_r2,
                   bucket=cafezinho-media, key=lula/2026/evento.jpg
      - External:  kind=external_url, provider=external,
                   url=https://live.staticflickr.com/xxx.jpg
      - Local:     kind=local_file, provider=local_disk,
                   key=/var/cache/midias/abc.jpg
    """

    kind: StorageKind
    provider: StorageProvider = StorageProvider.EXTERNAL
    bucket: Optional[str] = Field(
        None,
        max_length=256,
        description="Bucket (quando aplicável ao kind).",
    )
    key: Optional[str] = Field(
        None,
        max_length=1024,
        description="Chave/path dentro do bucket (quando aplicável).",
    )
    url: Optional[HttpUrl] = Field(
        None,
        description="URL pública acessível, se disponível.",
    )


# ============================================================
# MIDIA RECORD — registro atômico do acervo
# ============================================================

class MidiaRecord(BaseModel):
    """Registro atômico de uma mídia no Acervo Editorial.

    Unidade fundamental do acervo. Cada registro é uma imagem (futuro:
    vídeo, áudio, documento) com metadados editoriais completos.

    INVARIANTES garantidas por Pydantic:
      - ``id`` é UUID único (auto-gerado se não fornecido).
      - ``width`` e ``height`` são inteiros positivos (1..65535).
      - ``title`` é não-vazio, até 500 chars.
      - ``credit`` é não-vazio (crédito editorial obrigatório).
      - ``license`` é valor válido de ``LicencaMidia``.
      - ``collected_at`` é timezone-aware (UTC default).
      - ``contract_version`` segue SemVer (default = ``CONTRACT_VERSION``).
    """

    # --- Identificação ---
    id: UUID = Field(default_factory=uuid4)
    external_id: Optional[str] = Field(
        None,
        max_length=256,
        description=(
            "ID na fonte origem (ex: 'photo_id' Flickr). "
            "Permite dedupe cross-source."
        ),
    )
    source: FonteMidia

    # --- Técnico ---
    mime_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="MIME type (ex: 'image/jpeg', 'image/png').",
    )
    width: int = Field(..., ge=1, le=65535, description="Largura em pixels.")
    height: int = Field(..., ge=1, le=65535, description="Altura em pixels.")
    bytes_size: int = Field(
        ...,
        ge=0,
        le=10_000_000_000,
        description="Tamanho do binário em bytes (hard cap 10 GB).",
    )
    sha256: Optional[str] = Field(
        None,
        min_length=64,
        max_length=64,
        description="Hash SHA-256 do binário (hex). Dedupe por conteúdo.",
    )

    # --- Armazenamento ---
    storage: StorageRef

    # --- Editorial ---
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(
        None,
        max_length=5000,
        description="Descrição/caption editorial (não é texto alternativo).",
    )
    alt_text: Optional[str] = Field(
        None,
        max_length=500,
        description="Texto alternativo para acessibilidade (futuro).",
    )
    credit: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Crédito editorial obrigatório (ex: 'Flickr/Planalto').",
    )
    license: LicencaMidia
    license_url: Optional[HttpUrl] = Field(
        None,
        description="URL da licença (ex: creativecommons.org/licenses/by/2.0/).",
    )
    source_url: Optional[HttpUrl] = Field(
        None,
        description="URL da página origem (DIFERENTE da URL do binário).",
    )

    # --- Entidades (pessoas, lugares, organizações, eventos) ---
    entities: list[str] = Field(
        default_factory=list,
        description="Entidades detectadas/vinculadas (ex: ['Lula', 'STF']).",
    )

    # --- Tags editoriais (livres, para categorização) ---
    tags: list[str] = Field(
        default_factory=list,
        description="Tags editoriais livres (ex: ['politica', 'evento-oficial']).",
    )

    # --- Proveniência ---
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Quando o registro foi criado no acervo (UTC).",
    )
    collected_by: OperatorRef

    # --- Validação (Vision Cataloger / curadoria) ---
    validation_status: StatusValidacao = StatusValidacao.PENDING
    validation_reason: Optional[str] = Field(
        None,
        max_length=2000,
        description="Motivo da aprovação/reprovação (quando aplicável).",
    )
    validated_at: Optional[datetime] = None
    validated_by: Optional[OperatorRef] = None

    # --- Versionamento do contrato ---
    contract_version: str = Field(
        default=CONTRACT_VERSION,
        description="Versão do contrato Pydantic deste registro (SemVer).",
    )


# ============================================================
# QUERY / PAGE (para consumidores consultarem)
# ============================================================

class MidiaQuery(BaseModel):
    """Consulta ao acervo. Todos os filtros são opcionais (AND lógico entre
    campos; OR dentro de listas)."""

    entities: Optional[list[str]] = Field(
        None,
        description="Filtrar por entidades (OR dentro da lista).",
    )
    source: Optional[FonteMidia] = None
    license: Optional[LicencaMidia] = None
    licenses_allowed: Optional[list[LicencaMidia]] = Field(
        None,
        description="Filtrar só licenças permitidas (OR dentro da lista).",
    )
    validation_status: Optional[StatusValidacao] = None
    storage_kind: Optional[StorageKind] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class MidiaPage(BaseModel):
    """Resultado paginado de busca no acervo."""

    items: list[MidiaRecord]
    total: int = Field(..., ge=0)
    offset: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    has_more: bool


# ============================================================
# RESULTADO DE VALIDAÇÃO — emitido por vision_cataloger / humanos
# ============================================================

class ResultadoValidacao(BaseModel):
    """Resultado de uma validação (Vision Cataloger, tribunal_visual, curadoria).

    Visão futura: diferentes provedores (Gemini Vision, Qwen-VL,
    tribunal_visual legado, curadoria humana) podem emitir validações.
    O validador identifica-se em ``validated_by``.
    """

    midia_id: UUID
    status: StatusValidacao
    reason: Optional[str] = Field(None, max_length=2000)
    validated_by: OperatorRef
    validated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ============================================================
# STATS — agregados para dashboard / monitoramento
# ============================================================

class AcervoStats(BaseModel):
    """Estatísticas agregadas do acervo."""

    total_midia: int = Field(..., ge=0)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_license: dict[str, int] = Field(default_factory=dict)
    by_validation_status: dict[str, int] = Field(default_factory=dict)
    by_collected_by: dict[str, int] = Field(default_factory=dict)
    last_updated: Optional[datetime] = None


# ============================================================
# EXCEÇÕES — hierarquia própria do acervo
# ============================================================

class AcervoEditorialError(Exception):
    """Erro base do Acervo Editorial de Mídia."""


class MidiaNaoEncontradaError(AcervoEditorialError):
    """Mídia não encontrada no acervo (lookup por id falhou)."""


class MidiaDuplicadaError(AcervoEditorialError):
    """Mídia duplicada (mesmo external_id+source ou mesmo sha256)."""


class ContratoInvalidoError(AcervoEditorialError):
    """Violação de contrato Pydantic na entrada/saída."""


# ============================================================
# EXPORTS — explícito para contratos estáveis
# ============================================================

__all__ = [
    # Constante
    "CONTRACT_VERSION",
    # Enums
    "FonteMidia",
    "LicencaMidia",
    "StatusValidacao",
    "StorageKind",
    "StorageProvider",
    # Modelos
    "OperatorRef",
    "StorageRef",
    "MidiaRecord",
    "MidiaQuery",
    "MidiaPage",
    "ResultadoValidacao",
    "AcervoStats",
    # Exceções
    "AcervoEditorialError",
    "MidiaNaoEncontradaError",
    "MidiaDuplicadaError",
    "ContratoInvalidoError",
]

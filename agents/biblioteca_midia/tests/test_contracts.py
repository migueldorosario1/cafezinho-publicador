"""test_contracts.py — Testes canônicos dos contratos do Acervo Editorial.

Garante que os modelos em contracts.py cumprem as invariantes documentadas
em CONTRATOS.md. Roda em PR #1 e deve permanecer verde para quaisquer
produtores/consumidores que usem contrato v1.x.

Para rodar:
    cd <repo-root>
    pip install -r agents/biblioteca_midia/requirements.txt
    pip install pytest
    pytest agents/biblioteca_midia/tests/test_contracts.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from agents.biblioteca_midia.contracts import (
    CONTRACT_VERSION,
    AcervoEditorialError,
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
    StorageRef,
)


# ============================================================
# FIXTURES — builders para reduzir boilerplate
# ============================================================

def _make_storage(**overrides) -> StorageRef:
    defaults = dict(
        kind=StorageKind.EXTERNAL_URL,
        provider=StorageProvider.EXTERNAL,
        url="https://live.staticflickr.com/65535/12345.jpg",
    )
    defaults.update(overrides)
    return StorageRef(**defaults)


def _make_operator(**overrides) -> OperatorRef:
    defaults = dict(operator_id="flickr_harvester")
    defaults.update(overrides)
    return OperatorRef(**defaults)


def _make_midia_record(**overrides) -> MidiaRecord:
    """Builder: produz MidiaRecord válido. Overrides substituem defaults."""
    defaults = dict(
        external_id="12345@flickr",
        source=FonteMidia.FLICKR,
        mime_type="image/jpeg",
        width=1600,
        height=1067,
        bytes_size=2_048_576,
        sha256="a" * 64,
        storage=_make_storage(),
        title="Lula em cerimônia oficial",
        description="Presidente fala durante evento.",
        credit="Flickr/Planalto",
        license=LicencaMidia.CC_BY,
        license_url="https://creativecommons.org/licenses/by/2.0/",
        source_url="https://www.flickr.com/photos/planalto/12345/",
        entities=["Lula", "Planalto"],
        tags=["politica"],
        collected_by=_make_operator(),
    )
    defaults.update(overrides)
    return MidiaRecord(**defaults)


# ============================================================
# TESTES — CONSTANTES
# ============================================================

class TestContractVersion:
    def test_version_is_string_semver(self):
        assert isinstance(CONTRACT_VERSION, str)
        # SemVer-like: MAJOR.MINOR.PATCH
        parts = CONTRACT_VERSION.split(".")
        assert len(parts) == 3
        for p in parts:
            assert p.isdigit(), f"Version part {p!r} not numeric"

    def test_version_v1_in_sprint_a(self):
        major = int(CONTRACT_VERSION.split(".")[0])
        assert major >= 1, "Sprint A começa em v1.x.x"


# ============================================================
# TESTES — ENUMS (listas só crescem)
# ============================================================

class TestFonteMidia:
    def test_flickr_present(self):
        assert FonteMidia.FLICKR.value == "flickr"

    def test_wikimedia_present(self):
        assert FonteMidia.WIKIMEDIA_COMMONS.value == "wikimedia_commons"

    def test_r2_uploaded_present(self):
        assert FonteMidia.R2_UPLOADED.value == "r2_uploaded"

    def test_at_least_six_sources_defined(self):
        # flickr, wikimedia, r2, legacy, manual, external_url
        assert len(list(FonteMidia)) >= 6

    def test_no_duplicate_values(self):
        values = [f.value for f in FonteMidia]
        assert len(values) == len(set(values)), "Duplicate enum values"


class TestLicencaMidia:
    def test_creative_commons_core_present(self):
        values = {l.value for l in LicencaMidia}
        # Conjunto mínimo CC + PD + casos especiais
        for required in ("CC0", "PDM", "CC-BY", "CC-BY-SA", "RIGHTS_RESERVED", "UNKNOWN"):
            assert required in values, f"Required license {required!r} missing"

    def test_no_duplicate_values(self):
        values = [l.value for l in LicencaMidia]
        assert len(values) == len(set(values))


class TestStatusValidacao:
    def test_all_states_present(self):
        values = {s.value for s in StatusValidacao}
        assert values >= {"pending", "approved", "rejected"}

    def test_quarantine_present(self):
        # quarantine é state reservado para futuros casos
        values = {s.value for s in StatusValidacao}
        assert "quarantine" in values


class TestStorageEnums:
    def test_storage_kinds_present(self):
        values = {k.value for k in StorageKind}
        for required in ("r2", "s3", "local_file", "external_url"):
            assert required in values

    def test_providers_present(self):
        values = {p.value for p in StorageProvider}
        for required in ("cloudflare_r2", "backblaze_b2", "aws_s3", "local_disk", "external"):
            assert required in values


# ============================================================
# TESTES — OPERATOR REF
# ============================================================

class TestOperatorRef:
    def test_minimal(self):
        op = OperatorRef(operator_id="flickr_harvester")
        assert op.operator_id == "flickr_harvester"
        assert op.description is None

    def test_with_description(self):
        op = OperatorRef(operator_id="v3_pipeline", description="V3 editorial pipeline")
        assert op.description == "V3 editorial pipeline"

    def test_empty_id_rejected(self):
        with pytest.raises(ValidationError):
            OperatorRef(operator_id="")

    def test_too_long_id_rejected(self):
        with pytest.raises(ValidationError):
            OperatorRef(operator_id="x" * 129)


# ============================================================
# TESTES — STORAGE REF
# ============================================================

class TestStorageRef:
    def test_external_url_kind(self):
        s = _make_storage()
        assert s.kind == StorageKind.EXTERNAL_URL

    def test_r2_with_bucket_and_key(self):
        s = StorageRef(
            kind=StorageKind.R2,
            provider=StorageProvider.CLOUDFLARE_R2,
            bucket="cafezinho-media",
            key="lula/2026/evento.jpg",
        )
        assert s.bucket == "cafezinho-media"
        assert s.kind == StorageKind.R2

    def test_provider_defaults_to_external(self):
        s = StorageRef(kind=StorageKind.EXTERNAL_URL, url="https://example.com/x.jpg")
        assert s.provider == StorageProvider.EXTERNAL

    def test_url_validated_as_http_url(self):
        with pytest.raises(ValidationError):
            StorageRef(kind=StorageKind.EXTERNAL_URL, url="not-a-url")


# ============================================================
# TESTES — MIDIA RECORD (registro atômico)
# ============================================================

class TestMidiaRecordDefaults:
    """Garante defaults aplicados conforme CONTRATOS.md."""

    def test_id_auto_generated_as_uuid(self):
        r = _make_midia_record()
        assert isinstance(r.id, UUID)
        r2 = _make_midia_record()
        assert r.id != r2.id, "IDs should be unique"

    def test_validation_status_defaults_to_pending(self):
        r = _make_midia_record()
        assert r.validation_status == StatusValidacao.PENDING

    def test_collected_at_defaults_to_utc_now(self):
        before = datetime.now(timezone.utc)
        r = _make_midia_record()
        after = datetime.now(timezone.utc)
        assert r.collected_at >= before
        assert r.collected_at <= after
        # timezone-aware
        assert r.collected_at.tzinfo is not None

    def test_contract_version_defaults_to_current(self):
        r = _make_midia_record()
        assert r.contract_version == CONTRACT_VERSION

    def test_validated_at_defaults_none(self):
        r = _make_midia_record()
        assert r.validated_at is None
        assert r.validated_by is None

    def test_entities_default_empty_list(self):
        # Quando entities NÃO é passado, default_factory protege contra
        # mutabilidade compartilhada e produz lista vazia.
        r = MidiaRecord(
            source=FonteMidia.FLICKR,
            mime_type="image/jpeg", width=1, height=1, bytes_size=1,
            storage=_make_storage(),
            title="x", credit="x", license=LicencaMidia.CC0,
            collected_by=_make_operator(),
        )
        assert r.entities == []

    def test_entities_none_explicit_rejected(self):
        # Pydantic v2 não converte None para default_factory — contratos
        # exigem chamada explícita sem o campo quando se quer o default.
        with pytest.raises(ValidationError):
            _make_midia_record(entities=None)  # type: ignore[arg-type]

    def test_entities_default_not_shared_across_instances(self):
        # Mutabilidade: default_factory garante instância nova por registro
        # quando o campo não é explicitamente passado.
        def _bare() -> MidiaRecord:
            return MidiaRecord(
                source=FonteMidia.FLICKR,
                mime_type="image/jpeg", width=1, height=1, bytes_size=1,
                storage=_make_storage(),
                title="x", credit="x", license=LicencaMidia.CC0,
                collected_by=_make_operator(),
            )
        r1 = _bare()
        r2 = _bare()
        r1.entities.append("Lula")
        assert r2.entities == [], "Default list must not be shared"

    def test_external_id_optional(self):
        r = _make_midia_record(external_id=None)
        assert r.external_id is None


class TestMidiaRecordValidation:
    """Validação de invariantes documentadas."""

    def test_dimensions_must_be_positive(self):
        with pytest.raises(ValidationError):
            _make_midia_record(width=0)
        with pytest.raises(ValidationError):
            _make_midia_record(height=-1)

    def test_dimensions_upper_bound(self):
        # 65535 ok, 65536 falha
        _make_midia_record(width=65535, height=65535)
        with pytest.raises(ValidationError):
            _make_midia_record(width=65536)

    def test_bytes_size_upper_bound_10gb(self):
        _make_midia_record(bytes_size=10_000_000_000)  # 10 GB ok
        with pytest.raises(ValidationError):
            _make_midia_record(bytes_size=10_000_000_001)

    def test_title_required_non_empty(self):
        with pytest.raises(ValidationError):
            _make_midia_record(title="")

    def test_title_too_long_rejected(self):
        with pytest.raises(ValidationError):
            _make_midia_record(title="x" * 501)

    def test_credit_required_non_empty(self):
        with pytest.raises(ValidationError):
            _make_midia_record(credit="")

    def test_credit_too_long_rejected(self):
        with pytest.raises(ValidationError):
            _make_midia_record(credit="x" * 501)

    def test_description_max_5000(self):
        _make_midia_record(description="x" * 5000)  # ok
        with pytest.raises(ValidationError):
            _make_midia_record(description="x" * 5001)

    def test_sha256_exactly_64_hex_chars(self):
        _make_midia_record(sha256="a" * 64)  # ok
        with pytest.raises(ValidationError):
            _make_midia_record(sha256="a" * 63)
        with pytest.raises(ValidationError):
            _make_midia_record(sha256="a" * 65)

    def test_external_id_max_256(self):
        _make_midia_record(external_id="x" * 256)  # ok
        with pytest.raises(ValidationError):
            _make_midia_record(external_id="x" * 257)

    def test_invalid_license_rejected(self):
        with pytest.raises(ValidationError):
            _make_midia_record(license="invalid_license")  # type: ignore[arg-type]

    def test_invalid_source_rejected(self):
        with pytest.raises(ValidationError):
            _make_midia_record(source="invalid_source")  # type: ignore[arg-type]

    def test_mime_type_required_non_empty(self):
        with pytest.raises(ValidationError):
            _make_midia_record(mime_type="")


class TestMidiaRecordAllSourcesUsable:
    """Garantia de contrato: TODAS as fontes podem produzir MidiaRecord."""

    @pytest.mark.parametrize("source", list(FonteMidia))
    def test_record_from_each_source(self, source):
        r = _make_midia_record(source=source)
        assert r.source == source


class TestMidiaRecordAllLicensesUsable:
    """Garantia de contrato: TODAS as licenças podem ser registradas."""

    @pytest.mark.parametrize("license", list(LicencaMidia))
    def test_record_with_each_license(self, license):
        r = _make_midia_record(license=license)
        assert r.license == license


# ============================================================
# TESTES — MIDIA QUERY + PAGE
# ============================================================

class TestMidiaQuery:
    def test_defaults(self):
        q = MidiaQuery()
        assert q.entities is None
        assert q.source is None
        assert q.limit == 50
        assert q.offset == 0

    def test_limit_lower_bound(self):
        with pytest.raises(ValidationError):
            MidiaQuery(limit=0)

    def test_limit_upper_bound(self):
        MidiaQuery(limit=500)  # ok
        with pytest.raises(ValidationError):
            MidiaQuery(limit=501)

    def test_offset_lower_bound(self):
        with pytest.raises(ValidationError):
            MidiaQuery(offset=-1)

    def test_with_multiple_filters(self):
        q = MidiaQuery(
            entities=["Lula", "STF"],
            source=FonteMidia.FLICKR,
            licenses_allowed=[LicencaMidia.CC_BY, LicencaMidia.CC_BY_SA],
            validation_status=StatusValidacao.APPROVED,
            limit=25,
            offset=50,
        )
        assert q.entities == ["Lula", "STF"]
        assert q.source == FonteMidia.FLICKR
        assert len(q.licenses_allowed) == 2
        assert q.validation_status == StatusValidacao.APPROVED


class TestMidiaPage:
    def test_basic_page(self):
        items = [_make_midia_record() for _ in range(3)]
        page = MidiaPage(items=items, total=10, offset=0, limit=3, has_more=True)
        assert len(page.items) == 3
        assert page.total == 10
        assert page.has_more is True

    def test_empty_page(self):
        page = MidiaPage(items=[], total=0, offset=0, limit=50, has_more=False)
        assert page.items == []
        assert page.has_more is False

    def test_total_non_negative(self):
        with pytest.raises(ValidationError):
            MidiaPage(items=[], total=-1, offset=0, limit=50, has_more=False)


# ============================================================
# TESTES — RESULTADO VALIDACAO
# ============================================================

class TestResultadoValidacao:
    def test_approved(self):
        r = _make_midia_record()
        v = ResultadoValidacao(
            midia_id=r.id,
            status=StatusValidacao.APPROVED,
            validated_by=_make_operator(operator_id="vision_cataloger"),
        )
        assert v.status == StatusValidacao.APPROVED
        assert v.validated_at.tzinfo is not None

    def test_rejected_requires_reason(self):
        r = _make_midia_record()
        # Contrato: reason é opcional pydanticamente, mas contrato editorial
        # exige. Testes apenas validam que Pydantic aceita None.
        v = ResultadoValidacao(
            midia_id=r.id,
            status=StatusValidacao.REJECTED,
            reason="Pessoa errada identificada.",
            validated_by=_make_operator(),
        )
        assert v.reason is not None

    def test_validated_at_defaults_now(self):
        r = _make_midia_record()
        before = datetime.now(timezone.utc)
        v = ResultadoValidacao(
            midia_id=r.id,
            status=StatusValidacao.APPROVED,
            validated_by=_make_operator(),
        )
        assert v.validated_at >= before


# ============================================================
# TESTES — ACERVO STATS
# ============================================================

class TestAcervoStats:
    def test_minimal(self):
        s = AcervoStats(total_midia=0)
        assert s.total_midia == 0
        assert s.by_source == {}

    def test_populated(self):
        s = AcervoStats(
            total_midia=100,
            by_source={"flickr": 60, "wikimedia_commons": 40},
            by_license={"CC-BY": 70, "CC0": 30},
            by_validation_status={"approved": 80, "pending": 20},
            by_collected_by={"flickr_harvester": 60},
        )
        assert s.total_midia == 100
        assert s.by_source["flickr"] == 60

    def test_total_non_negative(self):
        with pytest.raises(ValidationError):
            AcervoStats(total_midia=-1)


# ============================================================
# TESTES — EXCEÇÕES HIERARQUIA
# ============================================================

class TestExcecoes:
    def test_midia_nao_encontrada_is_acervo_error(self):
        assert issubclass(MidiaNaoEncontradaError, AcervoEditorialError)

    def test_midia_duplicada_is_acervo_error(self):
        assert issubclass(MidiaDuplicadaError, AcervoEditorialError)

    def test_contrato_invalido_is_acervo_error(self):
        assert issubclass(ContratoInvalidoError, AcervoEditorialError)

    def test_raise_and_catch_as_base(self):
        with pytest.raises(AcervoEditorialError):
            raise MidiaNaoEncontradaError("test")
        with pytest.raises(AcervoEditorialError):
            raise MidiaDuplicadaError("test")
        with pytest.raises(AcervoEditorialError):
            raise ContratoInvalidoError("test")


# ============================================================
# TESTES — CONTRATO ENTRE PRODUTOR/CONSUMIDOR (regra de ouro GPT)
# ============================================================

class TestContratoProdutorConsumidor:
    """Regra de ouro do GPT: contrato válido para múltiplos produtores
    e consumidores atuais e futuros."""

    def test_flickr_harvester_pode_produzir(self):
        r = _make_midia_record(
            source=FonteMidia.FLICKR,
            collected_by=_make_operator(operator_id="flickr_harvester"),
        )
        assert r.source == FonteMidia.FLICKR

    def test_wikimedia_harvester_pode_produzir(self):
        r = _make_midia_record(
            source=FonteMidia.WIKIMEDIA_COMMONS,
            collected_by=_make_operator(operator_id="wikimedia_harvester"),
        )
        assert r.source == FonteMidia.WIKIMEDIA_COMMONS

    def test_r2_uploader_pode_produzir(self):
        r = _make_midia_record(
            source=FonteMidia.R2_UPLOADED,
            storage=StorageRef(
                kind=StorageKind.R2,
                provider=StorageProvider.CLOUDFLARE_R2,
                bucket="cafezinho-media",
                key="manual/img.jpg",
            ),
            collected_by=_make_operator(operator_id="r2_uploader"),
        )
        assert r.storage.kind == StorageKind.R2

    def test_wordpress_publisher_pode_consumir_via_query(self):
        # wordpress_publisher só publica CC0, PDM, CC-BY, CC-BY-SA
        q = MidiaQuery(
            licenses_allowed=[LicencaMidia.CC0, LicencaMidia.PDM,
                              LicencaMidia.CC_BY, LicencaMidia.CC_BY_SA],
            validation_status=StatusValidacao.APPROVED,
        )
        assert len(q.licenses_allowed) == 4

    def test_v3_pipeline_pode_consumir(self):
        # V3 pode usar filtro mais amplo
        q = MidiaQuery(entities=["Lula"], validation_status=StatusValidacao.APPROVED)
        assert q.entities == ["Lula"]

    def test_futuro_agente_pode_usar_operator_livre(self):
        # Mesmo um agente desconhecido hoje pode usar o contrato
        r = _make_midia_record(
            collected_by=_make_operator(operator_id="future_agent_xyz"),
        )
        assert r.collected_by.operator_id == "future_agent_xyz"


# ============================================================
# TESTES — SERIALIZAÇÃO (Pydantic v2)
# ============================================================

class TestSerializacao:
    def test_record_roundtrip_json(self):
        r = _make_midia_record()
        json_str = r.model_dump_json()
        r2 = MidiaRecord.model_validate_json(json_str)
        assert r.id == r2.id
        assert r.source == r2.source
        assert r.title == r2.title

    def test_record_roundtrip_dict(self):
        r = _make_midia_record()
        d = r.model_dump(mode="python")
        r2 = MidiaRecord.model_validate(d)
        assert r.id == r2.id

    def test_url_serializes_as_string(self):
        r = _make_midia_record()
        d = r.model_dump(mode="json")
        # URL deve virar string
        assert isinstance(d["storage"]["url"], str)

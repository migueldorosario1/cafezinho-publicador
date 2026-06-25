# CONTRATOS — Acervo Editorial de Mídia

**Versão:** 1.0.0 (`CONTRACT_VERSION` em `contracts.py`)
**Data homologação:** 25/06/2026 16:37 BRT
**Homologadores:** GPT (Arquiteto-chefe) · Codex (Coordenador operacional) · Claude Code (Auditor técnico) · Miguel (Homologação final)
**Implementador:** GLM (Ming) · Zhipu AI · `glm-5.1` via wrapper Claude Code
**Fórum canônico:** `Projeto Cafezinho Agentes/Foruns/carta_glm_orientacoes_publicador_microsservicos_20260625.md`

---

## 1. Propósito

Este documento define o **contrato canônico** do Acervo Editorial de Mídia — o serviço central que mantém o banco de imagens (e futuramente vídeos/áudios) do Cafezinho Media Grupo.

O contrato é **a fonte de verdade** para todos os agentes que **produzem** ou **consomem** mídia no projeto. Enquanto o `contracts.py` é a implementação Pydantic executável, este `.md` é a referência humana — lida por desenvolvedores e agentes antes de qualquer integração.

**Regra de ouro** (GPT 25/06): *nenhum código deve ser escrito pensando apenas na Sprint A*. Todo contrato criado aqui deve permanecer válido quando:

- Flickr Harvester produzir mídias
- Wikimedia Harvester produzir mídias
- R2 Uploader depositar mídias
- Vision Cataloger validar mídias
- Embedding Cataloger vetorizar mídias
- WordPress Publisher consumir mídias
- V3 Pipeline (e futuros pipelines) consumirem o acervo
- Futuros agentes ainda não desenhados consumirem o acervo

---

## 2. Visão geral

```
                   ACERVO EDITORIAL DE MÍDIA
   ┌──────────────────────────────────────────────────┐
   │                                                  │
   │   Produtores ────► [ MidiaRecord ] ────► Consumidores
   │   (write)               Pydantic               (read)
   │                                                  │
   │   flickr_harvester        │                  wordpress_publisher
   │   wikimedia_harvester     │                  vision_cataloger (valida)
   │   r2_uploader             ▼                  embedding_cataloger
   │   manual                 SQLite                  v3_pipeline
   │   legacy_migration       (banco próprio)        futuros agentes
   │                                                  │
   └──────────────────────────────────────────────────┘
                            ▲
                            │
                  [ OperatorRef ] — quem tocou
```

- **Produtores** registram via `api.register_midia(MidiaRecord)`
- **Consumidores** consultam via `api.search_midia(MidiaQuery) -> MidiaPage`
- **Validadores** atualizam estado via `api.update_validation(midia_id, ResultadoValidacao)`
- **Banco** SQLite próprio em `agents/biblioteca_midia/data/acervo.db` (default)

---

## 3. Enums — listas fechadas que só crescem

### 3.1 `FonteMidia` — origem da mídia

| Valor | Descrição | Produtor responsável |
|---|---|---|
| `flickr` | Imagem colhida do Flickr (API oficial) | `flickr_harvester` |
| `wikimedia_commons` | Imagem do Wikimedia Commons | `wikimedia_harvester` |
| `r2_uploaded` | Upload manual via r2_uploader | `r2_uploader` (UI/CLI) |
| `legacy_banco_midia` | Migração do `banco_midia_cafezinho.db` | `legacy_migration` |
| `manual` | Adição manual via CLI/UI por humano | `manual:<usuario>` |
| `external_url` | URL externa sem upload (ex: og:image) | qualquer agente |

**Regra:** novos produtores entram como novo valor nesta lista. **Nunca remover valores existentes** — mesmo se o produtor for desativado, registros antigos ainda referenciam.

### 3.2 `LicencaMidia` — licença editorial

| Valor | Significado | Publicável no Cafezinho? |
|---|---|---|
| `CC0` | Domínio público doado | ✅ |
| `PDM` | Domínio público (obra em PD) | ✅ |
| `CC-BY` | Atribuição | ✅ |
| `CC-BY-SA` | Atribuição-CompartilhaIgual | ✅ |
| `CC-BY-ND` | Atribuição-SemDerivações | ⚠️ Caso a caso |
| `CC-BY-NC` | Atribuição-NãoComercial | ⚠️ Caso a caso |
| `CC-BY-NC-SA` | Atribuição-NC-SA | ⚠️ Caso a caso |
| `CC-BY-NC-ND` | Atribuição-NC-ND | ⚠️ Caso a caso |
| `RIGHTS_RESERVED` | Direitos reservados | ❌ (só com permissão explícita) |
| `UNKNOWN` | Não identificada | ❌ (aguarda análise) |

**Política editorial** (definida em runtime, não no contrato): o Cafezinho publica por padrão `CC0`, `PDM`, `CC-BY`, `CC-BY-SA`. Demais licenças requerem curadoria humana.

**Regra:** todas as licenças podem ser **registradas** no acervo. A filtragem editorial acontece via `MidiaQuery.licenses_allowed`.

### 3.3 `StatusValidacao` — estado editorial

| Valor | Significado |
|---|---|
| `pending` | Aguardando validação pelo Vision Cataloger / curadoria |
| `approved` | Aprovada para uso editorial (Visually + contextualmente OK) |
| `rejected` | Reprovada (motivo em `validation_reason`) |
| `quarantine` | Suspeita — aguarda análise humana |

### 3.4 `StorageKind` × `StorageProvider`

**StorageKind** (tipo lógico):
- `r2` — Cloudflare R2
- `s3` — S3 compatível (incluindo B2 via S3 API)
- `local_file` — arquivo em disco
- `external_url` — URL externa (não hospedada por nós)

**StorageProvider** (físico):
- `cloudflare_r2`, `backblaze_b2`, `aws_s3`, `local_disk`, `external`

`StorageKind` é o que importa para lógica do contrato. `StorageProvider` é metadado informativo (qual back-end físico).

---

## 4. Modelos Pydantic

### 4.1 `OperatorRef` — quem tocou o registro

```python
class OperatorRef(BaseModel):
    operator_id: str          # 1-128 chars, ex: "flickr_harvester"
    description: str | None   # opcional, humano
```

**Idempotência:** `operator_id` é **string livre** — permite futuros agentes sem mudar o enum. Exemplos canônicos:

- `"flickr_harvester"`, `"wikimedia_harvester"`, `"r2_uploader"`
- `"vision_cataloger"` (validador)
- `"v3_pipeline"` (consumidor)
- `"manual:miguel"` (humano)
- `"legacy_migration"` (backfill)

### 4.2 `StorageRef` — onde está o binário

```python
class StorageRef(BaseModel):
    kind: StorageKind              # obrigatório
    provider: StorageProvider      # default: EXTERNAL
    bucket: str | None             # ex: "cafezinho-media"
    key: str | None                # path dentro do bucket
    url: HttpUrl | None            # URL pública, se acessível
```

**Exemplos:**

```python
# Flickr ao vivo (URL externa, sem upload nosso)
StorageRef(
    kind=StorageKind.EXTERNAL_URL,
    provider=StorageProvider.EXTERNAL,
    url="https://live.staticflickr.com/65535/xxx.jpg",
)

# R2 upload
StorageRef(
    kind=StorageKind.R2,
    provider=StorageProvider.CLOUDFLARE_R2,
    bucket="cafezinho-media",
    key="lula/2026/06/evento-oficial.jpg",
    url="https://media.ocafezinho.com/lula/2026/06/evento-oficial.jpg",
)
```

### 4.3 `MidiaRecord` — registro atômico

Esta é a unidade fundamental do acervo. **28 campos** organizados em 8 grupos:

| Grupo | Campos | Obrigatório? |
|---|---|---|
| **Identificação** | `id` (UUID, auto), `external_id`, `source` | `source` sim |
| **Técnico** | `mime_type`, `width`, `height`, `bytes_size`, `sha256` | 4 primeiros sim |
| **Armazenamento** | `storage` (StorageRef) | sim |
| **Editorial** | `title`, `description`, `alt_text`, `credit`, `license`, `license_url`, `source_url` | `title`, `credit`, `license` sim |
| **Entidades/Tags** | `entities: list[str]`, `tags: list[str]` | default `[]` |
| **Proveniência** | `collected_at`, `collected_by` | sim (auto-gen timestamp) |
| **Validação** | `validation_status`, `validation_reason`, `validated_at`, `validated_by` | default `pending` |
| **Versionamento** | `contract_version` | default `"1.0.0"` |

**Invariantes garantidas por Pydantic:**

- `width` e `height`: inteiros positivos, 1..65535
- `bytes_size`: 0..10 GB
- `sha256`: exatamente 64 chars (hex) quando presente
- `title`: 1..500 chars
- `description`: até 5000 chars
- `credit`: 1..500 chars (obrigatório)
- `external_id`: até 256 chars
- `entities` e `tags`: listas de strings (default vazio)

**Exemplo completo:**

```python
from datetime import datetime, timezone
from agents.biblioteca_midia.contracts import (
    MidiaRecord, OperatorRef, StorageRef,
    FonteMidia, LicencaMidia, StatusValidacao,
    StorageKind, StorageProvider,
)

record = MidiaRecord(
    external_id="12345@flickr",
    source=FonteMidia.FLICKR,
    mime_type="image/jpeg",
    width=1600, height=1067, bytes_size=2_048_576,
    sha256="a3f5b8c1d2e4f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1",
    storage=StorageRef(
        kind=StorageKind.EXTERNAL_URL,
        provider=StorageProvider.EXTERNAL,
        url="https://live.staticflickr.com/65535/12345.jpg",
    ),
    title="Lula em cerimônia oficial no Planalto",
    description="Presidente fala durante evento no Palácio do Planalto em Brasília.",
    credit="Flickr/Planalto",
    license=LicencaMidia.CC_BY,
    license_url="https://creativecommons.org/licenses/by/2.0/",
    source_url="https://www.flickr.com/photos/planalto/12345/",
    entities=["Lula", "Planalto", "Brasília"],
    tags=["politica", "evento-oficial"],
    collected_by=OperatorRef(operator_id="flickr_harvester"),
)
```

### 4.4 `MidiaQuery` + `MidiaPage` — busca paginada

```python
class MidiaQuery(BaseModel):
    entities: list[str] | None        # OR dentro da lista
    source: FonteMidia | None
    license: LicencaMidia | None
    licenses_allowed: list[LicencaMidia] | None  # OR (filtro editorial)
    validation_status: StatusValidacao | None
    storage_kind: StorageKind | None
    limit: int = 50    # 1..500
    offset: int = 0

class MidiaPage(BaseModel):
    items: list[MidiaRecord]
    total: int
    offset: int
    limit: int
    has_more: bool
```

**Semântica:** filtros diferentes são combinados com AND. Listas internas (entities, licenses_allowed) combinam com OR.

### 4.5 `ResultadoValidacao` — output do vision_cataloger

```python
class ResultadoValidacao(BaseModel):
    midia_id: UUID
    status: StatusValidacao           # approved / rejected / quarantine
    reason: str | None
    validated_by: OperatorRef         # ex: "vision_cataloger", "manual:miguel"
    validated_at: datetime            # default: agora UTC
```

**Múltiplos validadores podem coexistir** — cada validação é um evento. A última validação ganha. Visão futura:consenso entre N validadores.

### 4.6 `AcervoStats` — agregados

```python
class AcervoStats(BaseModel):
    total_midia: int
    by_source: dict[str, int]
    by_license: dict[str, int]
    by_validation_status: dict[str, int]
    by_collected_by: dict[str, int]
    last_updated: datetime | None
```

---

## 5. Regras de evolução (backwards-compatible)

Para manter o contrato **permanente** (serviço, não script):

1. **NUNCA remover campo existente** — se preciso, marcar como `deprecated` no docstring e manter funcional.
2. **Novos campos sempre com default** — agentes antigos continuam instanciando.
3. **Enums só crescem** — novos valores OK, remover valores NUNCA.
4. **Bump CONTRACT_VERSION** (SemVer) quando houver mudança:
   - `PATCH` (1.0.0 → 1.0.1): correção de docstring/description
   - `MINOR` (1.0.0 → 1.1.0): novo campo opcional ou novo valor de enum
   - `MAJOR` (1.0.0 → 2.0.0): mudança breaking (raro, requer migração)
5. **Toda mudança atualiza este `.md`** com data, justificativa e nome de quem aprovou.

---

## 6. Contrato entre produtor e consumidor

### 6.1 Obrigações do PRODUTOR (ex: flickr_harvester)

Ao chamar `register_midia(MidiaRecord(...))`, o produtor DEVE:

- Preencher todos os campos obrigatórios
- Garantir `width`, `height`, `bytes_size` corretos (medidos do binário real, não estimados)
- Calcular `sha256` quando possível (do binário em bytes)
- Identificar-se em `collected_by.operator_id`
- Preencher `entities` com pessoas/locais/organizações relevantes (pode ser vazio)
- Preencher `external_id` (ID na fonte origem) para permitir dedupe
- Preencher `license` e `license_url` com a licença real da fonte

### 6.2 Direitos do CONSUMIDOR (ex: wordpress_publisher)

Ao chamar `search_midia(MidiaQuery(...))`, o consumidor PODE:

- Filtrar por entidade: `entities=["Lula"]`
- Filtrar por licença publicável: `licenses_allowed=[CC0, PDM, CC_BY, CC_BY_SA]`
- Filtrar por status: `validation_status=APPROVED`
- Filtrar por fonte: `source=FLICKR`
- Paginar com `limit` + `offset`

### 6.3 Obrigações do VALIDADOR (vision_cataloger)

Ao chamar `update_validation(midia_id, ResultadoValidacao(...))`:

- Preencher `reason` sempre que reprovar/quarentena
- Identificar-se em `validated_by.operator_id`
- Não modificar campos da mídia — só o estado de validação

---

## 7. SQLite Schema (espelho do contrato)

Definido em `schema.py`. Tabelas:

- `midia` (1 linha por `MidiaRecord`)
- `midia_entity` (N entidades por mídia — busca eficiente)
- `midia_tag` (N tags por mídia — busca eficiente)
- `operators` (catálogo de operators vistos)
- `schema_version` (controle de migrations futuras)

**O schema implementa o contrato**, não o contrario. Mudou contrato →
muda schema (via migration versionada).

---

## 8. Fluxo end-to-end (exemplo)

```python
# 1. flickr_harvester coleta foto do Lula
record = MidiaRecord(
    source=FonteMidia.FLICKR,
    external_id="12345@flickr",
    ...
    collected_by=OperatorRef(operator_id="flickr_harvester"),
)
api.register_midia(record)
# → status: pending

# 2. vision_cataloger valida
api.update_validation(
    record.id,
    ResultadoValidacao(
        midia_id=record.id,
        status=StatusValidacao.APPROVED,
        reason="Pessoa identificada corretamente; licença CC-BY válida.",
        validated_by=OperatorRef(operator_id="vision_cataloger"),
    ),
)
# → status: approved

# 3. wordpress_publisher consome
page = api.search_midia(MidiaQuery(
    entities=["Lula"],
    licenses_allowed=[LicencaMidia.CC0, LicencaMidia.CC_BY, LicencaMidia.CC_BY_SA],
    validation_status=StatusValidacao.APPROVED,
    limit=10,
))
for midia in page.items:
    # usar midia.storage.url no WP
    ...
```

---

## 9. FAQ

**Q: Por que `OperatorRef` em vez de `operator_id: str` direto?**
A: Permite adicionar metadados no futuro (description, timestamp,versão do agente) sem quebrar contrato.

**Q: Por que `entities` é `list[str]` em vez de objetos estruturados?**
A: Simplicidade inicial. Futuras evolution (MINOR): pode-se adicionar campo opcional `entities_structured: list[Entity]` mantendo `entities` como strings para compat.

**Q: Por que permitir `UNKNOWN` no enum LicencaMidia?**
A: Produtores podem colher mídia antes de classificar licença. `UNKNOWN` é pendência reconhecida — filtro `licenses_allowed` exclui automaticamente.

**Q: O que acontece se um produtor tentar registrar mídia duplicada (mesmo external_id+source)?**
A: `api.register_midia` levanta `MidiaDuplicadaError`. Produtores devem tratar (skip ou update).

**Q: Contrato prevê múltiplos validadores?**
A: Atualmente só último valida ganha. Evolução futura (MINOR): adicionar lista `validations: list[ResultadoValidacao]`.

---

## 10. Histórico de versões

| Versão | Data | Mudança | Aprovado por |
|---|---|---|---|
| 1.0.0 | 25/06/2026 17:00 BRT | Versão inicial — Sprint A PR #1 | GPT, Codex, Claude, Miguel |

---

*Mantido por GLM (Ming) · Zhipu AI · `glm-5.1` via wrapper Claude Code.*
*Próxima edição: bump em CONTRACT_VERSION + entrada na tabela acima.*

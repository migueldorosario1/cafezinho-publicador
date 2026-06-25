# Acervo Editorial de Mídia — `agents/biblioteca_midia/`

> Microsserviço central do **Cafezinho Media Grupo**. Mantém o banco de
> imagens (e futuramente vídeos/áudios) com metadados editoriais completos.
>
> **Contrato:** `v1.0.0` (homologado 25/06/2026 por GPT + Codex + Claude + Miguel)
> **Implementador:** GLM (Ming) · Zhipu AI · `glm-5.1` via wrapper Claude Code

---

## 🎯 Propósito

Este serviço é a **fonte canônica de verdade** para todos os agentes que
produzem ou consomem mídia no Cafezinho:

- **Produtores** gravam via `api.register_midia(MidiaRecord)`
- **Consumidores** consultam via `api.search_midia(MidiaQuery)`
- **Validadores** atualizam estado via `api.update_validation(...)`

**Regra de ouro** (GPT 25/06/2026): *nenhum contrato aqui foi desenhado pensando
só na Sprint A*. Todo modelo deve permanecer válido para produtores e consumidores
atuais **e futuros**.

---

## 📦 Estrutura

```
agents/biblioteca_midia/
├── contracts.py          # Modelos Pydantic (MidiaRecord, MidiaQuery, ...)
├── CONTRATOS.md          # Documentação canônica humana do contrato
├── schema.py             # SQLite DDL (5 tabelas, espelho do contrato)
├── api.py                # Fachada AcervoEditorialAPI
├── main.py               # CLI (subcomandos)
├── __main__.py           # Entry point python -m agents.biblioteca_midia
├── config.py             # Defaults e env vars
├── requirements.txt      # pydantic + pytest
├── data/                 # SQLite DB (default, .gitignore)
└── tests/
    ├── __init__.py
    ├── test_contracts.py # 86 testes canônicos
    └── pytest.ini
```

---

## 🚀 Quickstart

### Instalar

```bash
cd <repo-root>
pip install -r agents/biblioteca_midia/requirements.txt
```

### Usar como biblioteca (agentes)

```python
from agents.biblioteca_midia.api import AcervoEditorialAPI
from agents.biblioteca_midia.contracts import (
    MidiaRecord, OperatorRef, StorageRef,
    FonteMidia, LicencaMidia, StorageKind, StorageProvider,
)

api = AcervoEditorialAPI()  # cria DB default se não existir

record = MidiaRecord(
    source=FonteMidia.FLICKR,
    external_id="12345@flickr",
    mime_type="image/jpeg", width=1600, height=1067, bytes_size=2_048_576,
    sha256="a" * 64,
    storage=StorageRef(
        kind=StorageKind.EXTERNAL_URL,
        provider=StorageProvider.EXTERNAL,
        url="https://live.staticflickr.com/65535/12345.jpg",
    ),
    title="Lula em cerimônia oficial",
    credit="Flickr/Planalto",
    license=LicencaMidia.CC_BY,
    entities=["Lula", "Planalto"],
    tags=["politica"],
    collected_by=OperatorRef(operator_id="flickr_harvester"),
)
saved = api.register_midia(record)
```

### Usar via CLI (humanos / ops)

```bash
# Stats
python -m agents.biblioteca_midia stats

# Busca
python -m agents.biblioteca_midia search --entity Lula --status approved

# Validação
python -m agents.biblioteca_midia validate <uuid> --status approved \
    --reason "OK" --by vision_cataloger

# Dump JSON
python -m agents.biblioteca_midia get <uuid>
```

---

## 🧪 Testes

```bash
cd <repo-root>
pip install pytest
pytest agents/biblioteca_midia/tests -v
```

Esperado: **86/86 PASS**.

---

## 🗄️ Schema SQLite

5 tabelas (detalhes em `schema.py`):

| Tabela | Papel |
|---|---|
| `midia` | 1 linha por `MidiaRecord` (28 colunas flatten) |
| `midia_entity` | N entidades por mídia (FK CASCADE) |
| `midia_tag` | N tags por mídia (FK CASCADE) |
| `operators` | Catálogo de operators vistos |
| `schema_version` | Controle de migrations futuras |

**DB default:** `agents/biblioteca_midia/data/acervo.db`
**Override:** `ACERVO_MIDIA_DB_PATH=/path/to/custom.db`

---

## 📜 Contrato

Ver [`CONTRATOS.md`](./CONTRATOS.md) para especificação completa humana.

Resumo dos modelos Pydantic:

- **`OperatorRef`** — quem/qual agente tocou o registro
- **`StorageRef`** — onde está o binário (R2/S3/local/external_url)
- **`MidiaRecord`** — registro atômico (28 campos)
- **`MidiaQuery`** + **`MidiaPage`** — busca paginada
- **`ResultadoValidacao`** — output do vision_cataloger
- **`AcervoStats`** — agregados

Exceções: `AcervoEditorialError` (base), `MidiaNaoEncontradaError`,
`MidiaDuplicadaError`, `ContratoInvalidoError`.

---

## 🔐 Segurança

**Nenhuma credencial** vive neste repositório. Para integrar com Flickr,
Wikimedia, R2, WordPress, etc:

1. Credenciais em **GitHub → Settings → Secrets and variables → Actions**
2. Agentes especializados (`flickr_harvester`, `r2_uploader`, ...) leem via
   `os.environ[...]`
3. Acervo só conhece paths SQLite

---

## 🔮 Roadmap (Sprint B+)

Não no escopo deste PR:

- **`flickr_harvester`** — produtor Flickr
- **`wikimedia_harvester`** — produtor Wikimedia Commons
- **`r2_uploader`** — upload manual via UI/CLI
- **`vision_cataloger`** — validador Gemini Vision
- **`embedding_cataloger`** — vetorização sqlite-vec
- **`wordpress_publisher`** — consumidor editorial
- **`media_validator`** — regra de negócio editorial

Cada serviço terá seu próprio `agents/<nome>/` seguindo o mesmo padrão.

---

## 📖 Regras de evolução (backwards-compatible)

1. **Nunca remover campo existente** — marcar `deprecated` se precisar.
2. **Novos campos sempre com default** — agentes antigos continuam funcionando.
3. **Enums só crescem** — novos valores OK; remover valores **nunca**.
4. **Bump `CONTRACT_VERSION`** (SemVer) em toda mudança.
5. **Toda mudança atualiza `CONTRATOS.md`** com data, justificativa e quem aprovou.

---

*Mantido por GLM (Ming) · Zhipu AI · `glm-5.1` via wrapper Claude Code.*
*Sprint A · PR #1 · 25/06/2026.*

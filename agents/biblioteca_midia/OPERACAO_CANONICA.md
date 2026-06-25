# Operacao Canonica Do Acervo Editorial De Midia

Esta regra existe para acabar com a confusao entre bancos antigos de midia.

## Fonte Canonica

Em producao Tencent, a unica fonte canonica do Acervo Editorial de Midia e:

```text
/root/agent_data/acervo_midia/acervo.db
```

Servicos permanentes devem executar com:

```bash
export ACERVO_MIDIA_DB_PATH=/root/agent_data/acervo_midia/acervo.db
```

O R2 guarda arquivos binarios. O SQLite canonico guarda metadados, estado,
busca, historico e referencias para R2.

## Bancos Legados

Os bancos abaixo nao podem receber novas escritas de produtores. Eles existem
apenas como fonte de importacao, reconciliacao ou auditoria:

| Banco | Uso permitido |
|---|---|
| `/root/agent_data/banco_midia/banco_imagens_reais.db` | importar bruto historico |
| `/root/agent_data/banco_midia/banco_imagens_curadas_v3.db` | importar curadoria V3 antiga |
| `/root/agent_data/banco_midia/banco_indice_r2_midia_v3.db` | reconciliar objetos R2 antigos |
| `/root/V3/banco_catalogo_midia_r2_v3.db` | backfill de metadados R2 |
| `/root/agent_data/banco_midia/banco_fontes_externas_midia_v3.db` | dedupe/auditoria de fontes |
| `/root/agent_data/banco_midia/banco_wp_media_index_v4.db` | reconciliar biblioteca WordPress |

## Regra De Escrita

Produtores novos escrevem somente via:

```python
AcervoEditorialAPI.register_midia(...)
```

Validadores atualizam somente via:

```python
AcervoEditorialAPI.update_validation(...)
```

Nenhum agente novo deve escrever diretamente em banco legado.

## Sequencia De Ordem

1. Criar o DB canonico se ainda nao existir.
2. Congelar bancos legados como somente leitura operacional.
3. Importar lotes pequenos para o canonico com relatorio.
4. Rejeitar imagem sem pessoa/tema confirmado quando a query exigir personagem.
5. Registrar `source`, `external_id`, `license`, `credit`, `storage` e `entities`.
6. So depois usar a imagem como candidata para publicacao.

## Incidente Que Motivou A Regra

Em 25/06/2026, uma imagem de plenario foi usada como se fosse uma foto de
Alexandre de Moraes. O problema nao foi tecnico de upload: foi erro de acervo.

Correcao estrutural: imagem de pessoa so pode ser `approved` para essa pessoa
quando houver confirmacao visual ou fonte confiavel suficientemente especifica.

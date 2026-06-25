# Publicador Cafezinho

Publicador simples para criar posts pendentes no WordPress a partir de `posts/entrada.md`.

## Uso do seletor automatico de imagem

O front matter do arquivo `posts/entrada.md` pode informar uma imagem destacada de duas formas:

```yaml
image_url: "https://exemplo.com/imagem.jpg"
```

ou:

```yaml
image_query: "Alexandre de Moraes STF"
```

`image_url` tem prioridade absoluta. Quando ele existe, o publicador usa essa URL diretamente, baixa a imagem, envia para a biblioteca de midia do WordPress e define a imagem como destacada.

Quando `image_url` nao existe e `image_query` existe, o publicador chama `agents.biblioteca_midia.selecionar_imagem(...)`. O seletor consulta o indice local `media_index/images.json` e retorna a melhor imagem aprovada.

O seletor considera apenas imagens elegiveis pelo indice, com `status` aprovado ou marcadas como destaque editorial. A pontuacao inicial e simples: prioriza correspondencias em pessoas, organizacoes, temas, palavras-chave e legenda, com bonus para `editorial_featured=true`.

Se nenhuma imagem for encontrada, ou se o indice falhar, o post continua sendo criado sem imagem destacada e o publicador imprime um aviso no log. Falha na selecao automatica de imagem nao deve impedir a publicacao pendente.

Exemplo:

```markdown
---
title: "Teste com seletor automatico de imagem"
status: "pending"
tags: "teste, cafezinho, r2"
image_query: "Alexandre de Moraes STF"
---

Este e um teste do seletor automatico de imagens do R2.
```

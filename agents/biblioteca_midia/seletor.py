"""Seletor minimo do Acervo Editorial de Midia.

Este modulo ainda usa `media_index/images.json`, mas a funcao publica
`selecionar_imagem(...)` e o contrato estavel para o publicador. A fonte de
dados pode migrar para SQLite, Vision, embeddings e R2 sem mudar os
consumidores.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


STATUS_ELEGIVEIS = {"approved", "editorial_featured"}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.lower()
    return re.sub(r"\s+", " ", texto).strip()


def termos_busca(query: str, titulo: str = "", conteudo: str = "") -> list[str]:
    base = normalizar(" ".join([query, titulo, conteudo]))
    termos = re.findall(r"[a-z0-9]+", base)
    return [termo for termo in termos if len(termo) > 2]


def carregar_indice(index_path: str) -> list[dict[str, Any]]:
    caminho = Path(index_path)
    if not caminho.exists():
        return []

    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados, list):
        return []

    return [item for item in dados if isinstance(item, dict)]


def campo_lista(imagem: dict[str, Any], campo: str) -> list[str]:
    valor = imagem.get(campo, [])
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, list):
        return [str(item) for item in valor if item]
    return []


def contem_termo(valores: list[str], termos: list[str]) -> bool:
    textos = [normalizar(valor) for valor in valores]
    for texto in textos:
        if any(termo in texto for termo in termos):
            return True
    return False


def imagem_elegivel(imagem: dict[str, Any]) -> bool:
    status = normalizar(str(imagem.get("status", "")))
    if status == "rejected":
        return False
    return status in STATUS_ELEGIVEIS or bool(imagem.get("editorial_featured"))


def score_imagem(imagem: dict[str, Any], termos: list[str]) -> int:
    score = 0

    if contem_termo(campo_lista(imagem, "people"), termos):
        score += 100
    if contem_termo(campo_lista(imagem, "organizations"), termos):
        score += 60
    if contem_termo(campo_lista(imagem, "themes"), termos):
        score += 40
    if contem_termo(campo_lista(imagem, "keywords"), termos):
        score += 20
    if contem_termo([str(imagem.get("caption", ""))], termos):
        score += 10

    if score and bool(imagem.get("editorial_featured")):
        score += 30

    return score


def selecionar_imagem(
    query: str,
    titulo: str = "",
    conteudo: str = "",
    index_path: str = "media_index/images.json",
) -> dict[str, Any] | None:
    termos = termos_busca(query, titulo, conteudo)
    if not termos:
        return None

    melhor: dict[str, Any] | None = None
    melhor_score = 0

    for imagem in carregar_indice(index_path):
        if not imagem_elegivel(imagem):
            continue

        score = score_imagem(imagem, termos)
        if score > melhor_score:
            melhor = imagem
            melhor_score = score

    return melhor if melhor_score > 0 else None

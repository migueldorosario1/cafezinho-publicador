from __future__ import annotations

import json

from agents.biblioteca_midia.seletor import selecionar_imagem


def escrever_indice(tmp_path, imagens):
    caminho = tmp_path / "images.json"
    caminho.write_text(json.dumps(imagens), encoding="utf-8")
    return str(caminho)


def imagem_base(**overrides):
    imagem = {
        "image_id": "moraes-posse-2023",
        "url": "https://example.com/moraes.jpg",
        "people": ["Alexandre de Moraes"],
        "organizations": ["STF"],
        "themes": ["judiciário", "política"],
        "keywords": ["alexandre de moraes", "moraes", "stf", "supremo"],
        "caption": "Alexandre de Moraes durante cerimônia oficial",
        "credit": "Foto: acervo público",
        "alt": "Alexandre de Moraes em cerimônia oficial",
        "status": "approved",
        "editorial_featured": True,
    }
    imagem.update(overrides)
    return imagem


def test_query_completa_retorna_moraes(tmp_path):
    index_path = escrever_indice(tmp_path, [imagem_base()])

    resultado = selecionar_imagem("Alexandre de Moraes STF", index_path=index_path)

    assert resultado is not None
    assert resultado["image_id"] == "moraes-posse-2023"


def test_query_parcial_retorna_por_people(tmp_path):
    index_path = escrever_indice(tmp_path, [imagem_base()])

    resultado = selecionar_imagem("Moraes Supremo", index_path=index_path)

    assert resultado is not None
    assert resultado["people"] == ["Alexandre de Moraes"]


def test_query_sem_correspondencia_retorna_none(tmp_path):
    index_path = escrever_indice(tmp_path, [imagem_base()])

    resultado = selecionar_imagem("Petrobras refinaria", index_path=index_path)

    assert resultado is None


def test_imagem_rejected_nao_e_retornada(tmp_path):
    index_path = escrever_indice(tmp_path, [imagem_base(status="rejected")])

    resultado = selecionar_imagem("Alexandre de Moraes STF", index_path=index_path)

    assert resultado is None


def test_editorial_featured_ganha_prioridade(tmp_path):
    comum = imagem_base(
        image_id="moraes-comum",
        caption="Alexandre de Moraes no STF",
        editorial_featured=False,
    )
    destaque = imagem_base(
        image_id="moraes-destaque",
        editorial_featured=True,
    )
    index_path = escrever_indice(tmp_path, [comum, destaque])

    resultado = selecionar_imagem("Moraes STF", index_path=index_path)

    assert resultado is not None
    assert resultado["image_id"] == "moraes-destaque"

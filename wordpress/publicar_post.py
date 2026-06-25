from __future__ import annotations

import os
import requests

from .utils import lista_ids, wp_auth, wp_base_url

TIMEOUT_CURTO = 20
TIMEOUT_POST = 120


def criar_ou_obter_tag(nome: str) -> int | None:
    nome = nome.strip()
    if not nome:
        return None

    base = wp_base_url()
    auth = wp_auth()

    try:
        busca = requests.get(
            f"{base}/wp-json/wp/v2/tags",
            params={"search": nome, "per_page": 20},
            auth=auth,
            timeout=TIMEOUT_CURTO,
        )
        busca.raise_for_status()

        for tag in busca.json():
            if tag.get("name", "").strip().lower() == nome.lower():
                return int(tag["id"])

        cria = requests.post(
            f"{base}/wp-json/wp/v2/tags",
            json={"name": nome},
            auth=auth,
            timeout=TIMEOUT_CURTO,
        )
        cria.raise_for_status()
        return int(cria.json()["id"])
    except requests.RequestException as erro:
        print(f"Aviso: tag ignorada '{nome}'. Motivo: {erro}")
        return None


def resolver_tags(tags_texto: str | None) -> list[int]:
    if not tags_texto:
        return []
    ids: list[int] = []
    for nome in [t.strip() for t in tags_texto.split(",") if t.strip()]:
        tag_id = criar_ou_obter_tag(nome)
        if tag_id:
            ids.append(tag_id)
    return ids


def criar_post(
    titulo: str,
    conteudo: str,
    excerpt: str | None = None,
    status: str = "pending",
    category_ids: str | None = None,
    tags: str | None = None,
    featured_media: int | None = None,
) -> dict:
    if not titulo.strip():
        raise ValueError("Titulo vazio")
    if not conteudo.strip():
        raise ValueError("Conteudo vazio")

    author_id = int(os.getenv("CAFEZINHO_WP_AUTHOR_ID", "0") or "0")
    payload: dict = {"title": titulo, "content": conteudo, "status": status or "pending"}

    if author_id:
        payload["author"] = author_id
    if excerpt:
        payload["excerpt"] = excerpt

    categorias = lista_ids(category_ids)
    if categorias:
        payload["categories"] = categorias

    tag_ids = resolver_tags(tags)
    if tag_ids:
        payload["tags"] = tag_ids

    if featured_media:
        payload["featured_media"] = featured_media

    resposta = requests.post(
        f"{wp_base_url()}/wp-json/wp/v2/posts",
        json=payload,
        auth=wp_auth(),
        timeout=TIMEOUT_POST,
    )

    if resposta.status_code >= 400:
        raise RuntimeError(f"Erro ao criar post: {resposta.status_code} {resposta.text}")

    return resposta.json()

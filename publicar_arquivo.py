from __future__ import annotations

import re
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from wordpress.publicar_post import criar_post
from wordpress.upload_media import enviar_midia_por_url
from agents.biblioteca_midia import selecionar_imagem


def carregar_env() -> None:
    if load_dotenv:
        load_dotenv()


def extrair_campo(cabecalho: str, nome: str, padrao: str = "") -> str:
    regex = rf"^{re.escape(nome)}:\s*(.*)$"
    for linha in cabecalho.splitlines():
        achou = re.match(regex, linha.strip())
        if achou:
            return achou.group(1).strip().strip('"').strip("'")
    return padrao


def ler_post(caminho: str) -> dict:
    texto = Path(caminho).read_text(encoding="utf-8")

    if texto.startswith("---"):
        partes = texto.split("---", 2)
        cabecalho = partes[1]
        corpo = partes[2].strip()
    else:
        cabecalho = ""
        corpo = texto.strip()

    titulo = extrair_campo(cabecalho, "title")
    if not titulo:
        primeira_linha = corpo.splitlines()[0].strip() if corpo else "Post sem titulo"
        titulo = primeira_linha.replace("#", "").strip() or "Post sem titulo"

    return {
        "titulo": titulo,
        "conteudo": corpo,
        "excerpt": extrair_campo(cabecalho, "excerpt"),
        "status": extrair_campo(cabecalho, "status", "pending"),
        "category_ids": extrair_campo(cabecalho, "category_ids"),
        "tags": extrair_campo(cabecalho, "tags"),
        "image_url": extrair_campo(cabecalho, "image_url"),
        "image_query": extrair_campo(cabecalho, "image_query"),
        "image_alt": extrair_campo(cabecalho, "image_alt"),
        "image_caption": extrair_campo(cabecalho, "image_caption"),
    }


def legenda_com_credito(caption: str = "", credit: str = "") -> str:
    partes = [parte.strip() for parte in [caption, credit] if parte and parte.strip()]
    return " — ".join(partes)


def resolver_imagem_destacada(dados: dict) -> tuple[str, str, str]:
    if dados["image_url"]:
        return dados["image_url"], dados["image_alt"], dados["image_caption"]

    if not dados["image_query"]:
        return "", "", ""

    try:
        imagem = selecionar_imagem(
            dados["image_query"],
            titulo=dados["titulo"],
            conteudo=dados["conteudo"],
        )
    except Exception as erro:
        print(f"Aviso: seletor automatico de imagem falhou. Motivo: {erro}")
        return "", "", ""

    if not imagem:
        print(f"Aviso: nenhuma imagem encontrada para image_query='{dados['image_query']}'")
        return "", "", ""

    print(f"Imagem selecionada automaticamente: {imagem.get('image_id')}")
    return (
        str(imagem.get("url", "")),
        str(imagem.get("alt", "")),
        legenda_com_credito(str(imagem.get("caption", "")), str(imagem.get("credit", ""))),
    )


def main() -> None:
    carregar_env()
    dados = ler_post("posts/entrada.md")

    featured_media = None
    image_url, image_alt, image_caption = resolver_imagem_destacada(dados)
    if image_url:
        print("Enviando imagem destacada ao WordPress")
        featured_media = enviar_midia_por_url(
            image_url,
            alt_text=image_alt,
            caption=image_caption,
        )
        if featured_media:
            print(f"Imagem enviada. Media ID: {featured_media}")
        else:
            print("Aviso: publicacao seguira sem imagem destacada")

    post = criar_post(
        titulo=dados["titulo"],
        conteudo=dados["conteudo"],
        excerpt=dados["excerpt"] or None,
        status=dados["status"] or "pending",
        category_ids=dados["category_ids"] or None,
        tags=dados["tags"] or None,
        featured_media=featured_media,
    )

    print("Post criado com sucesso")
    print(f"ID: {post.get('id')}")
    print(f"Status: {post.get('status')}")
    print(f"Link: {post.get('link')}")


if __name__ == "__main__":
    main()

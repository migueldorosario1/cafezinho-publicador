from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from agents.biblioteca_midia import selecionar_imagem
from wordpress.publicar_post import criar_post
from wordpress.upload_media import enviar_midia_por_url, obter_url_midia
from wordpress.utils import wp_base_url


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
        "inline_image_url": extrair_campo(cabecalho, "inline_image_url"),
        "inline_image_alt": extrair_campo(cabecalho, "inline_image_alt"),
        "inline_image_caption": extrair_campo(cabecalho, "inline_image_caption"),
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


def figura_html(url: str, alt_text: str = "", caption: str = "") -> str:
    alt = html.escape(alt_text or "")
    src = html.escape(url, quote=True)
    legenda = html.escape(caption or "")
    figcaption = f"<figcaption>{legenda}</figcaption>" if legenda else ""
    return (
        '<figure class="wp-block-image size-large">'
        f'<img src="{src}" alt="{alt}" />'
        f"{figcaption}"
        "</figure>"
    )


def inserir_imagem_inline(dados: dict, featured_media: int | None, featured_url: str) -> str:
    inline_url = dados.get("inline_image_url") or ""
    if not inline_url:
        return dados["conteudo"].replace("{{INLINE_IMAGE}}", "")

    media_id: int | None
    if featured_media and inline_url == featured_url:
        media_id = featured_media
        print("Reutilizando a imagem destacada tambem no corpo")
    else:
        print("Enviando imagem inline ao WordPress")
        media_id = enviar_midia_por_url(
            inline_url,
            alt_text=dados.get("inline_image_alt") or "",
            caption=dados.get("inline_image_caption") or "",
        )

    if not media_id:
        print("Aviso: imagem inline indisponivel; removendo marcador do corpo")
        return dados["conteudo"].replace("{{INLINE_IMAGE}}", "")

    source_url = obter_url_midia(media_id)
    bloco = figura_html(
        source_url,
        alt_text=dados.get("inline_image_alt") or "",
        caption=dados.get("inline_image_caption") or "",
    )
    return dados["conteudo"].replace("{{INLINE_IMAGE}}", bloco)


def gravar_recibo(dados: dict) -> None:
    pasta = Path("recibos")
    pasta.mkdir(parents=True, exist_ok=True)

    recibo = {
        **dados,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "github_sha": os.getenv("GITHUB_SHA", ""),
        "github_run_id": os.getenv("GITHUB_RUN_ID", ""),
    }

    conteudo = json.dumps(recibo, ensure_ascii=False, indent=2) + "\n"
    (pasta / "ultimo.json").write_text(conteudo, encoding="utf-8")

    identificador = os.getenv("GITHUB_SHA", "").strip() or "local"
    (pasta / f"{identificador}.json").write_text(conteudo, encoding="utf-8")


def main() -> None:
    dados: dict = {}
    try:
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

        conteudo_final = inserir_imagem_inline(dados, featured_media, image_url)

        post = criar_post(
            titulo=dados["titulo"],
            conteudo=conteudo_final,
            excerpt=dados["excerpt"] or None,
            status=dados["status"] or "pending",
            category_ids=dados["category_ids"] or None,
            tags=dados["tags"] or None,
            featured_media=featured_media,
        )

        post_id = int(post["id"])
        edit_link = f"{wp_base_url()}/wp-admin/post.php?post={post_id}&action=edit"
        public_link = str(post.get("link") or "")

        gravar_recibo(
            {
                "ok": True,
                "post_id": post_id,
                "titulo": dados["titulo"],
                "status": str(post.get("status") or dados["status"]),
                "edit_link": edit_link,
                "public_link": public_link,
                "featured_media_id": featured_media,
                "categoria_ids": dados.get("category_ids") or "",
                "tags": dados.get("tags") or "",
            }
        )

        print("Post criado com sucesso")
        print(f"ID: {post_id}")
        print(f"Status: {post.get('status')}")
        print(f"Link de edicao: {edit_link}")
        print(f"Link publico: {public_link}")
    except Exception as erro:
        gravar_recibo(
            {
                "ok": False,
                "titulo": dados.get("titulo", ""),
                "status": "error",
                "erro": str(erro),
            }
        )
        raise


if __name__ == "__main__":
    main()

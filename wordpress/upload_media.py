from __future__ import annotations

import logging
import mimetypes
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from PIL import Image

from .utils import wp_auth, wp_base_url


def nome_arquivo(url: str) -> str:
    parsed = urlparse(url)
    nome = Path(parsed.path).name
    return nome or "imagem-cafezinho.jpg"


def otimizar_imagem_para_wordpress(conteudo: bytes, nome: str) -> tuple[bytes, str, str]:
    """Gera uma versão leve para evitar timeout no upload ao WordPress."""
    try:
        imagem = Image.open(BytesIO(conteudo))
        imagem.thumbnail((1600, 1600))
        if imagem.mode not in ("RGB", "L"):
            imagem = imagem.convert("RGB")

        saida = BytesIO()
        imagem.save(saida, format="JPEG", quality=84, optimize=True, progressive=True)
    except Exception as erro:
        logging.warning("Nao foi possivel otimizar imagem %s: %s", nome, erro)
        tipo_original = mimetypes.guess_type(nome)[0] or "image/jpeg"
        return conteudo, tipo_original, nome

    nome_jpg = f"{Path(nome).stem}.jpg"
    return saida.getvalue(), "image/jpeg", nome_jpg


def enviar_midia_por_url(url: str, alt_text: str = "", caption: str = "") -> Optional[int]:
    """Envia uma imagem remota para o WordPress.

    Falhas na origem da imagem (404, timeout, DNS etc.) não devem derrubar
    a publicação inteira. Nesses casos retornamos None e o post pode ser
    criado sem imagem destacada.

    Erros no upload para o WordPress continuam sendo exceção, porque indicam
    problema real de credencial/API do publicador.
    """
    try:
        origem = requests.get(url, timeout=60)
    except requests.exceptions.RequestException as erro:
        logging.warning("Falha ao baixar imagem %s: %s", url, erro)
        return None

    if origem.status_code == 404:
        logging.warning("Imagem nao encontrada (404): %s. Publicando sem imagem.", url)
        return None

    try:
        origem.raise_for_status()
    except requests.exceptions.RequestException as erro:
        logging.warning("Erro ao baixar imagem %s: %s. Publicando sem imagem.", url, erro)
        return None

    nome = nome_arquivo(url)
    conteudo, tipo, nome = otimizar_imagem_para_wordpress(origem.content, nome)

    headers = {
        "Content-Disposition": f'attachment; filename="{nome}"',
        "Content-Type": tipo,
    }

    envio = requests.post(
        f"{wp_base_url()}/wp-json/wp/v2/media",
        headers=headers,
        data=conteudo,
        auth=wp_auth(),
        timeout=120,
    )

    if envio.status_code >= 400:
        raise RuntimeError(f"Erro ao enviar midia: {envio.status_code} {envio.text}")

    media = envio.json()
    media_id = int(media["id"])

    meta = {}
    if alt_text:
        meta["alt_text"] = alt_text
    if caption:
        meta["caption"] = caption

    if meta:
        atualiza = requests.post(
            f"{wp_base_url()}/wp-json/wp/v2/media/{media_id}",
            json=meta,
            auth=wp_auth(),
            timeout=60,
        )
        atualiza.raise_for_status()

    return media_id

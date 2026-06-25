from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import requests

from .utils import wp_auth, wp_base_url


def nome_arquivo(url: str) -> str:
    parsed = urlparse(url)
    nome = Path(parsed.path).name
    return nome or "imagem-cafezinho.jpg"


def enviar_midia_por_url(url: str, alt_text: str = "", caption: str = "") -> int:
    origem = requests.get(url, timeout=60)
    origem.raise_for_status()

    nome = nome_arquivo(url)
    tipo = origem.headers.get("content-type") or mimetypes.guess_type(nome)[0] or "image/jpeg"

    headers = {
        "Content-Disposition": f'attachment; filename="{nome}"',
        "Content-Type": tipo,
    }

    envio = requests.post(
        f"{wp_base_url()}/wp-json/wp/v2/media",
        headers=headers,
        data=origem.content,
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

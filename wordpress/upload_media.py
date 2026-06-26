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

WP_IMAGE_MIN_BYTES = 50 * 1024
WP_IMAGE_TARGET_BYTES = 100 * 1024
WP_IMAGE_MAX_BYTES = 500 * 1024


def nome_arquivo(url: str) -> str:
    parsed = urlparse(url)
    nome = Path(parsed.path).name
    return nome or "imagem-cafezinho.jpg"


def otimizar_imagem_para_wordpress(conteudo: bytes, nome: str) -> tuple[bytes, str, str]:
    """Gera uma versão leve para imagem destacada no WordPress.

    Mantemos o original bom no R2. Para o WordPress, buscamos a faixa
    saudável de 50 KB a 100 KB e nunca aceitamos passar de 500 KB quando a
    imagem puder ser processada.
    """
    try:
        imagem = Image.open(BytesIO(conteudo))
        if imagem.mode not in ("RGB", "L"):
            imagem = imagem.convert("RGB")

        melhor_dentro_faixa: bytes | None = None
        menor_ate_maximo: bytes | None = None
        maior_abaixo_minimo: bytes | None = None
        for limite in (1400, 1200, 1000, 850, 700):
            tentativa = imagem.copy()
            tentativa.thumbnail((limite, limite))
            for qualidade in (90, 86, 82, 78, 74, 70, 66, 62, 58, 54, 50, 46):
                saida = BytesIO()
                tentativa.save(
                    saida,
                    format="JPEG",
                    quality=qualidade,
                    optimize=True,
                    progressive=True,
                )
                dados = saida.getvalue()
                tamanho = len(dados)
                if WP_IMAGE_MIN_BYTES <= tamanho <= WP_IMAGE_TARGET_BYTES:
                    if melhor_dentro_faixa is None or tamanho > len(melhor_dentro_faixa):
                        melhor_dentro_faixa = dados
                elif tamanho < WP_IMAGE_MIN_BYTES:
                    if maior_abaixo_minimo is None or tamanho > len(maior_abaixo_minimo):
                        maior_abaixo_minimo = dados
                elif tamanho <= WP_IMAGE_MAX_BYTES:
                    if menor_ate_maximo is None or tamanho < len(menor_ate_maximo):
                        menor_ate_maximo = dados

        escolhido = melhor_dentro_faixa or menor_ate_maximo or maior_abaixo_minimo
        if escolhido and len(escolhido) <= WP_IMAGE_MAX_BYTES:
            nome_jpg = f"{Path(nome).stem}.jpg"
            if len(escolhido) < WP_IMAGE_MIN_BYTES:
                logging.warning("Imagem %s ficou abaixo de 50 KB apos otimizacao", nome)
            return escolhido, "image/jpeg", nome_jpg
    except Exception as erro:
        logging.warning("Nao foi possivel otimizar imagem %s: %s", nome, erro)
        tipo_original = mimetypes.guess_type(nome)[0] or "image/jpeg"
        return conteudo, tipo_original, nome

    logging.warning("Imagem %s nao atingiu limite maximo apos otimizacao", nome)
    tipo_original = mimetypes.guess_type(nome)[0] or "image/jpeg"
    return conteudo, tipo_original, nome


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

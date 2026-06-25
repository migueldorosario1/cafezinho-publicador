"""agents/biblioteca_midia/ — Acervo Editorial de Mídia.

Serviço independente que mantém o acervo de mídias (imagens, futuramente
vídeos) com metadados editoriais completos: origem, licença, crédito,
entidades, dimensões, armazenamento e estado de validação.

Produtores (flickr_harvester, wikimedia_harvester, r2_uploader) registram
mídias no acervo. Consumidores (wordpress_publisher, vision_cataloger,
embedding_cataloger, V3, futuros agentes) consultam via API bem definida.

Contratos canônicos em ``contracts.py`` — estáveis para todos os
produtores e consumidores atuais e futuros.
"""

from .seletor import selecionar_imagem

__version__ = "0.1.0"

__all__ = ["selecionar_imagem"]

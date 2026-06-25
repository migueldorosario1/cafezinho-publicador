"""agents/_shared/ — Contratos e utilidades compartilhadas entre agentes.

Este namespace NÃO contém lógica de domínio — apenas:
- esquemas Pydantic compartilhados (ex: timestamps, IDs)
- exceções base do projeto
- helpers de logging/config

Cada agente de domínio (biblioteca_midia, wordpress_publisher, ...)
mantém seus próprios contratos em ``agents/<nome>/contracts.py``.
"""

__version__ = "0.1.0"

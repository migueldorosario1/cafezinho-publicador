"""agents/ — Pacote raiz dos microsserviços do Publicador Cafezinho.

Cada subpacote (agents/biblioteca_midia, agents/wordpress_publisher, ...)
é um serviço independente, com seu próprio README, requirements, config,
main e tests. Comunicação entre serviços via contratos Pydantic versionados
e SQLite compartilhado (SQLite-first).

Convenção: cada agente expõe sua API mínima em ``agents/<nome>/api.py``
e CLI em ``agents/<nome>/main.py``.
"""

__version__ = "0.1.0"

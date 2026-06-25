"""Ponto de entrada para ``python -m agents.biblioteca_midia``.

Delega para ``main.main()``.
"""

import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())

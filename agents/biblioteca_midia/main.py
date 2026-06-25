"""main.py — CLI mínima do Acervo Editorial de Mídia.

Interface de linha de comando para operações manuais (debug, ops,
inspeção). Não é camada obrigatória — agentes consomem via ``api.py``
diretamente. CLI existe para:

- Inspeção manual por humanos (Miguel, curadoria)
- Scripts bash que orquestram o acervo
- Debug em produção (``python -m agents.biblioteca_midia stats``)
- Smoke checks em CI

Subcomandos:
  - ``stats``              — agregados (AcervoStats)
  - ``get <uuid>``         — dump de MidiaRecord como JSON
  - ``search``             — busca com flags --entity, --source, etc
  - ``validate <uuid>``    — atualiza estado de validação
  - ``delete <uuid>``      — remove mídia
  - ``info``               — versão do contrato + path do DB

Uso::

    python -m agents.biblioteca_midia stats
    python -m agents.biblioteca_midia get 6761a89e-d1b8-4917-9f62-85f3aaa1a5b9
    python -m agents.biblioteca_midia search --entity Lula --status approved
    python -m agents.biblioteca_midia validate <uuid> --status approved \\
        --reason "OK" --by vision_cataloger
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional
from uuid import UUID

from .api import AcervoEditorialAPI, _resolve_db_path
from .contracts import (
    CONTRACT_VERSION,
    FonteMidia,
    LicencaMidia,
    MidiaNaoEncontradaError,
    MidiaQuery,
    ResultadoValidacao,
    StatusValidacao,
    OperatorRef,
)


# ============================================================
# PRINTERS
# ============================================================

def _print_json(obj) -> None:
    """Printa como JSON pretty."""
    print(json.dumps(obj, indent=2, default=str, ensure_ascii=False))


def _print_stats(stats) -> None:
    """Formato human-friendly para stats."""
    print(f"Acervo Editorial de Mídia — stats")
    print(f"  Contrato: v{CONTRACT_VERSION}")
    print(f"  DB: {_resolve_db_path()}")
    print(f"  Total: {stats.total_midia}")
    print()
    print("  Por fonte:")
    for k, v in sorted(stats.by_source.items()):
        print(f"    {k:.<30} {v}")
    print()
    print("  Por licença:")
    for k, v in sorted(stats.by_license.items()):
        print(f"    {k:.<30} {v}")
    print()
    print("  Por status:")
    for k, v in sorted(stats.by_validation_status.items()):
        print(f"    {k:.<30} {v}")
    print()
    print("  Por operador (top 10):")
    items = sorted(stats.by_collected_by.items(), key=lambda x: -x[1])[:10]
    for k, v in items:
        print(f"    {k:.<30} {v}")
    if stats.last_updated:
        print()
        print(f"  Última atualização: {stats.last_updated.isoformat()}")


# ============================================================
# SUBCOMANDOS
# ============================================================

def cmd_stats(args: argparse.Namespace) -> int:
    api = AcervoEditorialAPI()
    stats = api.stats()
    if args.json:
        _print_json(stats.model_dump(mode="json"))
    else:
        _print_stats(stats)
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    info = {
        "contract_version": CONTRACT_VERSION,
        "db_path": _resolve_db_path(),
        "schema_version_max": 1,
    }
    _print_json(info)
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    api = AcervoEditorialAPI()
    try:
        r = api.get_midia(args.uuid)
    except MidiaNaoEncontradaError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    _print_json(r.model_dump(mode="json"))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    api = AcervoEditorialAPI()
    query = MidiaQuery(
        entities=args.entity or None,
        source=FonteMidia(args.source) if args.source else None,
        licenses_allowed=(
            [LicencaMidia(l) for l in args.license]
            if args.license
            else None
        ),
        validation_status=(
            StatusValidacao(args.status) if args.status else None
        ),
        limit=args.limit,
        offset=args.offset,
    )
    page = api.search_midia(query)
    if args.json:
        _print_json(page.model_dump(mode="json"))
    else:
        print(f"Total: {page.total} | offset={page.offset} "
              f"limit={page.limit} has_more={page.has_more}")
        for r in page.items:
            print(f"  [{r.validation_status.value}] {r.id} "
                  f"{r.source.value:<20} {r.title[:60]}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    api = AcervoEditorialAPI()
    try:
        r = api.update_validation(
            args.uuid,
            ResultadoValidacao(
                midia_id=UUID(args.uuid) if isinstance(args.uuid, str) else args.uuid,
                status=StatusValidacao(args.status),
                reason=args.reason,
                validated_by=OperatorRef(operator_id=args.by),
            ),
        )
    except MidiaNaoEncontradaError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    print(f"OK: {r.id} agora é {r.validation_status.value}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    if not args.yes:
        print("Use --yes para confirmar delete.", file=sys.stderr)
        return 2
    api = AcervoEditorialAPI()
    try:
        api.delete_midia(args.uuid)
    except MidiaNaoEncontradaError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    print(f"OK: {args.uuid} removido.")
    return 0


# ============================================================
# PARSER
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agents.biblioteca_midia",
        description="CLI do Acervo Editorial de Mídia",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # stats
    p_stats = sub.add_parser("stats", help="Agregados do acervo")
    p_stats.add_argument("--json", action="store_true", help="JSON output")
    p_stats.set_defaults(func=cmd_stats)

    # info
    p_info = sub.add_parser("info", help="Info do ambiente")
    p_info.set_defaults(func=cmd_info)

    # get
    p_get = sub.add_parser("get", help="Dump de MidiaRecord")
    p_get.add_argument("uuid", help="UUID da mídia")
    p_get.set_defaults(func=cmd_get)

    # search
    p_search = sub.add_parser("search", help="Busca paginada")
    p_search.add_argument("--entity", action="append", help="Entidade (OR)")
    p_search.add_argument("--source", help=f"Fonte: {[s.value for s in FonteMidia]}")
    p_search.add_argument("--license", action="append",
                           help=f"Licença (OR): {[l.value for l in LicencaMidia]}")
    p_search.add_argument("--status",
                           help=f"Status: {[s.value for s in StatusValidacao]}")
    p_search.add_argument("--limit", type=int, default=50)
    p_search.add_argument("--offset", type=int, default=0)
    p_search.add_argument("--json", action="store_true")
    p_search.set_defaults(func=cmd_search)

    # validate
    p_val = sub.add_parser("validate", help="Atualiza validação")
    p_val.add_argument("uuid", help="UUID da mídia")
    p_val.add_argument("--status", required=True,
                        help=f"Novo status: {[s.value for s in StatusValidacao]}")
    p_val.add_argument("--reason", help="Motivo")
    p_val.add_argument("--by", required=True,
                        help="operator_id (ex: vision_cataloger)")
    p_val.set_defaults(func=cmd_validate)

    # delete
    p_del = sub.add_parser("delete", help="Remove mídia")
    p_del.add_argument("uuid", help="UUID da mídia")
    p_del.add_argument("--yes", action="store_true", help="Confirma")
    p_del.set_defaults(func=cmd_delete)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

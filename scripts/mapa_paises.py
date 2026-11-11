#!/usr/bin/env python3
"""Gera o mapa de colaboração entre países a partir de um projeto Redes.

Uso:
    python3 scripts/mapa_paises.py <dados.redes> <saida.svg> [destaque]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redes.viz.mapa import colaboracao, mapa_svg  # noqa: E402


def metricas(dados: dict) -> list[tuple[str, str]]:
    total = dados["total"] or 1
    return [
        (f"{dados['total']}", "documentos"),
        (f"{len(dados['documentos'])}", "países"),
        (f"{len(dados['ligacoes'])}", "cooperações"),
        (f"{dados['densidade']:.1%}".replace(".", ","), "densidade da rede"),
        (f"{dados['grau_medio']:.1f}".replace(".", ","), "cooperações por país"),
        (f"{dados['internacionais'] / total:.1%}".replace(".", ","), "coautoria internacional"),
    ]


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    dados = colaboracao(Path(argv[1]))
    destaque = argv[3] if len(argv) > 3 and argv[3] else (
        max(dados["documentos"], key=dados["documentos"].get) if dados["documentos"] else "")

    svg = mapa_svg(
        dados["documentos"],
        dados["ligacoes"],
        destaque=destaque,
        subtitulo=(f"{dados['total']} documentos · {len(dados['documentos'])} países · "
                   f"{len(dados['ligacoes'])} cooperações"),
        legenda=(f"Coautoria internacional: {dados['internacionais']} de {dados['total']} "
                 f"documentos ({dados['internacionais'] / max(1, dados['total']):.1%})"
                 .replace(".", ",")),
        metricas=metricas(dados),
    )
    Path(argv[2]).write_text(svg, encoding="utf-8")
    print(f"documentos: {dados['total']}")
    print(f"países: {len(dados['documentos'])}")
    print(f"cooperações distintas: {len(dados['ligacoes'])}")
    print(f"densidade: {dados['densidade']:.1%} | cooperações por país: {dados['grau_medio']:.2f}")
    print(f"mais conectado: {dados['mais_conectado']} ({dados['grau_maximo']} parceiros)")
    a, b, p = dados["maior"]
    print(f"maior cooperação: {a} — {b} ({p} documentos)")
    print(f"internacionais: {dados['internacionais']} "
          f"({dados['internacionais'] / max(1, dados['total']):.1%})")
    print(f"svg: {argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

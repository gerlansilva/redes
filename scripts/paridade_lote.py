#!/usr/bin/env python3
"""Verificação de paridade em lote contra todos os relatórios gerados.

Percorre as combinações projeto × unidade × período dos relatórios do CELII e
confere cada GraphML com o redes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from paridade import compara

RAIZ = Path("/tmp/demo/celii")
FREQUENCIA = {"Words": 1, "Authors": 1, "References": 2,
              "AuthorsReference": 2, "ReferenceSources": 2}


def main() -> int:
    falhas = 0
    total = 0

    for recorte, projeto in (("completo", "proj-completo"),
                             ("periodos", "proj-periodos")):
        for unidade, minimo in FREQUENCIA.items():
            pasta = RAIZ / "relatorios" / recorte / unidade / "html" / "misc"
            for graphml in sorted(pasta.glob("wholeNetwork-period*.graphml")):
                periodo = int(re.search(r"period(\d+)", graphml.name).group(1))
                total += 1
                try:
                    falhas += compara(RAIZ / projeto / "dados.scimat", unidade,
                                      periodo, graphml, minimo)
                except Exception as erro:  # noqa: BLE001
                    falhas += 1
                    print(f"  ERRO {unidade} p{periodo}: {erro}")

    print(f"\n{total} análises · {falhas} divergências")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())

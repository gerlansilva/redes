#!/usr/bin/env python3
"""Rede de países no padrão das demais redes (halos por agrupamento).

Uso:
    python3 scripts/rede_paises.py <dados.redes> <saida.svg> [periodo|todos]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scimatpy.kb import ProjetoScimat  # noqa: E402
from scimatpy.pipeline import Configuracao, executa_periodo  # noqa: E402
from scimatpy.viz.halo import halo_svg  # noqa: E402
from scimatpy.viz.mapa import colaboracao  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    projeto = Path(argv[1])
    saida = Path(argv[2])
    recorte = argv[3] if len(argv) > 3 else "todos"

    config = Configuracao(unidade="Countries", minimo_frequencia=1)
    with ProjetoScimat(projeto) as kb:
        periodos = kb.periodos()
        if recorte not in ("todos", ""):
            periodos = [p for p in periodos if p.nome == recorte]
            if not periodos:
                print("período não encontrado", file=sys.stderr)
                return 1
        for periodo in periodos:
            resultado = executa_periodo(kb, periodo.id, periodo.nome, config)
            if not resultado.rede.nos:
                print(f"{periodo.nome}: sem países no período, figura não gerada",
                      file=sys.stderr)
                continue
            dados = colaboracao(projeto)
            subtitulo = (f"{dados['total']} documentos · {len(dados['documentos'])} países · "
                         f"{len(dados['ligacoes'])} cooperações")
            svg = halo_svg(resultado, "Rede de países", subtitulo=subtitulo,
                           largura=1120, altura=720)
            nome = saida if len(periodos) == 1 else saida.with_name(
                f"{saida.stem}-{periodo.posicao}{saida.suffix}")
            nome.parent.mkdir(parents=True, exist_ok=True)
            nome.write_text(svg, encoding="utf-8")
            print(f"halo: {nome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

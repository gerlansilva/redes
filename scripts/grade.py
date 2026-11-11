#!/usr/bin/env python3
"""Reproduz a grade de análises do CELII e compara com o TSV do Bibliomapa."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import collections

from redes.kb import ProjetoScimat
from redes.pipeline import Configuracao, executa_periodo

RAIZ = Path("/tmp/demo/celii")
from redes.grade import grade  # noqa: E402


def le_referencia(arquivo: Path):
    with open(arquivo, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main() -> int:
    recorte = sys.argv[1] if len(sys.argv) > 1 else "completo"
    if len(sys.argv) > 2:
        projeto = Path(sys.argv[2]).parent
    else:
        projeto = RAIZ / ("proj-completo" if recorte == "completo" else "proj-periodos")
    referencia = le_referencia(RAIZ / f"out-{recorte}" / "analises.tsv")
    por_unidade = collections.defaultdict(list)
    for linha in referencia:
        por_unidade[linha["unidade"]].append(linha)

    falhas = 0
    analises = 0
    compativeis = 0
    fora = 0
    posicao_unidade = collections.defaultdict(int)

    caminho = Path(sys.argv[2]) if len(sys.argv) > 2 else projeto / "dados.scimat"
    with ProjetoScimat(caminho) as kb:
        periodos = kb.periodos()
        for (eixo, unidade, matriz, algoritmo, similaridade,
             minimo_freq, minimo_cooc, rede_min, rede_max,
             mapeador, medida) in grade():
            analises += 1
            linhas_unidade = por_unidade.get(unidade)
            if not linhas_unidade:
                # A referência Java cobre cinco unidades; Países veio depois.
                fora += len(periodos)
                continue
            indice = posicao_unidade[unidade]
            posicao_unidade[unidade] += 1

            for posicao, periodo in enumerate(periodos):
                linha = linhas_unidade[indice * len(periodos) + posicao]
                if linha["status"] != "ok":
                    continue

                config = Configuracao(
                    unidade=unidade, matriz=matriz, algoritmo=algoritmo,
                    similaridade=similaridade, minimo_frequencia=minimo_freq,
                    minimo_coocorrencia=minimo_cooc, tamanho_minimo=rede_min,
                    tamanho_maximo=rede_max,
                    mapeadores=(mapeador,),
                    indices=(medida,) if medida else
                    ("h", "g", "hg", "q2", "media", "soma", "minimo", "maximo"),
                )

                try:
                    resultado = executa_periodo(kb, periodo.id, periodo.nome, config)
                except Exception as erro:  # noqa: BLE001
                    falhas += 1
                    print(f"ERRO {eixo} {unidade} {algoritmo} {matriz} {periodo.nome}: "
                          f"{type(erro).__name__}: {erro}")
                    continue

                compativeis += 1
                obtido = {
                    "documentos": resultado.dataset_original.quantidade_documentos(),
                    "itens": resultado.dataset_original.quantidade_itens(),
                    "itens_reduzidos": resultado.dataset.quantidade_itens(),
                    "grupos": len(resultado.grupos),
                    "maior_grupo": max((len(g.nos) for g in resultado.grupos), default=0),
                    "grupos_unitarios": sum(1 for g in resultado.grupos if len(g.nos) == 1),
                    "nos_rede": resultado.rede.quantidade_nos(),
                    "arestas_rede": resultado.rede.quantidade_arestas(),
                }

                divergencias = []
                for campo, valor in obtido.items():
                    esperado = int(float(linha[campo]))
                    if esperado != valor:
                        divergencias.append(f"{campo}: ref {esperado}, py {valor}")

                for campo, chave in (("centralidade_media", "centralidade"),
                                     ("densidade_media", "densidade")):
                    if resultado.grupos:
                        media = sum(getattr(g, chave) for g in resultado.grupos) / len(resultado.grupos)
                    else:
                        media = 0.0
                    esperado = float(linha[campo])
                    if abs(esperado - media) > 1e-3:
                        divergencias.append(f"{campo}: ref {esperado:.4f}, py {media:.4f}")

                if divergencias:
                    falhas += 1
                    print(f"DIVERGE {eixo} {unidade} {algoritmo} {matriz} "
                          f"{similaridade} {periodo.nome}: " + "; ".join(divergencias))

    print(f"\n{analises} análises · {compativeis} períodos comparados · "
          f"{falhas} divergências · {fora} períodos sem referência")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())

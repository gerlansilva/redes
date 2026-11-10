#!/usr/bin/env python3
"""Compara o scimatpy com as saídas do Bibliomapa/SciMAT.

Lê o GraphML exportado pelo relatório e confere, para o mesmo projeto e a mesma
configuração: conjunto de nós e rótulos, arestas, partição em agrupamentos,
frequência, grau e PageRank. Serve como teste de regressão do port.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scimatpy.kb import ProjetoScimat
from scimatpy.pipeline import Configuracao, executa_periodo


def carrega_graphml(caminho: Path):
    grafo = nx.read_graphml(caminho)
    rotulos = {no: dados["rotulo"] for no, dados in grafo.nodes(data=True)}
    grupos: dict[str, set[str]] = {}
    for no, dados in grafo.nodes(data=True):
        grupo = dados.get("grupo") or "Sem grupo"
        grupos.setdefault(grupo, set()).add(rotulos[no])
    arestas = {(rotulos[a], rotulos[b]) if rotulos[a] <= rotulos[b]
               else (rotulos[b], rotulos[a]) for a, b in grafo.edges()}
    return grafo, rotulos, grupos, arestas


def compara(projeto: Path, unidade: str, periodo_indice: int, graphml: Path,
            minimo_frequencia: int) -> int:
    falhas = 0

    with ProjetoScimat(projeto) as kb:
        periodos = kb.periodos()
        periodo = periodos[periodo_indice]
        config = Configuracao(unidade=unidade, minimo_frequencia=minimo_frequencia,
                              mapeadores=("nucleo",))
        resultado = executa_periodo(kb, periodo.id, periodo.nome, config)

    grafo, rotulos, grupos_ref, arestas_ref = carrega_graphml(graphml)

    meus_rotulos = {no: resultado.dataset.rotulo_item(no) for no in resultado.rede.nos}
    minhas_arestas = {(meus_rotulos[a], meus_rotulos[b]) if meus_rotulos[a] <= meus_rotulos[b]
                      else (meus_rotulos[b], meus_rotulos[a])
                      for a, b, _ in resultado.rede.arestas()}

    meus_grupos: dict[str, set[str]] = {}
    for grupo in resultado.grupos:
        meus_grupos[grupo.rotulo] = {meus_rotulos[no] for no in grupo.nos}
    for no in resultado.rede.nos:
        if no not in resultado.conjunto.grupo_do_no:
            meus_grupos.setdefault("Sem grupo", set()).add(meus_rotulos[no])

    def compara_conjunto(nome, esperado, obtido):
        nonlocal falhas
        if esperado == obtido:
            print(f"  ok   {nome}: {len(esperado)}")
            return
        falhas += 1
        faltam = sorted(esperado - obtido)[:5]
        sobram = sorted(obtido - esperado)[:5]
        print(f"  FALHA {nome}: esperado {len(esperado)}, obtido {len(obtido)}")
        if faltam:
            print(f"        faltam: {faltam}")
        if sobram:
            print(f"        sobram: {sobram}")

    print(f"{unidade} · {periodo.nome} · min_freq={minimo_frequencia}")
    compara_conjunto("nós", set(rotulos.values()), set(meus_rotulos.values()))
    compara_conjunto("arestas", arestas_ref, minhas_arestas)

    chaves = set(grupos_ref) | set(meus_grupos)
    divergentes = [c for c in chaves if grupos_ref.get(c, set()) != meus_grupos.get(c, set())]
    if divergentes:
        falhas += 1
        print(f"  FALHA agrupamentos: {len(divergentes)} divergem de {len(chaves)}")
        for chave in divergentes[:4]:
            print(f"        {chave!r}: ref {len(grupos_ref.get(chave, set()))}, "
                  f"scimatpy {len(meus_grupos.get(chave, set()))}")
    else:
        print(f"  ok   agrupamentos: {len(chaves)}")

    # Medidas dos nós, quando presentes no GraphML.
    inverso = {rotulo: no for no, rotulo in meus_rotulos.items()}
    for medida in ("frequencia", "grau", "pagerank"):
        if not all(medida in dados for _, dados in grafo.nodes(data=True)):
            continue
        erros = 0
        for no, dados in grafo.nodes(data=True):
            meu = inverso.get(dados["rotulo"])
            if meu is None:
                continue
            if medida == "frequencia":
                valor = resultado.frequencia_nos[meu]
            elif medida == "grau":
                valor = resultado.centralidades["grau"][meu]
            else:
                valor = resultado.centralidades["pagerank"][meu]
            if abs(float(dados[medida]) - valor) > 1e-6:
                erros += 1
        if erros:
            falhas += 1
            print(f"  FALHA {medida}: {erros} nós divergem")
        else:
            print(f"  ok   {medida}")

    return falhas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("projeto", help="caminho do dados.scimat")
    parser.add_argument("unidade", help="Words, Authors, References, ...")
    parser.add_argument("graphml", help="GraphML de referência do relatório")
    parser.add_argument("--periodo", type=int, default=0)
    parser.add_argument("--min-freq", type=int, default=1)
    args = parser.parse_args()

    return 1 if compara(Path(args.projeto), args.unidade, args.periodo,
                        Path(args.graphml), args.min_freq) else 0


if __name__ == "__main__":
    raise SystemExit(main())

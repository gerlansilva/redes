#!/usr/bin/env python3
"""Gera os valores de referência da paridade com o Python.

Uso (a partir da raiz do repositório):
    python3 rust/crates/redes-core/tests/gera_referencia.py [DIR_DOS_PROJETOS]

Roda o pipeline do Python (`redes.pipeline.executa_periodo`) em várias
configurações e grava `tests/referencia/<projeto>.json.gz`, que o teste de
paridade em Rust (`tests/paridade.rs`) lê.
"""
from __future__ import annotations

import gzip
import json
import math
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))

from redes.kb import ProjetoRedes                      # noqa: E402
from redes.pipeline import Configuracao, executa_periodo  # noqa: E402

DADOS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/claude/t")
SAIDA = Path(__file__).resolve().parent / "referencia"
PROJETOS = ["serj_auto", "novo142", "eecera59_auto", "zotero", "segat"]

SIMILARIDADES = ["EquivalenceIndex", "AssociationStrength", "InclusionIndex",
                 "JaccardIndex", "SaltonCosine"]


def casos(nome: str):
    """Lista de dicts de parâmetros (nomes do Rust)."""
    base = dict(matriz="CoOccurrence", min_freq=1, min_cooc=1, rede_min=2,
                rede_max=15, corte=0.0, mapeadores=["nucleo"], k_core=2,
                palavras=["autor", "fonte"])
    c = []
    # 1. Words: todos os algoritmos e similaridades
    for alg in ["CentersSimples", "Louvain", "AverageLink", "CompleteLink",
                "SingleLink", "SumLink"]:
        for sim in SIMILARIDADES:
            c.append({**base, "unidade": "Words", "algoritmo": alg, "similaridade": sim})
    # 2. Words: frequência mínima, tamanho do grupo, mapeadores, palavras, corte
    for alg in ["CentersSimples", "Louvain"]:
        for mf, rmin, rmax in [(2, 2, 15), (3, 2, 10), (2, 3, 8), (1, 2, 5), (1, 4, 15), (1, 2, 2)]:
            c.append({**base, "unidade": "Words", "algoritmo": alg, "min_freq": mf,
                      "rede_min": rmin, "rede_max": rmax})
    for mp in [["nucleo", "interseccao", "secundarios", "kcore", "uniao"], ["kcore"]]:
        for alg in ["CentersSimples", "Louvain"]:
            c.append({**base, "unidade": "Words", "algoritmo": alg, "mapeadores": mp, "k_core": 3})
    for pal in (["autor"], ["fonte"], ["adicionada"], []):
        c.append({**base, "unidade": "Words", "algoritmo": "CentersSimples", "palavras": pal})
    for corte in (0.05, 0.2, 1.0):
        for alg in ["AverageLink", "CompleteLink", "SingleLink", "SumLink"]:
            c.append({**base, "unidade": "Words", "algoritmo": alg, "corte": corte})
    c.append({**base, "unidade": "Words", "algoritmo": "CentersSimples", "min_cooc": 2})
    c.append({**base, "unidade": "Words", "algoritmo": "Louvain", "min_cooc": 2, "similaridade": "JaccardIndex"})
    c.append({**base, "unidade": "Words", "algoritmo": "CentersSimples", "ignorar": ["Estatística", "education"]})
    # 3. Outras unidades
    for un in ["Authors", "References", "AuthorsReference", "ReferenceSources", "Countries"]:
        for alg in ["CentersSimples", "Louvain"]:
            for mf in (1, 2):
                c.append({**base, "unidade": un, "algoritmo": alg, "min_freq": mf})
        c.append({**base, "unidade": un, "algoritmo": "AverageLink", "min_freq": 2})
        c.append({**base, "unidade": un, "algoritmo": "CentersSimples", "min_freq": 2,
                  "similaridade": "SaltonCosine", "rede_max": 8,
                  "mapeadores": ["nucleo", "uniao"]})
    # 4. Acoplamento
    for alg in ["CentersSimples", "Louvain"]:
        for sim in ["EquivalenceIndex", "JaccardIndex", "SaltonCosine"]:
            c.append({**base, "unidade": "Words", "matriz": "BasicCoupling", "algoritmo": alg,
                      "similaridade": sim, "mapeadores": ["acoplamento", "uniao"]})
        c.append({**base, "unidade": "References", "matriz": "BasicCoupling", "algoritmo": alg,
                  "min_freq": 2, "mapeadores": ["acoplamento"]})
        c.append({**base, "unidade": "Words", "matriz": "BasicCoupling", "algoritmo": alg,
                  "min_cooc": 3, "mapeadores": ["acoplamento"]})
        for m in ["AggregatedCouplingBasedOnAuthor", "AggregatedCouplingBasedOnJournal"]:
            c.append({**base, "unidade": "Words", "matriz": m, "algoritmo": alg,
                      "mapeadores": ["nucleo", "uniao"]})
            c.append({**base, "unidade": "References", "matriz": m, "algoritmo": alg,
                      "min_freq": 3, "mapeadores": ["nucleo"]})
    return c


def configuracao(p: dict) -> Configuracao:
    return Configuracao(
        unidade=p["unidade"], matriz=p["matriz"], algoritmo=p["algoritmo"],
        similaridade=p["similaridade"] if "similaridade" in p else "EquivalenceIndex",
        minimo_frequencia=p["min_freq"], minimo_coocorrencia=p["min_cooc"],
        tamanho_minimo=p["rede_min"], tamanho_maximo=p["rede_max"], corte=p["corte"],
        mapeadores=tuple(p["mapeadores"]), k_core=p["k_core"],
        palavras=tuple(p["palavras"]), ignorar=tuple(p.get("ignorar", ())))


def digest(docs) -> list:
    docs = sorted(docs)
    return [len(docs), sum(docs), sum(d * d for d in docs)]


def resumo_periodo(res) -> dict:
    grupos = res.grupos
    arestas = res.rede.arestas()
    return {
        "periodo": res.periodo,
        "documentos": res.dataset_original.quantidade_documentos(),
        "itens": res.dataset_original.quantidade_itens(),
        "itens_reduzidos": res.dataset.quantidade_itens(),
        "grupos": len(grupos),
        "maior_grupo": max((len(g.nos) for g in grupos), default=0),
        "grupos_unitarios": sum(1 for g in grupos if len(g.nos) == 1),
        "nos_rede": res.rede.quantidade_nos(),
        "arestas_rede": res.rede.quantidade_arestas(),
        "centralidade_media": sum(g.centralidade for g in grupos) / len(grupos) if grupos else 0.0,
        "densidade_media": sum(g.densidade for g in grupos) / len(grupos) if grupos else 0.0,
        "arestas_soma": math.fsum(v for _, _, v in arestas),
        "arestas_soma_ponderada": math.fsum(v * (a % 97 + 3 * (b % 89)) for a, b, v in arestas),
        "frequencias": digest(res.frequencia_nos.values()),
        "grupos_lista": [{
            "nos": g.nos, "principal": g.principal, "exibicao": g.exibicao,
            "c": g.centralidade, "d": g.densidade,
            "cf": g.centralidade_faixa, "df": g.densidade_faixa,
            "docs": {m: digest(d) for m, d in g.documentos.items()},
            "medidas": g.medidas,
        } for g in grupos],
    }


def main() -> None:
    SAIDA.mkdir(exist_ok=True)
    for nome in PROJETOS:
        caminho = DADOS / f"{nome}.redes"
        saida = []
        inicio = time.time()
        with ProjetoRedes(caminho) as kb:
            periodos = kb.periodos()
            for p in casos(nome):
                try:
                    cfg = configuracao(p)
                    rs = [resumo_periodo(executa_periodo(kb, per.id, per.nome, cfg))
                          for per in periodos]
                    saida.append({"params": p, "periodos": rs})
                except Exception as erro:  # noqa: BLE001 - registra a falha do Python
                    saida.append({"params": p, "erro": f"{type(erro).__name__}: {erro}"})
        with gzip.open(SAIDA / f"{nome}.json.gz", "wt", encoding="utf-8", compresslevel=9) as f:
            json.dump(saida, f, ensure_ascii=False, separators=(",", ":"))
        print(f"{nome}: {len(saida)} casos em {time.time() - inicio:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Referência da paridade da segunda leva (Instituições, componente mínimo,
centralidades, pontos de virada, qualidade, rótulos por tema, longitudinal).

Uso (a partir da raiz do repositório):
    python3 rust/crates/redes-core/tests/gera_referencia2.py [DIR_DOS_PROJETOS]

Grava `tests/referencia2/<projeto>.json.gz`, que `tests/paridade2.rs` lê.
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
ARGV = sys.argv[1:]
sys.argv = sys.argv[:1]

import gera_referencia as g1                              # noqa: E402
from redes import longitudinal, measures, pivos, qualidade, rotulos  # noqa: E402
from redes.kb import ProjetoRedes                         # noqa: E402
from redes.pipeline import Configuracao, executa_periodo  # noqa: E402

DADOS = Path(ARGV[0]) if ARGV else Path("/home/claude/t")
SAIDA = Path(__file__).resolve().parent / "referencia2"
PROJETOS = {"serj_auto": True, "novo142": True, "eecera59_auto": True, "zotero": False, "segat": False,
            "novo142_auto": False}
LIMITE_CENTRAL = 400          # intermediação em Python é cara: só redes até isto
EXTRAS = {"centralidades": True, "pivos": True, "qualidade": True, "rotulos": True}


def limpa(x):
    """Troca não finitos por None e converte conjuntos/tuplas para JSON."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {str(k): limpa(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [limpa(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted(limpa(v) for v in x)
    return x


def configuracao(p: dict) -> Configuracao:
    c = g1.configuracao(p)
    c.componente_minimo = p.get("componente_minimo")
    return c


def casos() -> list[dict]:
    base = dict(matriz="CoOccurrence", min_freq=1, min_cooc=1, rede_min=2, rede_max=15, corte=0.0,
                mapeadores=["nucleo"], k_core=2, palavras=["autor", "fonte"], similaridade="EquivalenceIndex")
    c = []
    # Instituições: todos os algoritmos, filtro de componente e frequência mínima
    for alg in ["CentersSimples", "Louvain", "AverageLink", "CompleteLink", "SingleLink", "SumLink"]:
        c.append({**base, "unidade": "Institutions", "algoritmo": alg})
    for cm in (1, 2, 3, 5, 8):
        for alg in ["CentersSimples", "Louvain"]:
            c.append({**base, "unidade": "Institutions", "algoritmo": alg, "componente_minimo": cm})
    for mf in (2, 3):
        c.append({**base, "unidade": "Institutions", "algoritmo": "Louvain", "min_freq": mf})
        c.append({**base, "unidade": "Institutions", "algoritmo": "CentersSimples", "min_freq": mf,
                  "similaridade": "JaccardIndex", "mapeadores": ["nucleo", "uniao"]})
    # Componente mínimo em Authors e Countries
    for un in ("Authors", "Countries"):
        for cm in (2, 3, 5):
            for alg in ["CentersSimples", "Louvain"]:
                c.append({**base, "unidade": un, "algoritmo": alg, "componente_minimo": cm})
    # Centralidades, pivôs, qualidade e rótulos (extras ligados)
    ex = dict(extras=EXTRAS)
    c.append({**base, **ex, "unidade": "Words", "algoritmo": "CentersSimples"})
    c.append({**base, **ex, "unidade": "Words", "algoritmo": "Louvain", "min_freq": 2})
    c.append({**base, **ex, "unidade": "Words", "algoritmo": "CentersSimples", "min_freq": 2,
              "similaridade": "JaccardIndex", "mapeadores": ["nucleo", "uniao"]})
    c.append({**base, **ex, "unidade": "Words", "algoritmo": "AverageLink", "min_freq": 2})
    c.append({**base, **ex, "unidade": "Authors", "algoritmo": "CentersSimples"})
    c.append({**base, **ex, "unidade": "Authors", "algoritmo": "Louvain", "min_freq": 2})
    c.append({**base, **ex, "unidade": "References", "algoritmo": "CentersSimples", "min_freq": 2})
    c.append({**base, **ex, "unidade": "References", "algoritmo": "Louvain", "min_freq": 3})
    c.append({**base, **ex, "unidade": "ReferenceSources", "algoritmo": "Louvain", "min_freq": 2})
    c.append({**base, **ex, "unidade": "AuthorsReference", "algoritmo": "CentersSimples", "min_freq": 2})
    c.append({**base, **ex, "unidade": "Countries", "algoritmo": "CentersSimples"})
    c.append({**base, **ex, "unidade": "Institutions", "algoritmo": "CentersSimples"})
    c.append({**base, **ex, "unidade": "Institutions", "algoritmo": "Louvain", "componente_minimo": 2})
    c.append({**base, **ex, "unidade": "Words", "matriz": "BasicCoupling", "algoritmo": "CentersSimples",
              "mapeadores": ["acoplamento", "uniao"]})
    c.append({**base, **ex, "unidade": "Words", "matriz": "AggregatedCouplingBasedOnJournal",
              "algoritmo": "Louvain", "mapeadores": ["nucleo"]})
    return c


def citacoes_do_grupo(res, grupo, p) -> int:
    if p["matriz"] == "BasicCoupling":
        docs = grupo.nos
    else:
        from redes.mappers import nucleo
        fonte = res.agregado if res.agregado is not None else res.dataset
        docs = nucleo(res.rede, fonte, grupo.nos)
    return sum(res.dataset.citacoes(d) for d in docs)


def periodo(kb, per, p) -> dict:
    cfg = configuracao(p)
    res = executa_periodo(kb, per.id, per.nome, cfg)
    r = g1.resumo_periodo(res)
    r["documentos_projeto"] = kb.conexao.execute("SELECT COUNT(*) FROM Document").fetchone()[0]
    for lg, gr in zip(r["grupos_lista"], res.grupos):
        lg["citacoes"] = citacoes_do_grupo(res, gr, p)
    r["filtro"] = limpa(res.filtro_agrupamento)
    if res.ies is not None:
        r["ies"] = limpa({**res.ies, "unioes": res.ies["unioes"]})
    extras = p.get("extras") or {}
    n = res.rede.quantidade_nos()
    if extras.get("centralidades") and n <= LIMITE_CENTRAL:
        c = res.centralidades
        r["centralidades"] = {str(no): [c[k][no] for k in ("grau", "intermediacao", "proximidade", "autovetor", "pagerank")]
                              for no in res.rede.nos}
    if extras.get("pivos") and (n <= LIMITE_CENTRAL or n > pivos.LIMITE_NOS):
        pv = pivos.pontos_de_virada(res, None, 10)
        r["pivos"] = limpa({k: pv[k] for k in ("n_nos", "suficiente", "pivos", "termos_descritores",
                                               "avisos", "nao_calculado")})
    if extras.get("qualidade"):
        q = qualidade.avalia(res)
        q = dict(q)
        q["silhueta_por_grupo"] = [q["silhueta_por_grupo"][i] for i in range(len(res.grupos))]
        r["qualidade"] = limpa(q)
    if extras.get("rotulos"):
        rt = rotulos.rotula_grupos(None if False else kb, res)
        r["rotulos"] = limpa({str(i): v for i, v in rt.items()})
    return r


def longitudinais(kb) -> list[dict]:
    saida = []
    per = kb.periodos()
    if len(per) < 2:
        return saida
    base = dict(matriz="CoOccurrence", min_freq=1, min_cooc=1, rede_min=2, rede_max=15, corte=0.0,
                mapeadores=["nucleo"], k_core=2, palavras=["autor", "fonte"], similaridade="EquivalenceIndex")
    for p, medida in [
        ({**base, "unidade": "Words", "algoritmo": "CentersSimples"}, "EquivalenceIndex"),
        ({**base, "unidade": "Words", "algoritmo": "Louvain", "min_freq": 2}, "JaccardIndex"),
        ({**base, "unidade": "Words", "algoritmo": "CentersSimples", "min_freq": 2, "corte": 0.05}, "InclusionIndex"),
        ({**base, "unidade": "Words", "algoritmo": "Louvain"}, "SaltonCosine"),
        ({**base, "unidade": "Words", "algoritmo": "CentersSimples"}, "AssociationStrength"),
        ({**base, "unidade": "Authors", "algoritmo": "CentersSimples"}, "EquivalenceIndex"),
        ({**base, "unidade": "References", "algoritmo": "Louvain", "min_freq": 2}, "JaccardIndex"),
    ]:
        m = longitudinal.constroi(kb, configuracao(p), per, medida)
        indice = {id(no): i for i, no in enumerate(m.nos)}
        saida.append({
            "params": p, "medida": medida,
            "periodos": m.periodos,
            "nos": [{"periodo": n.periodo, "selo": n.selo, "rotulo": n.rotulo, "itens": sorted(n.itens),
                     "principal": n.principal, "tamanho": n.tamanho,
                     "nomes": {str(k): v for k, v in n.nomes.items()}} for n in m.nos],
            "elos": [[indice[id(e.origem)], indice[id(e.destino)], e.peso, e.principal_comum] for e in m.elos],
            "sobreposicao": limpa(m.sobreposicao),
            "transicoes": limpa(m.transicoes),
            "parametros": m.parametros,
            "pajek": longitudinal.evolucao_pajek(m),
        })
    return saida


def main() -> None:
    SAIDA.mkdir(exist_ok=True)
    for nome in PROJETOS:
        caminho = DADOS / f"{nome}.redes"
        if not caminho.is_file():
            continue
        saida, inicio = [], time.time()
        with ProjetoRedes(caminho) as kb:
            periodos = kb.periodos()
            if nome == "novo142_auto":
                lista = []          # só longitudinal
            else:
                lista = casos()
            for p in lista:
                try:
                    rs = [periodo(kb, per, p) for per in periodos]
                    saida.append({"params": p, "periodos": rs})
                except Exception as erro:  # noqa: BLE001
                    saida.append({"params": p, "erro": f"{type(erro).__name__}: {erro}"})
            longi = longitudinais(kb)
        with gzip.open(SAIDA / f"{nome}.json.gz", "wt", encoding="utf-8", compresslevel=9) as f:
            json.dump({"casos": saida, "longitudinal": longi}, f, ensure_ascii=False, separators=(",", ":"))
        print(f"{nome}: {len(saida)} casos, {len(longi)} longitudinais em {time.time() - inicio:.0f}s",
              file=sys.stderr)


if __name__ == "__main__":
    main()

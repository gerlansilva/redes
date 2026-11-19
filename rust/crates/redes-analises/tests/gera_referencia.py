"""Gera as referências de paridade (JSON gzip) a partir do Python de referência.

Uso (a partir da raiz do worktree que contém o pacote `redes`):

    PYTHONPATH=/home/claude/rust-wt python3 crates/redes-analises/tests/gera_referencia.py \
        /home/claude/t/serj_auto.redes /home/claude/t/novo142.redes

Cada projeto gera `tests/ref/<nome>.json.gz` com os números de cada análise e contagens de
elementos dos SVG. O teste `paridade.rs` compara o Rust com esses arquivos.
"""
import gzip
import json
import os
import re
import sqlite3
import sys
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))


def contagem_svg(svg: str) -> dict:
    """Quantas vezes cada elemento aparece (ignora `<svg>` e atributos)."""
    c = Counter(re.findall(r"<([a-zA-Z]+)[\s>/]", svg))
    return dict(c)


def so_numeros(x):
    return x


def similitude(caminho: str, saida: dict, **kw):
    from redes import similitude as S
    from redes.viz import similitude as V
    con = sqlite3.connect(caminho)
    try:
        for rotulo, params in kw.items():
            try:
                res = S.analisa(con, None, **params)
            except S.SemResumos as e:
                saida.setdefault("similitude", {})[rotulo] = {"erro": str(e)}
                continue
            svg = V.svg(res, "Similitude")
            saida.setdefault("similitude", {})[rotulo] = {
                "params": params, "res": res, "svg": contagem_svg(svg), "svg_texto": svg,
                "graphml": S.graphml(res), "csv_formas": S.csv_formas(res),
                "csv_arestas": S.csv_arestas(res),
            }
    finally:
        con.close()


BASE = dict(matriz="CoOccurrence", min_freq=1, min_cooc=1, rede_min=2, rede_max=15, corte=0.0,
            mapeadores=["nucleo"], k_core=2, palavras=["autor", "fonte"], similaridade="EquivalenceIndex")
CASOS_CORPUS = {
    "palavras": {**BASE, "unidade": "Words", "algoritmo": "CentersSimples", "min_freq": 2},
    "palavras_louvain": {**BASE, "unidade": "Words", "algoritmo": "Louvain", "min_freq": 2},
    "autores": {**BASE, "unidade": "Authors", "algoritmo": "CentersSimples"},
    "referencias": {**BASE, "unidade": "References", "algoritmo": "CentersSimples", "min_freq": 2},
}


def limpa(x):
    """Troca não finitos por None e converte tuplas/conjuntos para JSON."""
    import math
    if hasattr(x, "tolist"):
        return limpa(x.tolist())
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {str(k): limpa(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [limpa(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted(limpa(v) for v in x)
    return x


def avancadas(caminho: str, saida: dict):
    sys.path.insert(0, os.path.join(AQUI, "..", "..", "redes-core", "tests"))
    import gera_referencia as g1
    from redes import dendro_helper, dendrograma, linha_do_tempo, rajadas
    from redes.kb import ProjetoRedes
    from redes.pipeline import executa_periodo
    from redes.viz import densidade as vd
    from redes.viz import dendrograma as vdg
    from redes.viz import linha_do_tempo as vlt
    con = sqlite3.connect(caminho)
    saida["rajadas"] = {
        tipo: limpa(rajadas.calcula(con, tipo, limite=20, minimo_documentos=3)) for tipo in ("palavras", "referencias")}
    con.close()
    with ProjetoRedes(caminho) as kb:
        per = kb.periodos()[0]
        for rotulo, params in CASOS_CORPUS.items():
            config = g1.configuracao(params)
            res = executa_periodo(kb, per.id, per.nome, config)
            for lig in dendrograma.LIGACOES:
                d, omit = dendro_helper.dendrograma_do_periodo(res, 60, lig)
                if d is None:
                    saida.setdefault("dendrograma", {})[f"{rotulo}/{lig}"] = {"vazio": True}
                    continue
                ng = d["n_grupos_sugerido"]
                part = d.corte(n_grupos=ng)
                saida.setdefault("dendrograma", {})[f"{rotulo}/{lig}"] = {
                    "params": params, "ligacao": lig, "nos": d["nos"], "ordem": d["ordem"],
                    "alturas": d["alturas"], "coph": d["coph"], "sugerido": ng, "fusoes": limpa(d["fusoes"]),
                    "particao": limpa(part), "comparacao": limpa(d.comparacao(part)) if d.get("grupos_rede") else None,
                    "frases": dendrograma.interpreta(d, ng), "omitidos": omit,
                    "svg_texto": vdg.svg(d, ng, "Dendrograma"),
                }
            if params["unidade"] in ("Words", "Authors", "References"):
                dados = linha_do_tempo.constroi(kb, config, 40)
                saida.setdefault("linha", {})[rotulo] = {
                    "params": params, "dados": limpa(dados),
                    "svg_texto": vlt.svg(dados, "Linha do tempo", {}),
                }
                corpus = linha_do_tempo_corpus(kb, config)
                dd = vd.calcula(corpus)
                saida.setdefault("densidade", {})[rotulo] = {
                    "params": params, "n_nos": len(dd["nos"]), "aviso": dd.get("aviso"),
                    "nos": limpa(dd["nos"]), "pesos": limpa(dd["pesos"]),
                    "svg": contagem_svg(vd.svg(corpus, "Mapa", unidade=config.unidade, dados=dd)),
                }


def linha_do_tempo_corpus(kb, config):
    from redes import linha_do_tempo
    from redes.pipeline import executa_periodo
    return executa_periodo(linha_do_tempo._TodosOsDocumentos(kb), 0, "Corpus", config)


def duplo_mapa(caminho: str, saida: dict):
    from redes import duplo_mapa as dm
    from redes.viz import duplo_mapa as vdm
    con = sqlite3.connect(caminho)
    saida["duplo_mapa"] = {}
    for rotulo, (e, d) in {"padrao": (10, 16), "pequeno": (4, 6), "grande": (25, 40)}.items():
        dados = dm.calcula_do_banco(con, e, d)
        saida["duplo_mapa"][rotulo] = {"max": [e, d], "dados": limpa(dados), "svg_texto": vdm.svg(dados, "Duplo mapa"),
                                      "aplicavel": dm.aplicavel(con)}
    con.close()


def main(caminhos):
    for caminho in caminhos:
        nome = os.path.basename(caminho).replace(".redes", "")
        saida: dict = {"projeto": nome}
        similitude(caminho, saida,
                   padrao={}, binomial={"indice_nome": "binomial", "n_formas": 40},
                   cosseno_frase={"indice_nome": "cosseno", "segmento": "frase", "extras": 0},
                   en={"idioma": "en", "n_formas": 30})
        avancadas(caminho, saida)
        duplo_mapa(caminho, saida)
        os.makedirs(os.path.join(AQUI, "ref"), exist_ok=True)
        with gzip.open(os.path.join(AQUI, "ref", nome + ".json.gz"), "wt", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, sort_keys=True, default=str)
        print("ok", nome)


if __name__ == "__main__":
    main(sys.argv[1:])

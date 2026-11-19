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


def main(caminhos):
    for caminho in caminhos:
        nome = os.path.basename(caminho).replace(".redes", "")
        saida: dict = {"projeto": nome}
        similitude(caminho, saida,
                   padrao={}, binomial={"indice_nome": "binomial", "n_formas": 40},
                   cosseno_frase={"indice_nome": "cosseno", "segmento": "frase", "extras": 0},
                   en={"idioma": "en", "n_formas": 30})
        for modulo in sorted(f[:-3] for f in os.listdir(AQUI) if f.startswith("ref_") and f.endswith(".py")):
            pass
        os.makedirs(os.path.join(AQUI, "ref"), exist_ok=True)
        with gzip.open(os.path.join(AQUI, "ref", nome + ".json.gz"), "wt", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, sort_keys=True, default=str)
        print("ok", nome)


if __name__ == "__main__":
    main(sys.argv[1:])

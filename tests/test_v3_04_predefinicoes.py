"""Predefinições de rigor: três botões e parâmetros que chegam à API."""
from pathlib import Path

import redes
from redes import api

UI = Path(redes.__file__).parent / "ui"


def test_tres_botoes_e_valores():
    html = (UI / "index.html").read_text(encoding="utf-8")
    for chave in ("padrao", "estrito", "amplo"):
        assert f'data-predef="{chave}"' in html
    js = (UI / "app.js").read_text(encoding="utf-8")
    assert "estrito: { auto: false, freq: 3, cooc: 2 }" in js
    assert "minimo_coocorrencia: estado.cooc" in js


def test_cooccurrencia_minima_chega_a_api(projeto):
    d = api.descreve_projeto(Path(projeto))
    base = {"projeto": str(projeto), "unidade": "Words", "periodo": d["periodos"][0]["id"]}
    amplo = api.analisa({**base, "minimo_frequencia": 1, "minimo_coocorrencia": 1})
    estrito = api.analisa({**base, "minimo_frequencia": 3, "minimo_coocorrencia": 2})
    assert estrito["parametros"]["minimo_coocorrencia"] == 2
    assert estrito["resumo"]["nos"] <= amplo["resumo"]["nos"]

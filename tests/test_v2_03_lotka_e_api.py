"""Lotka sem zeros na curva esperada; API recusa .redes inválido com mensagem clara."""
import math
from collections import Counter

import pytest

from redes import bibliometria
from redes.api import ErroApi, _valida_projeto


def test_lotka_esperada_nunca_zero():
    producao = Counter({f"a{i}": n for i, n in enumerate([1, 1, 1, 2, 3, 147, 400])})
    pontos = bibliometria.lotka(producao)["pontos"]
    assert all(p["esperada"] > 0 for p in pontos)
    ultimo = pontos[-1]
    assert math.isclose(ultimo["esperada"], (6 / math.pi ** 2) / ultimo["documentos"] ** 2, rel_tol=1e-5)


def test_api_recusa_arquivo_que_nao_e_projeto(tmp_path):
    falso = tmp_path / "falso.redes"
    falso.write_text("nada", encoding="utf-8")
    with pytest.raises(ErroApi, match="não é um projeto"):
        _valida_projeto(str(falso))


def test_api_recusa_extensao_errada(tmp_path):
    outro = tmp_path / "x.db"
    outro.write_text("x")
    with pytest.raises(ErroApi, match=r"\.redes"):
        _valida_projeto(str(outro))


def test_api_aceita_projeto(projeto):
    assert _valida_projeto(str(projeto)) == projeto.resolve()

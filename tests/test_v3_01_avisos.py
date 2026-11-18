"""Avisos de limite mínimo: calculados na API, nunca bloqueiam a análise."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from redes import api, avisos


def _config(unidade="Words", matriz="CoOccurrence"):
    return SimpleNamespace(unidade=unidade, matriz=matriz)


class _Original:
    def __init__(self, docs, freqs=()):
        self.docs, self.freqs = docs, list(freqs)

    def quantidade_documentos(self):
        return self.docs

    def lista_itens(self):
        return list(range(len(self.freqs)))

    def frequencia_item(self, i):
        return self.freqs[i]


def _res(docs, freqs=()):
    return SimpleNamespace(dataset_original=_Original(docs, freqs))


def codigos(lista):
    return {a["codigo"] for a in lista}


def test_limites_documentados_no_modulo():
    assert avisos.LIMITES["documentos_por_periodo"] == 20
    assert avisos.LIMITES["fracao_tema_dominante"] == 0.40
    for chave in avisos.LIMITES:
        assert f"``{chave}``" in avisos.__doc__


def test_periodo_pequeno_avisa_com_a_frase_pedida():
    a = avisos.avisos_de_limite(_res(16), _config(), [])
    msg = next(x["mensagem"] for x in a if x["codigo"] == "periodo_pequeno")
    assert msg.startswith("Só 16 documentos neste período; a classificação dos temas pode mudar muito")
    assert "periodo_pequeno" not in codigos(avisos.avisos_de_limite(_res(20), _config(), []))


def test_tema_dominante_acima_de_40_por_cento():
    a = avisos.avisos_de_limite(_res(50), _config(), [("saúde", 21), ("b", 3)])
    assert "tema_dominante" in codigos(a)
    assert "tema_dominante" not in codigos(
        avisos.avisos_de_limite(_res(50), _config(), [("saúde", 20)]))


def test_cocitacao_com_poucas_referencias_em_comum():
    r = _res(30, [1, 1, 2, 3, 1])
    a = avisos.avisos_de_limite(r, _config("References"), [])
    assert "poucas_referencias_em_comum" in codigos(a)
    r2 = _res(30, [2] * 12)
    assert "poucas_referencias_em_comum" not in codigos(
        avisos.avisos_de_limite(r2, _config("References"), []))
    assert "poucas_referencias_em_comum" not in codigos(
        avisos.avisos_de_limite(r, _config("Words"), []))


def test_corpus_focal_e_aviso_para_paises_e_instituicoes():
    corpus = avisos.corpus_focal({"Lopes, C.E.": 45, "Outro": 5}, 50)
    assert corpus["focal"] and corpus["autores_focais"][0]["nome"] == "Lopes, C.E."
    for unidade in ("Countries", "Institutions"):
        a = avisos.avisos_de_limite(_res(50), _config(unidade), [], corpus)
        assert "autor_focal" in codigos(a)
    assert "autor_focal" not in codigos(avisos.avisos_de_limite(_res(50), _config("Words"), [], corpus))
    assert not avisos.corpus_focal({"a": 10, "b": 10}, 50)["focal"]
    assert not avisos.corpus_focal({"a": 45, "b": 45, "c": 45}, 50)["focal"]  # 3 focais


def test_api_analisa_devolve_avisos_sem_bloquear(projeto):
    d = api.descreve_projeto(Path(projeto))
    assert d["corpus"]["focal"] is True       # Silva e Costa estão em todos os documentos? só 2 focais
    r = api.analisa({"projeto": str(projeto), "unidade": "Words", "periodo": d["periodos"][0]["id"]})
    assert "periodo_pequeno" in codigos(r["avisos"])       # 6 documentos
    assert r["grupos"], "o aviso não pode impedir a análise"
    assert all(a["nivel"] == "limite" for a in r["avisos"] if a["codigo"] == "periodo_pequeno")

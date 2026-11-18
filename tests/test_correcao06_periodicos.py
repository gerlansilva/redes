import sqlite3

from redes.build import constroi, unifica_periodicos
from redes.loaders.base import DocumentoFonte


def _docs(*periodicos):
    return [DocumentoFonte(titulo=f"T{i}", autores=["A, B."], ano="2020", periodico=p,
                           palavras_autor=["x"]) for i, p in enumerate(periodicos)]


def test_une_caixa_acento_pontuacao():
    docs = _docs("Suma", "SUMA", "Suma", "Educación Matemática", "Educacion Matematica.", "Outra")
    unidos = unifica_periodicos(docs)
    assert [d.periodico for d in docs][:3] == ["Suma"] * 3
    assert docs[3].periodico == docs[4].periodico == "Educación Matemática"
    assert unidos["Suma"] == ["SUMA", "Suma"]


def test_constroi_grava_um_periodico_e_opcao_de_desligar(tmp_path):
    for unir, esperado in ((True, 1), (False, 2)):
        destino = tmp_path / f"p{unir}.redes"
        constroi(_docs("Suma", "SUMA"), destino, [("2020", 2020, 2020)], unir_periodicos=unir)
        n = sqlite3.connect(destino).execute("SELECT COUNT(*) FROM Journal").fetchone()[0]
        assert n == esperado

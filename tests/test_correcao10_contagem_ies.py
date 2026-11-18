import sqlite3

from redes import bibliometria, ies
from redes.build import constroi
from redes.loaders.base import DocumentoFonte


def _doc(i, afil):
    return DocumentoFonte(titulo=f"T{i}", autores=["A, B."], ano="2020", periodico="J",
                          afiliacoes=[afil], paises=["Spain"], palavras_autor=["x"])


def test_indicador_principal_e_unidade_institutions_concordam(tmp_path):
    docs = [_doc(1, "Universidad de Granada, Granada, Spain"),
            _doc(2, "University of Granada, Granada, Spain"),
            _doc(3, "Universidad de Sevilla, Sevilla, Spain")]
    destino = tmp_path / "p.redes"
    constroi(docs, destino, [("2020", 2020, 2020)])
    conexao = sqlite3.connect(destino)
    assert len(ies.indice_de_ies(conexao).nomes) == 2
    assert bibliometria.calcula(conexao)["principal"]["instituicoes"] == 2

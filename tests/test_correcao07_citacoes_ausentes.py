import sqlite3

from redes import bibliometria
from redes.build import constroi
from redes.loaders.base import DocumentoFonte
from redes.loaders.openalex import _citacoes


def test_vazio_vira_none_e_zero_continua_zero():
    assert _citacoes("") is None
    assert _citacoes("  ") is None
    assert _citacoes("0") == 0
    assert _citacoes("12") == 12


def test_indicadores_tratam_ausente(tmp_path):
    docs = [DocumentoFonte(titulo=f"T{i}", autores=["A, B."], ano="2020", periodico="J",
                           palavras_autor=["x"], citacoes=c)
            for i, c in enumerate([10, None, 0])]
    destino = tmp_path / "p.redes"
    resumo = constroi(docs, destino, [("2020", 2020, 2020)])
    assert resumo["sem_citacoes"] == 1
    conexao = sqlite3.connect(destino)
    assert conexao.execute("SELECT COUNT(*) FROM Document WHERE citationsCount IS NULL").fetchone()[0] == 1
    principal = bibliometria.calcula(conexao)
    assert principal["principal"]["documentos_sem_citacao"] == 1
    assert principal["principal"]["citacoes_por_documento"] == 5.0   # 10 / 2 informados
    assert any("sem contagem de citações" in l for l in principal["lacunas"])

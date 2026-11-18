"""Auxiliares dos testes: projeto sintético mínimo."""
from pathlib import Path

import pytest

from redes.build import constroi
from redes.loaders.base import DocumentoFonte


def docs_sinteticos():
    docs = []
    for i in range(6):
        docs.append(DocumentoFonte(
            titulo=f"Artigo {i}", autores=["Silva, A.", "Costa, B."] + (["Lima, C."] if i % 2 else []),
            ano=str(2010 + i), citacoes=i, periodico="Revista X",
            palavras_autor=["tema um", "tema dois"] + (["tema tres"] if i % 2 else ["tema quatro"]),
            palavras_fonte=["revista x"]))
    return docs


@pytest.fixture
def projeto(tmp_path) -> Path:
    destino = tmp_path / "dados.redes"
    constroi(docs_sinteticos(), destino, [("2010–2015", 2010, 2015)])
    return destino

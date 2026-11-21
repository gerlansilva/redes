"""Frequência mínima: muda a rede, não o corpus.

A frequência mínima filtra os itens que entram na rede (nós, arestas e
agrupamentos). Os documentos, as citações e os demais indicadores do corpus
continuam os mesmos. Este teste fixa as duas coisas.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from redes.api import analisa
from redes.build import constroi
from redes.loaders.base import DocumentoFonte

# Frequências das palavras no corpus de teste: alfa 4, beta 3, gama 3,
# delta 2, unico 1.
PALAVRAS = [
    ["alfa", "beta", "gama"],
    ["alfa", "beta", "delta"],
    ["alfa", "gama", "delta"],
    ["beta", "gama"],
    ["alfa", "unico"],
]


class FrequenciaMinimaTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        documentos = [
            DocumentoFonte(titulo=f"Doc {i}", autores=[f"Autor {i}"],
                           ano=str(2020 + i), palavras_autor=palavras)
            for i, palavras in enumerate(PALAVRAS, start=1)
        ]
        cls.workspace = Path(tempfile.mkdtemp())
        cls.projeto = cls.workspace / "freq" / "dados.redes"
        constroi(documentos, cls.projeto, [("2020\u20132024", 2020, 2024)])

    def resumo(self, frequencia: int) -> dict:
        resultado = analisa({
            "projeto": str(self.projeto), "unidade": "Words",
            "minimo_frequencia": frequencia, "minimo_coocorrencia": 1,
            "tamanho_minimo": 1, "tamanho_maximo": 15,
            "componente_minimo": 1, "periodo": "todos",
        })
        return resultado["resumo"]

    def test_subir_a_frequencia_reduz_itens_nos_e_arestas(self):
        resumos = [self.resumo(f) for f in (1, 2, 3, 4)]
        # Itens e nós: 5, 4, 3 e 1 palavras com frequência >= f.
        self.assertEqual([5, 4, 3, 1], [r["itens_reduzidos"] for r in resumos])
        self.assertEqual([5, 4, 3, 1], [r["nos"] for r in resumos])
        # Arestas e grupos nunca aumentam quando o corte sobe.
        self.assertEqual([7, 6, 3, 0], [r["arestas"] for r in resumos])
        self.assertEqual([1, 1, 1, 0], [r["grupos"] for r in resumos])

    def test_documentos_nao_mudam_com_a_frequencia(self):
        for frequencia in (1, 2, 3, 4):
            self.assertEqual(5, self.resumo(frequencia)["documentos"], frequencia)

    def test_descer_a_frequencia_devolve_os_itens(self):
        alto = self.resumo(4)
        baixo = self.resumo(1)
        self.assertLess(alto["nos"], baixo["nos"])
        self.assertLess(alto["arestas"], baixo["arestas"])
        self.assertEqual(baixo["documentos"], alto["documentos"])


if __name__ == "__main__":
    unittest.main()

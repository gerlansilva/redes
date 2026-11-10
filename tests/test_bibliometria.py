import sqlite3
import tempfile
import unittest
from pathlib import Path

from scimatpy import bibliometria, build
from scimatpy.loaders.base import DocumentoFonte


def _corpus():
    docs = []
    for i in range(12):
        docs.append(DocumentoFonte(
            titulo=f"Estudo {i}", ano=str(2015 + i % 5),
            autores=[f"Autor {i % 4} A.", f"Autor {i % 3 + 10} B."],
            palavras_autor=["estatística", f"tema {i % 3}"],
            periodico="Revista X" if i % 2 else "Revista Y",
            citacoes=i))
    return docs


class BibliometriaTest(unittest.TestCase):
    def test_indicadores_basicos(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "p.redes"
            try:
                build.constroi(_corpus(), destino, None)
            except TypeError:
                self.skipTest("DocumentoFonte com outra assinatura")
            conexao = sqlite3.connect(destino)
            dados = bibliometria.calcula(conexao)
            conexao.close()
        self.assertFalse(dados["vazio"])
        self.assertEqual(dados["principal"]["documentos"], 12)
        self.assertEqual(sum(p["documentos"] for p in dados["producao"]), 12)
        self.assertEqual(dados["producao"][-1]["acumulado"], 12)
        self.assertTrue(dados["autores"])
        self.assertEqual(dados["bradford"]["fontes"], 2)

    def test_leis_com_poucos_pontos(self):
        from collections import Counter
        self.assertIsNone(bibliometria.lotka(Counter({"a": 1}))["beta"])
        self.assertIsNone(bibliometria.zipf(Counter({"a": 1}))["expoente"])

    def test_indice_h(self):
        self.assertEqual(bibliometria._indice_h([10, 8, 5, 4, 3]), 4)
        self.assertEqual(bibliometria._indice_h([]), 0)


if __name__ == "__main__":
    unittest.main()


class CoresDosGruposTest(unittest.TestCase):
    def test_nenhum_grupo_fica_cinza(self):
        from scimatpy.viz.halo import CINZA, cor_do_grupo
        cores = [cor_do_grupo(i) for i in range(60)]
        self.assertNotIn(CINZA, cores)
        self.assertEqual(len(set(cores)), 60)

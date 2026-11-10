import sqlite3
import tempfile
import unittest
from pathlib import Path

from scimatpy import build, rajadas, termos
from scimatpy.loaders.base import DocumentoFonte
from scimatpy.viz import descritiva


class KleinbergTest(unittest.TestCase):
    def test_detecta_pico(self):
        achados = rajadas.kleinberg([0, 0, 1, 6, 7, 6, 1, 0, 0, 0], [10] * 10)
        self.assertEqual(len(achados), 1)
        inicio, fim, forca = achados[0]
        self.assertGreaterEqual(inicio, 2)
        self.assertLessEqual(fim, 6)
        self.assertGreater(forca, 0)

    def test_serie_plana_nao_tem_rajada(self):
        self.assertEqual(rajadas.kleinberg([2] * 12, [10] * 12), [])

    def test_serie_vazia(self):
        self.assertEqual(rajadas.kleinberg([], []), [])
        self.assertEqual(rajadas.kleinberg([0, 0], [5, 5]), [])


class TermosTest(unittest.TestCase):
    def test_remove_vazias_e_genericas(self):
        titulos = ["O ensino de estatística nas escolas", "A study of statistics teaching",
                   "Estudio sobre la enseñanza de la estadística"]
        r = termos.termos_dos_titulos(titulos)["palavras"]
        for fora in ("de", "nas", "of", "the", "la", "estudo", "study", "estudio", "sobre"):
            self.assertNotIn(fora, r)
        self.assertIn("estatística", r)

    def test_mantem_genericas_se_pedido(self):
        r = termos.termos_dos_titulos(["Study of teaching"], tirar_academicas=False)["palavras"]
        self.assertIn("study", r)

    def test_une_plural_e_acento(self):
        r = termos.termos_dos_titulos(["Student attitudes", "Students attitude",
                                       "Educação estatística", "Educacao estatistica"])["palavras"]
        self.assertEqual(sum(1 for k in r if k.startswith("student")), 1)
        self.assertEqual(r[next(k for k in r if k.startswith("student"))], 2)
        self.assertEqual(sum(1 for k in r if k.lower().startswith("educa")), 1)

    def test_possessivo(self):
        r = termos.termos_dos_titulos(["Children's thinking", "Children thinking"])["palavras"]
        self.assertEqual(r["children"], 2)

    def test_expressao_nao_atravessa_palavra_vazia(self):
        r = termos.termos_dos_titulos(["Teaching of statistics", "Teaching of statistics"])
        self.assertNotIn("teaching statistics", r["expressoes"])

    def test_ocultar(self):
        r = termos.termos_dos_titulos(["Statistics students"], ocultar=["Statistics"])["palavras"]
        self.assertNotIn("statistics", r)

    def test_nuvem_sem_sobreposicao(self):
        itens = descritiva.layout_nuvem([(f"palavra{i}", 40 - i) for i in range(40)])
        self.assertGreater(len(itens), 30)
        def caixa(i):
            meia = 0.28 * i["tamanho"] * len(i["termo"]) + 3
            altura = i["tamanho"] * 1.08
            topo = i["y"] - 0.78 * altura
            return (i["x"] - meia, topo, i["x"] + meia, topo + altura)

        caixas = [caixa(i) for i in itens]
        for a in range(len(caixas)):
            for b in range(a + 1, len(caixas)):
                x = caixas[a]; y = caixas[b]
                self.assertTrue(x[2] <= y[0] or y[2] <= x[0] or x[3] <= y[1] or y[3] <= x[1])


class RajadasBancoTest(unittest.TestCase):
    def test_palavra_em_alta(self):
        docs = []
        for ano in range(2010, 2022):
            for i in range(6):
                quente = ano in (2016, 2017, 2018) and i < 5
                docs.append(DocumentoFonte(
                    titulo=f"Doc {ano}-{i}", ano=str(ano),
                    autores=[f"Autor {i} X."],
                    palavras_autor=["tema fixo"] + (["tema quente"] if quente else [])))
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "p.redes"
            build.constroi(docs, destino, None)
            conexao = sqlite3.connect(destino)
            dados = rajadas.calcula(conexao, "palavras", minimo_documentos=3)
            nuvem = termos.nuvem_dados(conexao, "titulos")
            conexao.close()
        achados = {r["termo"]: r for r in dados["rajadas"]}
        quente = next(r for t, r in achados.items() if "QUENTE" in t.upper())
        self.assertTrue(2015 <= quente["inicio"] <= 2018)
        self.assertGreaterEqual(quente["fim"], 2017)
        self.assertTrue(descritiva.rajadas_svg(dados, "t").startswith("<svg"))
        self.assertTrue(nuvem["termos"])

    def test_tipo_invalido(self):
        with self.assertRaises(ValueError):
            rajadas.calcula(sqlite3.connect(":memory:"), "xyz")


class RelatorioTemBibliometriaTest(unittest.TestCase):
    def test_pagina_gerada(self):
        from scimatpy import api
        base = Path("/home/claude/t/eecera59.redes")
        if not base.exists():
            self.skipTest("projeto de exemplo ausente")
        r = api.gera_relatorio({"projeto": str(base), "unidade": "Words", "minimo_frequencia": 2})
        pasta = Path(r["resumo"]["html"])
        self.assertTrue((pasta / "bibliometria.html").exists())
        self.assertIn("bibliometria.html", (pasta / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

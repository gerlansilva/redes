"""Testes das figuras: legenda sem vazamento e dados da rede interativa."""

from __future__ import annotations

import math
import unittest
from pathlib import Path

from redes.viz.cluster import rede_de_agrupamentos_svg
from redes.viz.halo import geometria_legenda
from redes.viz.strategic import dados_diagrama


class LegendaTest(unittest.TestCase):

    def test_legenda_cabe_na_altura(self):
        for quantidade in (1, 5, 14, 30, 83, 300):
            for altura in (780, 820):
                legenda = geometria_legenda(quantidade, altura,
                                            topo=118, base=48)
                visiveis = legenda["visiveis"]
                linhas = math.ceil(visiveis / legenda["colunas"]) \
                    if visiveis else 0
                fim = 118 + linhas * legenda["passo"]
                self.assertLessEqual(fim, altura - 48 + 1,
                                     f"{quantidade} em {altura}px: {legenda}")
                self.assertGreaterEqual(legenda["colunas"], 1)
                if quantidade > legenda["visiveis"]:
                    self.assertGreater(legenda["restantes"], 0)

    def test_poucos_grupos_ficam_em_uma_coluna(self):
        legenda = geometria_legenda(5, 780)
        self.assertEqual(1, legenda["colunas"])
        self.assertEqual(0, legenda["restantes"])

    def test_muitos_grupos_usam_colunas(self):
        legenda = geometria_legenda(83, 780)
        self.assertGreater(legenda["colunas"], 1)
        self.assertEqual(83, legenda["visiveis"])


if __name__ == "__main__":
    unittest.main()


class DiagramaTest(unittest.TestCase):

    def _grupos(self):
        return [
            {"selo": 1, "rotulo": "A", "centralidade_faixa": 0.9,
             "densidade_faixa": 0.8, "itens": 10, "documentos": 4,
             "centralidade": 9.0, "densidade": 8.0, "quadrante": "motor"},
            {"selo": 2, "rotulo": "B", "centralidade_faixa": 0.2,
             "densidade_faixa": 0.1, "itens": 3, "documentos": 2,
             "centralidade": 2.0, "densidade": 1.0, "quadrante": "emergente"},
        ]

    def test_pontos_e_quadrantes(self):
        dados = dados_diagrama(self._grupos(), "Words")
        self.assertEqual(2, len(dados["pontos"]))
        self.assertEqual(10, dados["max_nos"])
        self.assertEqual(["motor", "nicho", "emergente", "basico"],
                         [item["chave"] for item in dados["quadrantes"]])
        self.assertEqual(1, dados["pontos"][0]["selo"])
        self.assertEqual(0.9, dados["pontos"][0]["x"])

    def test_rotulos_por_unidade(self):
        palavras = dados_diagrama(self._grupos(), "Words")
        paises = dados_diagrama(self._grupos(), "Countries")
        self.assertEqual("Motores", palavras["quadrantes"][0]["curto"])
        self.assertEqual("Núcleos", paises["quadrantes"][0]["curto"])
        self.assertEqual("Núcleos de cooperação",
                         paises["quadrantes"][0]["rotulo"])


class RedeAgrupamentosTest(unittest.TestCase):

    def _resultado(self):
        import tempfile
        from redes.build import constroi
        from redes.kb import ProjetoRedes
        from redes.loaders.base import DocumentoFonte
        from redes.pipeline import Configuracao, executa_periodo

        documentos = [
            DocumentoFonte(titulo="A", autores=["Silva, A."], ano="2020",
                           citacoes=3, periodico="R",
                           palavras_autor=["tema um", "tema dois"]),
            DocumentoFonte(titulo="B", autores=["Costa, B."], ano="2020",
                           citacoes=1, periodico="R",
                           palavras_autor=["tema dois", "tema tres"]),
            DocumentoFonte(titulo="C", autores=["Lima, C."], ano="2020",
                           citacoes=2, periodico="R",
                           palavras_autor=["tema tres"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "dados.redes"
            constroi(documentos, destino, [("2020", 2020, 2020)])
            with ProjetoRedes(destino) as kb:
                periodo = kb.periodos()[0]
                config = Configuracao(unidade="Words", matriz="CoOccurrence")
                return executa_periodo(kb, periodo.id, periodo.nome, config)

    def test_svg_valido(self):
        resultado = self._resultado()
        svg = rede_de_agrupamentos_svg(resultado, "Rede de agrupamentos")
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("agrupamentos", svg)
        self.assertIn("associações", svg)

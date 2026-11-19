import re
import tempfile
import unittest
from pathlib import Path

from redes import api, build, pipeline, relatorio_unico
from redes.api import ProjetoRedes, _config
from redes.loaders.base import DocumentoFonte


def _docs():
    return [DocumentoFonte(
        titulo=f"Doc {i}", ano=str(2015 + i % 6), periodico="R",
        autores=[f"Autor {i % 5} A.", f"Autor {i % 3 + 5} B.", "Autor Z Z."],
        palavras_autor=[f"tema {i % 4}", f"tema {i % 3 + 4}", "geral"]) for i in range(40)]


class RelatorioUnicoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        projeto = cls.dir / "c.redes"
        build.constroi(_docs(), projeto,
                       periodos=[("A", 2015, 2017), ("B", 2018, 2020), ("C", 2021, 2021)])
        with ProjetoRedes(projeto) as kb:
            periodos = kb.periodos()
            config = _config({"unidade": "Words", "matriz": "CoOccurrence",
                              "minimo_frequencia": 2})
            resultados = [pipeline.executa_periodo(kb, p.id, p.nome, config)
                          for p in periodos]
            secoes = [{"rotulo": "Estrutura conceitual", "descricao": "Descrição.",
                       "pasta": "conceitual", "config": config, "resultados": resultados}]
            ignoradas = [{"rotulo": "Cocitação de referências",
                          "motivo": "a base não traz referências."}]
            cls.saida = relatorio_unico.gera_arquivo_unico(
                cls.dir / "unico.html", kb, periodos, secoes, ignoradas)
        cls.html = cls.saida.read_text(encoding="utf-8")

    def test_arquivo_unico_sem_referencias_externas(self):
        self.assertEqual(self.saida.name, "unico.html")
        self.assertEqual([p.name for p in self.dir.iterdir() if p.suffix == ".html"],
                         ["unico.html"])
        self.assertNotIn('src="images/', self.html)
        self.assertNotRegex(self.html, r'href="[^"#][^"]*\.html')
        self.assertNotRegex(self.html, r'<img |<script|<link ')
        self.assertNotRegex(self.html, r'src="[^d]')

    def test_estrutura_numeracao_e_legendas(self):
        for trecho in ("Relatório completo — Redes", "Figura 1 — ", "Tabela 1 — ",
                       "1 Visão geral descritiva", "2 Estrutura conceitual",
                       "2.1 Parâmetros", "2.2 Por período", "2.4 Evolução",
                       "Maior grupo", "Análises não geradas",
                       "Cocitação de referências", "<svg"):
            self.assertIn(trecho, self.html)
        figuras = [int(n) for n in re.findall(r"<figcaption>Figura (\d+) — ", self.html)]
        self.assertEqual(figuras, list(range(1, len(figuras) + 1)))
        tabelas = [int(n) for n in re.findall(r"<caption>Tabela (\d+) — ", self.html)]
        self.assertEqual(tabelas, list(range(1, len(tabelas) + 1)))

    def test_sumario_e_ids(self):
        ids = re.findall(r'\sid="([^"]+)"', self.html)
        self.assertEqual(len(ids), len(set(ids)), "ids duplicados")
        destinos = re.findall(r'href="#([^"]+)"', self.html)
        self.assertTrue(len(destinos) > 5)
        for destino in destinos:
            self.assertIn(destino, ids)

    def test_prefixa_ids_de_svg(self):
        svg = ('<svg><defs><linearGradient id="g"/></defs>'
               '<rect fill="url(#g)"/></svg>')
        saida = relatorio_unico._prefixa_ids(svg, "fig-3")
        self.assertIn('id="fig-3-g"', saida)
        self.assertIn("url(#fig-3-g)", saida)


if __name__ == "__main__":
    unittest.main()

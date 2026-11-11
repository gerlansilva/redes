import html
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scimatpy import api, build, metodo, pipeline, rajadas, relatorio_unico, report
from scimatpy.api import ProjetoScimat, _config
from scimatpy.loaders.base import DocumentoFonte


def _docs():
    return [DocumentoFonte(
        titulo=f"Doc {i}", ano=str(2015 + i % 6), periodico="R",
        autores=[f"Autor {i % 5} A.", f"Autor {i % 3 + 5} B.", "Autor Z Z."],
        palavras_autor=[f"tema {i % 4}", f"tema {i % 3 + 4}", "geral"],
        citacoes=i % 7) for i in range(40)]


def _texto(trecho: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", trecho)))


class MetodoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = cls.dir / "c.redes"
        build.constroi(_docs(), cls.projeto,
                       periodos=[("A", 2015, 2017), ("B", 2018, 2020), ("C", 2021, 2021)])
        cls.kb = ProjetoScimat(cls.projeto)
        cls.periodos = cls.kb.periodos()
        cls.config = _config({"unidade": "Words", "matriz": "CoOccurrence",
                              "minimo_frequencia": 2})
        cls.resultados = [pipeline.executa_periodo(cls.kb, p.id, p.nome, cls.config)
                          for p in cls.periodos]

    @classmethod
    def tearDownClass(cls):
        cls.kb.fecha()

    # ------------------------------------------------------------- indicadores

    def test_indicadores_batem_com_os_resultados(self):
        dados = metodo.indicadores(self.resultados, self.periodos, self.kb, self.config)
        self.assertEqual(len(dados), len(self.resultados) + 1)
        total, por_periodo = dados[0], dados[1:]
        for r, d in zip(self.resultados, por_periodo):
            self.assertEqual(d["escopo"], r.periodo)
            self.assertEqual(d["documentos"], r.dataset_original.quantidade_documentos())
            self.assertEqual(d["grupos"], r.dataset_original.quantidade_itens())
            self.assertEqual(d["itens_reduzidos"], r.dataset.quantidade_itens())
            self.assertEqual(d["rede_nos"], r.rede.quantidade_nos())
            self.assertEqual(d["rede_arestas"], r.rede.quantidade_arestas())
            self.assertEqual(d["agrupamentos"], len(r.grupos))
            self.assertEqual(d["maior_agrupamento"],
                             max((len(g.nos) for g in r.grupos), default=0))
            self.assertEqual(sum(d["quadrantes"].values()), len(r.grupos))
            # Cada nó da rede está num agrupamento ou fora de todos.
            self.assertEqual(d["itens_agrupados"] + d["itens_sem_agrupamento"], d["rede_nos"])
            # Redução só tira itens; grafias vêm antes dos grupos.
            self.assertLessEqual(d["itens_reduzidos"], d["grupos"])
            self.assertGreaterEqual(d["grafias"], d["grupos"])
            self.assertLessEqual(d["maior_agrupamento"], self.config.tamanho_maximo)
        self.assertEqual(total["agrupamentos"], sum(d["agrupamentos"] for d in por_periodo))
        self.assertEqual(total["maior_agrupamento"],
                         max(d["maior_agrupamento"] for d in por_periodo))
        ids = set()
        for r in self.resultados:
            ids |= set(r.dataset_original.documentos)
        self.assertEqual(total["documentos"], len(ids))
        self.assertGreaterEqual(total["grafias"], max(d["grafias"] for d in por_periodo))
        self.assertIsNone(total["rede_nos"])

    def test_um_periodo_tem_uma_coluna_so(self):
        dados = metodo.indicadores(self.resultados[:1], self.periodos[:1], self.kb)
        self.assertEqual(len(dados), 1)
        cabecalho, linhas = metodo.indicadores_linhas(dados, self.config)
        self.assertEqual(len(cabecalho), 2)
        self.assertTrue(all(len(linha) == 2 for linha in linhas))

    def test_tabela_mostra_os_numeros_calculados(self):
        texto = _texto(metodo.indicadores_html(self.resultados, self.periodos, self.kb,
                                               self.config))
        for rotulo in ("Grafias distintas na base", "Grupos de palavras (itens)",
                       "Itens após redução (freq. ≥ 2)", "Agrupamentos (freq. ≥ 2)",
                       "Maior agrupamento", "Rede", "Todos os períodos"):
            self.assertIn(rotulo, texto)
        for r in self.resultados:
            self.assertIn(f"{r.rede.quantidade_nos()} nós · "
                          f"{r.rede.quantidade_arestas()} arestas", texto)
            self.assertIn(r.periodo, texto)

    # ------------------------------------------------------ parâmetros e método

    def test_parametros_vem_da_configuracao_usada(self):
        config = _config({"unidade": "Words", "matriz": "CoOccurrence",
                          "similaridade": "JaccardIndex", "algoritmo": "AverageLink",
                          "minimo_frequencia": 2, "minimo_coocorrencia": 2,
                          "tamanho_minimo": 3, "tamanho_maximo": 9, "corte": 0.1,
                          "ignorar": ["geral", "<b>x</b>"]})
        resultados = [pipeline.executa_periodo(self.kb, p.id, p.nome, config)
                      for p in self.periodos]
        texto = _texto(metodo.parametros_html(config, self.periodos, resultados, 2,
                                              "JaccardIndex"))
        for esperado in ("Índice de Jaccard", "Ligação média", "mínimo 3, máximo 9 nós",
                         "Ponto de corte 0,1", "Frequência mínima 2", "geral",
                         "Medida temporal (evolução e sobreposição) Índice de Jaccard"):
            self.assertIn(esperado, texto)
        for r in resultados:
            self.assertIn(f"{r.periodo} ({r.dataset_original.quantidade_documentos()} "
                          "documentos)", texto)
        self.assertNotIn("<b>x</b>", metodo.parametros_html(config, self.periodos, resultados))
        algoritmo = _texto(metodo.algoritmo_html(config, "JaccardIndex"))
        self.assertIn("aglomeração hierárquica", algoritmo)
        self.assertIn("média dos pesos", algoritmo)
        self.assertIn("Índice de Jaccard (adotada)", algoritmo)

    def test_algoritmo_descreve_cada_variante(self):
        esperado = {"CentersSimples": "centro de um agrupamento",
                    "CompleteLink": "menor peso",
                    "SingleLink": "maior peso",
                    "SumLink": "soma dos pesos das ligações entre os dois grupos",
                    "Louvain": "modularidade"}
        for algoritmo, trecho in esperado.items():
            config = _config({"algoritmo": algoritmo})
            self.assertIn(trecho, _texto(metodo.algoritmo_html(config)))
        for matriz, trecho in (("BasicCoupling", "Cada documento do período é um nó"),
                               ("AggregatedCouplingBasedOnAuthor", "Cada autor é um nó"),
                               ("AggregatedCouplingBasedOnJournal", "Cada periódico é um nó")):
            config = _config({"matriz": matriz, "unidade": "References"})
            self.assertIn(trecho, _texto(metodo.algoritmo_html(config)))
        texto = _texto(metodo.algoritmo_html(self.config))
        for trecho in ("10 × a soma", "100 × a soma", "0,5", "índice h", "q2"):
            self.assertIn(trecho, texto)

    def test_metodo_da_bibliometria_le_as_constantes_do_codigo(self):
        texto = _texto(metodo.metodo_bibliometria_html())
        for trecho in ("Kleinberg", "Viterbi", "Lotka", "Bradford", "Zipf",
                       "palavras vazias", "índice h", "s = 2", "γ = 1",
                       "e não de citações recebidas"):
            self.assertIn(trecho, texto)
        with mock.patch.object(rajadas, "S_PADRAO", 3.0), \
                mock.patch.object(rajadas, "MINIMO_DOCUMENTOS", 7):
            texto = _texto(metodo.metodo_bibliometria_html())
        self.assertIn("s = 3", texto)
        self.assertIn("pelo menos 7 documentos", texto)

    # ----------------------------------------------------------------- relatórios

    def test_relatorio_unico_traz_o_bloco_em_cada_analise(self):
        outra = _config({"unidade": "Authors", "matriz": "CoOccurrence",
                         "minimo_frequencia": 1})
        res2 = [pipeline.executa_periodo(self.kb, p.id, p.nome, outra) for p in self.periodos]
        secoes = [
            {"rotulo": "Estrutura conceitual", "descricao": "D.", "pasta": "conceitual",
             "config": self.config, "resultados": self.resultados},
            {"rotulo": "Autores", "descricao": "D.", "pasta": "autores",
             "config": outra, "resultados": res2},
        ]
        saida = relatorio_unico.gera_arquivo_unico(self.dir / "u.html", self.kb,
                                                   self.periodos, secoes, [])
        pagina = saida.read_text(encoding="utf-8")
        for trecho in ("2.1 Parâmetros e método", "3.1 Parâmetros e método",
                       "2.1.1 Parâmetros adotados", "2.1.2 Indicadores",
                       "2.1.3 Como funciona", "Método e parâmetros"):
            self.assertIn(trecho, pagina)
        self.assertEqual(pagina.count("Grafias distintas na base"), 2)
        self.assertRegex(pagina, r"<caption>Tabela \d+ — Indicadores da análise")
        tabelas = [int(n) for n in re.findall(r"<caption>Tabela (\d+) — ", pagina)]
        self.assertEqual(tabelas, list(range(1, len(tabelas) + 1)))
        self.assertNotRegex(pagina, r"<script|<link |<img ")
        # Os números do relatório são os dos resultados.
        bloco = _texto(pagina[pagina.index('id="s2-parametros"'):pagina.index('id="s2-periodos"')])
        for r in self.resultados:
            self.assertIn(f"{r.rede.quantidade_nos()} nós", bloco)

    def test_relatorio_em_pastas_traz_o_bloco(self):
        destino = self.dir / "pasta"
        resumo = report.gera_html(destino, self.kb, self.periodos, self.config,
                                  devolve_resultados=True)
        indice = (destino / "index.html").read_text(encoding="utf-8")
        for trecho in ("Parâmetros e método", "Parâmetros adotados", "Indicadores",
                       "Como funciona", "Tabela 1 — ", "Tabela 2 — ", "Todos os períodos"):
            self.assertIn(trecho, indice)
        self.assertIn(f"{resumo['agrupamentos']}", _texto(indice))
        bib = (destino / "bibliometria.html").read_text(encoding="utf-8")
        self.assertIn("Método e parâmetros", bib)
        self.assertIn("Kleinberg", bib)
        secoes = [{"rotulo": "Estrutura conceitual", "descricao": "D.", "pasta": ".",
                   "config": self.config, "resultados": resumo["resultados"]}]
        report.gera_pagina_completa(destino, self.kb, secoes, [])
        completo = (destino / "index.html").read_text(encoding="utf-8")
        self.assertIn("2.2 Parâmetros e método", completo)
        self.assertIn("Itens após redução (freq. ≥ 2)", completo)

    def test_relatorio_completo_pela_api(self):
        # Arquivo único: só o .html (sem a pasta de páginas, que custava centenas de arquivos).
        r = api.gera_relatorio_completo({"projeto": str(self.projeto), "formato": "unico"})
        unico_pasta = api.RELATORIOS[r["token"]]
        self.assertEqual(["relatorio-completo.html"], sorted(p.name for p in unico_pasta.iterdir()))
        unico = (unico_pasta / "relatorio-completo.html").read_text(encoding="utf-8")
        r = api.gera_relatorio_completo({"projeto": str(self.projeto), "formato": "pastas"})
        pasta = api.RELATORIOS[r["token"]]
        completo = (pasta / "index.html").read_text(encoding="utf-8")
        self.assertFalse((pasta / "relatorio-completo.html").exists())
        for pagina in (completo, unico):
            self.assertIn("Parâmetros e método", pagina)
            self.assertIn("Maior agrupamento", pagina)
        self.assertIn("Método e parâmetros", (pasta / "bibliometria.html").read_text(encoding="utf-8"))


class MetodoSerjTest(unittest.TestCase):
    CAMINHO = Path("/home/claude/t/serj.redes")

    @unittest.skipUnless(CAMINHO.exists(), "base de referência ausente")
    def test_indicadores_em_base_real(self):
        with ProjetoScimat(self.CAMINHO) as kb:
            periodos = kb.periodos()
            config = _config({"unidade": "Words", "matriz": "CoOccurrence",
                              "minimo_frequencia": 3})
            resultados = [pipeline.executa_periodo(kb, p.id, p.nome, config)
                          for p in periodos]
            dados = metodo.indicadores(resultados, periodos, kb, config)
        for r, d in zip(resultados, dados[-len(resultados):]):
            self.assertEqual(d["agrupamentos"], len(r.grupos))
            self.assertEqual(d["itens_reduzidos"], r.rede.quantidade_nos())
            self.assertGreaterEqual(d["grafias"], d["grupos"])
            self.assertLessEqual(d["maior_agrupamento"], config.tamanho_maximo)


if __name__ == "__main__":
    unittest.main()

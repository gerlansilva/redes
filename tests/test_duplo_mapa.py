"""Duplo mapa de áreas das revistas: classificação, cálculo, SVG, API, relatórios e interface."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from unittest import mock

from redes import api, areas, build, cache_figuras, duplo_mapa, metodo, pipeline, relatorio_unico, report
from redes.api import ProjetoRedes, _config, cria_servidor
from redes.loaders.base import DocumentoFonte
from redes.viz import duplo_mapa as viz
from redes.viz.linha_do_tempo import largura as largura_texto

UI = Path(api.__file__).with_name("ui")
NS = "{http://www.w3.org/2000/svg}"

REVISTAS = ["Journal of Statistics Education", "Child Development", "Revista Obscura",
            "Psychiatry Research"]
CITADAS = ["Educational Studies in Mathematics", "Cognition", "Psychiatry Research",
           "Journal of Statistics Education", "Nature", "Periódico Misterioso"]


def _docs(com_refs=True, com_revista=True):
    docs = []
    for i in range(24):
        refs = ([f"Autor{j} A., {1990 + j}, {CITADAS[(i + j) % len(CITADAS)]}, {j + 1}, pp. 1-9"
                 for j in range(4)] if com_refs else [])
        docs.append(DocumentoFonte(
            titulo=f"Documento {i}", autores=[f"Autor, {i % 5}."], ano=str(2010 + i % 10),
            periodico=REVISTAS[i % len(REVISTAS)] if com_revista else "",
            palavras_autor=["estatistica", "ensino", f"tema{i % 3}"], referencias=refs))
    return docs


def _contagens():
    c = Counter()
    c[("Journal of Statistics Education", "Educational Studies in Mathematics")] = 30
    c[("Journal of Statistics Education", "The American Statistician")] = 20
    c[("Journal of Statistics Education", "Cognition")] = 5
    c[("Child Development", "Cognition")] = 25
    c[("Child Development", "Psychological Review")] = 10
    c[("Child Development", "Periódico Misterioso")] = 8
    c[("Revista Obscura", "Nature")] = 6
    c[("Revista Obscura", "Periódico Misterioso")] = 4
    return {"citacoes": c, "documentos": 40, "documentos_com_revista": 40,
            "referencias_sem_fonte": 12}


class ClassificacaoTest(unittest.TestCase):
    def setUp(self):
        areas.usa_arquivo(None)

    tearDown = setUp

    def test_termos_por_palavra_prefixo_expressao_e_nome_inteiro(self):
        casos = {
            "Educational Studies in Mathematics": ("Educação", "educ*"),
            "Journal of Statistical Software": ("Matemática e estatística", "statist*"),
            "Developmental Psychology": ("Psicologia", "psychol*"),
            "Journal of Affective Disorders": ("Saúde e psiquiatria", "affect*"),
            "Nature": ("Multidisciplinar", "=nature"),
            "Nature Reviews": ("Não classificado", ""),
            "Revista de Ensino de Ciências": ("Educação", "ensin*"),
            "Journal of Early Childhood Research": ("Educação", "early childhood"),
            "Developmental Review": ("Psicologia", "developmental*"),
            "Development Economics": ("Ciências sociais", "econom*"),   # "develop" sozinho não é psicologia
        }
        for nome, esperado in casos.items():
            self.assertEqual(esperado, areas.classifica(nome), nome)

    def test_sem_acento_sem_caixa_e_palavra_inteira(self):
        self.assertEqual("Educação", areas.classifica("EDUCAÇÃO MATEMÁTICA EM REVISTA")[0])
        self.assertEqual("Educação", areas.classifica("Educacion Matematica")[0])
        # "med" é palavra inteira: não casa dentro de "Comedy".
        self.assertEqual("Não classificado", areas.classifica("Comedy Quarterly")[0])
        self.assertEqual("Saúde e psiquiatria", areas.classifica("Med Care")[0])
        self.assertEqual(("Não classificado", ""), areas.classifica(""))
        self.assertEqual(("Não classificado", ""), areas.classifica(None))

    def test_ordem_das_areas_decide(self):
        self.assertEqual("Educação", areas.classifica("Statistics Education Research Journal")[0])

    def test_arquivo_de_configuracao_acrescenta_fixa_e_substitui(self):
        with tempfile.TemporaryDirectory() as d:
            arquivo = Path(d) / "areas.json"
            arquivo.write_text(json.dumps({
                "areas": [{"nome": "Física", "cor": "#0284C7", "termos": ["physic*", "optic*"]}],
                "revistas": {"Cognition": "Física"}}), encoding="utf-8")
            areas.usa_arquivo(str(arquivo))
            self.assertEqual(("Física", "physic*"), areas.classifica("Physical Review Letters"))
            self.assertEqual(("Física", "(fixada)"), areas.classifica("COGNITION"))
            self.assertEqual("Educação", areas.classifica("Teaching Statistics")[0])
            self.assertEqual("#0284C7", areas.cores()["Física"])
            arquivo.write_text(json.dumps({
                "areas": [{"nome": "Só uma", "termos": ["teach*"]}], "substitui": True}),
                encoding="utf-8")
            os.utime(arquivo, ns=(10 ** 18, 10 ** 18 + 5))
            areas.usa_arquivo(str(arquivo))
            self.assertEqual("Só uma", areas.classifica("Teaching Statistics")[0])
            self.assertEqual("Não classificado", areas.classifica("Child Development")[0])

    def test_arquivo_ruim_cai_para_as_areas_padrao(self):
        with tempfile.TemporaryDirectory() as d:
            arquivo = Path(d) / "ruim.json"
            arquivo.write_text("{ não é json", encoding="utf-8")
            areas.usa_arquivo(str(arquivo))
            self.assertEqual("Educação", areas.classifica("Teaching Statistics")[0])
            areas.usa_arquivo(str(Path(d) / "nao-existe.json"))
            self.assertEqual("Educação", areas.classifica("Teaching Statistics")[0])


class PuroTest(unittest.TestCase):
    def setUp(self):
        areas.usa_arquivo(None)

    def test_estrutura_e_contagens(self):
        d = duplo_mapa.calcula(_contagens(), 3, 6)
        self.assertTrue(d["aplicavel"])
        self.assertEqual({"Journal of Statistics Education", "Child Development", "Revista Obscura"},
                         {i["original"] for i in d["esquerda"]})
        self.assertEqual(108, sum(f["valor"] for f in d["fluxos"]))
        self.assertAlmostEqual(1.0, sum(f["pct"] for f in d["fluxos"]))
        a = {(f["origem"], f["destino"]): f["valor"] for f in d["fluxos"]}
        self.assertEqual(30, a[("Educação", "Educação")])
        self.assertEqual(20, a[("Educação", "Matemática e estatística")])
        self.assertEqual(5, a[("Educação", "Psicologia")])
        self.assertEqual(35, a[("Psicologia", "Psicologia")])
        self.assertEqual(8, a[("Psicologia", "Não classificado")])
        self.assertEqual(6, a[("Não classificado", "Multidisciplinar")])
        cob = d["cobertura"]
        self.assertEqual(108, cob["referencias"])
        self.assertEqual(12, cob["sem_fonte"])
        self.assertEqual(108, cob["desenhadas"])
        # Não classificadas entre as citadas: Periódico Misterioso (12) de 108.
        self.assertAlmostEqual(12 / 108, cob["pct_citadas_nao_classificadas"])
        self.assertAlmostEqual(10 / 108, cob["pct_citantes_nao_classificadas"])
        self.assertTrue(any("aproximada" in x for x in d["avisos"]))

    def test_tabela_audita_revista_area_e_termo(self):
        d = duplo_mapa.calcula(_contagens(), 2, 3)
        linha = {l["revista"]: l for l in d["tabela"]}
        self.assertEqual("Educação", linha["Journal of Statistics Education"]["area"])
        self.assertEqual("educ*", linha["Journal of Statistics Education"]["termo"])
        self.assertTrue(linha["Journal of Statistics Education"]["no_desenho"])
        # sem área e frequente, mas fora do desenho: aparece marcada
        fora = [l for l in d["tabela"] if not l["no_desenho"]]
        self.assertTrue(fora)
        self.assertTrue(all(l["area"] == "Não classificado" for l in fora))
        self.assertLessEqual(len(fora), duplo_mapa.EXTRAS_NAO_CLASSIFICADAS)

    def test_nomes_em_maiusculas_ficam_legiveis(self):
        c = Counter({("STATISTICS EDUCATION RESEARCH JOURNAL", "JOURNAL OF EDUCATIONAL PSYCHOLOGY"): 4})
        d = duplo_mapa.calcula({"citacoes": c, "documentos": 2, "documentos_com_revista": 2})
        self.assertEqual("Statistics education research journal", d["esquerda"][0]["nome"])
        self.assertEqual("STATISTICS EDUCATION RESEARCH JOURNAL", d["esquerda"][0]["original"])
        self.assertEqual("Educação", d["esquerda"][0]["area"])

    def test_nao_se_aplica_sem_dados(self):
        d = duplo_mapa.calcula({"citacoes": Counter(), "documentos": 10, "documentos_com_revista": 10})
        self.assertFalse(d["aplicavel"])
        self.assertIn("referências com periódico", d["aviso"])
        d = duplo_mapa.calcula({"citacoes": Counter(), "documentos": 10, "documentos_com_revista": 0})
        self.assertIn("periódico dos documentos", d["aviso"])
        self.assertEqual("", viz.svg(d))

    def test_limites_e_corte(self):
        d = duplo_mapa.calcula(_contagens(), 1, 2)
        self.assertEqual(1, len(d["esquerda"]))
        self.assertEqual(2, len(d["direita"]))
        self.assertEqual(3, d["total_esquerda"])

    def test_um_unico_periodico_avisa(self):
        c = Counter({("Teaching Statistics", "Cognition"): 5, ("Teaching Statistics", "Science"): 2})
        d = duplo_mapa.calcula({"citacoes": c, "documentos": 3, "documentos_com_revista": 3})
        self.assertTrue(any("única revista" in a for a in d["avisos"]))
        self.assertTrue(viz.svg(d).startswith("<svg"))

    def test_porcentagem(self):
        self.assertEqual("18%", duplo_mapa.porcentagem(0.184))
        self.assertEqual("5,6%", duplo_mapa.porcentagem(0.0558))
        self.assertEqual("0%", duplo_mapa.porcentagem(0))

    def test_svg_valido_deterministico_e_com_aviso_de_aproximacao(self):
        d = duplo_mapa.calcula(_contagens(), 3, 6)
        s = viz.svg(d, "Título")
        ET.fromstring(s)
        self.assertEqual(s, viz.svg(duplo_mapa.calcula(_contagens(), 3, 6), "Título"))
        for trecho in ("Classificação aproximada", "palavras do NOME", "revista → área",
                       "Revistas que publicam o corpus", "Revistas citadas", "Sem área:"):
            self.assertIn(trecho, s)
        self.assertNotIn("Título", viz.svg(d).split("</desc>")[1].split("<g")[0])

    def test_tudo_dentro_da_area_do_grafico(self):
        nomes = ["Revista Internacional de Educação Matemática e Estatística em Contextos Diversos %d" % i
                 for i in range(12)]
        c = Counter()
        for i, a in enumerate(nomes):
            for j, b in enumerate(nomes[::-1]):
                c[(a, b + " Journal of Psychology")] = (i * 7 + j * 3) % 11 + 1
        for dados in (duplo_mapa.calcula(_contagens(), 3, 6), duplo_mapa.calcula(
                {"citacoes": c, "documentos": 99, "documentos_com_revista": 99}, 12, 12)):
            raiz = ET.fromstring(viz.svg(dados, "Duplo mapa — título bem comprido para testar o corte"))
            _, _, w, h = [float(v) for v in raiz.get("viewBox").split()]
            for t in raiz.iter(NS + "text"):
                texto = "".join(x for x in t.itertext() if x is not None)
                titulo = t.find(NS + "title")
                if titulo is not None:
                    texto = texto.replace("".join(titulo.itertext()), "")
                tam = float(t.get("font-size"))
                lt = largura_texto(texto, tam, t.get("font-weight") == "700")
                x, y = float(t.get("x")), float(t.get("y"))
                anc = t.get("text-anchor", "start")
                x0 = x - (lt if anc == "end" else lt / 2 if anc == "middle" else 0)
                self.assertGreaterEqual(x0, -0.5, texto)
                self.assertLessEqual(x0 + lt, w + 0.5, texto)
                self.assertGreaterEqual(y - tam, -0.5, texto)
                self.assertLessEqual(y + tam * 0.3, h + 0.5, texto)
            for tag in ("rect", "path"):
                for e in raiz.iter(NS + tag):
                    if tag == "rect" and e.get("width") == str(int(w)):
                        continue
                    if tag == "rect":
                        self.assertLessEqual(float(e.get("x")) + float(e.get("width")), w)
                        self.assertLessEqual(float(e.get("y")) + float(e.get("height")), h + 0.5)

    def test_faixas_conservam_a_soma_e_a_mesma_escala(self):
        d = duplo_mapa.calcula(_contagens(), 3, 6)
        lay = viz.layout(d)
        for f in lay["faixas"]:
            self.assertAlmostEqual(max(1.0, f["valor"] * lay["escala"]), f["espessura"])
        self.assertEqual(108, sum(f["valor"] for f in lay["faixas"]))
        self.assertLessEqual(lay["escala"], viz.ESCALA_MAX)

    def test_ids_unicos_entre_figuras(self):
        a = viz.svg(duplo_mapa.calcula(_contagens(), 3, 6))
        b = viz.svg(duplo_mapa.calcula(_contagens(), 2, 4))
        ia = set(re.findall(r'id="([^"]+)"', a))
        ib = set(re.findall(r'id="([^"]+)"', b))
        self.assertFalse(ia & ib)

    def test_rotulos_com_caracteres_de_controle_e_xml(self):
        c = Counter({("Educ <b>&\x00 Journal", "Cognition ‮ Teaching"): 3})
        s = viz.svg(duplo_mapa.calcula({"citacoes": c, "documentos": 1, "documentos_com_revista": 1}))
        ET.fromstring(s)
        self.assertNotIn("\x00", s)


class BancoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = cls.dir / "d.redes"
        build.constroi(_docs(), cls.projeto, [("2010–2014", 2010, 2014), ("2015–2019", 2015, 2019)])

    def test_le_do_projeto(self):
        with ProjetoRedes(self.projeto) as kb:
            self.assertTrue(duplo_mapa.aplicavel(kb.conexao))
            d = duplo_mapa.calcula_do_banco(kb.conexao)
        self.assertTrue(d["aplicavel"])
        self.assertEqual(4, d["total_esquerda"])
        self.assertEqual(24, d["cobertura"]["documentos"])
        nomes = {l["revista"] for l in d["tabela"]}
        self.assertIn("Cognition", nomes)
        self.assertGreater(d["cobertura"]["pct_citadas_nao_classificadas"], 0)

    def test_base_sem_referencias_ou_sem_periodico_nao_se_aplica(self):
        for kwargs, trecho in (({"com_refs": False}, "referências com periódico"),
                               ({"com_revista": False}, "periódico dos documentos")):
            projeto = self.dir / f"x-{len(kwargs)}-{next(iter(kwargs))}.redes"
            build.constroi(_docs(**kwargs), projeto, [("2010–2019", 2010, 2019)])
            with ProjetoRedes(projeto) as kb:
                self.assertFalse(duplo_mapa.aplicavel(kb.conexao))
                d = duplo_mapa.calcula_do_banco(kb.conexao)
            self.assertFalse(d["aplicavel"])
            self.assertIn(trecho, d["aviso"])


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = cls.dir / "d.redes"
        cls.sem_refs = cls.dir / "s.redes"
        build.constroi(_docs(), cls.projeto, [("2010–2014", 2010, 2014), ("2015–2019", 2015, 2019)])
        build.constroi(_docs(com_refs=False), cls.sem_refs, [("2010–2019", 2010, 2019)])
        cls.servidor = cria_servidor(0, cls.dir)
        cls.base = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def pede(self, rota, dados=None):
        corpo = json.dumps(dados).encode() if dados is not None else None
        req = urllib.request.Request(
            self.base + rota, data=corpo,
            headers={"Content-Type": "application/json"} if corpo else {})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def token(self, projeto=None, **extra):
        st, corpo, _ = self.pede("/api/analisa", {
            "projeto": str(projeto or self.projeto), "unidade": "Words", "minimo_frequencia": 1,
            "periodo": 1, **extra})
        self.assertEqual(200, st, corpo)
        return json.loads(corpo)["token"]

    def test_post_com_projeto_devolve_estrutura(self):
        st, corpo, _ = self.pede("/api/duplo-mapa", {"projeto": str(self.projeto)})
        self.assertEqual(200, st, corpo)
        d = json.loads(corpo)
        for chave in ("svg", "nota", "avisos", "areas", "fluxos", "tabela", "cobertura",
                      "n_esquerda", "n_direita", "total_esquerda", "total_direita",
                      "max_esq", "max_dir"):
            self.assertIn(chave, d)
        self.assertTrue(d["svg"].lstrip().startswith("<svg"))
        self.assertEqual(duplo_mapa.MAX_ESQ, d["max_esq"])
        self.assertEqual(duplo_mapa.MAX_DIR, d["max_dir"])
        self.assertIn("aproximada", d["nota"])
        self.assertTrue(d["tabela"])
        self.assertNotIn("Duplo mapa —", d["svg"].split("</desc>")[1].split("<g")[0])

    def test_token_limites_e_download(self):
        token = self.token()
        for q, esperado in ((dict(max_esq="1"), ("max_esq", 3)), (dict(max_esq="99"), ("max_esq", 30)),
                            (dict(max_dir="1"), ("max_dir", 5)), (dict(max_dir="99"), ("max_dir", 40))):
            st, corpo, _ = self.pede("/api/duplo-mapa?" + urllib.parse.urlencode({"token": token, **q}))
            self.assertEqual(200, st, corpo)
            self.assertEqual(esperado[1], json.loads(corpo)[esperado[0]])
        st, svg, cab = self.pede("/api/duplo-mapa?" + urllib.parse.urlencode(
            {"token": token, "baixar": "1", "max_esq": "3", "max_dir": "5"}))
        self.assertEqual(200, st)
        self.assertIn("image/svg+xml", cab["Content-Type"])
        self.assertIn("duplo-mapa.svg", cab["Content-Disposition"])
        self.assertIn(duplo_mapa.TITULO, svg.decode())
        ET.fromstring(svg)

    def test_funciona_com_qualquer_tipo_de_analise(self):
        token = self.token(matriz="BasicCoupling", unidade="References", mapeadores=["acoplamento"])
        st, corpo, _ = self.pede("/api/duplo-mapa?token=" + token)
        self.assertEqual(200, st, corpo)

    def test_erros_claros(self):
        st, corpo, _ = self.pede("/api/duplo-mapa", {"projeto": str(self.sem_refs)})
        self.assertEqual(400, st)
        self.assertIn("referências com periódico", json.loads(corpo)["erro"])
        token = self.token(self.sem_refs)
        st, corpo, _ = self.pede("/api/duplo-mapa?token=" + token)
        self.assertEqual(400, st)
        self.assertIn("periódico", json.loads(corpo)["erro"])
        st, corpo, _ = self.pede("/api/duplo-mapa", {"projeto": str(self.projeto), "max_esq": "x"})
        self.assertEqual(400, st)
        self.assertIn("max_esq", json.loads(corpo)["erro"])
        st, corpo, _ = self.pede("/api/duplo-mapa", {"projeto": str(self.projeto), "max_dir": "x"})
        self.assertEqual(400, st)
        self.assertIn("max_dir", json.loads(corpo)["erro"])
        st, _, _ = self.pede("/api/duplo-mapa", {})
        self.assertEqual(400, st)
        st, _, _ = self.pede("/api/duplo-mapa?token=inexistente")
        self.assertIn(st, (400, 404, 410))
        st, _, _ = self.pede("/api/duplo-mapa", {"projeto": "/nao/existe.redes"})
        self.assertEqual(400, st)


class RelatoriosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = cls.dir / "r.redes"
        cls.sem_refs = cls.dir / "s.redes"
        build.constroi(_docs(), cls.projeto, [("2010–2014", 2010, 2014), ("2015–2019", 2015, 2019)])
        build.constroi(_docs(com_refs=False), cls.sem_refs, [("2010–2019", 2010, 2019)])

    def unico(self, projeto=None, n_secoes=2, **cfg):
        with ProjetoRedes(projeto or self.projeto) as kb:
            periodos = kb.periodos()
            secoes = []
            for k in range(n_secoes):
                config = _config({"minimo_frequencia": 1, "tamanho_maximo": 6, "unidade": "Words", **cfg})
                resultados = [pipeline.executa_periodo(kb, p.id, p.nome, config) for p in periodos]
                secoes.append({"rotulo": f"Análise {k}", "descricao": "Descrição.", "pasta": f"a{k}",
                               "config": config, "resultados": resultados})
            nome = f"u-{projeto.name if projeto else 'r'}-{len(cfg)}.html"
            saida = relatorio_unico.gera_arquivo_unico(self.dir / nome, kb, periodos, secoes, [])
        return saida.read_text(encoding="utf-8")

    def test_unico_tem_figura_numerada_nota_e_tabelas_uma_vez(self):
        html = self.unico()
        self.assertEqual(1, html.count(report.TITULO_SECAO_DUPLO + "</h3>"))   # só na primeira análise
        self.assertRegex(html, r"Figura \d+ — Duplo mapa — áreas das revistas")
        for trecho in ("Como ler:", "palavras do NOME", "Classificação aproximada",
                       "Revista → área, para conferência", "Fluxos entre áreas",
                       "Termo que decidiu", "Sem área:"):
            self.assertIn(trecho, html)
        self.assertRegex(html, r"Tabela \d+ — Revista → área")
        self.assertNotIn("\x00", html)
        self.assertLess(html.index("Mapa de densidade (corpus completo)</h3>"),
                        html.index(report.TITULO_SECAO_DUPLO + "</h3>"))
        self.assertLess(html.index(report.TITULO_SECAO_DUPLO + "</h3>"),
                        html.index("Dendrograma (agrupamento hierárquico)</h3>"))
        self.assertIn("Duplo mapa de áreas das revistas.", html)

    def test_unico_numeracao_de_tabelas_e_figuras_sem_repeticao(self):
        html = self.unico()
        tabelas = re.findall(r"<caption>Tabela (\d+) — ", html)
        figuras = re.findall(r"<figcaption>Figura (\d+) — ", html)
        self.assertEqual(sorted(set(tabelas), key=int), sorted(tabelas, key=int))
        self.assertEqual(list(range(1, len(tabelas) + 1)), sorted(int(t) for t in tabelas))
        self.assertEqual(list(range(1, len(figuras) + 1)), [int(f) for f in figuras])

    def test_unico_omite_quando_nao_se_aplica_ou_falha(self):
        html = self.unico(self.sem_refs)
        self.assertNotIn(report.TITULO_SECAO_DUPLO, html)
        self.assertNotIn("Duplo mapa de áreas das revistas.", html)
        self.assertIn("Dendrograma (agrupamento hierárquico)", html)
        cache_figuras.limpa()          # o cache de figuras é do processo; sem isso o mock não vale
        with mock.patch("redes.duplo_mapa.calcula_do_banco", side_effect=RuntimeError("x")):
            html = self.unico()
        cache_figuras.limpa()          # o resultado vazio da falha não pode ficar para os outros testes
        self.assertNotIn(report.TITULO_SECAO_DUPLO + "</h3>", html)
        self.assertIn("Mapa de densidade (corpus completo)", html)

    def test_pastas(self):
        with ProjetoRedes(self.projeto) as kb:
            periodos = kb.periodos()
            config = _config({"unidade": "Words", "minimo_frequencia": 1, "tamanho_maximo": 6})
            destino = self.dir / "pastas"
            report.gera_html(destino, kb, periodos, config)
            indice = (destino / "index.html").read_text(encoding="utf-8")
            self.assertIn(f'id="duplo-mapa">{report.TITULO_SECAO_DUPLO}', indice)
            self.assertIn('src="images/duploMapa.svg"', indice)
            for trecho in ("Como ler:", "Classificação aproximada", "Termo que decidiu",
                           "Revista → área, para conferência"):
                self.assertIn(trecho, indice)
            ET.parse(destino / "images" / "duploMapa.svg")
            self.assertIn("Duplo mapa de áreas das revistas.", indice)
        with ProjetoRedes(self.sem_refs) as kb:
            destino2 = self.dir / "pastas2"
            report.gera_html(destino2, kb, kb.periodos(), config)
            self.assertNotIn(report.TITULO_SECAO_DUPLO, (destino2 / "index.html").read_text(encoding="utf-8"))
            self.assertFalse((destino2 / "images" / "duploMapa.svg").exists())

    def test_metodo_traz_parametros_algoritmo_e_numeracao_sequencial(self):
        config = _config({"unidade": "Words"})
        texto = metodo.algoritmo_html(config, None, 2)
        self.assertIn("Duplo mapa de áreas das revistas.", texto)
        for trecho in (f"{duplo_mapa.MAX_ESQ} revistas que mais citam", "aproximada",
                       "palavras do <em>nome</em>", "Não classificado", "z-score"):
            self.assertIn(trecho, texto)
        numeros = [int(n) for n in re.findall(r"<strong>(\d+)\. ", texto)]
        self.assertEqual(list(range(1, len(numeros) + 1)), numeros)
        with mock.patch.object(duplo_mapa, "MAX_ESQ", 7), mock.patch.object(duplo_mapa, "MAX_DIR", 21):
            alterado = metodo.algoritmo_html(config, None, 2)
        self.assertIn("7 revistas que mais citam", alterado)
        self.assertIn("as 21 mais citadas", alterado)
        for cfg in (config, _config({"unidade": "References", "matriz": "BasicCoupling",
                                     "mapeadores": ["acoplamento"]})):
            sem = metodo.algoritmo_html(cfg, None, 2, com_duplo=False)
            self.assertNotIn("Duplo mapa de áreas das revistas.", sem)
            nums = [int(n) for n in re.findall(r"<strong>(\d+)\. ", sem)]
            self.assertEqual(list(range(1, len(nums) + 1)), nums)

    def test_metodo_html_so_inclui_o_item_quando_a_base_permite(self):
        config = _config({"unidade": "Words", "minimo_frequencia": 1})
        with ProjetoRedes(self.projeto) as kb:
            com = metodo.metodo_html(config, kb.periodos(), (), None, None, kb)
        with ProjetoRedes(self.sem_refs) as kb:
            sem = metodo.metodo_html(config, kb.periodos(), (), None, None, kb)
        self.assertIn("Duplo mapa de áreas das revistas.", com)
        self.assertNotIn("Duplo mapa de áreas das revistas.", sem)


class InterfaceTest(unittest.TestCase):
    """Checagens estáticas da aba, do reset e do menu (o fluxo vivo está nos prints Playwright)."""

    @classmethod
    def setUpClass(cls):
        cls.js = (UI / "app.js").read_text(encoding="utf-8")
        cls.html = (UI / "index.html").read_text(encoding="utf-8")

    def test_aba_depois_da_densidade_e_sempre_visivel(self):
        ordem = re.findall(r'data-aba="([a-z]+)"', self.html)
        self.assertEqual(ordem.index("densidade") + 1, ordem.index("duplomapa"))
        self.assertIn('id="blocoDuploMapa"', self.html)
        self.assertIn('duplomapa: "blocoDuploMapa"', self.js)
        grupos = re.search(r"const GRUPOS_ABAS = \[.*?\];", self.js, re.S).group(0)
        self.assertIn('"duplomapa"', grupos)
        self.assertNotIn("ABAS_SIMPLES", self.js)
        config = re.search(r"const CONFIG_ABAS = \{.*?\n\};", self.js, re.S).group(0)
        veiculos = re.search(r"veiculos: \{.*?\},", config, re.S).group(0)
        self.assertIn('"duplomapa"', veiculos)
        self.assertEqual(config.count('"duplomapa"'), 1)   # só na análise de periódicos
        self.assertIn('chave === "duplomapa"', self.js)

    def test_reset_ao_trocar_de_projeto_e_de_analise(self):
        projeto = re.search(r"function aplicarProjeto\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("limparDuploMapa(true)", projeto)
        resultado = re.search(r"function renderizarResultado\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("limparDuploMapa(false)", resultado)
        self.assertIn('abaAtual() === "duplomapa"', resultado)
        limpa = re.search(r"function limparDuploMapa\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("dm.seq += 1", limpa)
        self.assertIn("mensagemDuploMapa", limpa)
        self.assertIn('dm.motivo = ""', limpa)

    def test_mensagem_clara_quando_nao_se_aplica_e_menu_exportar(self):
        carrega = re.search(r"async function carregarDuploMapa\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("dm.motivo = erro.message", carrega)
        self.assertIn("mensagemDuploMapa(erro.message)", carrega)
        self.assertIn("!duploMapaAplicavel()", self.js)
        self.assertIn('data-exp="duplomapa-svg" data-precisa="resultado"', self.html)
        self.assertIn('tipo === "duplomapa-svg"', self.js)
        self.assertIn("/api/duplo-mapa?", self.js)
        self.assertIn('link.download = "duplo-mapa.svg"', self.js)

    def test_tabela_auditavel_e_aviso_de_aproximacao_na_tela(self):
        for id_ in ("dmTabelaCaixa", "dmCorpo", "dmAviso", "dmFigura", "vazioDuploMapa"):
            self.assertIn(f'id="{id_}"', self.html)
        self.assertIn("Revista → área", self.html)
        self.assertIn("Termo que decidiu", self.html)
        self.assertIn("palavras do NOME", self.html)
        self.assertIn("Classificação aproximada", self.js)
        self.assertIn("pct_revistas_nao_classificadas", self.js)

    def test_sem_tema_escuro_no_trecho_novo(self):
        css = (UI / "style.css").read_text(encoding="utf-8")
        trecho = css[css.index(".dm-figura"):].split("/* ---")[0]
        self.assertNotIn("prefers-color-scheme", trecho)


if __name__ == "__main__":
    unittest.main()

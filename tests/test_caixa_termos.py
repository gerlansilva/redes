"""Caixa dos termos do SciMAT: STATISTICAL-REASONING sai como "Statistical reasoning".

Só a exibição muda (`scimatpy.texto.termo_legivel`): o dado guardado, os ids e as
chaves de agrupamento ficam como o importador os gravou.
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from scimatpy import api, exports, report, texto
from scimatpy.build import constroi
from scimatpy.kb import ProjetoScimat
from scimatpy.loaders.base import DocumentoFonte
from scimatpy.pipeline import Configuracao, executa_periodo
from scimatpy.viz.halo import halo_svg, layout_halo
from scimatpy.viz.strategic import diagrama_svg

BRUTO = re.compile(r"\b[A-Z]{3,}-[A-Z]{3,}\b")

TEMAS = [
    ["statistical reasoning", "teacher education", "e-learning", "spss"],
    ["probability", "simulation", "self-efficacy", "pisa"],
    ["statistics anxiety", "attitudes", "south africa", "big data"],
]


def _docs(n=18):
    docs = []
    for i in range(n):
        docs.append(DocumentoFonte(
            titulo=f"Estudo {i}", ano=str(2015 + i % 4), autores=[f"Autor{i % 3}, A."],
            palavras_autor=list(TEMAS[i % 3])))
    return docs


class TermoLegivelTest(unittest.TestCase):

    def test_regra_do_pedido(self):
        casos = {
            "STATISTICAL-REASONING": "Statistical reasoning",
            "STATISTICS-EDUCATION-RESEARCH": "Statistics education research",
            "SOUTH AFRICA": "South africa",
            "E-LEARNING": "E-learning",
            "SELF-EFFICACY": "Self efficacy",
            "COVID-19": "COVID-19",
            "K-12": "K-12",
            "ENSINO-DE-ESTATÍSTICA": "Ensino de estatística",
            "CHILDREN'S-LEARNING": "Children's learning",
        }
        for entrada, esperado in casos.items():
            self.assertEqual(esperado, texto.termo_legivel(entrada), entrada)

    def test_siglas_ficam_em_maiusculas(self):
        for sigla in ("SPSS", "PISA", "ICME", "TIMSS"):
            self.assertEqual(sigla, texto.termo_legivel(sigla))
        self.assertEqual("Teaching with SPSS", texto.termo_legivel("TEACHING-WITH-SPSS"))
        self.assertEqual("PISA results", texto.termo_legivel("PISA-RESULTS"))
        # fora da lista, o termo curto segue a regra geral
        self.assertEqual("Abc", texto.termo_legivel("ABC"))

    def test_siglas_configuraveis(self):
        self.addCleanup(texto.esquece_siglas)
        self.assertEqual("Xyz", texto.termo_legivel("XYZ"))
        texto.registra_siglas("xyz")
        self.assertEqual("XYZ", texto.termo_legivel("XYZ"))
        self.assertIn("XYZ", texto.siglas())
        texto.esquece_siglas()
        self.assertNotIn("XYZ", texto.siglas())
        os.environ["REDES_SIGLAS"] = "QWE, RTY"
        try:
            self.assertEqual("QWE", texto.termo_legivel("QWE"))
            self.assertEqual("QWE results", texto.termo_legivel("QWE-RESULTS"))
        finally:
            del os.environ["REDES_SIGLAS"]

    def test_caixa_mista_e_minuscula_ficam_intactas(self):
        for termo in ("Statistical reasoning", "South Africa", "statistical-reasoning",
                      "Lee H.S.", "E-Learning", "123", "", "iPad"):
            self.assertEqual(termo, texto.termo_legivel(termo), termo)
        self.assertEqual("", texto.termo_legivel(None))

    def test_so_palavras_chave_mudam(self):
        self.assertEqual("Statistical reasoning", texto.exibe_termo("Words", "STATISTICAL-REASONING"))
        for unidade in ("Authors", "Countries", "Institutions", "References",
                        "ReferenceSources", "AuthorsReference"):
            self.assertEqual("STATISTICAL-REASONING",
                             texto.exibe_termo(unidade, "STATISTICAL-REASONING"), unidade)

    def test_busca_acha_pelo_exibido_e_pelo_original(self):
        chave = texto.texto_de_busca
        self.assertEqual(chave("Statistical reasoning"), chave("STATISTICAL-REASONING"))
        self.assertEqual(chave("E-learning"), chave("E-LEARNING"))

    def test_rotulo_automatico(self):
        self.assertEqual("Statistical reasoning · PISA results · Teacher education",
                         texto.rotulo_legivel("statistical reasoning · pisa results · teacher education"))
        # palavra comum que também é sigla não vira sigla num texto em minúsculas
        self.assertEqual("Stem cells", texto.termo_de_rotulo("stem cells"))
        self.assertEqual("STEM education", texto.termo_legivel("STEM-EDUCATION"))

    def test_em_frase(self):
        self.assertEqual("statistical reasoning", texto.em_frase("Statistical reasoning"))
        self.assertEqual("SPSS", texto.em_frase("SPSS"))
        self.assertEqual("PISA results", texto.em_frase("PISA results"))


class ExibicaoNoProjetoTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pasta = Path(tempfile.mkdtemp())
        cls.caminho = cls.pasta / "dados.redes"
        constroi(_docs(), cls.caminho, [("2015–2018", 2015, 2018)])
        with ProjetoScimat(cls.caminho) as kb:
            periodo = kb.periodos()[0]
            cls.r = executa_periodo(kb, periodo.id, periodo.nome, Configuracao())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.pasta, ignore_errors=True)

    def test_dado_guardado_nao_muda(self):
        con = sqlite3.connect(self.caminho)
        nomes = {linha[0] for linha in con.execute("SELECT wordName FROM Word")}
        con.close()
        self.assertIn("STATISTICAL-REASONING", nomes)
        self.assertIn("E-LEARNING", nomes)
        self.assertIn("SOUTH-AFRICA", nomes)
        self.assertIn("STATISTICAL-REASONING", set(self.r.dataset.itens.values()))
        self.assertTrue(all(g.rotulo == g.rotulo.upper() for g in self.r.grupos))

    def test_rotulo_e_exibicao(self):
        exibidos = {self.r.rotulo(no) for no in self.r.rede.nos}
        self.assertIn("Statistical reasoning", exibidos)
        self.assertIn("E-learning", exibidos)
        self.assertIn("SPSS", exibidos)
        self.assertIn("PISA", exibidos)
        self.assertIn("South africa", exibidos)
        self.assertFalse(any(BRUTO.search(e) for e in exibidos), exibidos)
        for g in self.r.grupos:
            self.assertEqual(texto.termo_legivel(g.rotulo), g.exibicao)
            self.assertNotEqual(g.rotulo, g.exibicao) if "-" in g.rotulo else None

    def test_figuras_svg(self):
        for svg in (halo_svg(self.r, "Rede"), diagrama_svg(self.r, "Estratégico")):
            self.assertFalse(BRUTO.search(re.sub(r"<[^>]+>", " ", svg)))
        legivel = max((g.exibicao for g in self.r.grupos), key=len)[:12]
        self.assertIn(legivel, halo_svg(self.r, "Rede") + diagrama_svg(self.r, "x"))
        dados = layout_halo(self.r)
        for no in dados["nos"]:
            self.assertFalse(BRUTO.search(no["rotulo"]), no["rotulo"])
        for g in dados["grupos"]:
            self.assertFalse(BRUTO.search(g["rotulo"]), g["rotulo"])
            self.assertEqual(texto.termo_legivel(g["rotulo_original"]), g["rotulo"])

    def test_exportacoes_tem_forma_legivel(self):
        rotulos = {no: self.r.item(no) for no in self.r.rede.nos}
        net = exports.pajek(self.r.rede, rotulos)
        self.assertIn("Statistical reasoning", net)
        self.assertFalse(BRUTO.search(net))
        tsv = exports.indices_tsv(self.r)
        self.assertFalse(BRUTO.search(tsv))
        self.assertEqual(len(tsv.splitlines()) - 1,
                         len(self.r.grupos) * len(self.r.configuracao.mapeadores))

    def test_api_analisa_exportar_e_base(self):
        resposta = api.analisa({"projeto": str(self.caminho), "unidade": "Words"})
        texto_json = repr([g["rotulo"] for g in resposta["grupos"]]
                          + [n for g in resposta["grupos"] for n in g["nos"]])
        self.assertFalse(BRUTO.search(texto_json), texto_json)
        self.assertIn("Statistical reasoning", texto_json)
        detalhe = api.detalhe_grupo(resposta["token"], 1)
        self.assertFalse(BRUTO.search(repr([i["rotulo"] for i in detalhe["itens"]])))
        for tipo in ("rede-pajek", "rede-graphml", "indices-tsv"):
            conteudo, _, _ = api.exportar(resposta["token"], tipo)
            self.assertFalse(BRUTO.search(conteudo.decode("utf-8")), tipo)
        # o XML de grupos é o formato de troca da base: mantém o dado guardado
        xml, _, _ = api.exportar(resposta["token"], "grupos-xml")
        self.assertIn("STATISTICAL-REASONING", xml.decode("utf-8"))
        base = api.base_conhecimento(str(self.caminho))
        grupo = next(g for g in base["grupos"]["palavra"] if g["nome"] == "STATISTICAL-REASONING")
        self.assertEqual("Statistical reasoning", grupo["exibicao"])
        autor = base["grupos"]["autor"][0]
        self.assertEqual(autor["nome"], autor["exibicao"])

    def test_siglas_vao_para_a_interface(self):
        self.assertIn("SPSS", texto.siglas())

    def test_nuvem_e_bibliometria(self):
        from scimatpy import bibliometria, rajadas, termos
        con = sqlite3.connect(self.caminho)
        try:
            nuvem = termos.nuvem_dados(con, "palavras")
            nomes = {t["termo"] for t in nuvem["termos"]}
            self.assertIn("Statistical reasoning", nomes)
            self.assertFalse(any(BRUTO.search(n) for n in nomes))
            bib = bibliometria.calcula(con)
            self.assertIn("Statistical reasoning", {p["nome"] for p in bib["palavras"]})
            dados = rajadas.calcula(con, "palavras", minimo_documentos=2)
            for linha in dados["rajadas"]:
                self.assertEqual(texto.termo_legivel(linha["termo"]), linha["termo_exibicao"])
        finally:
            con.close()

    def test_relatorio_em_pastas_e_unico(self):
        for formato in ("pastas", "unico"):
            resposta = api.gera_relatorio_completo(
                {"projeto": str(self.caminho), "formato": formato})
            raiz = next(d for t, d in api.RELATORIOS.items() if t in resposta["url"])
            for arquivo in Path(raiz).rglob("*"):
                if arquivo.suffix not in (".html", ".svg", ".net"):
                    continue
                texto_visivel = re.sub(r"<[^>]+>", " ", arquivo.read_text(errors="replace"))
                # (a nota de método da nuvem cita a forma guardada como exemplo)
                texto_visivel = texto_visivel.replace("(STATISTICAL-REASONING)", "")
                achados = set(BRUTO.findall(texto_visivel))
                self.assertFalse(achados, (formato, arquivo.name, sorted(achados)[:5]))


def _playwright_disponivel() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except Exception:
        return False
    return bool(os.environ.get("PLAYWRIGHT_BROWSERS_PATH"))


@unittest.skipUnless(_playwright_disponivel(),
                     "defina PLAYWRIGHT_BROWSERS_PATH para o teste no navegador")
class NavegadorTest(unittest.TestCase):
    """A interface usa a mesma regra do Python, e a busca da Base acha as duas formas."""

    CASOS = ["STATISTICAL-REASONING", "SOUTH AFRICA", "E-LEARNING", "SPSS", "PISA",
             "COVID-19", "SELF-EFFICACY", "Lee H.S.", "South Africa", "ABC", "ENSINO-DE-ESTATÍSTICA",
             "TEACHING-WITH-SPSS", "3D-PRINTING", "K-12", "statistical-reasoning"]

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pasta = Path(tempfile.mkdtemp())
        cls.projeto = cls.pasta / "dados.redes"
        constroi(_docs(), cls.projeto, [("2015–2018", 2015, 2018)])
        cls.servidor = api.cria_servidor(0, cls.pasta)
        cls.url = f"http://127.0.0.1:{cls.servidor.server_address[1]}/?pular=1"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        cls.nav = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.nav.close()
        cls.pw.stop()
        cls.servidor.shutdown()
        cls.servidor.server_close()
        shutil.rmtree(cls.pasta, ignore_errors=True)

    def _abre(self, largura=1280, altura=720):
        pg = self.nav.new_page(viewport={"width": largura, "height": altura})
        self.addCleanup(pg.close)
        pg.goto(self.url)
        pg.wait_for_timeout(500)
        pg.click('summary:has-text("Abrir projeto existente")')
        pg.fill("#caminhoProjeto", str(self.projeto))
        pg.click("#btnAbrirCaminho")
        pg.wait_for_timeout(2500)
        return pg

    def test_js_igual_ao_python(self):
        pg = self._abre()
        js = pg.evaluate("(casos)=>casos.map(c=>[termoLegivel(c), nomeLegivel(c,'Words')])", self.CASOS)
        for caso, (legivel, nome) in zip(self.CASOS, js):
            self.assertEqual(texto.termo_legivel(caso), legivel, caso)
            if caso != "statistical-reasoning":
                self.assertEqual(texto.termo_legivel(caso), nome, caso)

    def test_busca_da_base_pelo_exibido_e_pelo_original(self):
        pg = self._abre()
        pg.evaluate("()=>abrirBase()")
        pg.wait_for_selector("#baseGrupos input.nome")
        pg.select_option("#baseTipo", "palavra")
        for busca in ("statistical reasoning", "STATISTICAL-REASONING", "statistical-reasoning"):
            pg.fill("#buscaBase", busca)
            pg.wait_for_timeout(200)
            valores = pg.eval_on_selector_all("#baseGrupos input.nome", "e=>e.map(x=>x.value)")
            self.assertEqual(["Statistical reasoning"], valores, busca)
        titulo = pg.eval_on_selector("#baseGrupos input.nome", "e=>e.title")
        self.assertIn("STATISTICAL-REASONING", titulo)

    def test_figuras_sem_caixa_alta_e_sem_corte(self):
        for largura, altura in ((1440, 900), (1280, 720)):
            pg = self._abre(largura, altura)
            pg.evaluate("()=>{const c=document.getElementById('modoAvancado');"
                        "if(!c.checked){c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}))}}")
            pg.click("[data-analise=conceitual]")
            pg.wait_for_selector("#seloQualidade", state="visible", timeout=60000)
            for aba in ("rede", "diagrama", "grupos", "linhatempo", "densidade"):
                pg.evaluate(f"()=>document.querySelector('.aba[data-aba={aba}]').click()")
                pg.wait_for_timeout(1200)
                r = pg.evaluate("""()=>{
                  const vis=e=>e.getClientRects().length>0;
                  const textos=[...document.querySelectorAll('body *')].filter(e=>e.children.length===0&&vis(e)
                    &&!['SCRIPT','STYLE'].includes(e.tagName)).map(e=>e.textContent.trim());
                  const fora=[];
                  document.querySelectorAll('svg').forEach(s=>{
                    if(!vis(s)) return; const vb=s.viewBox&&s.viewBox.baseVal; if(!vb||!vb.width) return;
                    s.querySelectorAll('text').forEach(t=>{ if(!vis(t)) return; let b; try{b=t.getBBox()}catch(_){return}
                      if(b.x<vb.x-1||b.x+b.width>vb.x+vb.width+1) fora.push(t.textContent.slice(0,30))});});
                  return {textos, fora, sx: document.documentElement.scrollWidth-innerWidth}}""")
                bruto = {m for t in r["textos"] for m in BRUTO.findall(t)}
                self.assertFalse(bruto, (largura, aba, bruto))
                self.assertEqual([], r["fora"], (largura, aba))
                self.assertLessEqual(r["sx"], 0, (largura, aba))


if __name__ == "__main__":
    unittest.main()

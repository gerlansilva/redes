"""Integração de qualidade dos agrupamentos e rótulos novos: relatórios, API e diagramas."""

from __future__ import annotations

import json
import re
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from scimatpy import api, metodo, qualidade, rotulos
from scimatpy.api import cria_servidor
from scimatpy.build import constroi
from scimatpy.kb import ProjetoScimat
from scimatpy.texto import rotulo_legivel
from scimatpy.loaders.base import DocumentoFonte
from scimatpy.pipeline import executa_periodo

SERJ = Path("/home/claude/t/serj_auto.redes")
RAIZ = Path(__file__).resolve().parents[1]

LINHAS_NOVAS = ("Modularidade Q", "Q do Louvain (referência)", "Silhueta média",
                "% dos itens em agrupamentos", "Qualidade do mapa")


def _projeto_pequeno(workspace: Path) -> Path:
    documentos = [
        DocumentoFonte(titulo="Statistics education and teacher training",
                       autores=["Lopes, C.E.", "Mendonça, L.A."], ano="2020",
                       palavras_autor=["statistics education", "teacher education",
                                       "probability"]),
        DocumentoFonte(titulo="Probability teaching with technology",
                       autores=["Santos, M."], ano="2021",
                       palavras_autor=["probability", "teaching", "technology"]),
    ]
    caminho = workspace / "pequeno" / "dados.scimat"
    constroi(documentos, caminho, [("2020–2021", 2020, 2021)])
    return caminho


def _linha(html: str, rotulo: str) -> str:
    achado = re.search(r"<tr><td>" + re.escape(rotulo) + r"</td>(.*?)</tr>", html, re.S)
    assert achado, f"linha {rotulo!r} ausente"
    return achado.group(1)


class LimiaresTest(unittest.TestCase):
    """O texto do método repete limiares que moram em `qualidade.avalia`."""

    def test_limiares_do_texto_iguais_aos_do_codigo(self):
        fonte = (RAIZ / "scimatpy" / "qualidade.py").read_text(encoding="utf-8")
        lim = metodo.LIMIARES_QUALIDADE
        esperado = {
            "q_ruim": r"if q < ([0-9.]+):",
            "q_atencao": r"elif q < ([0-9.]+):",
            "razao": r'out\["razao"\] < ([0-9.]+)',
            "silhueta_atencao": r"elif sm < ([0-9.]+):",
            "pct_negativos": r"pn > ([0-9.]+)",
            "pct_grupos_ruim": r"if pu < ([0-9.]+):",
            "pct_grupos_ok": r"elif pu < ([0-9.]+):",
        }
        for chave, padrao in esperado.items():
            achado = re.search(padrao, fonte)
            self.assertIsNotNone(achado, chave)
            self.assertAlmostEqual(float(achado.group(1)), lim[chave], msg=chave)
        self.assertIn("if sm < 0:", fonte)
        self.assertEqual(0.0, lim["silhueta_ruim"])
        self.assertEqual(qualidade.GRUPO_GRANDE, lim["grupo_grande"])

    def test_texto_cita_constantes(self):
        from scimatpy.pipeline import Configuracao
        texto = metodo._texto_qualidade(Configuracao(unidade="Authors"))
        self.assertIn(f"{rotulos.MINIMO_DOCUMENTOS} documentos", texto)
        self.assertIn(f"menos de {qualidade.MINIMO_NOS} itens", texto)
        self.assertIn("não invalida o mapa", texto)
        self.assertIn("artefato", texto)           # só para autores
        outro = metodo._texto_qualidade(Configuracao(unidade="Words"))
        self.assertNotIn("artefato", outro)


class SinteticoTest(unittest.TestCase):
    """Base minúscula: qualidade indefinida e nenhum rótulo novo."""

    @classmethod
    def setUpClass(cls):
        cls.workspace = Path(tempfile.mkdtemp())
        cls.projeto = _projeto_pequeno(cls.workspace)

    def test_analisa_sem_rotulos_e_qualidade_indefinida(self):
        r = api.analisa({"projeto": str(self.projeto), "unidade": "Words",
                         "minimo_frequencia": 1})
        self.assertEqual("indefinido", r["qualidade"]["nivel"])
        self.assertIsNone(r["qualidade"]["q"])
        self.assertTrue(r["qualidade"]["avisos"])
        self.assertGreater(len(r["grupos"]), 0)
        for g in r["grupos"]:
            for campo in ("rotulo_novo", "rotulo_indicativo", "silhueta", "ano_medio"):
                self.assertIn(campo, g)
            self.assertIsNone(g["rotulo_novo"])
            self.assertIsNone(g["silhueta"])
        for resposta in (r["figuras"]["estrategico"],):
            self.assertTrue(resposta.startswith("/figura/"))

    def test_relatorio_mostra_indefinido_sem_zero(self):
        with ProjetoScimat(self.projeto) as kb:
            periodos = kb.periodos()
            config = api._config({"unidade": "Words", "minimo_frequencia": 1})
            resultados = [executa_periodo(kb, p.id, p.nome, config) for p in periodos]
            html = metodo.indicadores_html(resultados, periodos, kb, config)
            # tabela de agrupamentos sem rótulo novo: só o atual
            grupos = sorted(resultados[0].grupos, key=lambda g: (-len(g.nos), g.rotulo))
            cab, linhas, _ = metodo.tabela_agrupamentos(
                kb, resultados[0], grupos, [], lambda v: f"{v:.1f}")
        for rotulo in LINHAS_NOVAS:
            self.assertIn(f"<td>{rotulo}</td>", html)
        self.assertIn("Indefinido", html)
        for rotulo in LINHAS_NOVAS[:3]:
            self.assertEqual("<td class=\"num\">—</td>", _linha(html, rotulo).strip())
        self.assertNotIn("rot-novo", "".join(sum(linhas, [])))
        self.assertEqual("Agrupamento", cab[1])
        self.assertIn("Avisos de qualidade", html)

    def test_relatorio_completo_pequeno_nao_quebra(self):
        try:
            r = api.gera_relatorio_completo({"projeto": str(self.projeto), "formato": "unico"})
        except api.ErroApi:
            self.skipTest("a base pequena não gera nenhuma análise")
        pagina = (api.CACHE / f"rel-{r['token']}" / "relatorio-completo.html").read_text("utf-8")
        self.assertIn("Qualidade do mapa", pagina)
        self.assertIn("selo-q-indefinido", pagina)


@unittest.skipUnless(SERJ.exists(), "projeto serj_auto ausente")
class SerjTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.relatorio = api.gera_relatorio_completo(
            {"projeto": str(SERJ), "formato": "unico"})
        cls.pasta = api.CACHE / f"rel-{cls.relatorio['token']}"
        cls.unico = (cls.pasta / "relatorio-completo.html").read_text("utf-8")

    def test_relatorio_unico_tem_linhas_e_selos(self):
        for rotulo in LINHAS_NOVAS:
            self.assertIn(f"<td>{rotulo}</td>", self.unico)
        self.assertRegex(self.unico, r'class="selo-q selo-q-(ok|atencao|ruim|indefinido)"')
        self.assertIn("Avisos de qualidade", self.unico)
        self.assertIn("Qualidade do mapa.", self.unico)
        self.assertIn("Rótulos dos agrupamentos.", self.unico)
        self.assertIn("Silhueta</th>", self.unico)
        self.assertIn("Ano médio</th>", self.unico)
        self.assertIn("Documentos (núcleo)</th>", self.unico)

    def test_indefinido_nunca_mostra_zero(self):
        # Em toda linha de indicadores, indefinido vem com "—" nas quatro medidas.
        tabelas = re.findall(r"<table.*?</table>", self.unico, re.S)
        achou = False
        for t in tabelas:
            if "<td>Modularidade Q</td>" not in t:
                continue
            niveis = re.findall(r"<td>Qualidade do mapa</td>(.*?)</tr>", t, re.S)[0]
            colunas = re.findall(r"<td class=\"num\">(.*?)</td>", niveis, re.S)
            for i, c in enumerate(colunas):
                if "Indefinido" in c:
                    achou = True
                    for rotulo in LINHAS_NOVAS[:3]:
                        celulas = re.findall(r"<td class=\"num\">(.*?)</td>",
                                             _linha(t, rotulo), re.S)
                        self.assertEqual("—", celulas[i], rotulo)
        # (não exige haver indefinido em serj; só que, havendo, nunca seja 0)
        self.assertIsInstance(achou, bool)

    def test_rotulo_novo_aparece_na_tabela(self):
        with ProjetoScimat(SERJ) as kb:
            p = kb.periodos()[0]
            config = api._config({"unidade": "Words", "minimo_frequencia": 2})
            r = executa_periodo(kb, p.id, p.nome, config)
            novos = rotulos.rotula_grupos(kb, r)
            self.assertTrue(novos)
            grupos = sorted(r.grupos, key=lambda g: (-len(g.nos), g.rotulo or ""))
            cab, linhas, num = metodo.tabela_agrupamentos(
                kb, r, grupos, [("nucleo:documentos", "Documentos")], lambda v: f"{v:.1f}")
        self.assertEqual(["Nº", "Agrupamento", "Itens", "Silhueta", "Ano médio",
                          "Documentos (núcleo)", "Quadrante", "Centralidade", "Densidade",
                          "Documentos"], cab)
        celulas = "".join(l[1] for l in linhas)
        primeiro = next(iter(novos.values()))
        self.assertIn(rotulo_legivel(primeiro["rotulo"]), celulas)
        self.assertIn("rot-atual", celulas)
        self.assertTrue(all(len(l) == len(cab) for l in linhas))
        # o subtítulo (rótulo atual) está presente em quem tem rótulo novo
        for g in grupos[:1]:
            self.assertIn(g.exibicao, linhas[0][1])

    def test_formato_em_pastas(self):
        r = api.gera_relatorio_completo({"projeto": str(SERJ), "formato": "pastas"})
        pasta = api.CACHE / f"rel-{r['token']}"
        paginas = list(pasta.glob("*/period0.html"))
        self.assertTrue(paginas)
        texto = paginas[0].read_text("utf-8")
        self.assertIn("Silhueta</th>", texto)
        self.assertIn("rot-novo", texto)
        indice = (paginas[0].parent / "index.html").read_text("utf-8")
        self.assertIn("<td>Modularidade Q</td>", indice)
        self.assertIn("selo-q", indice)

    def test_diagramas_usam_rotulo_novo_e_padrao_se_mantem(self):
        from scimatpy.viz.halo import halo_svg
        from scimatpy.viz.strategic import diagrama_svg
        with ProjetoScimat(SERJ) as kb:
            p = kb.periodos()[0]
            config = api._config({"unidade": "Words", "minimo_frequencia": 2})
            r = executa_periodo(kb, p.id, p.nome, config)
            novos = rotulos.rotula_grupos(kb, r)
        padrao = diagrama_svg(r, "t")
        com = diagrama_svg(r, "t", rotulos=novos)
        self.assertEqual(padrao, diagrama_svg(r, "t", rotulos=None))
        self.assertNotEqual(padrao, com)
        curto = " · ".join(next(iter(novos.values()))["termos"][:2])
        # a legenda abrevia com "…"; o rótulo atual (item central) é todo em um só termo
        trecho = (curto[:1].upper() + curto[1:])[:24]
        self.assertIn(trecho, com)
        self.assertEqual(halo_svg(r, "t"), halo_svg(r, "t", rotulos=None))
        self.assertNotEqual(halo_svg(r, "t"), halo_svg(r, "t", rotulos=novos))


@unittest.skipUnless(SERJ.exists(), "projeto serj_auto ausente")
class ApiHttpTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workspace = Path(tempfile.mkdtemp())
        cls.servidor = cria_servidor(0, cls.workspace)
        cls.base = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def analisa(self, unidade):
        corpo = json.dumps({"projeto": str(SERJ), "unidade": unidade,
                            "minimo_frequencia": 2}).encode()
        pedido = urllib.request.Request(
            self.base + "/api/analisa", data=corpo,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(pedido, timeout=120) as resposta:
            return json.loads(resposta.read())

    def test_campos_em_palavras_e_referencias(self):
        for unidade in ("Words", "References"):
            r = self.analisa(unidade)
            q = r["qualidade"]
            self.assertIn(q["nivel"], ("ok", "atencao", "ruim", "indefinido"))
            self.assertIn("silhueta_por_selo", q)
            self.assertEqual(len(r["grupos"]), len(q["silhueta_por_selo"]))
            for g in r["grupos"]:
                for campo in ("rotulo_novo", "rotulo_indicativo", "silhueta", "ano_medio"):
                    self.assertIn(campo, g)
                self.assertEqual(g["silhueta"], q["silhueta_por_selo"][str(g["selo"])])
            self.assertTrue(any(g["rotulo_novo"] for g in r["grupos"]), unidade)

    def test_agrupamento_individual_traz_campos(self):
        r = self.analisa("Words")
        with urllib.request.urlopen(
                f"{self.base}/api/grupo?token={r['token']}&selo=1", timeout=60) as resp:
            d = json.loads(resp.read())
        self.assertIn("rotulo_novo", d["grupo"])
        self.assertIn("ano_medio", d["grupo"])

    def test_falha_em_qualidade_nao_derruba(self):
        original = api.modulo_qualidade.avalia
        original_rot = api.modulo_rotulos.rotula_grupos
        try:
            def boom(*a, **k):
                raise RuntimeError("falha simulada")
            api.modulo_qualidade.avalia = boom
            api.modulo_rotulos.rotula_grupos = boom
            r = self.analisa("Words")
        finally:
            api.modulo_qualidade.avalia = original
            api.modulo_rotulos.rotula_grupos = original_rot
        self.assertIsNone(r["qualidade"])
        self.assertGreater(len(r["grupos"]), 0)
        self.assertIsNone(r["grupos"][0]["rotulo_novo"])
        self.assertIsNone(r["grupos"][0]["silhueta"])

    def test_tsv_continua(self):
        r = self.analisa("Words")
        with urllib.request.urlopen(
                f"{self.base}/api/exportar?token={r['token']}&tipo=indices-tsv",
                timeout=60) as resp:
            self.assertGreater(len(resp.read()), 20)


if __name__ == "__main__":
    unittest.main()

"""Mapa de densidade: módulo puro, rota /api/densidade, relatórios, método e interface."""

from __future__ import annotations

import json
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import numpy as np

from redes import api, build, metodo, pipeline, relatorio_unico, report
from redes.api import ProjetoRedes, _config, cria_servidor
from redes.loaders.base import DocumentoFonte
from redes.viz import densidade

UI = Path(api.__file__).with_name("ui")

TEMAS = [["estatistica", "probabilidade", "ensino", "graficos", "media"],
         ["formacao", "professores", "docencia", "curriculo", "pratica"],
         ["tecnologia", "software", "dados", "simulacao", "planilha"]]


def _docs():
    docs = []
    for i in range(36):
        palavras = list(TEMAS[i % 3])
        if i % 4 == 0:
            palavras += ["ponte", TEMAS[(i + 1) % 3][0]]
        docs.append(DocumentoFonte(
            titulo=f"Documento {i}", autores=[f"Autor, {i % 6}.", "Autora, Z."],
            ano=str(2010 + i % 10), palavras_autor=palavras,
            referencias=[f"Ref{j} A., {1990 + j}, Rev" for j in {i % 5, (i + 2) % 5}]))
    return docs


class _Rede:
    def __init__(self, nos, arestas):
        self.nos = list(nos)
        self._arestas = arestas

    def arestas(self):
        return iter(self._arestas)


class _Res:
    """Resultado mínimo: o que `densidade.svg` lê (rede, frequências e rótulos)."""

    def __init__(self, n=30, arestas=True, rotulos=None):
        nos = list(range(n))
        ar = []
        if arestas:
            for i in range(n):
                for j in range(i + 1, n):
                    if (i // 10 == j // 10 and (i + j) % 3 == 0) or (j - i == 1):
                        ar.append((i, j, 1.0 + (i + j) % 4))
        self.rede = _Rede(nos, ar)
        self.frequencia_nos = {i: 40 - i for i in nos}
        self._rotulos = rotulos or {}

    def rotulo(self, no):
        return self._rotulos.get(no, f"item {no}")


def _caixas(svg_texto):
    """(viewBox, quadro, caixas de rótulo estimadas) lidos do SVG, sem navegador."""
    raiz = ET.fromstring(svg_texto)
    ns = "{http://www.w3.org/2000/svg}"
    _, _, w, h = [float(v) for v in raiz.get("viewBox").split()]
    quadro = next(r for r in raiz.iter(ns + "rect") if r.get("fill") == "none")
    q = tuple(float(quadro.get(k)) for k in ("x", "y", "width", "height"))
    return (w, h), q, raiz, ns


class PuroTest(unittest.TestCase):
    def test_svg_valido_e_deterministico(self):
        res = _Res()
        a = densidade.svg(res, "Titulo & <teste>")
        self.assertEqual(a, densidade.svg(res, "Titulo & <teste>"))
        raiz = ET.fromstring(a)                       # XML bem formado (escapa & e <)
        self.assertTrue(raiz.tag.endswith("svg"))
        self.assertIn("data:image/png;base64,", a)
        self.assertNotIn("<script", a)
        sem_imagem = re.sub(r'href="data:[^"]*"', "", a)
        self.assertNotRegex(sem_imagem, r"\b(nan|inf)\b")

    def test_tudo_dentro_da_area_do_grafico(self):
        res = _Res(80, rotulos={i: "RÓTULO-MUITO-LONGO-DE-PALAVRA-CHAVE-%d" % i for i in range(0, 80, 3)})
        for titulo in ("", "Mapa de densidade — teste"):
            texto = densidade.svg(res, titulo)
            (w, h), (qx, qy, qw, qh), raiz, ns = _caixas(texto)
            self.assertEqual(densidade.LARGURA, w)
            for c in raiz.iter(ns + "circle"):
                self.assertTrue(qx <= float(c.get("cx")) <= qx + qw)
                self.assertTrue(qy <= float(c.get("cy")) <= qy + qh)
            achou = 0
            for t in raiz.iter(ns + "text"):
                if t.get("text-anchor") != "middle" or t.get("font-size") == "11":
                    continue
                achou += 1
                fs = float(t.get("font-size"))
                meia = densidade._largura_texto("".join(t.itertext()).split(" — ")[-1] or "", fs) / 2
                x, y = float(t.get("x")), float(t.get("y"))
                self.assertGreaterEqual(x - meia, qx)
                self.assertLessEqual(x + meia, qx + qw)
                self.assertGreaterEqual(y - fs, qy)
                self.assertLessEqual(y + fs * 0.4, qy + qh)
            self.assertGreater(achou, 3)
            # a legenda fica na faixa de baixo, dentro do SVG
            self.assertLessEqual(qy + qh + densidade.RODAPE, h + 1e-6)
            for t in raiz.iter(ns + "text"):
                self.assertLessEqual(float(t.get("y")), h)
                self.assertGreaterEqual(float(t.get("x")), 0)

    def test_rotulos_sem_sobreposicao_e_com_limite(self):
        x = np.array([100.0, 104.0, 300.0, 500.0])
        y = np.array([100.0, 102.0, 200.0, 300.0])
        pesos = np.array([10.0, 9.0, 8.0, 7.0])
        esc = densidade.escolhe_rotulos(["AAAAAAAA", "BBBBBBBB", "CCCCCCCC", "DDDDDDDD"], x, y,
                                        pesos, (0, 0, 600, 400))
        self.assertEqual([0, 2, 3], [e[0] for e in esc])      # B colide com A e sai
        esc = densidade.escolhe_rotulos(["AAAAAAAA", "BBBBBBBB", "CCCCCCCC", "DDDDDDDD"], x, y,
                                        pesos, (0, 0, 600, 400), maximo=1)
        self.assertEqual(1, len(esc))
        # rótulo que não cabe inteiro no quadro é descartado
        esc = densidade.escolhe_rotulos(["A" * 20], np.array([5.0]), np.array([200.0]),
                                        np.array([1.0]), (0, 0, 600, 400))
        self.assertEqual([], esc)

    def test_rotulo_longo_e_cortado_com_texto_inteiro_na_dica(self):
        longos = {i: f"PALAVRA{i}-" * 8 for i in range(30)}
        texto = densidade.svg(_Res(rotulos=longos))
        raiz = ET.fromstring(texto)
        ns = "{http://www.w3.org/2000/svg}"
        cortados = 0
        for t in raiz.iter(ns + "text"):
            titulo = t.find(ns + "title")
            if titulo is None:
                continue
            visivel = (titulo.tail or "").strip()
            cortados += visivel.endswith("…")
            self.assertLessEqual(len(visivel), densidade.LIMITE_ROTULO)
            self.assertTrue(titulo.text.startswith("PALAVRA"))
            self.assertGreater(len(titulo.text), len(visivel))     # texto inteiro na dica
        self.assertGreater(cortados, 0)

    def test_poucos_itens_ou_sem_ligacoes_nao_desenham(self):
        self.assertEqual("", densidade.svg(_Res(3)))
        self.assertIn("Poucos itens", densidade.calcula(_Res(3))["aviso"])
        self.assertEqual("", densidade.svg(_Res(20, arestas=False)))
        self.assertIn("ligações", densidade.calcula(_Res(20, arestas=False))["aviso"])

    def test_parametros_sao_limitados_e_mudam_a_figura(self):
        res = _Res(60)
        d = densidade.calcula(res, topo=10 ** 6, suavizacao=99)
        self.assertEqual(densidade.LIMITE_NOS[1], d["topo"])
        self.assertEqual(60, len(d["nos"]))
        self.assertEqual(densidade.LIMITE_SUAVIZACAO[1], d["suavizacao"])
        d = densidade.calcula(res, topo=1, suavizacao=-5)
        self.assertEqual(densidade.LIMITE_NOS[0], len(d["nos"]))
        self.assertEqual(densidade.LIMITE_SUAVIZACAO[0], d["suavizacao"])
        self.assertNotEqual(densidade.svg(res, suavizacao=2), densidade.svg(res, suavizacao=8))

    def test_densidade_normalizada_e_ponderada(self):
        dens = densidade.densidade_gaussiana(np.array([50.0, 150.0]), np.array([50.0, 50.0]),
                                             np.array([1.0, 4.0]), 200, 100, 15, 100, 50)
        self.assertAlmostEqual(1.0, float(dens.max()))
        self.assertGreaterEqual(float(dens.min()), 0.0)
        gx = np.linspace(0, 200, 100)
        coluna = dens[25]                              # linha do meio (y = 50)
        self.assertGreater(coluna[np.argmin(abs(gx - 150))], 3 * coluna[np.argmin(abs(gx - 50))])

    def test_layout_aproxima_itens_ligados(self):
        s = np.zeros((8, 8))
        for a, b in ((0, 1), (0, 2), (1, 2), (4, 5), (4, 6), (5, 6)):
            s[a, b] = s[b, a] = 1.0
        s[2, 4] = s[4, 2] = 0.1
        x = densidade.layout_vos(s)
        self.assertTrue(np.isfinite(x).all())
        d = lambda i, j: float(np.linalg.norm(x[i] - x[j]))     # noqa: E731
        self.assertLess(d(0, 1), d(0, 5))
        self.assertLess(d(4, 5), d(1, 5))
        self.assertTrue(np.allclose(x, densidade.layout_vos(s)))   # semente fixa

    def test_rede_pequena_e_densa_nao_diverge(self):
        n = 6
        s = np.ones((n, n)) - np.eye(n)
        self.assertTrue(np.isfinite(densidade.layout_vos(s)).all())

    def test_ids_unicos_entre_figuras(self):
        a = densidade.svg(_Res(20), "A")
        b = densidade.svg(_Res(25), "B")
        ia = re.search(r'id="(dn[0-9a-f]+)-g"', a).group(1)
        ib = re.search(r'id="(dn[0-9a-f]+)-g"', b).group(1)
        self.assertNotEqual(ia, ib)

    def test_escala_de_cores_vai_de_branco_a_amarelo(self):
        c = densidade.mapa_de_cores(np.array([0.0, 1.0]))
        self.assertEqual([255, 255, 255], c[0].tolist())
        self.assertGreater(c[1][0], 200)
        self.assertLess(c[1][2], 60)


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = cls.dir / "d.redes"
        build.constroi(_docs(), cls.projeto, [("2010–2014", 2010, 2014), ("2015–2019", 2015, 2019)])
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

    def pedido(self, **extra):
        return {"projeto": str(self.projeto), "unidade": "Words", "minimo_frequencia": 1,
                "periodo": 1, **extra}

    def token(self, **extra):
        st, corpo, _ = self.pede("/api/analisa", self.pedido(**extra))
        self.assertEqual(200, st, corpo)
        return json.loads(corpo)["token"]

    def test_post_devolve_estrutura(self):
        st, corpo, _ = self.pede("/api/densidade", self.pedido())
        self.assertEqual(200, st, corpo)
        d = json.loads(corpo)
        for chave in ("svg", "unidade", "n_nos", "n_total", "max_nos", "suavizacao"):
            self.assertIn(chave, d)
        self.assertTrue(d["svg"].lstrip().startswith("<svg"))
        self.assertEqual(densidade.TOPO_NOS, d["max_nos"])
        self.assertEqual(densidade.SUAVIZACAO, d["suavizacao"])
        self.assertGreaterEqual(d["n_nos"], densidade.MINIMO_NOS)
        self.assertNotIn("Mapa de densidade —", d["svg"].split("<image")[0].split("</desc>")[1])

    def test_token_limites_e_download(self):
        token = self.token()
        for q, esperado in ((dict(max_nos="5"), 20), (dict(max_nos="900"), 300),
                            (dict(suavizacao="0"), 4), (dict(suavizacao="50"), 4)):
            st, corpo, _ = self.pede("/api/densidade?" + urllib.parse.urlencode({"token": token, **q}))
            self.assertEqual(200, st, corpo)
            d = json.loads(corpo)
            if "max_nos" in q:
                self.assertEqual(esperado, d["max_nos"])
            else:
                self.assertEqual(1 if q["suavizacao"] == "0" else 9, d["suavizacao"])
        st, svg, cab = self.pede("/api/densidade?" + urllib.parse.urlencode(
            {"token": token, "baixar": "1"}))
        self.assertEqual(200, st)
        self.assertIn("image/svg+xml", cab["Content-Type"])
        self.assertIn("densidade.svg", cab["Content-Disposition"])
        self.assertIn("Mapa de densidade — Palavras-chave (corpus completo)", svg.decode())
        ET.fromstring(svg)

    def test_erros_claros(self):
        st, corpo, _ = self.pede("/api/densidade", self.pedido(matriz="BasicCoupling",
                                                               unidade="References",
                                                               mapeadores=["acoplamento"]))
        self.assertEqual(400, st)
        self.assertIn("co-ocorrência", json.loads(corpo)["erro"])
        st, corpo, _ = self.pede("/api/densidade", self.pedido(max_nos="x"))
        self.assertEqual(400, st)
        self.assertIn("max_nos", json.loads(corpo)["erro"])
        st, corpo, _ = self.pede("/api/densidade", self.pedido(suavizacao="x"))
        self.assertEqual(400, st)
        st, corpo, _ = self.pede("/api/densidade", {})
        self.assertEqual(400, st)
        st, _, _ = self.pede("/api/densidade?token=inexistente")
        self.assertIn(st, (400, 404, 410))
        st, corpo, _ = self.pede("/api/densidade", {"projeto": "/nao/existe.redes"})
        self.assertEqual(400, st)

    def test_poucos_itens_viram_mensagem(self):
        with mock.patch("redes.viz.densidade.MINIMO_NOS", 10 ** 6):
            st, corpo, _ = self.pede("/api/densidade", self.pedido())
        # Sem itens suficientes não é erro: a tela mostra o aviso (200); só o download falha.
        self.assertEqual(200, st)
        dados = json.loads(corpo)
        self.assertIsNone(dados["svg"])
        self.assertIn("Poucos itens", dados["aviso"])
        with mock.patch("redes.viz.densidade.MINIMO_NOS", 10 ** 6):
            st, corpo, _ = self.pede("/api/densidade", dict(self.pedido(), baixar="1"))
        self.assertEqual(400, st)
        self.assertIn("Poucos itens", json.loads(corpo)["erro"])


class RelatoriosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = cls.dir / "r.redes"
        build.constroi(_docs(), cls.projeto, [("2010–2014", 2010, 2014), ("2015–2019", 2015, 2019)])

    def unico(self, **cfg):
        with ProjetoRedes(self.projeto) as kb:
            config = _config({"minimo_frequencia": 1, "tamanho_maximo": 6, **cfg})
            periodos = kb.periodos()
            resultados = [pipeline.executa_periodo(kb, p.id, p.nome, config) for p in periodos]
            secao = {"rotulo": "Análise de teste", "descricao": "Descrição.", "pasta": "teste",
                     "config": config, "resultados": resultados}
            saida = relatorio_unico.gera_arquivo_unico(
                self.dir / f"u-{len(cfg)}-{cfg.get('unidade', 'W')}.html", kb, periodos, [secao], [])
        return saida.read_text(encoding="utf-8")

    def test_unico_tem_a_secao_com_figura_numerada_e_nota(self):
        html = self.unico(unidade="Words")
        self.assertIn("Mapa de densidade (corpus completo)", html)
        self.assertRegex(html, r"Figura \d+ — Mapa de densidade — Palavras-chave \(corpus completo\)")
        for trecho in ("Como ler:", "densidade", "áreas azuis"):
            self.assertIn(trecho, html)
        self.assertNotIn("\x00", html)
        self.assertLess(html.index("Linha do tempo (corpus completo)"),
                        html.index("Mapa de densidade (corpus completo)"))
        self.assertLess(html.index("Mapa de densidade (corpus completo)"),
                        html.index("Dendrograma (agrupamento hierárquico)"))
        self.assertIn("Mapa de densidade.", html)             # item do método

    def test_unico_omite_quando_nao_se_aplica_ou_falha(self):
        html = self.unico(unidade="References", matriz="BasicCoupling", mapeadores=["acoplamento"])
        self.assertNotIn("Mapa de densidade (corpus completo)", html)
        self.assertIn("Dendrograma (agrupamento hierárquico)", html)
        with mock.patch("redes.report.densidade_do_corpus", side_effect=RuntimeError("x")):
            html = self.unico(unidade="Words", tamanho_maximo=5)
        self.assertNotIn("Mapa de densidade (corpus completo)", html)
        self.assertIn("Linha do tempo (corpus completo)", html)

    def test_pastas(self):
        with ProjetoRedes(self.projeto) as kb:
            periodos = kb.periodos()
            config = _config({"unidade": "Words", "minimo_frequencia": 1, "tamanho_maximo": 6})
            destino = self.dir / "pastas"
            report.gera_html(destino, kb, periodos, config)
            indice = (destino / "index.html").read_text(encoding="utf-8")
            self.assertIn('id="densidade">Mapa de densidade (corpus completo)', indice)
            self.assertIn('src="images/densidade.svg"', indice)
            self.assertIn("Como ler:", indice)
            ET.parse(destino / "images" / "densidade.svg")
            destino2 = self.dir / "pastas2"
            report.gera_html(destino2, kb, periodos, _config(
                {"unidade": "References", "matriz": "BasicCoupling",
                 "mapeadores": ["acoplamento"], "minimo_frequencia": 1}))
            self.assertNotIn("Mapa de densidade (corpus completo)",
                             (destino2 / "index.html").read_text(encoding="utf-8"))
            self.assertFalse((destino2 / "images" / "densidade.svg").exists())

    def test_metodo_traz_parametros_e_algoritmo_com_constantes_do_modulo(self):
        texto = metodo.algoritmo_html(_config({"unidade": "Words"}), None, 2)
        self.assertIn("Mapa de densidade.", texto)
        for trecho in (f"{densidade.TOPO_NOS} itens mais frequentes", "núcleos gaussianos",
                       "largura de banda", "normalizada pelo máximo", "atração e repulsão",
                       f"{densidade.ITERACOES} iterações"):
            self.assertIn(trecho, texto)
        with mock.patch.object(densidade, "TOPO_NOS", 77), mock.patch.object(densidade, "ITERACOES", 321):
            alterado = metodo.algoritmo_html(_config({"unidade": "Words"}), None, 2)
        self.assertIn("77 itens mais frequentes", alterado)
        self.assertIn("321 iterações", alterado)
        acoplamento = metodo.algoritmo_html(
            _config({"unidade": "References", "matriz": "BasicCoupling",
                     "mapeadores": ["acoplamento"]}), None, 2)
        self.assertNotIn("Mapa de densidade.", acoplamento)


class InterfaceTest(unittest.TestCase):
    """Checagens estáticas da aba, do reset e do menu (o fluxo vivo está nos prints Playwright)."""

    @classmethod
    def setUpClass(cls):
        cls.js = (UI / "app.js").read_text(encoding="utf-8")
        cls.html = (UI / "index.html").read_text(encoding="utf-8")

    def test_aba_depois_da_linha_do_tempo_e_sempre_visivel(self):
        ordem = re.findall(r'data-aba="([a-z]+)"', self.html)
        self.assertEqual(ordem.index("linhatempo") + 1, ordem.index("densidade"))
        self.assertIn('id="blocoDensidade"', self.html)
        self.assertIn('densidade: "blocoDensidade"', self.js)
        grupos = re.search(r"const GRUPOS_ABAS = \[.*?\];", self.js, re.S).group(0)
        self.assertIn('"densidade"', grupos)
        self.assertNotIn("ABAS_SIMPLES", self.js)
        config = re.search(r"const CONFIG_ABAS = \{.*?\n\};", self.js, re.S).group(0)
        self.assertEqual(config.count('"densidade"'), 8)   # vale em todas as unidades

    def test_reset_ao_trocar_de_projeto_e_de_analise(self):
        projeto = re.search(r"function aplicarProjeto\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("limparDensidade(true)", projeto)
        resultado = re.search(r"function renderizarResultado\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("limparDensidade(false)", resultado)
        self.assertIn('abaAtual() === "densidade"', resultado)
        limpa = re.search(r"function limparDensidade\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("dn.seq += 1", limpa)
        self.assertIn("mensagemDensidade", limpa)
        self.assertIn('chave === "densidade"', self.js)

    def test_mensagem_quando_nao_se_aplica_e_menu_exportar(self):
        self.assertIn("MOTIVO_DENSIDADE", self.js)
        self.assertIn("!densidadeAplicavel()", self.js)
        self.assertIn('data-exp="densidade-svg" data-precisa="resultado"', self.html)
        self.assertIn('tipo === "densidade-svg"', self.js)
        self.assertIn("/api/densidade?", self.js)
        self.assertIn('link.download = "densidade.svg"', self.js)

    def test_sem_tema_escuro_no_trecho_novo(self):
        css = (UI / "style.css").read_text(encoding="utf-8")
        trecho = css[css.index(".dn-figura"):].split("/* ---")[0]
        self.assertNotIn("prefers-color-scheme", trecho)


if __name__ == "__main__":
    unittest.main()

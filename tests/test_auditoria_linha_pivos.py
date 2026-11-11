"""Correções da auditoria independente da linha do tempo e dos pontos de virada."""

from __future__ import annotations

import json
import math
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from scimatpy import api, build, linha_do_tempo, metodo, pipeline, pivos, relatorio_unico, report
from scimatpy.api import ErroApi, ProjetoScimat, _config, cria_servidor
from scimatpy.pipeline import Configuracao
from scimatpy.viz import linha_do_tempo as viz

import test_linha_do_tempo as tlt
import test_linha_pivos_integracao as tlp
import test_pivos as tpv

NS = "{http://www.w3.org/2000/svg}"
UI = Path(api.__file__).with_name("ui")


def _numeros_do_metodo(texto: str) -> list[int]:
    return [int(n) for n in re.findall(r"<strong>(\d+)\. ", texto)]


class NumeracaoDoMetodoTest(unittest.TestCase):
    def test_numeracao_sequencial_em_todas_as_configuracoes(self):
        configs = [Configuracao(unidade="Words"),
                   Configuracao(unidade="Authors"),
                   Configuracao(unidade="References", matriz="BasicCoupling",
                                mapeadores=("acoplamento",)),
                   Configuracao(unidade="Words", matriz="AggregatedCouplingBasedOnAuthor")]
        for config in configs:
            for n_periodos in (None, 1, 3):
                numeros = _numeros_do_metodo(metodo.algoritmo_html(config, "EquivalenceIndex", n_periodos))
                self.assertEqual(list(range(1, len(numeros) + 1)), numeros,
                                 (config.unidade, config.matriz, n_periodos))

    def test_frentes_nao_repete_o_nove(self):
        config = Configuracao(unidade="References", matriz="BasicCoupling", mapeadores=("acoplamento",))
        numeros = _numeros_do_metodo(metodo.algoritmo_html(config, None, 2))
        self.assertEqual(1, numeros.count(9))
        self.assertEqual(list(range(1, 13)), numeros)       # 8 + duplo mapa + pontos de virada + qualidade + rótulos

    def test_palavras_vai_ate_catorze(self):
        numeros = _numeros_do_metodo(metodo.algoritmo_html(Configuracao(unidade="Words"), None, 2))
        self.assertEqual(list(range(1, 15)), numeros)


class RelatorioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = tlp._constroi(cls.dir)

    def unico(self, so_primeiro=False, **cfg):
        config = _config({"minimo_frequencia": 1, "tamanho_maximo": 6, **cfg})
        with ProjetoScimat(self.projeto) as kb:
            periodos = kb.periodos()[:1] if so_primeiro else kb.periodos()
            resultados = [pipeline.executa_periodo(kb, p.id, p.nome, config) for p in periodos]
            secao = {"rotulo": "Teste", "descricao": "D.", "pasta": "t", "config": config,
                     "resultados": resultados}
            saida = relatorio_unico.gera_arquivo_unico(
                self.dir / f"a-{so_primeiro}-{cfg.get('unidade', 'W')}.html", kb, periodos, [secao], [])
        return saida.read_text(encoding="utf-8")

    def test_aria_labelledby_com_ids_existentes(self):
        html = self.unico(unidade="Words")
        ids = set(re.findall(r'\sid="([^"]+)"', html))
        usos = re.findall(r'aria-labelledby="([^"]*)"', html)
        self.assertGreaterEqual(len(usos), 3)
        for lista in usos:
            for ident in lista.split():
                self.assertIn(ident, ids, lista)
        self.assertEqual(len(ids), len(re.findall(r'\sid="', html)))

    def test_prefixa_ids_de_aria_labelledby(self):
        svg = ('<svg aria-labelledby="t d"><title id="t">a</title><desc id="d">b</desc>'
               '<g aria-describedby="d"/></svg>')
        saida = relatorio_unico._prefixa_ids(svg, "fig-7")
        self.assertIn('aria-labelledby="fig-7-t fig-7-d"', saida)
        self.assertIn('aria-describedby="fig-7-d"', saida)
        self.assertIn('id="fig-7-t"', saida)

    def test_subsecoes_sequenciais_sem_evolucao(self):
        html = self.unico(so_primeiro=True, unidade="Words")
        titulos = re.findall(r'<h3 id="[^"]+">2\.(\d+) ', html)
        self.assertEqual(list(range(1, len(titulos) + 1)), [int(t) for t in titulos])
        self.assertNotRegex(html, r"<h3[^>]*>2\.\d Evolução")
        self.assertIn("2.4 Linha do tempo (corpus completo)", html)
        self.assertIn("2.5 Mapa de densidade (corpus completo)", html)
        self.assertIn("2.6 Dendrograma", html)

    def test_subsecoes_sequenciais_com_evolucao(self):
        html = self.unico(unidade="Words")
        titulos = [int(t) for t in re.findall(r'<h3 id="[^"]+">2\.(\d+) ', html)]
        self.assertEqual(list(range(1, len(titulos) + 1)), titulos)
        self.assertIn("2.4 Evolução", html)
        self.assertIn("2.5 Linha do tempo", html)

    def test_aviso_de_rajada_so_de_autores_no_relatorio_e_no_metodo(self):
        html = self.unico(unidade="Words")
        self.assertIn("só sobre as palavras-chave dos autores", html)
        self.assertIn("calculadas só sobre as palavras-chave dos autores", html)

    def test_nao_calculado_no_relatorio(self):
        config = _config({"minimo_frequencia": 1, "tamanho_maximo": 6})
        with ProjetoScimat(self.projeto) as kb:
            periodo = kb.periodos()[0]
            r = pipeline.executa_periodo(kb, periodo.id, periodo.nome, config)
            with mock.patch.object(pivos, "LIMITE_NOS", 3):
                texto = metodo.pivos_html(kb, r, lambda c, l, g, n=(): "<table/>", "Leg.")
        self.assertIn("Não calculado: rede com", texto)
        self.assertIn("(limite 3)", texto)
        self.assertNotIn("Nenhum ponto de virada", texto)


class PivosTest(unittest.TestCase):
    def test_rede_acima_do_limite_diz_nao_calculado(self):
        from scimatpy.network import Rede
        n = pivos.LIMITE_NOS + 1
        rede = Rede(range(n))
        rede.adiciona_aresta(0, 1, 1.0)
        res = tpv._resultado(rede)
        res.conjunto.grupo_do_no.update({0: 0, 1: 1})
        r = pivos.pontos_de_virada(res)
        self.assertEqual([], r["pivos"])
        self.assertEqual(f"Não calculado: rede com {n} nós (limite {pivos.LIMITE_NOS}); a "
                         "intermediação foi pulada para não travar. Filtre a rede e tente de novo.",
                         r["nao_calculado"])
        publico = api._pivos_publicos(r, {})
        self.assertEqual(r["nao_calculado"], publico["nao_calculado"])

    def test_rede_normal_nao_tem_nao_calculado(self):
        self.assertIsNone(pivos.pontos_de_virada(tpv._resultado())["nao_calculado"])

    def test_plural_de_nos_nos_avisos(self):
        from scimatpy.network import Rede
        self.assertEqual("1 nó", pivos._nos(1))
        self.assertEqual("5 nós", pivos._nos(5))
        rede = Rede([0])
        r = pivos.pontos_de_virada(tpv._resultado(rede))
        avisos = " ".join(r["avisos"])
        self.assertIn("só 1 nó ", avisos)
        self.assertNotIn("1 nós", avisos)

    def test_ui_e_relatorio_usam_o_plural_correto(self):
        js = (UI / "app.js").read_text(encoding="utf-8")
        self.assertIn('plural(p.n_nos, "nó", "nós")', js)
        self.assertIn("p.nao_calculado ||", js)


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = tlp._constroi(cls.dir)
        cls.servidor = cria_servidor(0, cls.dir)
        cls.base = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def pede(self, rota, dados):
        req = urllib.request.Request(self.base + rota, data=json.dumps(dados).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def pedido(self, **extra):
        return {"projeto": str(self.projeto), "unidade": "Words", "minimo_frequencia": 1,
                "periodo": 1, **extra}

    def test_infinito_devolve_400_nas_rotas_novas(self):
        for rota, campo in (("/api/linha-do-tempo", "max_nos"), ("/api/densidade", "max_nos"),
                            ("/api/densidade", "suavizacao"), ("/api/dendrograma", "limite"),
                            ("/api/dendrograma", "n_grupos")):
            for valor in (float("inf"), float("-inf")):
                st, corpo = self.pede(rota, self.pedido(**{campo: valor}))
                self.assertEqual(400, st, (rota, campo, valor, corpo))
                self.assertIn(campo, corpo["erro"])
                self.assertIn("finito", corpo["erro"])

    def test_nan_e_texto_continuam_400(self):
        for valor in (float("nan"), "abc", [1]):
            st, corpo = self.pede("/api/linha-do-tempo", self.pedido(max_nos=valor))
            self.assertEqual(400, st, valor)

    def test_inteiro_limitado_overflow(self):
        with self.assertRaises(ErroApi) as ctx:
            api._inteiro_limitado(float("inf"), 40, 10, 60, "max_nos")
        self.assertIn("max_nos", str(ctx.exception))
        self.assertEqual(60, api._inteiro_limitado(10 ** 30, 40, 10, 60, "max_nos"))

    def test_unidades_da_linha_do_tempo_coerentes_entre_api_e_relatorio(self):
        for unidade in api.UNIDADES:
            config = _config({"unidade": unidade})
            esperado = unidade in metodo.UNIDADES_LINHA_DO_TEMPO
            self.assertEqual(esperado, report.linha_do_tempo_aplicavel(config), unidade)
            st, corpo = self.pede("/api/linha-do-tempo", self.pedido(unidade=unidade))
            if esperado:
                self.assertEqual(200, st, (unidade, corpo))
            else:
                self.assertEqual(400, st, unidade)
                self.assertIn("palavras-chave, autores e referências", corpo["erro"])
        js = (UI / "app.js").read_text(encoding="utf-8")
        self.assertIn('const UNIDADES_LINHA_DO_TEMPO = ["Words", "Authors", "References"];', js)

    def test_falha_nos_pivos_vira_aviso_visivel(self):
        with mock.patch("scimatpy.api.modulo_pivos.pontos_de_virada",
                        side_effect=RuntimeError("quebrou")):
            st, d = self.pede("/api/analisa", self.pedido())
        self.assertEqual(200, st)
        p = d["pivos"]
        self.assertTrue(p["nao_calculado"].startswith("Não calculado"))
        self.assertIn("quebrou", p["nao_calculado"])
        self.assertIn(p["nao_calculado"], p["avisos"])

    def test_sem_nenhum_ano_a_mensagem_diz_que_nenhum_documento_traz_o_ano(self):
        pasta, destino = tlt._projeto(tlt._docs(anos=[None], por_ano=6))
        try:
            with self.assertRaises(ErroApi) as ctx:
                api.linha_do_tempo_do_pedido({"projeto": str(destino), "unidade": "Words",
                                              "minimo_frequencia": 2, "tamanho_maximo": 15})
        finally:
            pasta.cleanup()
        self.assertIn("Nenhum documento do projeto traz o ano", str(ctx.exception))


class LinhaDoTempoDadosTest(unittest.TestCase):
    def test_termos_descritor_ficam_de_fora_e_avisam(self):
        docs = tlt._docs(palavras_extra=["geral", "humano"])    # presentes em 100% dos documentos
        pasta, destino = tlt._projeto(docs)
        try:
            with ProjetoScimat(destino) as kb:
                d = linha_do_tempo.constroi(kb, tlt._config(), max_nos=60, por_faixa=1000)
        finally:
            pasta.cleanup()
        rotulos = {n["rotulo"] for f in d["faixas"] for n in f["nos"]}
        self.assertNotIn("geral", rotulos)
        self.assertNotIn("humano", rotulos)
        self.assertTrue(rotulos)
        self.assertEqual(2, d["omitidos"]["descritores"])
        self.assertTrue(any("2 termos-descritor omitidos" in a for a in d["avisos"]), d["avisos"])
        # os dois descritores não contam como "itens de fora"
        self.assertEqual(0, d["omitidos"]["itens"])

    def test_um_unico_descritor_no_singular(self):
        pasta, destino = tlt._projeto(tlt._docs(palavras_extra=["geral"]))
        try:
            with ProjetoScimat(destino) as kb:
                d = linha_do_tempo.constroi(kb, tlt._config(), max_nos=60)
        finally:
            pasta.cleanup()
        self.assertTrue(any("1 termo-descritor omitido" in a for a in d["avisos"]), d["avisos"])

    def test_sem_descritores_nao_avisa(self):
        d = tlt._dados(tlt._docs())
        self.assertEqual(0, d["omitidos"]["descritores"])
        self.assertFalse(any("descritor" in a for a in d["avisos"]))

    def test_aviso_de_sem_ano_para_referencias_cita_o_intervalo(self):
        docs = tlt._docs()
        pasta, destino = tlt._projeto(docs)
        try:
            with ProjetoScimat(destino) as kb:
                kb.conexao.execute("UPDATE Reference SET year = '9999'")
                config = api._config({"unidade": "References", "minimo_frequencia": 1,
                                      "tamanho_maximo": 15, "tamanho_minimo": 2,
                                      "mapeadores": ["nucleo"]})
                d = linha_do_tempo.constroi(kb, config)
        finally:
            pasta.cleanup()
        self.assertEqual([], d["faixas"])
        self.assertIn("Nenhuma referência dos agrupamentos tem ano válido", d["avisos"][0])
        self.assertIn("1400", d["avisos"][0])
        self.assertTrue(any("não trazem um ano válido" in a or "não traz um ano válido" in a
                            for a in d["avisos"]))
        self.assertFalse(any("documentos não trazem o ano" in a for a in d["avisos"]))

    def test_valor_nan_ou_infinito_na_ligacao_nao_gera_stroke_nan(self):
        manual = tlt._manual(
            [tlt._faixa(0, "A", [tlt._no(1, "x", 2010), tlt._no(2, "y", 2012)]),
             tlt._faixa(1, "B", [tlt._no(3, "z", 2014)])],
            [{"origem": 1, "destino": 2, "valor": float("nan"), "cruzada": False},
             {"origem": 1, "destino": 3, "valor": float("inf"), "cruzada": True},
             {"origem": 2, "destino": 3, "valor": 2.0, "cruzada": True}])
        texto = viz.svg(manual, "NaN")
        self.assertNotRegex(texto, r'(?i)="-?(nan|inf)')
        ET.fromstring(texto)
        self.assertEqual(1, texto.count('stroke="#9AA3B2"') - texto.count('stroke="#9AA3B2" stroke-opacity=".7"'))

    def test_arestas_nan_nao_entram_nos_dados(self):
        from scimatpy.network import Rede
        self.assertFalse(linha_do_tempo._finito(float("nan")))
        self.assertFalse(linha_do_tempo._finito(float("inf")))
        self.assertFalse(linha_do_tempo._finito(None))
        self.assertTrue(linha_do_tempo._finito(0.5))
        self.assertIsNotNone(Rede)


class FiguraTest(unittest.TestCase):
    def _manual(self, **no_extra):
        return tlt._manual([
            tlt._faixa(0, "Tema", [tlt._no(1, "alfa", 2012, rajada=True, rajada_inicio=2005,
                                           rajada_fim=2013, primeiro=2010, ultimo=2014, **no_extra),
                                   tlt._no(2, "beta", 2015, primeiro=2015, ultimo=2015)])])

    def test_rajada_que_comeca_antes_do_eixo_tem_setinha(self):
        texto = viz.svg(self._manual(), "Seta")
        raiz = ET.fromstring(texto)
        setas = [e for e in raiz.iter(f"{NS}path") if e.get("class") == "lt-seta-rajada"]
        self.assertEqual(1, len(setas))
        self.assertEqual("#DC2626", setas[0].get("stroke"))

    def test_rajada_dentro_do_eixo_nao_tem_setinha(self):
        dados = tlt._manual([tlt._faixa(0, "Tema", [
            tlt._no(1, "alfa", 2012, rajada=True, rajada_inicio=2011, rajada_fim=2013,
                    primeiro=2010, ultimo=2014), tlt._no(2, "beta", 2015)])])
        self.assertNotIn("lt-seta-rajada", viz.svg(dados, "Sem seta"))

    def test_rajada_que_termina_depois_do_eixo_tem_setinha_na_direita(self):
        dados = tlt._manual([tlt._faixa(0, "Tema", [
            tlt._no(1, "alfa", 2012, rajada=True, rajada_inicio=2011, rajada_fim=2030,
                    primeiro=2010, ultimo=2014), tlt._no(2, "beta", 2015)])])
        self.assertEqual(1, viz.svg(dados, "Dir").count('class="lt-seta-rajada"'))

    def test_legenda_do_anel_avisa_que_so_palavras_dos_autores(self):
        texto = viz.svg(self._manual(), "Legenda")
        self.assertIn("rajadas calculadas só sobre palavras-chave dos autores", texto)
        dados = self._manual()
        dados["unidade"] = "References"
        self.assertNotIn("só sobre palavras-chave dos autores", viz.svg(dados, "Ref"))

    def test_largura_minima_cabe_na_caixa_de_1280(self):
        css = (UI / "style.css").read_text(encoding="utf-8")
        minimo = int(re.search(r"\.lt-figura svg \{[^}]*min-width: (\d+)px", css).group(1))
        self.assertLessEqual(minimo, 924)       # caixa da figura em 1280 px de tela


class TextosTest(unittest.TestCase):
    def test_nenhum_texto_diz_que_sigma_repete_a_forca_da_rajada(self):
        js = (UI / "app.js").read_text(encoding="utf-8")
        fontes = [Path(metodo.__file__).read_text(encoding="utf-8"), js]
        for texto in fontes:
            self.assertNotIn("quase repete o ranking", texto)
            self.assertNotIn("praticamente repete o ranking", texto)
        self.assertIn("acompanha sobretudo a intermediação", js)
        self.assertIn("0,89 e 0,97", fontes[0])

    def test_metodo_nao_fala_em_atividade_anual_sob_a_faixa(self):
        texto = metodo.algoritmo_html(Configuracao(unidade="Words"), None, 2)
        self.assertNotIn("atividade anual", texto)
        self.assertNotIn("sob a faixa", texto)
        self.assertIn("traço vermelho sobre essa linha marca os anos da rajada", texto)

    def test_metodo_cita_descritores_e_rajada_so_de_autores(self):
        texto = metodo.algoritmo_html(Configuracao(unidade="Words"), None, 2)
        self.assertIn("só sobre as palavras-chave dos autores", texto)
        self.assertIn("termos-descritor", texto)
        autores = metodo.algoritmo_html(Configuracao(unidade="Authors"), None, 2)
        self.assertIn("não há rajada para autores", autores)


if __name__ == "__main__":
    unittest.main()

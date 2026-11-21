"""Integração da linha do tempo e dos pontos de virada: API, relatórios, halo e interface."""

from __future__ import annotations

import json
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

from redes import api, build, metodo, pipeline, relatorio_unico, report
from redes.api import ProjetoRedes, _config, cria_servidor
from redes.loaders.base import DocumentoFonte
from redes.viz.halo import halo_svg

UI = Path(api.__file__).with_name("ui")

TEMAS = [["estatistica", "probabilidade", "ensino", "graficos", "media"],
         ["formacao", "professores", "docencia", "curriculo", "pratica"],
         ["tecnologia", "software", "dados", "simulacao", "planilha"]]


def _docs():
    docs = []
    for i in range(36):
        palavras = list(TEMAS[i % 3])
        if i % 4 == 0:
            palavras.append("ponte")            # liga os três temas
            palavras.append(TEMAS[(i + 1) % 3][0])
        docs.append(DocumentoFonte(
            titulo=f"Documento {i}", autores=[f"Autor, {i % 6}.", "Autora, Z."],
            ano=str(2010 + i % 10), palavras_autor=palavras,
            referencias=[f"Ref{j} A., {1990 + j}, Rev" for j in {i % 5, (i + 2) % 5}]))
    return docs


def _constroi(diretorio: Path) -> Path:
    caminho = diretorio / "lp.redes"
    build.constroi(_docs(), caminho, [("2010–2014", 2010, 2014), ("2015–2019", 2015, 2019)])
    return caminho


class RotasTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = _constroi(cls.dir)
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
        return {"projeto": str(self.projeto), "unidade": "Words",
                "minimo_frequencia": 1, "periodo": 1, **extra}

    def analisa(self, **extra):
        st, corpo, _ = self.pede("/api/analisa", self.pedido(**extra))
        self.assertEqual(200, st, corpo)
        return json.loads(corpo)

    # ------------------------------------------------------------ linha do tempo

    def test_post_devolve_estrutura(self):
        st, corpo, _ = self.pede("/api/linha-do-tempo", self.pedido())
        self.assertEqual(200, st, corpo)
        d = json.loads(corpo)
        for chave in ("svg", "n_nos", "n_faixas", "anos", "avisos", "omitidos",
                      "max_nos", "atividade", "unidade"):
            self.assertIn(chave, d)
        self.assertTrue(d["svg"].lstrip().startswith("<svg"))
        self.assertEqual(40, d["max_nos"])
        self.assertTrue(d["n_faixas"] >= 1)

    def test_token_limites_e_download(self):
        token = self.analisa()["token"]
        for pedido, esperado in (("5", 10), ("100", 60), ("25", 25)):
            q = urllib.parse.urlencode({"token": token, "max_nos": pedido})
            st, corpo, _ = self.pede(f"/api/linha-do-tempo?{q}")
            self.assertEqual(200, st)
            self.assertEqual(esperado, json.loads(corpo)["max_nos"])
        q = urllib.parse.urlencode({"token": token})
        st, svg, cab = self.pede(f"/api/linha-do-tempo?{q}&baixar=1")
        self.assertEqual(200, st)
        self.assertIn("image/svg+xml", cab["Content-Type"])
        self.assertIn("attachment", cab["Content-Disposition"])
        self.assertTrue(svg.lstrip().startswith(b"<svg"))
        self.assertIn("corpus completo".encode(), svg)

    def test_referencias_usam_o_ano_da_obra(self):
        st, corpo, _ = self.pede("/api/linha-do-tempo", self.pedido(unidade="References"))
        self.assertEqual(200, st, corpo)
        d = json.loads(corpo)
        self.assertEqual("referencia", d["posicao"])
        self.assertFalse(d["atividade"])

    def test_erros(self):
        st, corpo, _ = self.pede("/api/linha-do-tempo", self.pedido(max_nos="x"))
        self.assertEqual(400, st)
        self.assertIn("max_nos", json.loads(corpo)["erro"])
        st, corpo, _ = self.pede("/api/linha-do-tempo", self.pedido(unidade="Nada"))
        self.assertEqual(400, st)
        st, corpo, _ = self.pede("/api/linha-do-tempo", {})
        self.assertEqual(400, st)
        st, _, _ = self.pede("/api/linha-do-tempo?token=inexistente")
        self.assertEqual(410, st)
        st, corpo, _ = self.pede("/api/linha-do-tempo", {"projeto": "/nao/existe.redes"})
        self.assertEqual(400, st)

    def test_acoplamento_devolve_mensagem_clara(self):
        pedido = self.pedido(unidade="References", matriz="BasicCoupling",
                             mapeadores=["acoplamento"])
        st, corpo, _ = self.pede("/api/linha-do-tempo", pedido)
        self.assertEqual(400, st)
        erro = json.loads(corpo)["erro"]
        self.assertIn("acoplamento", erro)
        self.assertIn("documentos", erro)
        st, _, _ = self.pede("/api/linha-do-tempo?" + urllib.parse.urlencode(
            {**{k: v for k, v in pedido.items() if k != "mapeadores"}, "baixar": "1"}))
        self.assertEqual(400, st)

    def test_sem_anos_devolve_aviso_em_vez_de_figura_vazia(self):
        vazio = {"unidade": "Words", "faixas": [], "ligacoes": [], "anos": [],
                 "atividade": True, "avisos": ["Nenhum item dos agrupamentos tem ano."],
                 "omitidos": {"itens": 0, "agrupamentos": 0, "sem_ano": 3}}
        with mock.patch("redes.report.linha_do_tempo_do_corpus", return_value=(vazio, {})):
            st, corpo, _ = self.pede("/api/linha-do-tempo", self.pedido())
        self.assertEqual(400, st)
        self.assertIn("tem ano", json.loads(corpo)["erro"])

    # ------------------------------------------------------------ pontos de virada

    def test_analisa_devolve_pivos(self):
        d = self.analisa(tamanho_maximo=6)
        p = d["pivos"]
        self.assertTrue(p["pivos"])
        self.assertIsNotNone(p)
        self.assertFalse(p["adiado"])
        for chave in ("n_nos", "suficiente", "minimo_nos", "pivos", "tem_sigma",
                      "termos_descritores", "avisos"):
            self.assertIn(chave, p)
        self.assertFalse(p["suficiente"])          # poucos nós no corpus de teste
        self.assertTrue(any("Poucos dados" in a for a in p["avisos"]))
        json.dumps(p, allow_nan=False)             # JSON estrito
        for i in p["pivos"]:
            self.assertGreaterEqual(i["grupos_vizinhos"], 2)
            self.assertTrue(i["grupo_selo"])
            self.assertIsNone(i["sigma"])          # sem rajada, sem sigma
        self.assertFalse(p["tem_sigma"])

    def test_analise_nao_quebra_se_pivos_falhar(self):
        with mock.patch("redes.api.modulo_pivos.pontos_de_virada",
                        side_effect=RuntimeError("falha de teste")):
            d = self.analisa()
        # a falha não derruba a análise, mas aparece como aviso (e não como "sem pivôs")
        self.assertIn("Não calculado", d["pivos"]["nao_calculado"])
        self.assertIn("falha de teste", d["pivos"]["nao_calculado"])
        self.assertEqual([], d["pivos"]["pivos"])
        self.assertTrue(d["grupos"])
        self.assertTrue(d["figuras"]["halo"])
        # a figura da rede continua saindo, sem anéis
        st, svg, _ = self.pede(d["figuras"]["halo"])
        self.assertEqual(200, st)
        self.assertNotIn(b"ponto de virada", svg)

    def test_pivos_adiados_em_rede_grande_e_calculados_sob_demanda(self):
        with mock.patch.object(api, "LIMITE_PIVOS_INLINE", 0):
            d = self.analisa()
        self.assertTrue(d["pivos"]["adiado"])
        st, corpo, _ = self.pede("/api/pivos?token=" + d["token"])
        self.assertEqual(200, st, corpo)
        p = json.loads(corpo)
        self.assertFalse(p["adiado"])
        self.assertIn("pivos", p)
        st, _, _ = self.pede("/api/pivos?token=inexistente")
        self.assertEqual(410, st)
        st, _, _ = self.pede("/api/pivos")
        self.assertEqual(400, st)

    def test_halo_da_ui_marca_os_pivos(self):
        d = self.analisa(tamanho_maximo=6)
        self.assertTrue(d["pivos"]["pivos"])
        st, svg, _ = self.pede(d["figuras"]["halo"])
        self.assertEqual(200, st)
        self.assertIn("ponto de virada".encode(), svg)


class RelatoriosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = _constroi(cls.dir)

    def secao(self, kb, **cfg):
        config = _config({"minimo_frequencia": 1, "tamanho_maximo": 6, **cfg})
        periodos = kb.periodos()
        resultados = [pipeline.executa_periodo(kb, p.id, p.nome, config) for p in periodos]
        return periodos, {"rotulo": "Análise de teste", "descricao": "Descrição.",
                          "pasta": "teste", "config": config, "resultados": resultados}

    def unico(self, **cfg):
        with ProjetoRedes(self.projeto) as kb:
            periodos, secao = self.secao(kb, **cfg)
            saida = relatorio_unico.gera_arquivo_unico(
                self.dir / f"u-{len(cfg)}-{cfg.get('unidade', 'W')}.html", kb, periodos, [secao], [])
        return saida.read_text(encoding="utf-8")

    def test_unico_tem_linha_do_tempo_e_tabela_de_pivos(self):
        html = self.unico(unidade="Words")
        self.assertIn("Linha do tempo (corpus completo)", html)
        self.assertRegex(html, r"Figura \d+ — Linha do tempo — Palavras-chave \(corpus completo\)")
        for trecho in ("ano médio", "ano da própria obra", "primeiro ao último ano", "rajada"):
            self.assertIn(trecho, html)
        self.assertIn("Pontos de virada", html)
        self.assertRegex(html, r"Tabela \d+ — Pontos de virada de ")
        self.assertIn("Poucos dados", html)
        self.assertIn("<th>Intermediação</th>", html)
        self.assertNotIn("<th>Sigma</th>", html)       # sem rajada, sem coluna sigma
        self.assertNotIn("\x00", html)
        # o dendrograma segue a linha do tempo, com numeração própria
        self.assertLess(html.index("Linha do tempo (corpus completo)"),
                        html.index("Dendrograma (agrupamento hierárquico)"))

    def test_unico_omite_linha_do_tempo_quando_nao_se_aplica(self):
        for cfg in ({"unidade": "References", "matriz": "BasicCoupling",
                     "mapeadores": ["acoplamento"]},
                    {"unidade": "AuthorsReference"}):
            html = self.unico(**cfg)
            self.assertNotIn("Linha do tempo (corpus completo)", html, cfg)
            self.assertIn("Dendrograma (agrupamento hierárquico)", html)

    def test_unico_nao_quebra_se_a_linha_do_tempo_falhar(self):
        with mock.patch("redes.report.linha_do_tempo_do_corpus", side_effect=RuntimeError("x")):
            html = self.unico(unidade="Words", tamanho_maximo=5)
        self.assertNotIn("Linha do tempo (corpus completo)", html)

    def test_unico_nao_quebra_se_pivos_falhar(self):
        with mock.patch("redes.pivos.pontos_de_virada", side_effect=RuntimeError("x")):
            html = self.unico(unidade="Words", tamanho_maximo=7)
        self.assertNotIn("Pontos de virada de ", html)
        self.assertIn("Linha do tempo (corpus completo)", html)

    def test_metodo_traz_as_duas_secoes_com_constantes_dos_modulos(self):
        from redes import linha_do_tempo, pivos
        config = _config({"unidade": "Words"})
        texto = metodo.algoritmo_html(config, None, 2)
        self.assertIn("Linha do tempo.", texto)
        self.assertIn("Pontos de virada e sigma.", texto)
        self.assertIn(f"{linha_do_tempo.MAX_NOS} itens mais frequentes", texto)
        self.assertIn(f"{linha_do_tempo.POR_FAIXA} por faixa", texto)
        self.assertIn(f"{linha_do_tempo.RAJADA_MIN_DOCUMENTOS} documentos", texto)
        self.assertIn(f"{pivos.MINIMO_NOS} nós", texto)
        self.assertNotIn("praticamente repete", texto)
        self.assertIn("quem ordena o ranking por sigma é sobretudo a intermediação", texto)
        with mock.patch.object(linha_do_tempo, "MAX_NOS", 33), \
                mock.patch.object(pivos, "MINIMO_NOS", 77):
            alterado = metodo.algoritmo_html(config, None, 2)
        self.assertIn("33 itens mais frequentes", alterado)
        self.assertIn("77 nós", alterado)
        acoplamento = metodo.algoritmo_html(
            _config({"unidade": "References", "matriz": "BasicCoupling",
                     "mapeadores": ["acoplamento"]}), None, 2)
        self.assertNotIn("Linha do tempo.", acoplamento)
        self.assertIn("Pontos de virada e sigma.", acoplamento)

    def test_relatorio_em_pastas(self):
        with ProjetoRedes(self.projeto) as kb:
            periodos = kb.periodos()
            config = _config({"unidade": "Words", "minimo_frequencia": 1,
                              "tamanho_maximo": 6})
            destino = self.dir / "pastas"
            report.gera_html(destino, kb, periodos, config)
            indice = (destino / "index.html").read_text(encoding="utf-8")
            self.assertIn("Linha do tempo (corpus completo)", indice)
            self.assertTrue((destino / "images" / "linhaDoTempo.svg").exists())
            periodo = (destino / "period0.html").read_text(encoding="utf-8")
            self.assertIn("Pontos de virada", periodo)
            self.assertLess(periodo.index("Rede completa"), periodo.index("Pontos de virada"))
            destino2 = self.dir / "pastas2"
            report.gera_html(destino2, kb, periodos, _config(
                {"unidade": "References", "matriz": "BasicCoupling",
                 "mapeadores": ["acoplamento"], "minimo_frequencia": 1}))
            self.assertNotIn("Linha do tempo (corpus completo)",
                             (destino2 / "index.html").read_text(encoding="utf-8"))
            self.assertFalse((destino2 / "images" / "linhaDoTempo.svg").exists())

    def test_halo_com_e_sem_pivos(self):
        with ProjetoRedes(self.projeto) as kb:
            config = _config({"unidade": "Words", "minimo_frequencia": 1,
                              "tamanho_maximo": 6})
            r = pipeline.executa_periodo(kb, kb.periodos()[0].id, "p", config)
            pv = metodo.pivos_para_halo(kb, r)
        padrao = halo_svg(r, "t")
        self.assertEqual(padrao, halo_svg(r, "t", pivos=None))
        self.assertEqual(padrao, halo_svg(r, "t", pivos=[]))
        self.assertNotIn("ponto de virada", padrao)
        self.assertTrue(pv)
        marcado = halo_svg(r, "t", pivos=pv)
        self.assertIn("ponto de virada", marcado)
        self.assertNotEqual(padrao, marcado)
        # ids soltos e inexistentes: ignora os que não estão na rede
        com_id = halo_svg(r, "t", pivos=[next(iter(r.rede.nos)), 10 ** 9])
        self.assertIn("ponto de virada", com_id)


class InterfaceTest(unittest.TestCase):
    """Checagens estáticas da aba, do reset e do menu (o fluxo vivo está nos prints Playwright)."""

    @classmethod
    def setUpClass(cls):
        cls.js = (UI / "app.js").read_text(encoding="utf-8")
        cls.html = (UI / "index.html").read_text(encoding="utf-8")

    def test_aba_ao_lado_do_dendrograma(self):
        ordem = [m for m in re.findall(r'data-aba="([a-z]+)"', self.html)]
        self.assertEqual(ordem.index("dendrograma") + 1, ordem.index("linhatempo"))
        self.assertIn('id="blocoLinhaDoTempo"', self.html)
        self.assertIn('linhatempo: "blocoLinhaDoTempo"', self.js)
        config = re.search(r"const CONFIG_ABAS = \{.*?\n\};", self.js, re.S).group(0)
        self.assertEqual(config.count('"linhatempo"'), 6)   # nas análises gerais
        grupos = re.search(r"const GRUPOS_ABAS = \[.*?\];", self.js, re.S).group(0)
        self.assertIn('"linhatempo"', grupos)                 # sempre visível, no bloco Métodos

    def test_reset_ao_trocar_de_projeto_e_de_analise(self):
        projeto = re.search(r"function aplicarProjeto\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("limparLinhaDoTempo(true)", projeto)
        resultado = re.search(r"function renderizarResultado\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("limparLinhaDoTempo(false)", resultado)
        self.assertIn('abaAtual() === "linhatempo"', resultado)
        self.assertIn("renderizarPivos(resultado)", resultado)
        limpa = re.search(r"function limparLinhaDoTempo\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("lt.seq += 1", limpa)                  # ignora respostas atrasadas
        self.assertIn("mensagemLinhaDoTempo", limpa)

    def test_menu_exportar_tem_a_linha_do_tempo(self):
        self.assertIn('data-exp="linhatempo-svg" data-precisa="resultado"', self.html)
        self.assertIn('tipo === "linhatempo-svg"', self.js)
        self.assertIn("MOTIVO_LINHA_DO_TEMPO", self.js)

    def test_secao_de_pivos_na_aba_indices(self):
        indices = re.search(r'<section class="tabela-bloco" id="blocoIndices".*?</section>',
                            self.html, re.S).group(0)
        self.assertIn('id="pivosBloco"', indices)
        self.assertIn("Sigma", indices)


if __name__ == "__main__":
    unittest.main()

"""Regressões das auditorias de qualidade, rótulos novos e interface (itens 1 a 11)."""
from __future__ import annotations

import itertools
import os
import random
import re
import shutil
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from redes import api, metodo, qualidade, rotulos
from redes.kb import ProjetoRedes
from redes.texto import rotulo_legivel
from redes.network import Rede
from redes.pipeline import Configuracao, Grupo, executa_periodo

SERJ = Path("/home/claude/t/serj_auto.redes")
RAIZ = Path(__file__).resolve().parents[1]
UI = RAIZ / "redes" / "ui"


def _rede(n, arestas):
    r = Rede(range(n))
    for a, b, w in arestas:
        r.adiciona_aresta(a, b, w)
    return r


def _grupo(nos, **kw):
    return Grupo(nos=list(nos), principal=nos[0] if nos else None,
                 rotulo=f"G{nos[0]}" if nos else "", **kw)


def _blocos(tam=10, interno=0.6, externo=0.02, blocos=2, semente=1):
    rnd = random.Random(semente)
    n = tam * blocos
    arestas = []
    for a, b in itertools.combinations(range(n), 2):
        if a // tam == b // tam:
            arestas.append((a, b, interno * rnd.uniform(0.8, 1.0)))
        elif rnd.random() < 0.3:
            arestas.append((a, b, externo))
    return _rede(n, arestas), [list(range(i * tam, (i + 1) * tam)) for i in range(blocos)]


def _res(rede, grupos, unidade=None):
    r = SimpleNamespace(rede=rede, grupos=[_grupo(g) for g in grupos])
    if unidade:
        r.configuracao = SimpleNamespace(unidade=unidade)
    return r


# ---------------------------------------------------------------- 1 e 10


class TextoMetodoTest(unittest.TestCase):

    def test_rede_fragmentada_descreve_o_criterio_do_codigo(self):
        texto = metodo._texto_qualidade(Configuracao(unidade="Words"))
        self.assertNotIn("mais da metade dos componentes", texto)
        self.assertIn("mais componentes do que a metade dos itens", texto)
        self.assertIn("menos de 2 itens", texto)
        # o código testa exatamente isso
        fonte = (RAIZ / "redes" / "qualidade.py").read_text(encoding="utf-8")
        self.assertIn("comp > n_nos / 2", fonte)

    def test_limite_de_nos_vem_da_constante(self):
        self.assertEqual(2000, qualidade.LIMITE_NOS)
        self.assertEqual(qualidade.LIMITE_NOS,
                         qualidade.avalia.__defaults__[0])
        texto = metodo._texto_qualidade(Configuracao(unidade="Words"))
        self.assertIn(f"mais de {qualidade.LIMITE_NOS} itens", texto)
        self.assertNotIn("mais de 400 itens", texto)

    def test_silhueta_roda_ate_o_limite_novo(self):
        rede, grupos = _blocos(tam=30, blocos=3)
        sil = qualidade._silhuetas_validas(rede, [_grupo(g) for g in grupos],
                                           qualidade.LIMITE_NOS)
        self.assertIsNotNone(sil)
        self.assertIsNone(qualidade._silhuetas_validas(
            rede, [_grupo(g) for g in grupos], 50))


# ---------------------------------------------------------------- 2


class TabelaPortoesTest(unittest.TestCase):

    def _sil(self, resultado, **kw):
        return [l["silhueta"] for l in qualidade.tabela_grupos(resultado, **kw)]

    def test_avaliavel_tem_silhueta(self):
        rede, grupos = _blocos()
        self.assertTrue(all(s is not None for s in self._sil(_res(rede, grupos))))

    def test_poucos_itens_indefinido_sem_silhueta(self):
        rede, grupos = _blocos(tam=6)               # 12 itens < 15
        res = _res(rede, grupos)
        self.assertEqual("indefinido", qualidade.avalia(res)["nivel"])
        self.assertEqual([None, None], self._sil(res))

    def test_menos_de_dois_grupos_sem_silhueta(self):
        rede, grupos = _blocos()
        res = _res(rede, grupos[:1])
        self.assertEqual("indefinido", qualidade.avalia(res)["nivel"])
        self.assertEqual([None], self._sil(res))

    def test_sem_ligacoes_sem_silhueta(self):
        res = _res(_rede(20, []), [list(range(10)), list(range(10, 20))])
        self.assertEqual("indefinido", qualidade.avalia(res)["nivel"])
        self.assertEqual([None, None], self._sil(res))

    def test_silhueta_dispensada_pelo_limite(self):
        rede, grupos = _blocos()
        res = _res(rede, grupos)
        self.assertEqual([None, None], self._sil(res, limite_nos=5))

    def test_tabela_do_relatorio_mostra_traco(self):
        rede, grupos = _blocos(tam=6)
        res = _res(rede, grupos)
        res.configuracao = SimpleNamespace(unidade="Words")
        linhas = qualidade.tabela_grupos(res)
        self.assertTrue(all(l["silhueta"] is None for l in linhas))
        self.assertEqual("—", metodo._n2(linhas[0]["silhueta"]))


# ---------------------------------------------------------------- 5


class NumeroTest(unittest.TestCase):

    def test_perto_do_limiar_nao_arredonda_para_ele(self):
        self.assertEqual("0,1496", qualidade._num(0.1496, 2, (0.15, 0.30)))
        self.assertEqual("0,2999", qualidade._num(0.2999, 2, (0.15, 0.30)))
        self.assertEqual("0,146", qualidade._num(0.146, 2, (0.15,)))
        self.assertEqual("0,3004", qualidade._num(0.3004, 2, (0.30,)))

    def test_longe_do_limiar_duas_casas(self):
        self.assertEqual("0,92", qualidade._num(0.92, 2, (0.15, 0.30)))
        self.assertEqual("0,92", qualidade._num(0.92))

    def test_menos_zero_e_sinal_correto(self):
        self.assertEqual("0,00", qualidade._num(-0.0000001))
        self.assertEqual("0,00", qualidade._num(-0.001))
        self.assertEqual("−0,34", qualidade._num(-0.34))
        self.assertNotIn("-", qualidade._num(-0.34))
        self.assertEqual("−0,0004", qualidade._num(-0.0004, 2, (0.0, 0.10)))

    def test_percentuais_perto_de_limiar(self):
        self.assertEqual("29,7", qualidade._num(29.7, 0, (30,)))
        self.assertEqual("59,6", qualidade._num(59.6, 0, (60,)))
        self.assertEqual("45", qualidade._num(45.2, 0, (30, 60)))

    def test_aviso_nao_contradiz_o_selo(self):
        rede, grupos = _blocos()
        with mock.patch.object(qualidade, "modularidade", return_value=0.1496):
            a = qualidade.avalia(_res(rede, grupos))
        self.assertEqual("ok", a["nivel"])          # Q é só nota de nitidez
        texto = " ".join(a["avisos"])
        self.assertIn("0,1496", texto)
        self.assertNotIn("0,15)", texto)

    def test_aviso_de_silhueta_negativa_usa_sinal_e_sem_hifen(self):
        rede, grupos = _blocos()
        falsa = (list(range(20)), None, None)
        with mock.patch.object(qualidade, "_silhuetas_validas") as m:
            import numpy as np
            nos = list(range(20))
            rot = np.array([0] * 10 + [1] * 10)
            m.return_value = (nos, rot, np.full(20, -0.34))
            a = qualidade.avalia(_res(rede, grupos))
        texto = " ".join(a["avisos"])
        self.assertIn("coesão −0,34", texto)
        self.assertNotRegex(texto, r"coesão -")


# ---------------------------------------------------------------- 7 e 9


class CoautoriaTest(unittest.TestCase):

    def test_autores_nunca_ok(self):
        rede, grupos = _blocos()
        ok = qualidade.avalia(_res(rede, grupos, "Words"))
        self.assertEqual("ok", ok["nivel"])
        self.assertNotIn(qualidade.AVISO_COAUTORIA, ok["avisos"])
        aut = qualidade.avalia(_res(rede, grupos, "Authors"))
        self.assertEqual("atencao", aut["nivel"])
        self.assertIn(qualidade.AVISO_COAUTORIA, aut["avisos"])
        self.assertIn("artefato", qualidade.AVISO_COAUTORIA)
        self.assertIn("coautoria", qualidade.AVISO_COAUTORIA)
        self.assertEqual(aut["q"], ok["q"])

    def test_autores_ruim_e_indefinido_ficam(self):
        rede, grupos = _blocos()
        pares = [[2 * i, 2 * i + 1] for i in range(10)]            # só pares: cobertura útil 0%
        self.assertEqual("ruim", qualidade.avalia(_res(rede, pares, "Authors"))["nivel"])
        pequena, g = _blocos(tam=6)
        indef = qualidade.avalia(_res(pequena, g, "Authors"))
        self.assertEqual("indefinido", indef["nivel"])
        self.assertNotIn(qualidade.AVISO_COAUTORIA, indef["avisos"])

    def test_metodo_diz_que_autores_nao_tem_ok(self):
        texto = metodo._texto_qualidade(Configuracao(unidade="Authors"))
        self.assertIn("nunca é <em>OK</em>", texto)
        self.assertNotIn("nunca é <em>OK</em>",
                         metodo._texto_qualidade(Configuracao(unidade="Words")))

    def test_ui_mostra_avisos_no_popover(self):
        js = (UI / "app.js").read_text(encoding="utf-8")
        self.assertIn("for (const aviso of q.avisos) ul.append", js)


class TextosBordaTest(unittest.TestCase):

    def test_rede_vazia(self):
        a = qualidade.avalia(_res(Rede([]), []))
        texto = " ".join(a["avisos"])
        self.assertIn("A rede não tem itens", texto)
        self.assertNotIn("só 0", texto)

    def test_um_item_no_singular(self):
        a = qualidade.avalia(_res(Rede([5]), [[5]]))
        self.assertIn("só 1 item;", " ".join(a["avisos"]))

    def test_varios_itens_no_plural(self):
        rede, grupos = _blocos(tam=3)
        self.assertIn("só 6 itens", " ".join(qualidade.avalia(_res(rede, grupos))["avisos"]))

    def test_js_plural_e_caixa(self):
        js = (UI / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("${grupos.length} agrupamentos", js)
        self.assertNotIn("${resumo.grupos} agrupamentos", js)
        self.assertIn('plural(grupos.length, "agrupamento", "agrupamentos")', js)
        # nomes que vêm dos dados não têm a caixa reescrita
        self.assertIn("tudoMaiusculo", js)
        self.assertRegex(js, r"function maiuscula[\s\S]{0,200}\\p\{Lu\}\\\.")


# ---------------------------------------------------------------- 6 e 8 (estático)


class InterfaceEstaticaTest(unittest.TestCase):

    def test_abas_quebram_linha_sem_cortar(self):
        css = (UI / "style.css").read_text(encoding="utf-8")
        bloco = re.search(r"\n\.abas \{(.*?)\n\}", css, re.S).group(1)
        self.assertIn("flex-wrap: wrap", bloco)
        self.assertNotIn("overflow-x: auto", bloco)
        self.assertNotRegex(css, r"\.abas\.corte-(inicio|fim)\s*\{[^}]*mask-image")

    def test_popover_acima_da_barra_de_exportacao(self):
        css = (UI / "style.css").read_text(encoding="utf-8")
        z = int(re.search(r"\.barra-resultados\.com-popover \{ z-index: (\d+)", css).group(1))
        self.assertGreater(z, 20)             # .acoes-finais usa z-index 20
        self.assertIn(".pop-qualidade.acima", css)
        js = (UI / "app.js").read_text(encoding="utf-8")
        self.assertIn("function posicionarQualidade", js)
        self.assertIn("posicionarQualidade(true)", js)


# ---------------------------------------------------------------- 11


@unittest.skipUnless(SERJ.exists(), "projeto serj_auto ausente")
class CacheCorpusTest(unittest.TestCase):

    def setUp(self):
        rotulos.limpa_cache()
        self.addCleanup(rotulos.limpa_cache)

    def _resultado(self, kb, indice=0):
        p = kb.periodos()[indice]
        config = api._config({"unidade": "Words", "minimo_frequencia": 2})
        return executa_periodo(kb, p.id, p.nome, config)

    def _conta(self, funcao):
        with mock.patch.object(rotulos, "_Corpus", wraps=rotulos._Corpus) as m:
            saida = funcao()
        return saida, m.call_count

    def test_segunda_chamada_reaproveita_e_resultado_igual(self):
        with ProjetoRedes(SERJ) as kb:
            r = self._resultado(kb)
            a, n1 = self._conta(lambda: rotulos.rotula_grupos(kb, r))
            b, n2 = self._conta(lambda: rotulos.rotula_grupos(kb, r))
        self.assertEqual((1, 0), (n1, n2))
        self.assertTrue(a)
        self.assertEqual(a, b)

    def test_nova_conexao_do_mesmo_arquivo_reaproveita(self):
        with ProjetoRedes(SERJ) as kb:
            rotulos.rotula_grupos(kb, self._resultado(kb))
        with ProjetoRedes(SERJ) as kb2:
            _, n = self._conta(lambda: rotulos.rotula_grupos(kb2, self._resultado(kb2)))
        self.assertEqual(0, n)

    def test_outro_periodo_nao_reaproveita(self):
        with ProjetoRedes(SERJ) as kb:
            rotulos.rotula_grupos(kb, self._resultado(kb, 0))
            _, n = self._conta(lambda: rotulos.rotula_grupos(kb, self._resultado(kb, 1)))
        self.assertEqual(1, n)

    def test_limpa_cache_forca_recalculo(self):
        with ProjetoRedes(SERJ) as kb:
            r = self._resultado(kb)
            rotulos.rotula_grupos(kb, r)
            rotulos.limpa_cache()
            _, n = self._conta(lambda: rotulos.rotula_grupos(kb, r))
        self.assertEqual(1, n)

    def test_base_editada_e_outro_projeto_nunca_recebem_cache_velho(self):
        pasta = Path(tempfile.mkdtemp())
        copia = pasta / "copia.redes"
        shutil.copyfile(SERJ, copia)
        with ProjetoRedes(copia) as kb:
            r = self._resultado(kb)
            antes = rotulos.rotula_grupos(kb, r)
            self.assertTrue(antes)
        # edita os títulos da cópia: o marcador de versão muda
        con = sqlite3.connect(copia)
        con.execute("UPDATE Document SET title = 'Zzz qqq ' || idDocument")
        con.commit()
        con.close()
        os.utime(copia, ns=(10**18, 10**18 + 5))
        with ProjetoRedes(copia) as kb:
            r = self._resultado(kb)
            depois, n = self._conta(lambda: rotulos.rotula_grupos(kb, r))
        self.assertEqual(1, n)
        self.assertTrue(depois)
        # o arquivo original continua servindo o seu próprio cache
        with ProjetoRedes(SERJ) as kb:
            rotulos.rotula_grupos(kb, self._resultado(kb))
            _, n = self._conta(lambda: rotulos.rotula_grupos(kb, self._resultado(kb)))
        self.assertEqual(0, n)

    def test_mesmo_tamanho_mesmo_mtime_mas_outra_contagem(self):
        # o marcador inclui a contagem de documentos, não só o arquivo
        pasta = Path(tempfile.mkdtemp())
        a = pasta / "a.redes"
        shutil.copyfile(SERJ, a)
        with ProjetoRedes(a) as kb:
            chave1 = rotulos._chave_cache(kb, [1, 2, 3])
            kb.conexao.execute("CREATE TEMP TABLE x(i)")
            chave2 = rotulos._chave_cache(kb, [1, 2, 3])
            chave3 = rotulos._chave_cache(kb, [1, 2, 4])
        self.assertEqual(chave1, chave2)
        self.assertNotEqual(chave1, chave3)

    def test_sem_arquivo_nao_usa_cache(self):
        self.assertIsNone(rotulos._chave_cache(SimpleNamespace(conexao=None), [1]))
        self.assertIsNone(rotulos._chave_cache(
            SimpleNamespace(caminho=":memory:", conexao=None), [1]))

    def test_edicao_pela_api_limpa_o_cache(self):
        rotulos._cache_corpus["x"] = object()
        with mock.patch.object(api, "_edita_base", return_value={"ok": 1}):
            api.edita_base({"projeto": str(SERJ)})
        self.assertEqual(0, len(rotulos._cache_corpus))
        rotulos._cache_corpus["x"] = object()
        with mock.patch.object(api, "_edita_base", side_effect=RuntimeError("x")):
            with self.assertRaises(RuntimeError):
                api.edita_base({})
        self.assertEqual(0, len(rotulos._cache_corpus))


# ---------------------------------------------------------------- 3 e 4


@unittest.skipUnless(SERJ.exists(), "projeto serj_auto ausente")
class RotuloNovoPrincipalTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rotulos.limpa_cache()
        cls.kb = ProjetoRedes(SERJ)
        p = cls.kb.periodos()[0]
        cls.config = api._config({"unidade": "Words", "minimo_frequencia": 2})
        cls.r = executa_periodo(cls.kb, p.id, p.nome, cls.config)
        cls.novos = rotulos.rotula_grupos(cls.kb, cls.r)
        assert cls.novos

    @classmethod
    def tearDownClass(cls):
        cls.kb.fecha()

    def _indice_com_novo(self):
        indice = next(iter(self.novos))
        return indice, self.r.grupos[indice]

    def test_nome_do_grupo(self):
        indice, g = self._indice_com_novo()
        principal, sub, _ = metodo.nome_do_grupo(self.kb, self.r, g)
        self.assertEqual(rotulo_legivel(self.novos[indice]["rotulo"]), principal)
        self.assertEqual(g.exibicao, sub)
        sem = next(x for i, x in enumerate(self.r.grupos) if i not in self.novos)
        p2, s2, ind = metodo.nome_do_grupo(self.kb, self.r, sem)
        self.assertEqual((sem.exibicao, None, False), (p2, s2, ind))

    def test_rede_de_um_agrupamento_figura(self):
        from redes.viz.cluster import rede_agrupamento_svg
        indice, g = self._indice_com_novo()
        titulo = f"{self.r.periodo} — {g.exibicao}"
        padrao = rede_agrupamento_svg(self.r, g, titulo)
        self.assertEqual(padrao, rede_agrupamento_svg(self.r, g, titulo, rotulos=None))
        self.assertEqual(padrao, rede_agrupamento_svg(self.r, g, titulo, rotulos={}))
        com = rede_agrupamento_svg(self.r, g, titulo, rotulos=self.novos)
        self.assertNotEqual(padrao, com)
        novo = rotulo_legivel(self.novos[indice]["rotulo"])
        self.assertIn(novo[:20], com)
        self.assertIn(g.exibicao[:20], com)           # o atual vira subtítulo
        # grupo sem rótulo novo: figura idêntica à padrão
        sem = next(x for i, x in enumerate(self.r.grupos) if i not in self.novos)
        t2 = f"{self.r.periodo} — {sem.exibicao}"
        self.assertEqual(rede_agrupamento_svg(self.r, sem, t2),
                         rede_agrupamento_svg(self.r, sem, t2, rotulos=self.novos))

    def test_rede_de_agrupamentos_figura(self):
        from redes.viz.cluster import rede_de_agrupamentos_svg
        padrao = rede_de_agrupamentos_svg(self.r, "t")
        self.assertEqual(padrao, rede_de_agrupamentos_svg(self.r, "t", rotulos=None))
        com = rede_de_agrupamentos_svg(self.r, "t", rotulos=self.novos)
        # (O atual e o novo podem começar igual e ser cortados no mesmo ponto: só se confere o texto.)
        curto = " · ".join(next(iter(self.novos.values()))["termos"][:2])
        self.assertIn((curto[:1].upper() + curto[1:])[:24], com)

    def test_paginas_e_quadro_do_relatorio_em_pastas(self):
        r = api.gera_relatorio_completo({"projeto": str(SERJ), "formato": "pastas"})
        pasta = api.CACHE / f"rel-{r['token']}"
        achou = False
        for periodo in sorted(pasta.glob("*/period0.html")):
            html = periodo.read_text("utf-8")
            quadro = html[html.index("Métricas e rede de cada agrupamento"):]
            quadro = quadro[:quadro.index("<h2>Agrupamentos</h2>")]
            if 'class="rot-atual"' not in quadro:
                continue
            achou = True
            self.assertRegex(quadro, r'<a href="period0-cluster\d+\.html">[^<]+</a><br>'
                                     r'<span class="rot-atual">')
            paginas = sorted(periodo.parent.glob("period0-cluster*.html"))
            com_novo = [p for p in paginas
                        if "Rótulo atual (item central)" in p.read_text("utf-8")]
            self.assertTrue(com_novo)
            pg = com_novo[0].read_text("utf-8")
            h1 = re.search(r"<h1>(.*?)</h1>", pg).group(1)
            atual = re.search(r"Rótulo atual \(item central\): (.*?)</p>", pg).group(1)
            self.assertNotIn(atual, h1)               # o título é o rótulo novo
            self.assertIn("Nome atual (item central)", pg)
            self.assertNotIn(atual, re.search(r"<title>(.*?)</title>", pg).group(1))
            self.assertNotIn(atual, re.search(r'alt="Rede do agrupamento (.*?)"', pg).group(1))
            figura = (periodo.parent / "images"
                      / com_novo[0].name.replace("period0-cluster", "clusterNetwork-period0-cluster")
                      .replace(".html", ".svg")).read_text("utf-8")
            self.assertIn(re.search(r"<h1>[^—]*— (.*?)</h1>", pg).group(1)[:20], figura)
            self.assertTrue((periodo.parent / "images" / "clusterGraph-period0.svg").exists())
            break
        self.assertTrue(achou, "nenhuma análise com rótulo novo no relatório em pastas")

    def test_relatorio_unico_legendas_e_maior_grupo(self):
        r = api.gera_relatorio_completo({"projeto": str(SERJ), "formato": "unico"})
        html = (api.CACHE / f"rel-{r['token']}" / "relatorio-completo.html").read_text("utf-8")
        self.assertRegex(html, r"Rede do agrupamento \d+, “[^”]+” \(atual: “[^”]+”\)")
        resumo = re.search(r"Resumo por período.*?</table>", html, re.S).group(0)
        self.assertIn('class="rot-atual"', resumo)


@unittest.skipUnless(SERJ.exists(), "projeto serj_auto ausente")
class ChaveDoAgrupamentoTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.kb = ProjetoRedes(SERJ)

    @classmethod
    def tearDownClass(cls):
        cls.kb.fecha()

    def _resultado(self):
        p = self.kb.periodos()[0]
        return executa_periodo(self.kb, p.id, p.nome,
                               api._config({"unidade": "Words", "minimo_frequencia": 2}))

    def test_nomes_por_rotulo_chaveia_pelo_indice(self):
        from redes.viz.halo import nomes_por_rotulo
        r = self._resultado()
        for g in r.grupos:
            g.rotulo = "IGUAL"
        nomes = nomes_por_rotulo(r, {0: {"termos": ["alfa", "beta"]},
                                     1: {"termos": ["gama", "delta"]}})
        self.assertEqual({0: "Alfa · Beta", 1: "Gama · Delta"}, nomes)

    def test_legenda_estrategica_com_rotulos_atuais_repetidos(self):
        from redes.viz.strategic import diagrama_svg
        r = self._resultado()
        self.assertGreaterEqual(len(r.grupos), 2)
        for g in r.grupos:
            g.rotulo = "IGUAL"
        novos = {0: {"termos": ["alfa", "beta"], "rotulo": "alfa · beta"},
                 1: {"termos": ["gama", "delta"], "rotulo": "gama · delta"}}
        svg = diagrama_svg(r, "t", rotulos=novos)
        self.assertIn("Alfa · Beta", svg)
        self.assertIn("Gama · Delta", svg)

    def test_halo_rotulo_sem_grupo_repetido_nao_vaza(self):
        from redes.viz.halo import halo_svg, layout_halo
        r = self._resultado()
        self.assertGreaterEqual(len(r.grupos), 2)
        for g in r.grupos[:2]:
            g.rotulo = ""                          # "Sem grupo" em dois agrupamentos
        novos = {0: {"termos": ["alfa", "beta"], "rotulo": "alfa · beta"},
                 1: {"termos": ["gama", "delta"], "rotulo": "gama · delta"}}
        dados = layout_halo(r, rotulos=novos)
        juntos = next(g for g in dados["grupos"] if g["rotulo"] == "Sem grupo")
        self.assertEqual([0, 1], juntos["indices"])
        self.assertEqual("Sem grupo", juntos["rotulo_curto"])   # nenhum nome vale pelo conjunto
        svg = halo_svg(r, "t", rotulos=novos)
        self.assertNotIn("Alfa · Beta", svg)
        self.assertNotIn("Gama · delta", svg)

    def test_halo_um_agrupamento_usa_o_novo(self):
        from redes.viz.halo import halo_svg, layout_halo
        r = self._resultado()
        novos = {0: {"termos": ["alfa", "beta"], "rotulo": "alfa · beta"}}
        dados = layout_halo(r, rotulos=novos)
        por_atual = {g["rotulo_original"]: g for g in dados["grupos"]}
        g0 = por_atual[r.grupos[0].rotulo]
        self.assertEqual("Alfa · Beta", g0["rotulo_curto"])
        self.assertIn("Alfa · Beta", halo_svg(r, "t", rotulos=novos))
        self.assertEqual(halo_svg(r, "t"), halo_svg(r, "t", rotulos=None))


# ---------------------------------------------------------------- navegador (opcional)


def _playwright_disponivel() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except Exception:
        return False
    return bool(os.environ.get("PLAYWRIGHT_BROWSERS_PATH")) and SERJ.exists()


@unittest.skipUnless(_playwright_disponivel(),
                     "defina PLAYWRIGHT_BROWSERS_PATH para o teste no navegador")
class NavegadorTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.servidor = api.cria_servidor(0, Path(tempfile.mkdtemp()))
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

    def _abre(self, largura, altura, analise):
        pg = self.nav.new_page(viewport={"width": largura, "height": altura})
        self.addCleanup(pg.close)
        pg.goto(self.url)
        pg.wait_for_timeout(500)
        pg.click('summary:has-text("Abrir projeto existente")')
        pg.fill("#caminhoProjeto", str(SERJ))
        pg.click("#btnAbrirCaminho")
        pg.wait_for_timeout(3000)
        pg.evaluate("()=>{const c=document.getElementById('modoAvancado');"
                    "if(!c.checked){c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}))}}")
        pg.click(f"[data-analise={analise}]")
        pg.wait_for_selector("#seloQualidade", state="visible", timeout=60000)
        return pg

    def test_abas_nao_ficam_cortadas(self):
        for largura, altura in ((1280, 720), (1440, 900)):
            for analise in ("conceitual", "paises"):
                pg = self._abre(largura, altura, analise)
                r = pg.evaluate("""()=>{const a=document.querySelector('.abas');
                  const ar=a.getBoundingClientRect();
                  const fora=[...a.querySelectorAll('.aba:not(.oculta)')].filter(e=>{
                    const b=e.getBoundingClientRect(); return b.left<ar.left-1||b.right>ar.right+1}).length;
                  return {fora, rolagem:a.scrollWidth>a.clientWidth+1}}""")
                self.assertEqual({"fora": 0, "rolagem": False}, r, (largura, analise))

    def test_popover_cabe_acima_da_barra_de_exportacao(self):
        pg = self._abre(1280, 720, "autores")
        pg.click("#seloQualidade")
        pg.wait_for_timeout(400)
        r = pg.evaluate("""()=>{const p=document.getElementById('popQualidade').getBoundingClientRect();
          const a=document.querySelector('.acoes-finais').getBoundingClientRect();
          const meio=document.elementFromPoint(p.left+p.width/2,p.bottom-3);
          return {topo:p.top, base:p.bottom, vh:innerHeight, acoes:a.top,
                  visivel: !!meio && !!meio.closest('#popQualidade'),
                  texto: document.getElementById('popQualidade').innerText}}""")
        self.assertGreaterEqual(r["topo"], 0)
        self.assertLessEqual(r["base"], r["vh"])
        self.assertLessEqual(r["base"], r["acoes"] + 1)
        self.assertTrue(r["visivel"])
        self.assertIn("coautoria", r["texto"])
        self.assertRegex(r["texto"], "Atenção|Ruim")

    def test_nomes_legiveis_preservam_caixa_dos_dados(self):
        pg = self._abre(1280, 720, "conceitual")
        r = pg.evaluate("""()=>({
          a: nomeLegivel('Lee H.S.', 'Authors'), b: nomeLegivel('LEE H.S.', 'Authors'),
          c: nomeLegivel('South Africa', 'Words'), d: nomeLegivel('SOUTH-AFRICA', 'Words'),
          e: itemLegivel('South Africa', 'Words'), f: itemLegivel('STATISTICAL-REASONING', 'Words'),
          g: maiuscula('Lee H.S.'), h: maiuscula('lee h.s.'), i: maiuscula('probability'),
          j: numeroOuTraco(-0.001, 2), k: numeroOuTraco(-0.34, 2), l: numeroOuTraco(0.5, 2)})""")
        self.assertEqual("Lee H.S.", r["a"])
        self.assertEqual("Lee H.S.", r["b"])
        self.assertEqual("South Africa", r["c"])
        self.assertEqual("South africa", r["d"])       # tudo em maiúsculas: caixa de frase
        self.assertEqual("South Africa", r["e"])
        self.assertEqual("statistical reasoning", r["f"])
        self.assertEqual("Lee H.S.", r["g"])
        self.assertEqual("Lee h.s.", r["h"])
        self.assertEqual("Probability", r["i"])
        self.assertEqual("0,00", r["j"])
        self.assertEqual("−0,34", r["k"])
        self.assertEqual("0,50", r["l"])


if __name__ == "__main__":
    unittest.main()

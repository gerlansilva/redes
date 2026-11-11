"""Qualidade dos agrupamentos: Q, silhueta, níveis e tabela por grupo."""
from __future__ import annotations

import itertools
import random
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import networkx as nx

from scimatpy import qualidade
from scimatpy.network import Rede
from scimatpy.pipeline import Grupo

SERJ = Path("/home/claude/t/serj_auto.redes")


def _rede(n, arestas):
    r = Rede(range(n))
    for a, b, w in arestas:
        r.adiciona_aresta(a, b, w)
    return r


def _grupo(nos, **kw):
    return Grupo(nos=list(nos), principal=nos[0] if nos else None,
                 rotulo=f"G{nos[0]}" if nos else "", **kw)


def _res(rede, grupos):
    return SimpleNamespace(rede=rede, grupos=[_grupo(g) if not isinstance(g, Grupo) else g
                                              for g in grupos])


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


# ---- implementações independentes ----------------------------------------


def q_networkx(rede, grupos):
    g = nx.Graph()
    g.add_nodes_from(rede.nos)
    for a, b, w in rede.arestas():
        if w > 0:
            g.add_edge(a, b, weight=w)
    comunidades = [set(c) for c in grupos]
    usados = set().union(*comunidades) if comunidades else set()
    comunidades += [{n} for n in rede.nos if n not in usados]
    return nx.community.modularity(g, comunidades, weight="weight")


def silhuetas_independente(rede, grupos):
    nos = [n for g in grupos for n in g]
    rot = {n: i for i, g in enumerate(grupos) for n in g}
    maximo = max((w for _, _, w in rede.arestas()), default=0.0)
    esc = maximo if maximo > 1 else 1.0

    def d(a, b):
        return 0.0 if a == b else 1.0 - min(1.0, max(0.0, rede.valor(a, b)) / esc)

    saida = {}
    for n in nos:
        propria = [m for m in grupos[rot[n]] if m != n]
        if not propria:
            saida[n] = 0.0
            continue
        a = sum(d(n, m) for m in propria) / len(propria)
        b = min(sum(d(n, m) for m in g) / len(g)
                for i, g in enumerate(grupos) if i != rot[n])
        mx = max(a, b)
        saida[n] = (b - a) / mx if mx > 0 else 0.0
    return saida


class IndicadoresTest(unittest.TestCase):

    def test_dois_blocos_q_alto_e_igual_ao_networkx(self):
        rede, grupos = _blocos()
        a = qualidade.avalia(_res(rede, grupos))
        self.assertGreater(a["q"], 0.4)
        self.assertAlmostEqual(a["q"], q_networkx(rede, grupos), places=9)

    def test_dois_blocos_silhueta_alta_e_igual_a_independente(self):
        rede, grupos = _blocos()
        a = qualidade.avalia(_res(rede, grupos))
        ind = silhuetas_independente(rede, grupos)
        self.assertGreater(a["silhueta_media"], 0.5)
        self.assertAlmostEqual(a["silhueta_media"], sum(ind.values()) / len(ind), places=9)
        self.assertEqual(a["pct_silhueta_negativa"], 0.0)
        self.assertEqual(a["nivel"], "ok")
        self.assertEqual(a["avisos"], [])

    def test_q_ponderado_aleatorio_igual_ao_networkx(self):
        rnd = random.Random(7)
        n = 30
        rede = _rede(n, [(a, b, rnd.uniform(0.01, 3)) for a, b in
                         itertools.combinations(range(n), 2) if rnd.random() < 0.2])
        grupos = [list(range(0, 11)), list(range(11, 20)), list(range(20, 30))]
        a = qualidade.avalia(_res(rede, grupos))
        self.assertAlmostEqual(a["q"], q_networkx(rede, grupos), places=9)

    def test_rede_aleatoria_q_perto_de_zero(self):
        rnd = random.Random(3)
        n = 60
        rede = _rede(n, [(a, b, rnd.uniform(0.2, 1)) for a, b in
                         itertools.combinations(range(n), 2) if rnd.random() < 0.3])
        nos = list(range(n))
        rnd.shuffle(nos)
        grupos = [nos[i:i + 15] for i in range(0, n, 15)]
        a = qualidade.avalia(_res(rede, grupos))
        self.assertLess(abs(a["q"]), 0.05)
        self.assertEqual(a["nivel"], "ruim")

    def test_silhueta_aleatoria_igual_a_independente(self):
        rnd = random.Random(11)
        n = 40
        rede = _rede(n, [(a, b, rnd.uniform(0.05, 2.5)) for a, b in
                         itertools.combinations(range(n), 2) if rnd.random() < 0.25])
        grupos = [list(range(0, 15)), list(range(15, 30)), list(range(30, 38))]  # 38,39 sem grupo
        ind = silhuetas_independente(rede, grupos)
        esperado = sum(ind.values()) / len(ind)
        a = qualidade.avalia(_res(rede, grupos))
        self.assertAlmostEqual(a["silhueta_media"], esperado, places=9)
        self.assertAlmostEqual(
            a["silhueta_por_grupo"][2], sum(ind[x] for x in grupos[2]) / 8, places=9)

    def test_no_sem_grupo_conta_como_grupo_proprio(self):
        rede, grupos = _blocos()
        grupos = [grupos[0], grupos[1][:-2]]       # dois nós ficam de fora
        a = qualidade.avalia(_res(rede, grupos))
        self.assertAlmostEqual(a["q"], q_networkx(rede, grupos), places=9)
        self.assertAlmostEqual(a["pct_agrupados"], 90.0)

    def test_grupo_com_menos_de_3_nos_fora_da_media(self):
        rede, grupos = _blocos(tam=10, blocos=2)
        com_par = [grupos[0], grupos[1][:8], grupos[1][8:]]
        a = qualidade.avalia(_res(rede, com_par))
        self.assertIsNone(a["silhueta_por_grupo"][2])
        self.assertIsNotNone(a["silhueta_por_grupo"][1])
        ind = silhuetas_independente(rede, com_par)
        grandes = [n for g in com_par[:2] for n in g]
        self.assertAlmostEqual(a["silhueta_media"],
                               sum(ind[n] for n in grandes) / len(grandes), places=9)

    def test_q_louvain_e_razao(self):
        rede, grupos = _blocos()
        a = qualidade.avalia(_res(rede, grupos))
        self.assertIsNotNone(a["q_louvain"])
        self.assertAlmostEqual(a["razao"], a["q"] / a["q_louvain"])
        self.assertGreater(a["razao"], 0.9)

    def test_componentes(self):
        rede = _rede(6, [(0, 1, 1), (1, 2, 1), (3, 4, 1)])
        self.assertEqual(qualidade.componentes(rede), 3)
        self.assertEqual(qualidade.componentes(Rede([])), 0)


class IndefinidoTest(unittest.TestCase):

    def _indefinido(self, a, trecho):
        self.assertEqual(a["nivel"], "indefinido")
        for chave in ("q", "q_louvain", "razao", "silhueta_media", "pct_silhueta_negativa"):
            self.assertIsNone(a[chave], chave)
        self.assertTrue(any(trecho in t for t in a["avisos"]), a["avisos"])

    def test_poucos_nos(self):
        rede, grupos = _blocos(tam=6)
        self._indefinido(qualidade.avalia(_res(rede, grupos)), "poucos itens")

    def test_menos_de_dois_grupos(self):
        rede, grupos = _blocos()
        self._indefinido(qualidade.avalia(_res(rede, grupos[:1])), "menos de dois")
        self._indefinido(qualidade.avalia(_res(rede, [])), "menos de dois")

    def test_rede_vazia_e_um_no(self):
        a = qualidade.avalia(_res(Rede([]), []))
        self.assertEqual((a["n_nos"], a["pct_agrupados"], a["componentes"]), (0, 0.0, 0))
        self._indefinido(a, "não tem itens")
        self.assertNotIn("só 0", " ".join(a["avisos"]))
        self._indefinido(qualidade.avalia(_res(Rede([5]), [[5]])), "só 1 item;")

    def test_sem_ligacoes(self):
        rede = _rede(20, [])
        a = qualidade.avalia(_res(rede, [list(range(10)), list(range(10, 20))]))
        self._indefinido(a, "não tem ligações")


class LimiaresTest(unittest.TestCase):
    """Níveis a partir de Q, razão e silhueta, com os números injetados."""

    def _avalia(self, q, ql=None, sil=None):
        rede, grupos = _blocos()
        ql = q if ql is None else ql
        sequencia = iter([q, ql])
        if sil is None:
            sil_ret = None
        else:
            import numpy as np
            nos = list(range(20))
            rot = np.array([0] * 10 + [1] * 10)
            sil_ret = (nos, rot, np.array(sil, dtype=float))
        with mock.patch.object(qualidade, "modularidade", lambda *_: next(sequencia)), \
                mock.patch.object(qualidade, "_silhuetas_validas", lambda *_: sil_ret):
            return qualidade.avalia(_res(rede, grupos))

    def test_q(self):
        self.assertEqual(self._avalia(0.14)["nivel"], "ruim")
        self.assertEqual(self._avalia(0.15)["nivel"], "atencao")
        self.assertEqual(self._avalia(0.29)["nivel"], "atencao")
        self.assertEqual(self._avalia(0.30)["nivel"], "ok")

    def test_razao(self):
        a = self._avalia(0.4, ql=0.8)       # 0,5
        self.assertEqual(a["nivel"], "atencao")
        self.assertEqual(self._avalia(0.4, ql=0.6)["nivel"], "ok")   # 0,67
        self.assertIsNone(self._avalia(0.4, ql=0.0)["razao"])
        self.assertEqual(self._avalia(0.4, ql=0.0)["nivel"], "ok")

    def test_silhueta(self):
        self.assertEqual(self._avalia(0.5, sil=[-0.05] * 20)["nivel"], "ruim")
        self.assertEqual(self._avalia(0.5, sil=[0.04] * 20)["nivel"], "atencao")
        self.assertEqual(self._avalia(0.5, sil=[0.05] * 20)["nivel"], "ok")     # limiar: < 0,05
        self.assertEqual(self._avalia(0.5, sil=[0.2] * 20)["nivel"], "ok")

    def test_muitas_silhuetas_negativas(self):
        sil = [0.6] * 13 + [-0.1] * 7           # 35% negativos, média > 0,05
        a = self._avalia(0.5, sil=sil)
        self.assertEqual(a["nivel"], "atencao")
        self.assertAlmostEqual(a["pct_silhueta_negativa"], 35.0)

    def test_pouco_agrupados(self):
        rede, grupos = _blocos(tam=10, blocos=2)
        g60 = [grupos[0][:6], grupos[1][:6]]              # 12 de 20 = 60%: sem aviso
        self.assertFalse(any("entraram em agrupamentos" in t
                             for t in qualidade.avalia(_res(rede, g60))["avisos"]))
        grupos = [grupos[0][:5], grupos[1][:6]]           # 55%
        a = qualidade.avalia(_res(rede, grupos))
        self.assertIn(a["nivel"], ("atencao", "ruim"))
        self.assertTrue(any("55%" in t and "entraram em agrupamentos" in t
                            for t in a["avisos"]), a["avisos"])

    def test_rede_fragmentada_nunca_e_ok(self):
        arestas = [(2 * i, 2 * i + 1, 0.9) for i in range(20)]     # 20 pares
        rede = _rede(45, arestas)                                  # + 5 isolados
        grupos = [[2 * i, 2 * i + 1] for i in range(20)]
        a = qualidade.avalia(_res(rede, grupos))
        self.assertGreater(a["q"], 0.5)                            # Q alto...
        self.assertGreater(a["componentes"], a["n_nos"] / 2)
        self.assertEqual(a["nivel"], "atencao")                    # ...mas não é ok
        self.assertTrue(any("fragmentada" in t for t in a["avisos"]))

    def test_limite_nos_pula_silhueta(self):
        rede, grupos = _blocos()
        a = qualidade.avalia(_res(rede, grupos), limite_nos=10)
        self.assertIsNone(a["silhueta_media"])
        self.assertIsNone(a["pct_silhueta_negativa"])
        self.assertIsNotNone(a["q"])
        self.assertTrue(any("grande" in t for t in a["avisos"]))


class RobustezTest(unittest.TestCase):

    def test_determinismo(self):
        rede, grupos = _blocos(blocos=3, semente=5)
        a = qualidade.avalia(_res(rede, grupos))
        b = qualidade.avalia(_res(rede, grupos))
        self.assertEqual(a, b)

    def test_desempenho_150_nos(self):
        rede, grupos = _blocos(tam=15, blocos=10, semente=2)
        t = time.time()
        a = qualidade.avalia(_res(rede, grupos))
        qualidade.tabela_grupos(_res(rede, grupos))
        self.assertLess(time.time() - t, 2.0)
        self.assertEqual(a["n_nos"], 150)

    def test_grupos_de_um_no(self):
        rede, grupos = _blocos()
        a = qualidade.avalia(_res(rede, grupos))
        grupos2 = [grupos[0], grupos[1][:9], [grupos[1][9]]]
        b = qualidade.avalia(_res(rede, grupos2))
        self.assertIsNone(b["silhueta_por_grupo"][2])
        self.assertAlmostEqual(b["q"], q_networkx(rede, grupos2), places=9)
        self.assertEqual(a["n_grupos"], 2)


class TabelaTest(unittest.TestCase):

    def test_ordem_quadrante_ano_e_rotulo_novo(self):
        rede, grupos = _blocos(tam=10, blocos=2)
        g_pequeno = _grupo(grupos[0][:4], centralidade_faixa=0.2, densidade_faixa=0.9)
        g_pequeno.documentos["nucleo"] = {1, 2}
        g_grande = _grupo(grupos[1] + [], centralidade_faixa=0.9, densidade_faixa=0.9,
                          centralidade=3.0, densidade=7.0)
        g_grande.documentos["nucleo"] = {1, 2, 3, 4}
        g_vazio = _grupo(grupos[0][4:], centralidade_faixa=0.6, densidade_faixa=0.1)
        res = _res(rede, [g_pequeno, g_grande, g_vazio])
        t = qualidade.tabela_grupos(res, {1: {"rotulo": "a · b"}},
                                    anos={1: 2000, 2: 2010, 3: 2020})
        self.assertEqual([l["indice"] for l in t], [1, 2, 0])
        self.assertEqual([l["posicao"] for l in t], [1, 2, 3])
        self.assertEqual([l["itens"] for l in t], [10, 6, 4])
        self.assertEqual([l["quadrante"] for l in t], ["Motor", "Básico", "Nicho"])
        self.assertEqual(t[0]["rotulo_novo"], "A · B")
        self.assertIsNone(t[1]["rotulo_novo"])
        self.assertAlmostEqual(t[0]["ano_medio"], 2010.0)       # docs 1,2,3 (4 sem ano)
        self.assertIsNone(t[1]["ano_medio"])                    # sem documentos
        self.assertAlmostEqual(t[2]["ano_medio"], 2005.0)
        self.assertEqual(t[0]["documentos_nucleo"], 4)
        self.assertEqual((t[0]["centralidade"], t[0]["densidade"]), (3.0, 7.0))
        self.assertIsNotNone(t[0]["silhueta"])
        self.assertEqual(t[0]["rotulo"], g_grande.rotulo)

    def test_sem_anos_e_vazio(self):
        rede, grupos = _blocos()
        res = _res(rede, grupos)
        for g in res.grupos:
            g.documentos["nucleo"] = {1}
        self.assertTrue(all(l["ano_medio"] is None for l in qualidade.tabela_grupos(res)))
        self.assertEqual(qualidade.tabela_grupos(_res(Rede([]), [])), [])


@unittest.skipUnless(SERJ.exists(), "projeto serj_auto ausente")
class ProjetoRealTest(unittest.TestCase):

    def test_serj_auto(self):
        from scimatpy import api
        from scimatpy.kb import ProjetoScimat
        from scimatpy.pipeline import executa_periodo
        with ProjetoScimat(SERJ) as kb:
            periodo = kb.periodos()[0]
            cfg = api._config({"unidade": "References", "matriz": "CoOccurrence",
                               "minimo_frequencia": 2})
            res = executa_periodo(kb, periodo.id, periodo.nome, cfg)
            a = qualidade.avalia(res)
            self.assertIn(a["nivel"], ("ok", "atencao", "ruim"))
            self.assertAlmostEqual(a["q"], q_networkx(res.rede, [g.nos for g in res.grupos]), places=9)
            self.assertGreater(a["n_grupos"], 2)
            t = qualidade.tabela_grupos(res, kb=kb)
            self.assertEqual(len(t), len(res.grupos))
            self.assertTrue(any(l["ano_medio"] for l in t))


if __name__ == "__main__":
    unittest.main()

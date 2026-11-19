"""Rótulos automáticos por LLR de Dunning."""
from __future__ import annotations

import math
import sqlite3
import unittest
from pathlib import Path
from types import SimpleNamespace

from redes import rotulos
from redes.dataset import Dataset
from redes.pipeline import Grupo

SERJ = Path("/home/claude/t/serj_auto.redes")


class _Kb:
    """Banco mínimo com as tabelas que `rotulos` lê."""

    def __init__(self):
        self.conexao = sqlite3.connect(":memory:")
        self.conexao.executescript("""
            CREATE TABLE Document(idDocument INTEGER PRIMARY KEY, title VARCHAR, docAbstract VARCHAR);
            CREATE TABLE WordGroup(idWordGroup INTEGER PRIMARY KEY, groupName VARCHAR, stopGroup INTEGER);
            CREATE TABLE Word(idWord INTEGER PRIMARY KEY, wordName VARCHAR, WordGroup_idWordGroup INTEGER);
            CREATE TABLE Document_Word(Document_idDocument INTEGER, Word_idWord INTEGER, isAuthorWord INTEGER);
        """)
        self._w = {}

    def doc(self, i, titulo, resumo=None, palavras=()):
        self.conexao.execute("INSERT INTO Document VALUES (?,?,?)", (i, titulo, resumo))
        for p in palavras:
            if p not in self._w:
                self._w[p] = len(self._w) + 1
                self.conexao.execute("INSERT INTO Word VALUES (?,?,NULL)", (self._w[p], p))
            self.conexao.execute("INSERT INTO Document_Word VALUES (?,?,1)", (i, self._w[p]))


def _resultado(ids, grupos, unidade="Words"):
    ds = Dataset()
    for i in ids:
        ds.adiciona_documento(i)
    gs = []
    for docs in grupos:
        g = Grupo(nos=[1, 2], principal=1, rotulo="x")
        g.documentos["nucleo"] = set(docs)
        gs.append(g)
    return SimpleNamespace(dataset_original=ds, grupos=gs, dataset=ds, rede=None, agregado=None,
                           configuracao=SimpleNamespace(unidade=unidade))


def _corpus(n_grupo=8, n_resto=12, titulos=None):
    """Grupo A: raciocínio probabilístico; resto: software estatístico."""
    kb = _Kb()
    a = list(range(1, n_grupo + 1))
    r = list(range(100, 100 + n_resto))
    for i in a:
        kb.doc(i, f"Probabilistic reasoning of children, case {i}",
               "We examine intuitive judgments about chance events and sampling.",
               ["PROBABILISTIC-REASONING", "CHILDREN"])
    for i in r:
        kb.doc(i, f"Statistical software for classroom data {i}",
               "Spreadsheets and dynamic tools for analysis of data.",
               ["SOFTWARE", "CHILDREN"] if i % 2 else ["SOFTWARE"])
    return kb, a, r


class LlrTest(unittest.TestCase):

    def test_llr_igual_a_g2_direto(self):
        a, nc, b, nr = 7, 10, 3, 40
        n = nc + nr
        obs = [[a, nc - a], [b, nr - b]]
        total_col = [a + b, n - a - b]
        total_lin = [nc, nr]
        g2 = 0.0
        for i in range(2):
            for j in range(2):
                esp = total_lin[i] * total_col[j] / n
                if obs[i][j] > 0:
                    g2 += 2 * obs[i][j] * math.log(obs[i][j] / esp)
        self.assertAlmostEqual(rotulos.llr(a, nc, b, nr), g2, places=9)
        self.assertAlmostEqual(rotulos.llr(5, 10, 10, 20), 0.0, places=9)  # sem associação


class RotulosTest(unittest.TestCase):

    def test_termos_conhecidos_no_corpus_sintetico(self):
        kb, a, r = _corpus()
        out = rotulos.rotula_grupos(kb, _resultado(a + r, [a]))
        self.assertEqual(list(out), [0])
        r0 = out[0]
        self.assertEqual(r0["documentos"], 8)
        self.assertTrue(r0["indicativo"])               # 8 documentos
        self.assertEqual(r0["rotulo"], " · ".join(r0["termos"]))
        texto = " ".join(r0["termos"])
        self.assertIn("probabilistic", texto)
        self.assertNotIn("software", texto)
        self.assertNotIn("children", texto)            # presente nos dois lados
        self.assertLessEqual(len(r0["termos"]), 3)

    def test_n_termos(self):
        kb, a, r = _corpus()
        out = rotulos.rotula_grupos(kb, _resultado(a + r, [a]), n_termos=1)
        self.assertEqual(len(out[0]["termos"]), 1)

    def test_minimo_de_documentos(self):
        kb, a, r = _corpus(n_grupo=4)
        self.assertEqual(rotulos.rotula_grupos(kb, _resultado(a + r, [a])), {})
        kb, a, r = _corpus(n_grupo=5)
        out = rotulos.rotula_grupos(kb, _resultado(a + r, [a]))
        self.assertIn(0, out)
        self.assertTrue(out[0]["indicativo"])

    def test_indicativo_ate_9_documentos(self):
        for n, esperado in ((9, True), (10, False)):
            kb, a, r = _corpus(n_grupo=n, n_resto=20)
            out = rotulos.rotula_grupos(kb, _resultado(a + r, [a]))
            self.assertEqual(out[0]["indicativo"], esperado, n)

    def test_cobertura_acima_de_70_por_cento_sem_contraste(self):
        kb, a, r = _corpus(n_grupo=15, n_resto=5)       # 75%
        self.assertEqual(rotulos.rotula_grupos(kb, _resultado(a + r, [a])), {})
        kb, a, r = _corpus(n_grupo=14, n_resto=6)       # 70%: ainda rotula
        self.assertIn(0, rotulos.rotula_grupos(kb, _resultado(a + r, [a])))

    def test_documentos_sem_texto_ficam_ausentes(self):
        kb = _Kb()
        for i in range(1, 21):
            kb.doc(i, "", None)
        self.assertEqual(rotulos.rotula_grupos(kb, _resultado(range(1, 21), [range(1, 9)])), {})

    def test_termo_em_um_so_documento_descartado(self):
        kb, a, r = _corpus()
        kb.conexao.execute("UPDATE Document SET title='Unico raridade zebra' WHERE idDocument=1")
        out = rotulos.rotula_grupos(kb, _resultado(a + r, [a]), n_termos=10)
        self.assertNotIn("zebra", " ".join(out[0]["termos"]))

    def test_singular_plural_e_acento_unidos(self):
        kb = _Kb()
        for i in range(1, 9):
            titulo = ("Professores e educação matemática" if i % 2
                      else "Professor de educacao matematica")
            kb.doc(i, f"{titulo} {i}")
        for i in range(100, 112):
            kb.doc(i, f"Software livre {i}")
        out = rotulos.rotula_grupos(kb, _resultado(list(range(1, 9)) + list(range(100, 112)),
                                                   [range(1, 9)]), n_termos=5)
        termos = out[0]["termos"]
        # as quatro formas contam como um termo só: aparece uma vez, com 8 documentos
        self.assertEqual(sum("professor" in t for t in termos), 1, termos)
        self.assertEqual(sum("matem" in t for t in termos), 1, termos)

    def test_termo_contido_em_outro_nao_repete(self):
        kb, a, r = _corpus()
        out = rotulos.rotula_grupos(kb, _resultado(a + r, [a]), n_termos=5)
        termos = out[0]["termos"]
        self.assertFalse("probabilistic" in termos and "probabilistic reasoning" in termos)

    def test_determinismo(self):
        kb, a, r = _corpus()
        res = _resultado(a + r, [a, r])
        self.assertEqual(rotulos.rotula_grupos(kb, res), rotulos.rotula_grupos(kb, res))

    def test_dados_sujos_e_caracteres_especiais(self):
        kb = _Kb()
        for i in range(1, 9):
            kb.doc(i, f"Ünïcode «teste» ??? ​ #{i} 日本語 ∑", "©" if i % 2 else None,
                   ["", "A/B-TESTING"] if i % 3 else [])
        for i in range(100, 110):
            kb.doc(i, None, None)
        out = rotulos.rotula_grupos(kb, _resultado(list(range(1, 9)) + list(range(100, 110)),
                                                   [range(1, 9), [], [999]]))
        self.assertIsInstance(out, dict)
        self.assertTrue(set(out) <= {0})

    def test_entradas_vazias(self):
        kb = _Kb()
        self.assertEqual(rotulos.rotula_grupos(kb, _resultado([], [])), {})
        self.assertEqual(rotulos.rotula_grupos(kb, _resultado([1, 2], [])), {})
        self.assertEqual(rotulos.rotula_grupos(kb, _resultado([1, 2], [[1, 2]])), {})
        self.assertEqual(rotulos.rotula_grupos(kb, _resultado([1], [[]])), {})

    def test_palavras_de_resumo_nao_viram_termo(self):
        kb = _Kb()
        for i in range(1, 9):
            kb.doc(i, f"Chance {i}", "Results show that findings suggest chance events.",
                   ["CHANCE"])
        for i in range(100, 112):
            kb.doc(i, f"Software {i}", "Results show that findings suggest tools.", ["SOFTWARE"])
        out = rotulos.rotula_grupos(kb, _resultado(list(range(1, 9)) + list(range(100, 112)),
                                                   [range(1, 9)]), n_termos=6)
        for t in out[0]["termos"]:
            self.assertNotIn("results", t)
            self.assertNotIn("findings", t)

    def test_idiomas_nao_sao_traduzidos(self):
        kb = _Kb()
        for i in range(1, 9):
            kb.doc(i, f"Raciocínio probabilístico em crianças {i}")
        for i in range(100, 112):
            kb.doc(i, f"Ferramentas de software {i}")
        out = rotulos.rotula_grupos(kb, _resultado(list(range(1, 9)) + list(range(100, 112)),
                                                   [range(1, 9)]))
        self.assertTrue(any("probabil" in t for t in out[0]["termos"]))


@unittest.skipUnless(SERJ.exists(), "projeto serj_auto ausente")
class ProjetoRealTest(unittest.TestCase):

    def test_serj_auto(self):
        from redes import api
        from redes.kb import ProjetoRedes
        from redes.pipeline import executa_periodo
        with ProjetoRedes(SERJ) as kb:
            periodo = kb.periodos()[-1]
            for unidade in ("Words", "References"):
                cfg = api._config({"unidade": unidade, "matriz": "CoOccurrence",
                                   "minimo_frequencia": 2})
                res = executa_periodo(kb, periodo.id, periodo.nome, cfg)
                a = rotulos.rotula_grupos(kb, res)
                b = rotulos.rotula_grupos(kb, res)
                self.assertEqual(a, b)
                for i, r in a.items():
                    self.assertTrue(0 <= i < len(res.grupos))
                    self.assertGreaterEqual(r["documentos"], 5)
                    self.assertTrue(1 <= len(r["termos"]) <= 3)
            self.assertTrue(a, "esperava ao menos um rótulo em cocitação")


if __name__ == "__main__":
    unittest.main()


class UnidadesTest(unittest.TestCase):
    def test_tema_so_em_palavras_e_referencias(self):
        kb, a, b = _corpus()
        for unidade, esperado in (("Words", True), ("References", True),
                                  ("Authors", False)):
            r = _resultado(a + b, [set(a)], unidade)
            self.assertEqual(bool(rotulos.rotula_grupos(kb, r)), esperado, unidade)


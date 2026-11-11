import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from redes import dendrograma as dg
from redes.network import Rede
from redes.viz.dendrograma import svg

SERJ = Path("/home/claude/t/serj.redes")


def dois_blocos(tam=4, interno=0.8, ponte=0.1):
    rede = Rede(range(1, 2 * tam + 1))
    blocos = (list(range(1, tam + 1)), list(range(tam + 1, 2 * tam + 1)))
    for bloco in blocos:
        for i in bloco:
            for j in bloco:
                if i < j:
                    rede.adiciona_aresta(i, j, interno)
    rede.adiciona_aresta(tam, tam + 1, ponte)
    verdade = {no: (0 if no <= tam else 1) for no in rede.nos}
    return rede, verdade


class ConstroiTest(unittest.TestCase):
    def test_dois_blocos_corte_em_2(self):
        rede, verdade = dois_blocos()
        res = dg.constroi(rede, grupos_rede=verdade)
        particao = res.corte(n_grupos=2)
        self.assertEqual(len(set(particao.values())), 2)
        comp = res.comparacao(particao)
        self.assertEqual(comp["ari"], 1.0)
        self.assertEqual(comp["nmi"], 1.0)
        self.assertEqual(res["n_grupos_sugerido"], 2)
        self.assertGreater(res["coph"], 0.9)

    def test_formato_linkage(self):
        rede, _ = dois_blocos()
        for ligacao in dg.LIGACOES:
            res = dg.constroi(rede, ligacao=ligacao)
            n = len(rede.nos)
            self.assertEqual(len(res["fusoes"]), n - 1)
            self.assertEqual(res["fusoes"][-1][3], n)
            self.assertEqual(sorted(res["ordem"]), rede.nos)
            altura = res["alturas"]
            self.assertEqual(altura, sorted(altura))
            json.dumps(res)

    def test_ligacoes_na_raiz(self):
        rede, _ = dois_blocos()
        h = {l: dg.constroi(rede, ligacao=l)["alturas"][-1] for l in dg.LIGACOES}
        self.assertLessEqual(h["simples"], h["media"])
        self.assertLessEqual(h["media"], h["completa"])
        self.assertAlmostEqual(h["simples"], 0.9)
        self.assertAlmostEqual(h["completa"], 1.0)

    def test_corte_por_altura_e_extremos(self):
        rede, _ = dois_blocos()
        res = dg.constroi(rede)
        self.assertEqual(len(set(res.corte(altura=0.5).values())), 2)
        self.assertEqual(len(set(res.corte(n_grupos=1).values())), 1)
        self.assertEqual(len(set(res.corte(n_grupos=8).values())), 8)
        with self.assertRaises(ValueError):
            res.corte()
        with self.assertRaises(ValueError):
            res.corte(n_grupos=9)

    def test_ligacao_invalida_e_rede_vazia(self):
        rede, _ = dois_blocos()
        with self.assertRaises(ValueError):
            dg.constroi(rede, ligacao="ward")
        with self.assertRaises(ValueError):
            dg.constroi(Rede([]))

    def test_um_e_dois_nos(self):
        um = dg.constroi(Rede([7]))
        self.assertEqual(um["ordem"], [7])
        self.assertEqual(um.corte(n_grupos=1), {7: 0})
        self.assertIn("único nó", dg.interpreta(um, 1)[0])
        self.assertIn("<svg", svg(um))
        dois = Rede([1, 2])
        dois.adiciona_aresta(1, 2, 0.5)
        res = dg.constroi(dois)
        self.assertAlmostEqual(res["alturas"][0], 0.5)

    def test_normaliza_valores_acima_de_um(self):
        rede = Rede([1, 2, 3])
        rede.adiciona_aresta(1, 2, 10.0)
        rede.adiciona_aresta(2, 3, 5.0)
        res = dg.constroi(rede, ligacao="simples")
        self.assertAlmostEqual(res["alturas"][0], 0.0)
        self.assertAlmostEqual(res["alturas"][1], 0.5)

    def test_comparacao_parcial_e_discordante(self):
        particao = {1: 0, 2: 0, 3: 1, 4: 1}
        self.assertEqual(dg.comparacao(particao, {1: "a", 2: "a", 3: "b", 4: "b"})["ari"], 1.0)
        comp = dg.comparacao(particao, {1: 0, 2: 1, 3: 0, 4: 1})
        self.assertLess(comp["ari"], 0.0 + 1e-9)
        self.assertIsNone(dg.comparacao(particao, {})["ari"])
        self.assertEqual(dg.comparacao(particao, {1: 0, 2: 0, 9: 3})["n_comparados"], 2)


class InterpretaTest(unittest.TestCase):
    def test_frases(self):
        rede, verdade = dois_blocos()
        nomes = {no: f"termo{no}" for no in rede.nos}
        res = dg.constroi(rede, nomes=nomes, pesos={1: 5.0}, grupos_rede=verdade)
        frases = dg.interpreta(res, 2)
        texto = " ".join(frases)
        self.assertIn("2 grupos", texto)
        self.assertIn("maior ramo", texto)
        self.assertIn("pares mais próximos", texto)
        self.assertIn("Concordância alta", texto)
        self.assertNotIn("Aviso", texto)

    def test_avisos(self):
        rede = Rede([1, 2, 3])
        rede.adiciona_aresta(1, 2, 0.5)
        res = dg.constroi(rede)
        texto = " ".join(dg.interpreta(res, 2))
        self.assertIn("apenas 3 nós", texto)

    def test_aviso_cofenetica_baixa(self):
        import random
        gerador = random.Random(3)
        rede = Rede(range(30))
        for i in range(30):
            for j in range(i + 1, 30):
                rede.adiciona_aresta(i, j, gerador.random())
        res = dg.constroi(rede, ligacao="simples")
        if res["coph"] < dg.LIMITE_COPH:
            self.assertIn("cofenética", " ".join(dg.interpreta(res, 3)))
        res["coph"] = 0.3
        self.assertIn("abaixo de 0,6", " ".join(dg.interpreta(res, 3)))


class SvgTest(unittest.TestCase):
    def test_svg_valido_e_acessivel(self):
        rede, verdade = dois_blocos()
        res = dg.constroi(rede, nomes={n: f"t<{n}>&" for n in rede.nos})
        saida = svg(res, n_grupos=2, titulo="Palavras <2020>")
        raiz = ET.fromstring(saida)
        self.assertEqual(raiz.get("role"), "img")
        self.assertNotIn("<script", saida)
        self.assertLessEqual(int(raiz.get("width")), 900)
        ids = [e.get("id") for e in raiz.iter() if e.get("id")]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("corte", saida)
        self.assertIn("&lt;", saida)

    def test_ids_unicos_entre_svgs(self):
        rede, _ = dois_blocos()
        a = svg(dg.constroi(rede), 2)
        b = svg(dg.constroi(rede), 3)
        ids = lambda s: {e.get("id") for e in ET.fromstring(s).iter() if e.get("id")}  # noqa: E731
        self.assertFalse(ids(a) & ids(b))

    def test_rede_grande_cabe_na_largura(self):
        import random
        gerador = random.Random(1)
        rede = Rede(range(200))
        for i in range(200):
            for j in range(i + 1, 200):
                if gerador.random() < 0.1:
                    rede.adiciona_aresta(i, j, gerador.random())
        res = dg.constroi(rede, nomes={i: "palavra muito longa " * 3 for i in range(200)})
        self.assertEqual(ET.fromstring(svg(res, 8)).get("width"), "900")


@unittest.skipUnless(SERJ.exists(), "projeto de exemplo ausente")
class RedeRealTest(unittest.TestCase):
    def test_serj_palavras(self):
        from redes.kb import ProjetoScimat
        from redes.pipeline import Configuracao, executa_periodo

        with ProjetoScimat(SERJ) as kb:
            periodo = kb.periodos()[0]
            resultado = executa_periodo(kb, periodo.id, periodo.nome,
                                        Configuracao(unidade="Words"))
        rede = resultado.rede
        if rede.quantidade_nos() < 3:
            self.skipTest("rede muito pequena")
        grupos = {no: i for i, g in enumerate(resultado.grupos) for no in g.nos}
        nomes = {no: resultado.rotulo(no) for no in rede.nos}
        res = dg.constroi(rede, nomes=nomes, grupos_rede=grupos)
        self.assertEqual(sorted(res["ordem"]), rede.nos)
        k = min(3, len(rede.nos))
        comp = res.comparacao(res.corte(n_grupos=k))
        self.assertTrue(-1.0 <= comp["ari"] <= 1.0)
        self.assertTrue(dg.interpreta(res, k))
        ET.fromstring(svg(res, k, "serj"))


if __name__ == "__main__":
    unittest.main()

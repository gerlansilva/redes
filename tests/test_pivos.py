import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

from scimatpy import measures, pipeline, pivos, rajadas
from scimatpy.api import ProjetoScimat, _config
from scimatpy.network import Rede

SERJ = Path("/home/claude/t/serj_auto.redes")
TAM = 20            # nós por bloco
PONTE = 2 * TAM     # id da ponte
HUB = 2 * TAM + 1   # hub do bloco A


def _anel(rede, base):
    """Anel de TAM nós com vizinhos até 3 passos: sem hubs, muitas rotas curtas."""
    for i in range(TAM):
        for passo in (1, 2, 3):
            rede.adiciona_aresta(base + i, base + (i + passo) % TAM, 1.0)


def _rede_dois_blocos():
    rede = Rede(range(2 * TAM + 2))
    _anel(rede, 0)
    _anel(rede, TAM)
    for i in (0, 5, 10, 15):
        rede.adiciona_aresta(PONTE, i, 1.0)
        rede.adiciona_aresta(PONTE, TAM + i, 1.0)
    for i in range(0, 20, 2):          # hub do bloco A: liga metade do bloco
        rede.adiciona_aresta(HUB, i, 1.0)
    return rede


def _resultado(rede=None, rotulos=None, freq=None, documentos=100, agrupa=True,
               unidade="Words", matriz="CoOccurrence", centralidades=None):
    rede = rede or _rede_dois_blocos()
    grupo_do_no = {}
    if agrupa:
        for no in rede.nos:
            if no < TAM or no == HUB:
                grupo_do_no[no] = 0
            elif no < 2 * TAM:
                grupo_do_no[no] = 1
    rot = rotulos or {}
    return NS(
        configuracao=NS(unidade=unidade, matriz=matriz), rede=rede,
        grupos=[NS(nos=[]), NS(nos=[])] if agrupa else [],
        conjunto=NS(grupo_do_no=grupo_do_no),
        frequencia_nos=freq if freq is not None else {no: 5 for no in rede.nos},
        dataset_original=NS(quantidade_documentos=lambda: documentos),
        centralidades={} if centralidades is None else centralidades,
        rotulo=lambda no: rot.get(no, f"T{no:03d}"))


def _com_rajada(termos):
    """Substitui rajadas.calcula por uma lista fixa de (termo, força)."""
    dados = {"tipo": "palavras", "rajadas": [{"termo": t, "forca": f} for t, f in termos],
             "avisos": []}
    return mock.patch.object(rajadas, "calcula", return_value=dados)


KB = NS(conexao=None)


class PivosSinteticoTest(unittest.TestCase):
    def test_ponte_e_o_pivo(self):
        r = pivos.pontos_de_virada(_resultado())
        self.assertEqual(r["pivos"][0]["no"], PONTE)
        self.assertEqual(r["pivos"][0]["grupos_vizinhos"], 2)

    def test_no_sem_agrupamento_pode_ser_pivo(self):
        p = pivos.pontos_de_virada(_resultado())["pivos"][0]
        self.assertIsNone(p["grupo"])

    def test_hub_de_um_bloco_nao_e_pivo(self):
        res = _resultado()
        bc = measures.intermediacao(res.rede)
        n = res.rede.quantidade_nos()
        positivos = sorted(v for v in bc.values() if v > 0)
        self.assertGreater(bc[HUB], positivos[len(positivos) // 2])  # hub é central...
        r = pivos.pontos_de_virada(res, topo=50)
        self.assertNotIn(HUB, [p["no"] for p in r["pivos"]])  # ...mas só liga um grupo
        self.assertEqual(n, 42)

    def test_campos_e_intermediacao_normalizada(self):
        res = _resultado()
        p = pivos.pontos_de_virada(res)["pivos"][0]
        self.assertEqual(set(p), {"no", "rotulo", "intermediacao", "grau", "grupos_vizinhos",
                                  "grupo", "frequencia", "rajada", "sigma"})
        n = res.rede.quantidade_nos()
        esperado = measures.intermediacao(res.rede)[PONTE] / ((n - 1) * (n - 2) / 2)
        self.assertAlmostEqual(p["intermediacao"], esperado)
        self.assertEqual(p["grau"], 8)
        self.assertEqual(p["frequencia"], 5)

    def test_serializavel(self):
        r = pivos.pontos_de_virada(_resultado(), topo=5)
        self.assertEqual(json.loads(json.dumps(r, ensure_ascii=False))["n_nos"], 42)

    def test_suficiente_com_40_ou_mais(self):
        r = pivos.pontos_de_virada(_resultado())
        self.assertTrue(r["suficiente"])
        self.assertFalse(any("Poucos dados" in a for a in r["avisos"]))

    def test_poucos_nos_nao_suficiente(self):
        rede = Rede(range(12))
        for i in range(11):
            rede.adiciona_aresta(i, i + 1, 1.0)
        res = _resultado(rede)
        res.conjunto.grupo_do_no.update({i: 0 if i < 6 else 1 for i in range(12)})
        r = pivos.pontos_de_virada(res)
        self.assertFalse(r["suficiente"])
        self.assertEqual(r["n_nos"], 12)
        self.assertTrue(any("indício" in a for a in r["avisos"]))
        self.assertTrue(r["pivos"])      # ainda calcula, como indício

    def test_termo_descritor_fora_do_ranking(self):
        freq = {no: 5 for no in range(2 * TAM + 2)}
        freq[PONTE] = 80                      # 80% dos 100 documentos
        r = pivos.pontos_de_virada(_resultado(freq=freq, rotulos={PONTE: "REVISTA"}))
        self.assertNotIn(PONTE, [p["no"] for p in r["pivos"]])
        d = r["termos_descritores"]
        self.assertEqual([x["rotulo"] for x in d], ["REVISTA"])
        self.assertIn("80%", d[0]["motivo"])

    def test_exatamente_50_por_cento_nao_e_descritor(self):
        freq = {no: 5 for no in range(2 * TAM + 2)}
        freq[PONTE] = 50
        r = pivos.pontos_de_virada(_resultado(freq=freq))
        self.assertEqual(r["termos_descritores"], [])
        self.assertEqual(r["pivos"][0]["no"], PONTE)

    def test_acoplamento_nao_tem_descritor(self):
        freq = {no: 99 for no in range(2 * TAM + 2)}
        r = pivos.pontos_de_virada(_resultado(freq=freq, matriz="BasicCoupling"))
        self.assertEqual(r["termos_descritores"], [])

    def test_rede_sem_arestas(self):
        r = pivos.pontos_de_virada(_resultado(Rede(range(50))))
        self.assertEqual(r["pivos"], [])
        self.assertTrue(r["avisos"])

    def test_menos_de_tres_nos(self):
        rede = Rede([0, 1])
        rede.adiciona_aresta(0, 1, 1.0)
        r = pivos.pontos_de_virada(_resultado(rede))
        self.assertEqual((r["pivos"], r["suficiente"]), ([], False))

    def test_sem_agrupamentos(self):
        r = pivos.pontos_de_virada(_resultado(agrupa=False))
        self.assertEqual(r["pivos"], [])
        self.assertTrue(any("agrupamentos" in a for a in r["avisos"]))

    def test_topo_limita(self):
        res = _resultado()
        # grupos alternados: muitos nós com vizinhos em 2 grupos
        res.conjunto.grupo_do_no = {no: no % 2 for no in res.rede.nos}
        r = pivos.pontos_de_virada(res, topo=2)
        self.assertLessEqual(len(r["pivos"]), 2)
        self.assertEqual(len(pivos.pontos_de_virada(res, topo=0)["pivos"]), 0)

    def test_ordenado_por_intermediacao(self):
        res = _resultado()
        res.conjunto.grupo_do_no = {no: no % 2 for no in res.rede.nos}
        valores = [p["intermediacao"] for p in pivos.pontos_de_virada(res, topo=50)["pivos"]]
        self.assertGreater(len(valores), 1)
        self.assertEqual(valores, sorted(valores, reverse=True))

    def test_determinismo_e_desempate_por_rotulo(self):
        rede = Rede(range(4))
        # simetria total: quatro nós com a mesma intermediação em anel
        for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
            rede.adiciona_aresta(a, b, 1.0)
        res = _resultado(rede, rotulos={0: "d", 1: "c", 2: "b", 3: "a"})
        res.conjunto.grupo_do_no = {0: 0, 1: 1, 2: 0, 3: 1}
        a = pivos.pontos_de_virada(res)
        b = pivos.pontos_de_virada(res)
        self.assertEqual(a, b)
        self.assertEqual([p["rotulo"] for p in a["pivos"]], ["a", "b", "c", "d"])

    def test_rotulos_especiais_sem_escape(self):
        rot = {PONTE: '<b>"A&B" – ação\'s</b>'}
        r = pivos.pontos_de_virada(_resultado(rotulos=rot))
        self.assertEqual(r["pivos"][0]["rotulo"], rot[PONTE])

    def test_reaproveita_cache_de_centralidades(self):
        res = _resultado()
        cache = measures.intermediacao(res.rede)
        res.centralidades = {"intermediacao": cache}
        with mock.patch.object(measures, "intermediacao", side_effect=AssertionError):
            r = pivos.pontos_de_virada(res)
        self.assertEqual(r["pivos"][0]["no"], PONTE)

    def test_rede_enorme_e_pulada(self):
        rede = Rede(range(801))
        for i in range(800):
            rede.adiciona_aresta(i, i + 1, 1.0)
        res = _resultado(rede)
        res.conjunto.grupo_do_no = {i: i % 2 for i in range(801)}
        with mock.patch.object(measures, "intermediacao", side_effect=AssertionError):
            r = pivos.pontos_de_virada(res)
        self.assertEqual(r["pivos"], [])
        self.assertTrue(any("pulada" in a for a in r["avisos"]))

    def test_desempenho_150_nos(self):
        rede = Rede(range(150))
        for i in range(150):
            for passo in (1, 2, 7):
                rede.adiciona_aresta(i, (i + passo) % 150, 1.0 + i % 3)
        res = _resultado(rede)
        res.conjunto.grupo_do_no = {i: i // 30 for i in range(150)}
        t = time.time()
        r = pivos.pontos_de_virada(res)
        self.assertLess(time.time() - t, 3.0)
        self.assertEqual(r["n_nos"], 150)


class SigmaTest(unittest.TestCase):
    def test_formula(self):
        self.assertAlmostEqual(pivos.sigma(0.5, 2.0), 2.25)
        self.assertIsNone(pivos.sigma(0.5, None))
        self.assertIsNone(pivos.sigma(0.5, 0))

    def test_so_calcula_para_quem_tem_rajada(self):
        with _com_rajada([("T000", 3.0)]):
            r = pivos.pontos_de_virada(_resultado(rotulos={PONTE: "ponte"}), KB, topo=50)
        self.assertIsNone(r["pivos"][0]["sigma"])     # ponte sem rajada: None, não 1,0
        self.assertIsNone(r["pivos"][0]["rajada"])
        self.assertEqual([x["rotulo"] for x in r["nos_com_rajada"]], ["T000"])
        linha = r["nos_com_rajada"][0]
        self.assertAlmostEqual(linha["sigma"], (linha["intermediacao"] + 1) ** 3.0)
        for p in r["pivos"]:
            self.assertNotEqual(p["sigma"], 1.0)

    def test_casamento_pelo_nome_normalizado(self):
        rot = {PONTE: "Educação-Estatística"}
        with _com_rajada([("educacao estatistica", 2.0)]):
            r = pivos.pontos_de_virada(_resultado(rotulos=rot), KB)
        p = r["pivos"][0]
        self.assertEqual(p["rajada"], 2.0)
        self.assertAlmostEqual(p["sigma"], (p["intermediacao"] + 1) ** 2.0)

    def test_nao_casa_nomes_diferentes(self):
        with _com_rajada([("outro termo", 2.0)]):
            r = pivos.pontos_de_virada(_resultado(rotulos={PONTE: "ponte"}), KB)
        self.assertIsNone(r["pivos"][0]["sigma"])
        self.assertEqual(pivos.tabela_sigma(r), [])

    def test_sem_kb_sem_sigma(self):
        r = pivos.pontos_de_virada(_resultado())
        self.assertTrue(all(p["sigma"] is None for p in r["pivos"]))
        self.assertEqual(pivos.tabela_sigma(r), [])

    def test_outras_unidades_sem_sigma(self):
        with _com_rajada([("T040", 2.0)]) as m:
            r = pivos.pontos_de_virada(_resultado(unidade="Authors"), KB)
        m.assert_not_called()
        self.assertEqual(r["nos_com_rajada"], [])

    def test_rajada_do_descritor_aparece_na_tabela(self):
        freq = {no: 5 for no in range(2 * TAM + 2)}
        freq[PONTE] = 90
        with _com_rajada([("T040", 4.0)]):
            r = pivos.pontos_de_virada(_resultado(freq=freq), KB)
        self.assertEqual(r["termos_descritores"][0]["rajada"], 4.0)
        self.assertEqual([x["no"] for x in pivos.tabela_sigma(r)], [PONTE])

    def test_tabela_ordenada_e_filtrada(self):
        itens = [{"no": 1, "rotulo": "a", "intermediacao": 0.1, "sigma": 1.5},
                 {"no": 2, "rotulo": "b", "intermediacao": 0.3, "sigma": 1.5},
                 {"no": 3, "rotulo": "c", "intermediacao": 0.9, "sigma": None},
                 {"no": 4, "rotulo": "d", "intermediacao": 0.0, "sigma": 9.0}]
        t = pivos.tabela_sigma({"pivos": itens})
        self.assertEqual([i["no"] for i in t], [4, 2, 1])
        self.assertEqual(pivos.tabela_sigma({"pivos": []}), [])
        self.assertEqual(pivos.tabela_sigma({}), [])


@unittest.skipUnless(SERJ.exists(), "projeto de referência ausente")
class PivosProjetoRealTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        copia = cls.dir / "serj.redes"
        shutil.copy(SERJ, copia)
        cls.kb = ProjetoScimat(copia)

    @classmethod
    def tearDownClass(cls):
        cls.kb.fecha()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def _roda(self, unidade, periodo=0):
        p = self.kb.periodos()[periodo]
        cfg = _config({"unidade": unidade, "matriz": "CoOccurrence", "minimo_frequencia": 2})
        res = pipeline.executa_periodo(self.kb, p.id, p.nome, cfg)
        return res, pivos.pontos_de_virada(res, self.kb)

    def test_referencias(self):
        res, r = self._roda("References")
        self.assertTrue(r["suficiente"])
        self.assertTrue(r["pivos"])
        for p in r["pivos"]:
            self.assertGreaterEqual(p["grupos_vizinhos"], 2)
            self.assertGreater(p["intermediacao"], 0)
        json.dumps(r)

    def test_palavras_descritor(self):
        res, r = self._roda("Words")
        nomes = [t["rotulo"] for t in r["termos_descritores"]]
        self.assertIn("STATISTICS-EDUCATION-RESEARCH", nomes)
        self.assertNotIn("STATISTICS-EDUCATION-RESEARCH", [p["rotulo"] for p in r["pivos"]])
        self.assertFalse(r["suficiente"])       # ~24 nós por período

    def test_banco_original_intacto(self):
        import hashlib
        antes = hashlib.md5(SERJ.read_bytes()).hexdigest()
        self._roda("References")
        self.assertEqual(hashlib.md5(SERJ.read_bytes()).hexdigest(), antes)


if __name__ == "__main__":
    unittest.main()

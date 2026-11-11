"""Testes das medidas, dos agrupamentos e dos mapeadores de documentos."""

from __future__ import annotations

import math
import unittest

from redes import mappers, measures, similarity
from redes.clustering import centros_simples, ligacao_simples
from redes.dataset import Dataset
from redes.network import Rede


def _rede() -> Rede:
    rede = Rede([1, 2, 3, 4])
    for a, b, valor in ((1, 2, 1.0), (2, 3, 0.8), (3, 4, 0.6),
                        (1, 4, 0.5), (1, 3, 0.2)):
        rede.adiciona_aresta(a, b, valor)
    return rede


def _rede_itens() -> Rede:
    rede = Rede([10, 11, 12])
    for a, b in ((10, 11), (10, 12), (11, 12)):
        rede.adiciona_aresta(a, b, 1.0)
    return rede


def _dataset() -> Dataset:
    dados = Dataset()
    for doc_id in (1, 2, 3):
        dados.adiciona_documento(doc_id)
    dados.adiciona_item_ao_documento(1, 10, "dez")
    dados.adiciona_item_ao_documento(1, 11, "onze")
    dados.adiciona_item_ao_documento(2, 10, "dez")
    dados.adiciona_item_ao_documento(2, 12, "doze")
    dados.adiciona_item_ao_documento(3, 11, "onze")
    return dados


class SimilaridadeTest(unittest.TestCase):

    def test_formulas(self):
        # frequências 4 e 9, coocorrência 2
        self.assertAlmostEqual(4 / 36, similarity.equivalencia(4, 9, 2))
        self.assertAlmostEqual(2 / 36, similarity.forca_associacao(4, 9, 2))
        self.assertAlmostEqual(0.5, similarity.inclusao(4, 9, 2))
        self.assertAlmostEqual(2 / 11, similarity.jaccard(4, 9, 2))
        self.assertAlmostEqual(4 / 6, similarity.salton(4, 9, 2))

    def test_medidas_conhecidas(self):
        self.assertEqual(set(similarity.MEDIDAS), {
            "AssociationStrength", "EquivalenceIndex", "InclusionIndex",
            "JaccardIndex", "SaltonCosine"})

    def test_normaliza_substitui_pesos(self):
        dados = _dataset()
        rede = Rede([10, 11, 12])
        rede.adiciona_aresta(10, 11, 1)
        rede.adiciona_aresta(11, 12, 2)
        # frequências: 10 e 11 têm 2 documentos; 12 tem 1.
        similarity.normaliza_coocorrencia(dados, rede, "JaccardIndex")
        self.assertAlmostEqual(1 / 3, rede.valor(10, 11), places=6)
        self.assertAlmostEqual(2.0, rede.valor(11, 12), places=6)


class MedidasTest(unittest.TestCase):

    def test_indices_de_desempenho(self):
        citacoes = [10, 8, 5, 4, 3]
        self.assertEqual(4, measures.indice_h(citacoes))
        self.assertEqual(5, measures.indice_g(citacoes))
        self.assertAlmostEqual(math.sqrt(20), measures.indice_hg(citacoes))
        self.assertEqual(0, measures.indice_h([]))
        self.assertEqual(0, measures.indice_g([]))
        self.assertEqual(0.0, measures.indice_hg([]))
        self.assertEqual(0.0, measures.indice_q2([]))

    def test_q2_usa_mediana_dos_h_principais(self):
        # h = 3 (10, 8, 5); h ímpar, mediana dos h primeiros = 8
        self.assertAlmostEqual(math.sqrt(3 * 8),
                               measures.indice_q2([10, 8, 5, 2]))

    def test_faixa_normalizada(self):
        faixas = measures.faixa_normalizada([5.0, 1.0, 3.0])
        for obtido, esperado in zip(faixas, [1.0, 1 / 3, 2 / 3]):
            self.assertAlmostEqual(esperado, obtido)

    def test_callon(self):
        rede = Rede([1, 2, 3])
        rede.adiciona_aresta(1, 2, 2.0)
        rede.adiciona_aresta(2, 3, 3.0)
        self.assertAlmostEqual(30.0, measures.centralidade_callon(rede, [1, 2]))
        self.assertAlmostEqual(100.0, measures.densidade_callon(rede, [1, 2]))

    def test_centralidades(self):
        rede = _rede()
        graus = measures.grau_ponderado(rede)
        self.assertAlmostEqual(1.7, graus[1])
        self.assertAlmostEqual(1.8, graus[2])
        valores = measures.Centralidades(rede)
        self.assertIn("pagerank", valores)
        self.assertAlmostEqual(1.0, sum(valores["pagerank"].values()), places=6)
        self.assertEqual(set(measures.CENTRALIDADES), set(valores))

    def test_centralidades_sob_demanda(self):
        rede = Rede([1, 2])
        rede.adiciona_aresta(1, 2, 1.0)
        valores = measures.Centralidades(rede)
        self.assertEqual({}, valores._cache)
        valores["grau"]
        self.assertEqual({"grau"}, set(valores._cache))


class AgrupamentoTest(unittest.TestCase):

    def test_centros_simples(self):
        resultado = centros_simples(_rede(), 2, 3)
        self.assertEqual(1, len(resultado.agrupamentos))
        grupo = resultado.agrupamentos[0]
        self.assertEqual([1, 2, 3], grupo.nos)
        self.assertIn(grupo.principal, grupo.nos)
        self.assertEqual([4], resultado.nos_sem_grupo())

    def test_ligacao_simples_junta_tudo(self):
        resultado = ligacao_simples(_rede(), 2, 4)
        self.assertEqual([[1, 2, 3, 4]], [g.nos for g in resultado.agrupamentos])
        self.assertEqual([], resultado.nos_sem_grupo())


class MapeadoresTest(unittest.TestCase):

    def test_nucleo_e_secundarios(self):
        rede, dados = _rede_itens(), _dataset()
        self.assertEqual({1}, mappers.nucleo(rede, dados, [10, 11]))
        self.assertEqual({1, 2}, mappers.nucleo(rede, dados, [10, 11, 12]))
        self.assertEqual({2, 3}, mappers.secundarios(rede, dados, [10, 11]))
        self.assertEqual(set(), mappers.secundarios(rede, dados, []))

    def test_interseccao_uniao_e_kcore(self):
        rede, dados = _rede_itens(), _dataset()
        self.assertEqual({1}, mappers.interseccao(rede, dados, [10, 11]))
        self.assertEqual({1, 2, 3}, mappers.uniao(rede, dados, [10, 11]))
        self.assertEqual({1, 2}, mappers.k_core(dados, [10, 11, 12], 2))
        self.assertEqual({1, 2, 3}, mappers.k_core(dados, [10, 11, 12], 1))

    def test_acoplamento_devolve_os_proprios_nos(self):
        self.assertEqual({7, 9}, mappers.acoplamento(Rede([7, 9]), Dataset(),
                                                     [7, 9]))


if __name__ == "__main__":
    unittest.main()

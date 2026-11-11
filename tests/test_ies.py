"""Rede de IES: união conservadora de variantes e componentes pequenos sem agrupamento."""

import tempfile
import unittest
from pathlib import Path

from scimatpy import api, ies, metodo
from scimatpy.build import constroi
from scimatpy.kb import ProjetoScimat
from scimatpy.loaders.base import DocumentoFonte
from scimatpy.pipeline import Configuracao, executa_periodo

T = Path("/home/claude/t")


def _doc(i, *afiliacoes):
    return DocumentoFonte(titulo=f"Doc {i}", autores=[f"Autor, A{i}."], ano="2019",
                          afiliacoes=list(afiliacoes), palavras_autor=["estatistica"])


def _projeto() -> Path:
    docs = [
        # Componente grande: USP (3 grafias), UFSCar, Unicamp, Unesp.
        _doc(1, "Dept X, Universidade de São Paulo, São Paulo, Brazil",
             "Universidade Federal de São Carlos, São Carlos, Brazil",
             "Universidade Estadual de Campinas, Campinas, Brazil"),
        _doc(2, "Universidade de Sao Paulo, Brazil", "Universidade Estadual Paulista, Brazil",
             "Universidade Federal de São Carlos, Brazil"),
        _doc(3, "Dept Y, Univ. Sao Paulo - Brazil, Brazil", "UNIVERSIDADE ESTADUAL DE CAMPINAS, Brazil"),
        # Par (componente de 2) e instituição isolada.
        _doc(4, "University of Oxford, Oxford, United Kingdom",
             "University of Cambridge, Cambridge, United Kingdom"),
        _doc(5, "Hospital Foo, Atlantis"),
        # Mesmo nome em países diferentes: não une.
        _doc(6, "Universidad Nacional, Bogotá, Colombia",
             "Universidad Nacional, Buenos Aires, Argentina"),
        # Parecidas, mas não inequívocas: não une.
        _doc(7, "Universidade Federal de São Paulo, São Paulo, Brazil",
             "Federal University of São Carlos, Brazil"),
    ]
    destino = Path(tempfile.mkdtemp()) / "ies.redes"
    constroi(docs, destino, periodos=[("Todos", 2019, 2019)])
    return destino


class ChaveTest(unittest.TestCase):
    def test_variantes_inequivocas_tem_a_mesma_chave(self):
        iguais = [
            ("Universidade de São Paulo", "Universidade de Sao Paulo"),
            ("Universidade de São Paulo", "UNIVERSIDADE DE SÃO PAULO"),
            ("Universidade de São Paulo", "Univ. Sao Paulo"),
            ("University of Auckland", "The University of Auckland"),
            ("Universidade de São Paulo", "Universidade de São Paulo (USP)"),
            ("Universidade de São Paulo", "Universidade de São Paulo - Brazil"),
            ("Tel Aviv University.", "Tel Aviv University"),
            ("Universidad de Granada", "University of Granada"),
        ]
        for a, b in iguais:
            with self.subTest(a=a, b=b):
                self.assertEqual(ies.chave_ies(a), ies.chave_ies(b))

    def test_nomes_diferentes_nao_se_unem(self):
        diferentes = [
            ("Universidade de São Paulo", "Universidade Federal de São Paulo"),
            ("Universidade Federal de São Carlos", "Federal University of São Carlos"),
            ("University of Sydney", "Western Sydney University"),
            ("Universidad Nacional de Colombia", "Universidad Nacional"),
            ("Universidade de Brasília", "Universidade de Brasilia Norte"),
        ]
        for a, b in diferentes:
            with self.subTest(a=a, b=b):
                self.assertNotEqual(ies.chave_ies(a), ies.chave_ies(b))


class UnificaTest(unittest.TestCase):
    def test_unioes_registradas_com_motivo_e_adotado(self):
        indice = ies.unifica([
            (1, "Universidade de São Paulo", "Brasil"),
            (2, "Universidade de São Paulo", "Brasil"),
            (3, "Universidade de Sao Paulo", "Brasil"),
            (4, "Univ. Sao Paulo - Brazil", ""),
            (5, "Universidade Federal de São Paulo", "Brasil"),
        ])
        self.assertEqual(1, len(indice.unioes))
        uniao = indice.unioes[0]
        self.assertEqual("Universidade de São Paulo", uniao["adotado"])
        self.assertEqual(4, uniao["documentos"])
        nomes = {v["nome"]: v for v in uniao["variantes"]}
        self.assertEqual({"Universidade de São Paulo", "Universidade de Sao Paulo",
                          "Univ. Sao Paulo - Brazil"}, set(nomes))
        self.assertEqual("nome adotado", nomes["Universidade de São Paulo"]["motivo"])
        self.assertIn("acentos", nomes["Universidade de Sao Paulo"]["motivo"])
        self.assertEqual(2, indice.quantidade_variantes_unidas())
        # A federal continua separada.
        self.assertEqual(2, len(indice.nomes))

    def test_mesmo_nome_em_paises_diferentes_nao_une(self):
        indice = ies.unifica([
            (1, "Universidad Nacional", "Colômbia"),
            (2, "Universidad Nacional", "Argentina"),
            (3, "Universidad Nacional", ""),
        ])
        rotulos = set(indice.nomes.values())
        self.assertIn("Universidad Nacional (Colômbia)", rotulos)
        self.assertIn("Universidad Nacional (Argentina)", rotulos)
        self.assertEqual(3, len(rotulos))
        self.assertEqual([], indice.unioes)

    def test_pais_ausente_entra_no_unico_pais_conhecido(self):
        indice = ies.unifica([
            (1, "University of Oxford", "Reino Unido"),
            (2, "The University of Oxford", ""),
        ])
        self.assertEqual(1, len(indice.nomes))
        self.assertEqual(1, len(indice.unioes))

    def test_ids_estaveis_e_documentos_sem_repeticao(self):
        ocorrencias = [(1, "B Univ", ""), (1, "b univ", ""), (2, "A Univ", "")]
        a = ies.unifica(ocorrencias)
        b = ies.unifica(list(reversed(ocorrencias)))
        self.assertEqual(a.nomes, b.nomes)
        self.assertEqual(1, len(a.por_documento[1]))


class RedeIesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caminho = _projeto()

    def executa(self, **extra):
        with ProjetoScimat(self.caminho) as kb:
            periodo = kb.periodos()[0]
            return executa_periodo(kb, periodo.id, periodo.nome,
                                   Configuracao(unidade="Institutions", **extra))

    def test_variantes_do_projeto_sao_unidas(self):
        r = self.executa()
        nomes = {r.dataset.itens[n] for n in r.rede.nos}
        self.assertIn("Universidade de São Paulo", nomes)
        self.assertNotIn("Universidade de Sao Paulo", nomes)
        self.assertEqual(1, sum(1 for n in nomes if "Campinas" in n))
        # Não unidas: federal x estadual, ordem diferente, país diferente.
        self.assertIn("Universidade Federal de São Paulo", nomes)
        self.assertIn("Federal University of São Carlos", nomes)
        self.assertIn("Universidade Federal de São Carlos", nomes)
        self.assertIn("Universidad Nacional (Colômbia)", nomes)
        self.assertIn("Universidad Nacional (Argentina)", nomes)
        adotados = {u["adotado"] for u in r.ies["unioes"]}
        self.assertIn("Universidade de São Paulo", adotados)
        self.assertIn("Universidade Estadual de Campinas", adotados)
        for uniao in r.ies["unioes"]:
            chaves = {ies.chave_ies(v["nome"]) for v in uniao["variantes"]}
            self.assertEqual(1, len(chaves), uniao)

    def test_componente_menor_que_tres_fica_sem_agrupamento(self):
        r = self.executa()
        por_nome = {r.dataset.itens[n]: n for n in r.rede.nos}
        par = {por_nome["University of Oxford"], por_nome["University of Cambridge"]}
        agrupados = {n for g in r.grupos for n in g.nos}
        self.assertFalse(par & agrupados)
        self.assertTrue(par <= set(r.conjunto.nos_sem_grupo()))
        self.assertIn(por_nome["Hospital Foo"], r.conjunto.nos_sem_grupo())
        self.assertEqual(3, r.ies["componente_minimo"])
        self.assertIn(["University of Cambridge", "University of Oxford"],
                      [sorted(c) for c in r.ies["componentes_pequenos"]])
        self.assertGreaterEqual(r.ies["isolados"], 1)
        # O componente grande (USP, UFSCar, Unicamp, Unesp) continua agrupado.
        grande = {por_nome["Universidade de São Paulo"], por_nome["Universidade Estadual Paulista"]}
        self.assertTrue(grande <= agrupados)

    def test_parametro_um_aceita_todo_componente(self):
        r = self.executa(componente_minimo=1)
        por_nome = {r.dataset.itens[n]: n for n in r.rede.nos}
        agrupados = {n for g in r.grupos for n in g.nos}
        self.assertIn(por_nome["University of Oxford"], agrupados)
        self.assertEqual([], r.ies["componentes_pequenos"])

    def test_parametro_maior_descarta_mais(self):
        r = self.executa(componente_minimo=5)
        agrupados = {n for g in r.grupos for n in g.nos}
        tamanhos = sorted(len(c) for c in r.rede.componentes())
        # Nenhum agrupamento sai de componente com menos de 5 instituições.
        for g in r.grupos:
            comp = next(c for c in r.rede.componentes() if g.nos[0] in c)
            self.assertGreaterEqual(len(comp), 5)
        self.assertTrue(tamanhos)
        self.assertTrue(agrupados <= set(r.rede.nos))

    def test_outras_unidades_nao_mudam(self):
        with ProjetoScimat(self.caminho) as kb:
            periodo = kb.periodos()[0]
            r = executa_periodo(kb, periodo.id, periodo.nome, Configuracao(unidade="Words"))
        self.assertIsNone(r.ies)

    def test_validacao_do_parametro(self):
        with self.assertRaises(ValueError):
            Configuracao(unidade="Institutions", componente_minimo=0).valida()
        with self.assertRaises(api.ErroApi):
            api._config({"unidade": "Institutions", "componente_minimo": 0})
        self.assertEqual(3, api._config({"unidade": "Institutions"}).componente_minimo)
        self.assertEqual(4, api._config({"unidade": "Institutions", "componente_minimo": "4"}).componente_minimo)

    def test_api_devolve_tabela_e_parametro(self):
        resposta = api.analisa({"projeto": str(self.caminho), "unidade": "Institutions"})
        self.assertEqual("Institutions", resposta["parametros"]["unidade"])
        self.assertEqual(3, resposta["parametros"]["componente_minimo"])
        info = resposta["ies"]
        self.assertTrue(info["tabela"])
        self.assertEqual({"adotado", "variante", "documentos", "motivo"}, set(info["tabela"][0]))
        self.assertEqual(3, info["componente_minimo"])
        self.assertGreaterEqual(info["sem_agrupamento"], 3)
        outra = api.analisa({"projeto": str(self.caminho), "unidade": "Words"})
        self.assertIsNone(outra["ies"])

    def test_metodo_descreve_parametro_e_algoritmo(self):
        r = self.executa()
        linhas = metodo.parametros_linhas(r.configuracao)
        rotulos = [a for a, _ in linhas]
        self.assertIn("Tamanho mínimo do componente (IES)", rotulos)
        texto = metodo.algoritmo_html(r.configuracao)
        self.assertIn("variantes unidas", texto)
        self.assertIn("componentes conexos", texto)
        self.assertIn("sem agrupamento", texto)
        tabela = metodo.ies_html(r)
        self.assertIn("Variantes unidas", tabela)
        self.assertIn("Universidade de Sao Paulo", tabela)
        self.assertIn("sem agrupamento", tabela)
        # Outras unidades não ganham texto de IES.
        self.assertNotIn("Nomes das instituições", metodo.algoritmo_html(Configuracao(unidade="Words")))


@unittest.skipUnless(all((T / f"{n}.redes").exists() for n in ("serj_auto", "novo142", "eecera59")),
                     "projetos reais ausentes")
class ProjetosReaisTest(unittest.TestCase):
    def test_projetos_reais(self):
        for nome in ("serj_auto", "novo142", "eecera59"):
            with self.subTest(projeto=nome), ProjetoScimat(T / f"{nome}.redes") as kb:
                indice = kb.indice_ies()
                self.assertTrue(indice.nomes)
                self.assertGreaterEqual(len(indice.unioes), 1)
                for uniao in indice.unioes:
                    self.assertEqual(1, len({ies.chave_ies(v["nome"]) for v in uniao["variantes"]}))
                    self.assertGreaterEqual(len(uniao["variantes"]), 2)
                for periodo in kb.periodos():
                    r = executa_periodo(kb, periodo.id, periodo.nome,
                                        Configuracao(unidade="Institutions"))
                    componente = {no: len(c) for c in r.rede.componentes() for no in c}
                    for grupo in r.grupos:
                        for no in grupo.nos:
                            self.assertGreaterEqual(componente[no], 3)
                    sem = set(r.conjunto.nos_sem_grupo())
                    for comp in r.rede.componentes():
                        if len(comp) < 3:
                            self.assertTrue(set(comp) <= sem)


if __name__ == "__main__":
    unittest.main()

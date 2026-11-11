"""Tamanho mínimo do agrupamento em redes de entidades (Authors, Countries, Institutions)."""

import tempfile
import unittest
from pathlib import Path

from redes import api, cli, metodo
from redes.build import constroi
from redes.kb import ProjetoScimat
from redes.loaders.base import DocumentoFonte
from redes.pipeline import Configuracao, executa_periodo

T = Path("/home/claude/t")


def _projeto() -> Path:
    # Trio A-B-C (2 documentos), pares P1-P2, Q1-Q2 e R1-R2 (1 documento cada), autor isolado.
    grupos = [["A", "B", "C"], ["A", "B", "C"], ["P1", "P2"], ["Q1", "Q2"],
              ["R1", "R2"], ["Solo"]]
    docs = [DocumentoFonte(titulo=f"Doc {i}", autores=a, ano="2019",
                           afiliacoes=[], palavras_autor=["estatistica"])
            for i, a in enumerate(grupos)]
    destino = Path(tempfile.mkdtemp()) / "coautoria.redes"
    constroi(docs, destino, periodos=[("Todos", 2019, 2019)])
    return destino


def _roda(caminho, **config):
    with ProjetoScimat(caminho) as kb:
        periodo = kb.periodos()[0]
        return executa_periodo(kb, periodo.id, periodo.nome, Configuracao(**config))


class FiltroSinteticoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caminho = _projeto()

    def test_padrao_de_autores_nao_filtra(self):
        r = _roda(self.caminho, unidade="Authors")
        self.assertEqual(1, r.configuracao.agrupamento_minimo())
        self.assertEqual(1, r.filtro_agrupamento["minimo"])
        self.assertEqual(r.filtro_agrupamento["grupos_antes"], len(r.grupos))
        self.assertEqual(4, len(r.grupos))      # trio + 3 pares

    def test_tres_descarta_pares_e_mantem_o_trio_e_as_arestas(self):
        base = _roda(self.caminho, unidade="Authors")
        r = _roda(self.caminho, unidade="Authors", componente_minimo=3)
        self.assertEqual(1, len(r.grupos))
        self.assertEqual(4, r.filtro_agrupamento["grupos_antes"])
        self.assertEqual(1, r.filtro_agrupamento["grupos_depois"])
        self.assertEqual(3, r.filtro_agrupamento["componentes_pequenos"])
        self.assertEqual(7, r.filtro_agrupamento["nos_sem_agrupamento"])   # 6 dos pares + Solo
        # Nada some: mesmos nós, mesmas arestas, mesma frequência mínima.
        self.assertEqual(sorted(base.rede.nos), sorted(r.rede.nos))
        self.assertEqual(base.rede.quantidade_arestas(), r.rede.quantidade_arestas())
        self.assertEqual(1, r.configuracao.minimo_frequencia)
        agrupados = {n for g in r.grupos for n in g.nos}
        self.assertEqual(3, len(agrupados))
        self.assertEqual(len(r.rede.nos) - 3, len(r.conjunto.nos_sem_grupo()))

    def test_valor_igual_a_um_e_dois_equivalem_em_pares(self):
        # Pares têm 2 nós: mínimo 2 não descarta nada.
        r1 = _roda(self.caminho, unidade="Authors", componente_minimo=1)
        r2 = _roda(self.caminho, unidade="Authors", componente_minimo=2)
        self.assertEqual(len(r1.grupos), len(r2.grupos))

    def test_qualidade_trata_sem_grupo_como_grupo_proprio(self):
        r = _roda(self.caminho, unidade="Authors", componente_minimo=3)
        sem = r.conjunto.nos_sem_grupo()
        self.assertTrue(sem)
        agrupados = {n for g in r.grupos for n in g.nos}
        self.assertFalse(agrupados & set(sem))

    def test_palavras_nao_sofre_filtro(self):
        r = _roda(self.caminho, unidade="Words", componente_minimo=50)
        self.assertEqual(1, r.configuracao.agrupamento_minimo())
        self.assertIsNone(r.filtro_agrupamento)

    def test_padroes_por_unidade(self):
        self.assertEqual(1, Configuracao(unidade="Authors").agrupamento_minimo())
        self.assertEqual(1, Configuracao(unidade="Countries").agrupamento_minimo())
        self.assertEqual(3, Configuracao(unidade="Institutions").agrupamento_minimo())
        self.assertEqual(1, Configuracao(unidade="Institutions",
                                         componente_minimo=1).agrupamento_minimo())
        with self.assertRaises(ValueError):
            Configuracao(unidade="Authors", componente_minimo=0).valida()


class ApiCliTest(unittest.TestCase):
    def test_api_padroes_e_alias(self):
        self.assertEqual(1, api._config({"unidade": "Authors"}).componente_minimo)
        self.assertEqual(1, api._config({"unidade": "Countries"}).componente_minimo)
        self.assertEqual(3, api._config({"unidade": "Institutions"}).componente_minimo)
        self.assertEqual(4, api._config({"unidade": "Authors",
                                         "tamanho_minimo_agrupamento": "4"}).componente_minimo)
        self.assertEqual(2, api._config({"unidade": "Authors",
                                         "componente_minimo": 2}).componente_minimo)
        # O nome novo vence o antigo quando os dois vêm.
        self.assertEqual(5, api._config({"unidade": "Authors", "componente_minimo": 2,
                                         "tamanho_minimo_agrupamento": 5}).componente_minimo)
        with self.assertRaises(api.ErroApi):
            api._config({"unidade": "Authors", "tamanho_minimo_agrupamento": 0})
        with self.assertRaises(api.ErroApi):
            api._config({"unidade": "Authors", "tamanho_minimo_agrupamento": "inf"})

    def test_cli_aceita_os_dois_nomes(self):
        fonte = Path(cli.__file__).read_text(encoding="utf-8")
        self.assertIn("--tamanho-minimo-agrupamento", fonte)
        self.assertIn("--componente-min", fonte)

    def test_resposta_traz_parametro_e_efeito(self):
        caminho = _projeto()
        resposta = api.analisa({"projeto": str(caminho), "unidade": "Authors",
                                "tamanho_minimo_agrupamento": 3})
        self.assertEqual(3, resposta["parametros"]["tamanho_minimo_agrupamento"])
        self.assertEqual(3, resposta["parametros"]["componente_minimo"])
        self.assertEqual(4, resposta["filtro_agrupamento"]["grupos_antes"])
        self.assertEqual(1, resposta["filtro_agrupamento"]["grupos_depois"])
        self.assertEqual(1, len(resposta["grupos"]))


class TextoRelatorioTest(unittest.TestCase):
    def test_nota_de_relatorio_autores(self):
        caminho = _projeto()
        r = _roda(caminho, unidade="Authors", componente_minimo=3)
        html = metodo.filtro_agrupamento_html(r)
        self.assertIn("menos de 3 autores", html)
        self.assertIn("4 grupos antes do filtro, 1 depois", html)
        self.assertEqual("", metodo.filtro_agrupamento_html(
            _roda(caminho, unidade="Authors")))

    def test_texto_de_algoritmo_menciona_regra(self):
        texto = metodo._texto_ies_componentes(Configuracao(unidade="Authors", componente_minimo=3))
        self.assertIn("menos de 3 autores", texto)
        self.assertIn("frequência mínima não muda", texto)
        self.assertEqual("", metodo._texto_ies_componentes(Configuracao(unidade="Authors")))
        self.assertIn("instituições",
                      metodo._texto_ies_componentes(Configuracao(unidade="Institutions")))


@unittest.skipUnless((T / "serj_auto.redes").exists() and (T / "novo142.redes").exists(),
                     "projetos reais de teste ausentes")
class ProjetosReaisTest(unittest.TestCase):
    def grupos(self, nome, unidade, minimo):
        return len(_roda(T / nome, unidade=unidade, componente_minimo=minimo).grupos)

    def test_autores_serj_auto(self):
        self.assertEqual(39, self.grupos("serj_auto.redes", "Authors", 1))
        self.assertEqual(28, self.grupos("serj_auto.redes", "Authors", 3))

    def test_autores_novo142(self):
        self.assertEqual(101, self.grupos("novo142.redes", "Authors", 1))
        self.assertEqual(69, self.grupos("novo142.redes", "Authors", 3))

    def test_padrao_de_autores_e_paises_nao_muda_resultados(self):
        for nome in ("serj_auto.redes", "novo142.redes"):
            for unidade in ("Authors", "Countries"):
                padrao = len(_roda(T / nome, unidade=unidade).grupos)
                self.assertEqual(self.grupos(nome, unidade, 1), padrao, (nome, unidade))

    def test_instituicoes_mantem_padrao_tres(self):
        self.assertEqual(13, len(_roda(T / "serj_auto.redes", unidade="Institutions").grupos))
        self.assertEqual(29, len(_roda(T / "novo142.redes", unidade="Institutions").grupos))

    def test_filtro_nao_apaga_nos_nem_arestas(self):
        a = _roda(T / "novo142.redes", unidade="Authors")
        b = _roda(T / "novo142.redes", unidade="Authors", componente_minimo=3)
        self.assertEqual(sorted(a.rede.nos), sorted(b.rede.nos))
        self.assertEqual(a.rede.quantidade_arestas(), b.rede.quantidade_arestas())


if __name__ == "__main__":
    unittest.main()

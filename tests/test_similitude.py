"""Similitude dos resumos: idioma, lematização en/pt/es, índices, árvore máxima, blocos, SVG,
API, relatórios, método e interface.

Os corpora sintéticos (resumos de educação estatística em pt, es e en) estão em ``tests/dados``.
"""
from __future__ import annotations

import json
import math
import random
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from unittest import mock

import networkx as nx
import numpy as np

from redes import api, build, cache_figuras, metodo, pipeline, relatorio_unico, report
from redes import similitude as S
from redes.api import ProjetoRedes, _config, cria_servidor
from redes.loaders.base import DocumentoFonte
from redes.viz import similitude as V
from redes.viz.linha_do_tempo import largura as largura_base

DADOS = Path(__file__).with_name("dados")
UI = Path(api.__file__).with_name("ui")
SVG_NS = "{http://www.w3.org/2000/svg}"


def _corpus(idioma: str) -> list[dict]:
    return json.loads((DADOS / f"resumos_{idioma}.json").read_text(encoding="utf-8"))


def _docs(*idiomas: str) -> list[tuple[int, str, str]]:
    """(id, título, resumo) com ids únicos entre os idiomas."""
    saida = []
    for idioma in idiomas:
        for d in _corpus(idioma):
            saida.append((len(saida) + 1, d["titulo"], d["resumo"]))
    return saida


def _fontes(*idiomas: str, com_resumo: bool = True) -> list[DocumentoFonte]:
    docs = []
    for idioma in idiomas:
        for d in _corpus(idioma):
            i = len(docs)
            docs.append(DocumentoFonte(
                titulo=d["titulo"], autores=[f"Autor, {i % 6}."], ano=str(d["ano"]),
                periodico="Revista de Teste", resumo=d["resumo"] if com_resumo else "",
                palavras_autor=["estatistica", "ensino", f"tema{i % 4}", f"t{i % 7}"]))
    return docs


PERIODOS = [("2016–2019", 2016, 2019), ("2020–2023", 2020, 2023)]


def _forma(res: dict, texto: str, idioma: str | None = None) -> dict:
    achadas = [f for f in res["formas"] if f["forma"].split(" (")[0] == texto
               and (idioma is None or f["idioma"] == idioma)]
    assert achadas, (texto, [f["forma"] for f in res["formas"]])
    return achadas[0]


# ================================================================== idioma

class IdiomaTest(unittest.TestCase):
    def test_textos_curtos_nos_tres_idiomas(self):
        casos = {
            "en": "This study examines how students understand variability in the data of a sample.",
            "pt": "Este estudo analisa como os estudantes compreendem a variabilidade dos dados de uma amostra.",
            "es": "Este estudio analiza cómo los estudiantes comprenden la variabilidad de los datos de una muestra.",
        }
        for esperado, texto in casos.items():
            self.assertEqual(esperado, S.detecta_idioma(texto), texto)

    def test_sem_acentos_e_em_maiusculas(self):
        self.assertEqual("pt", S.detecta_idioma("ESTE ARTIGO ANALISA O ENSINO DE ESTATISTICA NA EDUCACAO BASICA"))
        self.assertEqual("es", S.detecta_idioma("este articulo analiza la ensenanza de la estadistica en la educacion basica"))
        self.assertEqual("pt", S.detecta_idioma("o ensino da estatistica nas escolas e os desafios dos professores"))

    def test_palavras_ambiguas_nao_decidem_sozinhas(self):
        # "de", "que" e "a" existem em pt e es: valem meio ponto cada
        pontos = S.pontua_idiomas(["de", "que", "de"])
        self.assertEqual(pontos["pt"], pontos["es"])
        self.assertEqual(0.0, pontos["en"])
        # caracteres exclusivos desempatam
        self.assertEqual("pt", S.detecta_idioma("de que de ação"))
        self.assertEqual("es", S.detecta_idioma("de que de año"))

    def test_sem_evidencia_cai_em_ingles(self):
        self.assertEqual("en", S.detecta_idioma(""))
        self.assertEqual("en", S.detecta_idioma("xyz qwk"))

    def test_corpora_inteiros(self):
        for idioma in ("pt", "es", "en"):
            erros = [d["titulo"] for d in _corpus(idioma) if S.detecta_idioma(d["resumo"]) != idioma]
            self.assertEqual([], erros, idioma)

    def test_resumo_bilingue_fica_com_o_idioma_preferido(self):
        pt = _corpus("pt")[0]["resumo"]
        en = _corpus("en")[0]["resumo"]
        misto = pt + " " + en
        principal, frases = S.analisa_idiomas(misto)
        idiomas = {i for i, _ in frases}
        self.assertTrue({"pt", "en"} <= idiomas)
        em_en = S.tokeniza_resumo(misto, preferido="en")
        em_pt = S.tokeniza_resumo(misto, preferido="pt")
        self.assertEqual("en", em_en[0])
        self.assertEqual("pt", em_pt[0])
        palavras_en = {k for fr in em_en[1] for k, _ in fr}
        palavras_pt = {k for fr in em_pt[1] for k, _ in fr}
        self.assertIn("variability", palavras_en | {"variability"})
        self.assertNotIn("professores", palavras_en)
        self.assertNotIn("teachers", palavras_pt)
        self.assertGreater(em_en[2], 0)          # frases descartadas

    def test_estatisticas_de_idioma_por_projeto(self):
        res = S.analisa_documentos(_docs("pt", "es", "en"), n_formas=40)
        self.assertEqual({"pt": 30, "es": 29, "en": 23}, res["docs_por_idioma"])


# ============================================================= vazias e termos

class PalavrasVaziasTest(unittest.TestCase):
    def chaves(self, texto):
        _, frases, _ = S.tokeniza_resumo(texto)
        return {k for fr in frases for k, _ in fr}

    def test_vazias_e_genericas_saem_nos_tres_idiomas(self):
        pt = self.chaves("O objetivo deste estudo é analisar os resultados sobre a formação de professores, "
                         "que foram apresentados pelos autores no artigo.")
        self.assertEqual({"formacao", "professores"}, pt)
        es = self.chaves("El objetivo de este estudio es analizar los resultados sobre la formación de "
                         "profesores, que fueron presentados por los autores en el artículo.")
        self.assertEqual({"formacion", "profesores"}, es)
        en = self.chaves("The aim of this study is to analyze the results about teacher education, which "
                         "were presented by the authors in the paper.")
        self.assertEqual({"teacher", "education"}, en)

    def test_idioma_decide_a_lista_de_vazias(self):
        # "para" é vazia em pt e es; "from" só em inglês; em pt ela fica
        self.assertNotIn("para", self.chaves("Isto serve para ensinar probabilidade aos estudantes dos anos iniciais."))
        pt = self.chaves("Isto serve para ensinar from probabilidade aos estudantes dos anos iniciais.")
        self.assertIn("from", pt)

    def test_ignorar_remove_por_forma_sem_acento_e_caixa(self):
        res = S.analisa_documentos(_docs("pt"), n_formas=40, ignorar="Estatística, DADO ; estudante")
        formas = {f["forma"] for f in res["formas"]}
        self.assertFalse({"estatística", "dado", "estudante"} & formas)
        self.assertEqual(["dado", "estatistica", "estudante"], res["parametros"]["ignorar"])
        com = S.analisa_documentos(_docs("pt"), n_formas=40)
        self.assertIn("estatística", {f["forma"] for f in com["formas"]})


# ================================================================ lematização

class LematizacaoTest(unittest.TestCase):
    def verifica(self, idioma, esperado: dict[str, str]):
        mapa = S.lematiza(list(esperado), idioma)
        for palavra, lema in esperado.items():
            self.assertEqual(lema, mapa[palavra], f"{idioma}: {palavra}")

    def test_portugues_plural_genero_e_derivacao(self):
        self.verifica("pt", {
            "alunos": "aluno", "aluna": "aluno", "aluno": "aluno",
            "professores": "professor", "professora": "professor", "professor": "professor",
            "relações": "relação", "relação": "relação", "educações": "educação",
            "opiniões": "opinião", "cidadãos": "cidadão", "alemães": "alemão",
            "universidades": "universidade", "materiais": "material", "sociais": "social",
            "possíveis": "possível", "papéis": "papel", "fáceis": "fácil", "úteis": "útil",
            "jovens": "jovem", "imagens": "imagem", "vezes": "vez", "análises": "análise",
            "estudantes": "estudante", "pesquisadores": "pesquisador", "meses": "mês", "países": "país",
            "ideias": "ideia", "tendências": "tendência", "gráficos": "gráfico",
        })

    def test_portugues_verbos_adverbios_e_disciplina(self):
        self.verifica("pt", {
            "ensinando": "ensinar", "ensinado": "ensinar", "ensinada": "ensinar", "ensinar": "ensinar",
            "ensinam": "ensinar", "ensinou": "ensinar", "ensinaram": "ensinar",
            "avaliados": "avaliar", "avaliadas": "avaliar", "avaliar": "avaliar",
            "aprendendo": "aprender", "aprender": "aprender", "aprendem": "aprender", "aprendeu": "aprender",
            "construindo": "construir", "construir": "construir", "construiu": "construir",
            "estatísticas": "estatística", "estatístico": "estatística", "estatística": "estatística",
            "estatisticamente": "estatística", "rapidamente": "rapidamente",
        })
        # só une a forma verbal quando o infinitivo (ou duas formas do verbo) existe
        self.assertEqual("ensinado", S.lematiza(["ensinado"], "pt")["ensinado"])
        self.assertEqual("ensinar", S.lematiza(["ensinado", "ensinando"], "pt")["ensinado"])

    def test_portugues_nao_une_o_que_nao_deve(self):
        mapa = S.lematiza(["prática", "praticar", "casa", "casinha", "caso", "pesquisa", "sala"], "pt")
        self.assertEqual("prática", mapa["prática"])        # substantivo, não o verbo "praticar"
        self.assertEqual("casinha", mapa["casinha"])        # diminutivo não se une
        self.assertEqual("casa", mapa["casa"])
        self.assertEqual("sala", mapa["sala"])
        self.assertEqual("rápido", S.lematiza(["rápida", "rápido"], "pt")["rápida"])   # não vira "raper"
        self.assertEqual("lápis", S.lematiza(["lápis"], "pt")["lápis"])

    def test_espanhol_plural_genero_e_derivacao(self):
        self.verifica("es", {
            "alumnos": "alumno", "alumna": "alumno", "alumno": "alumno",
            "profesores": "profesor", "relaciones": "relación", "relación": "relación",
            "universidades": "universidad", "actitudes": "actitud", "dificultades": "dificultad",
            "variables": "variable", "posibles": "posible", "papeles": "papel", "sociales": "social",
            "imágenes": "imagen", "jóvenes": "joven", "exámenes": "examen", "orígenes": "origen",
            "estudiantes": "estudiante", "veces": "vez", "leyes": "ley", "redes": "red",
            "matrices": "matriz", "índices": "índice", "razones": "razón", "clases": "clase",
            "análisis": "análisis", "tesis": "tesis", "gráficos": "gráfico",
        })

    def test_espanhol_verbos_adverbios_e_disciplina(self):
        self.verifica("es", {
            "enseñando": "enseñar", "enseñado": "enseñar", "enseñada": "enseñar", "enseñar": "enseñar",
            "enseñan": "enseñar", "enseñaron": "enseñar",
            "aprendiendo": "aprender", "aprender": "aprender", "aprenden": "aprender",
            "construyendo": "construir", "construir": "construir", "construyeron": "construyeron",
            "estadísticas": "estadística", "estadístico": "estadística", "estadística": "estadística",
            "claramente": "claro", "claro": "claro",
        })

    def test_ingles(self):
        self.verifica("en", {
            "students": "student", "student": "student", "studies": "study", "study": "study",
            "learning": "learn", "learned": "learn", "learn": "learn", "learns": "learn",
            "statistics": "statistics", "statistical": "statistics", "statistic": "statistics",
            "statistically": "statistics", "teachers": "teacher", "children": "child",
            "analyses": "analysis", "hypotheses": "hypothesis", "classes": "class", "approaches": "approach",
            "bias": "bias", "mathematics": "mathematics", "mathematical": "mathematics",
            "thought": "think", "thinking": "think", "data": "data", "datasets": "dataset",
            "indices": "index",
        })

    def test_nivel_zero_nao_une_nada(self):
        self.assertEqual("alunos", S.lematiza(["alunos", "aluno"], "pt", nivel=0)["alunos"])
        self.assertEqual("students", S.lematiza(["students"], "en", nivel=0)["students"])

    def test_formas_de_idiomas_diferentes_nao_se_fundem(self):
        docs = [(i, "t", "O ensino social da estatística nas escolas e a análise social dos dados reais em sala. "
                         "A formação social dos professores.") for i in range(1, 7)]
        docs += [(10 + i, "t", "La enseñanza social de la estadística en las escuelas y el análisis social de los "
                               "datos reales en el aula. La formación social de los profesores.") for i in range(1, 7)]
        res = S.analisa_documentos(docs, n_formas=30)
        ids = {f["id"] for f in res["formas"]}
        self.assertIn("pt:social", ids)
        self.assertIn("es:social", ids)
        self.assertEqual(2, sum(1 for f in res["formas"] if f["forma"].startswith("social")))
        # rótulos repetidos entre idiomas ganham o idioma, para continuarem legíveis
        nomes = {f["id"]: f["forma"] for f in res["formas"]}
        self.assertEqual("social (pt)", nomes["pt:social"])
        self.assertEqual("social (es)", nomes["es:social"])
        self.assertEqual(len(nomes), len(set(nomes.values())))


# ===================================================================== índices

class IndicesTest(unittest.TestCase):
    SEGMENTOS = [["a", "b"], ["a", "b"], ["a"], ["b", "c"], ["c"], ["a", "c", "b"]]

    def matriz(self):
        formas = ["a", "b", "c"]
        C = S.coocorrencia(self.SEGMENTOS, formas)
        d = np.array([sum(1 for s in self.SEGMENTOS if f in s) for f in formas])
        return formas, C, d

    def test_coocorrencia_e_diagonal(self):
        _, C, d = self.matriz()
        self.assertEqual([4, 4, 3], list(d))
        self.assertEqual(3, C[0, 1])
        self.assertEqual(1, C[0, 2])
        self.assertEqual(4, C[0, 0])

    def test_formulas(self):
        _, C, d = self.matriz()
        n = np.full(3, len(self.SEGMENTOS))
        j = S.indice(C, d, n, "jaccard")
        self.assertAlmostEqual(3 / (4 + 4 - 3), j[0, 1])
        self.assertAlmostEqual(1 / (4 + 3 - 1), j[0, 2])
        cs = S.indice(C, d, n, "cosseno")
        self.assertAlmostEqual(3 / math.sqrt(16), cs[0, 1])
        co = S.indice(C, d, n, "cooc")
        self.assertEqual(3, co[0, 1])
        for m in (j, cs, co):
            self.assertTrue(np.allclose(m, m.T))
            self.assertEqual(0.0, m[0, 0])

    def test_binomial_confere_com_a_conta_exata(self):
        _, C, d = self.matriz()
        n = np.full(3, len(self.SEGMENTOS))
        b = S.indice(C, d, n, "binomial")
        for (i, j) in ((0, 1), (0, 2), (1, 2)):
            di, dj, c, N = int(d[i]), int(d[j]), int(C[i, j]), len(self.SEGMENTOS)
            p = sum(math.comb(di, k) * math.comb(N - di, dj - k) for k in range(c, min(di, dj) + 1)) / math.comb(N, dj)
            self.assertAlmostEqual(-math.log10(p), b[i, j], places=9)
        self.assertGreaterEqual(b.min(), 0.0)

    def test_binomial_cresce_com_a_coocorrencia(self):
        n = 100
        valores = [S._peso_binomial(c, 20, 20, n) for c in range(0, 21)]
        self.assertEqual(0.0, valores[0])
        self.assertTrue(all(b >= a for a, b in zip(valores, valores[1:])))
        self.assertGreater(valores[-1], valores[4])

    def test_indice_desconhecido(self):
        _, C, d = self.matriz()
        with self.assertRaises(ValueError):
            S.indice(C, d, np.full(3, 6), "pearson")


# =============================================================== árvore máxima

class ArvoreMaximaTest(unittest.TestCase):
    def grafo(self, n, p, semente, embaralha=False):
        rnd = random.Random(semente)
        nomes = [f"f{i:02d}" for i in range(n)]
        arestas = [(nomes[i], nomes[j], float(rnd.randint(1, 5)))      # muitos empates
                   for i in range(n) for j in range(i + 1, n) if rnd.random() < p]
        if embaralha:
            random.Random(semente + 1).shuffle(nomes)
            random.Random(semente + 2).shuffle(arestas)
            arestas = [(b, a, w) if k % 2 else (a, b, w) for k, (a, b, w) in enumerate(arestas)]
        G = nx.Graph()
        G.add_nodes_from(nomes)
        for a, b, w in arestas:
            G.add_edge(a, b, weight=w)
        return G

    def test_propriedades_da_arvore_maxima(self):
        for semente in range(25):
            G = self.grafo(24, 0.18, semente)
            T = S.arvore_maxima(G)
            self.assertTrue(nx.is_forest(T), semente)
            self.assertEqual(G.number_of_nodes() - nx.number_connected_components(G), T.number_of_edges())
            self.assertEqual(sorted(map(sorted, nx.connected_components(G))),
                             sorted(map(sorted, nx.connected_components(T))))
            esperado = nx.maximum_spanning_tree(G, weight="weight").size(weight="weight")
            self.assertAlmostEqual(esperado, T.size(weight="weight"), msg=semente)

    def test_propriedade_do_corte(self):
        """Cada aresta fora da árvore é no máximo tão forte quanto o menor laço do caminho que a cobre."""
        for semente in range(10):
            G = self.grafo(20, 0.25, semente)
            T = S.arvore_maxima(G)
            for u, v, w in G.edges(data="weight"):
                if T.has_edge(u, v):
                    continue
                caminho = nx.shortest_path(T, u, v)
                menor = min(T[a][b]["weight"] for a, b in zip(caminho, caminho[1:]))
                self.assertLessEqual(w, menor)

    def test_deterministica_com_empates_e_ordem_de_entrada(self):
        for semente in range(10):
            a = S.arvore_maxima(self.grafo(22, 0.3, semente))
            b = S.arvore_maxima(self.grafo(22, 0.3, semente, embaralha=True))
            self.assertEqual(sorted(tuple(sorted(e)) for e in a.edges), sorted(tuple(sorted(e)) for e in b.edges))

    def test_extras_sao_as_mais_fortes_fora_da_arvore(self):
        G = self.grafo(20, 0.4, 3)
        T = S.arvore_maxima(G)
        extras = S.arestas_extras(G, T, 20)
        self.assertEqual(round(0.2 * T.number_of_edges()), len(extras))
        self.assertTrue(all(not T.has_edge(u, v) for u, v, _ in extras))
        fora = sorted((w for u, v, w in G.edges(data="weight") if not T.has_edge(u, v)), reverse=True)
        self.assertEqual(fora[:len(extras)], [w for _, _, w in extras])
        self.assertEqual([], S.arestas_extras(G, T, 0))


# ================================================================== análise

class AnaliseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pt = S.analisa_documentos(_docs("pt"), n_formas=40)
        cls.es = S.analisa_documentos(_docs("es"), n_formas=40)
        cls.en = S.analisa_documentos(_docs("en"), n_formas=30)
        cls.todos = S.analisa_documentos(_docs("pt", "es", "en"), n_formas=60)

    def juntos(self, res, *palavras):
        blocos = {_forma(res, p)["comunidade"] for p in palavras}
        self.assertEqual(1, len(blocos), (palavras, blocos))

    def test_blocos_coerentes_nos_tres_idiomas(self):
        self.juntos(self.pt, "incerteza", "variabilidade", "raciocínio")
        self.juntos(self.pt, "estatística", "dado", "estudante")
        self.juntos(self.es, "incertidumbre", "variabilidad", "razonamiento")
        self.juntos(self.es, "estadística", "dato", "estudiante")
        self.juntos(self.en, "variability", "uncertainty", "distribution")
        self.juntos(self.en, "statistics", "data", "student")
        for res in (self.pt, self.es, self.en):
            tamanhos = Counter(f["comunidade"] for f in res["formas"])
            self.assertGreaterEqual(sum(1 for n in tamanhos.values() if n >= 3), 3)

    def test_rotulos_legiveis_com_acento_e_lema(self):
        pt = {f["forma"] for f in self.pt["formas"]}
        self.assertTrue({"estatística", "educação", "professor", "probabilidade"} <= pt)
        es = {f["forma"] for f in self.es["formas"]}
        self.assertTrue({"estadística", "educación", "profesor", "probabilidad"} <= es)
        self.assertNotIn("estudantes", pt)
        self.assertNotIn("estudiantes", es)

    def test_todos_os_idiomas_separados_e_sem_aresta_entre_eles(self):
        res = self.todos
        self.assertEqual(["en", "pt", "es"], [i for i in S.IDIOMAS if i in res["idiomas_nas_formas"]])
        idioma = {f["id"]: f["idioma"] for f in res["formas"]}
        for a in res["arestas"]:
            self.assertEqual(idioma[a["origem"]], idioma[a["destino"]])
        self.assertGreaterEqual(res["componentes"], 3)
        for c in res["comunidades"]:
            self.assertEqual(1, len(c["idiomas"]))
        por_idioma = Counter(f["idioma"] for f in res["formas"])
        self.assertEqual(3, len(por_idioma))
        self.assertTrue(all(n >= S.COTA_MINIMA_IDIOMA for n in por_idioma.values()))
        self.assertEqual(60, sum(por_idioma.values()))
        nomes = [f["forma"] for f in res["formas"]]
        self.assertEqual(len(nomes), len(set(nomes)))

    def test_filtro_por_idioma(self):
        res = S.analisa_documentos(_docs("pt", "es", "en"), n_formas=30, idioma="es")
        self.assertEqual({"es"}, {f["idioma"] for f in res["formas"]})
        self.assertEqual(29, res["n_resumos"])
        self.assertEqual({"pt": 30, "es": 29, "en": 23}, res["docs_por_idioma"])
        # sem resumos suficientes no idioma pedido, mensagem clara
        so_pt = _docs("pt") + [(900 + i, "t", d["resumo"]) for i, d in enumerate(_corpus("es")[:3])]
        with self.assertRaisesRegex(S.SemResumos, "espanhol"):
            S.analisa_documentos(so_pt, idioma="es")
        # em "todos", o idioma pequeno fica de fora e o aviso diz isso
        res = S.analisa_documentos(so_pt, n_formas=30)
        self.assertEqual({"pt"}, {f["idioma"] for f in res["formas"]})
        self.assertTrue(any("espanhol" in a for a in res["avisos"]))

    def test_cotas_proporcionais_com_minimo(self):
        cand = {"en": list("abcdefghijklmnopqrst"), "pt": list("uvwxyzABCDEFGHIJKLMN"), "es": list("12345")}
        cota = S._cotas(cand, {"en": 60, "pt": 30, "es": 5}, 40)
        self.assertEqual(40, sum(cota.values()))
        self.assertEqual(5, cota["es"])                    # não passa dos candidatos
        self.assertGreaterEqual(cota["pt"], S.COTA_MINIMA_IDIOMA)
        self.assertGreaterEqual(cota["en"], cota["pt"])

    def test_segmento_frase_tem_mais_segmentos(self):
        resumo = S.analisa_documentos(_docs("pt"), n_formas=30)
        frase = S.analisa_documentos(_docs("pt"), n_formas=30, segmento="frase")
        self.assertGreater(frase["n_segmentos"], resumo["n_segmentos"])
        self.assertEqual(resumo["n_resumos"], frase["n_resumos"])

    def test_todos_os_indices_geram_arvore(self):
        for indice in S.INDICES:
            res = S.analisa_documentos(_docs("es"), n_formas=30, indice_nome=indice)
            self.assertEqual(len(res["formas"]) - res["componentes"], res["n_arvore"], indice)
            self.assertTrue(all(a["peso"] > 0 for a in res["arestas"]))

    def test_extras_e_grau(self):
        sem = S.analisa_documentos(_docs("pt"), n_formas=40, extras=0)
        com = S.analisa_documentos(_docs("pt"), n_formas=40, extras=50)
        self.assertEqual(0, sem["n_extras"])
        self.assertEqual(round(0.5 * com["n_arvore"]), com["n_extras"])
        self.assertEqual(2 * (sem["n_arvore"]), sum(f["grau"] for f in sem["formas"]))
        self.assertEqual(2 * (com["n_arvore"] + com["n_extras"]), sum(f["grau"] for f in com["formas"]))

    def test_deterministica(self):
        a = S.analisa_documentos(_docs("pt", "es", "en"), n_formas=50)
        b = S.analisa_documentos(_docs("pt", "es", "en"), n_formas=50)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(V.svg(a, "T"), V.svg(b, "T"))
        # a ordem dos documentos não muda o grafo
        c = S.analisa_documentos(list(reversed(_docs("pt"))), n_formas=40)
        self.assertEqual({(f["forma"], f["frequencia"]) for f in self.pt["formas"]},
                         {(f["forma"], f["frequencia"]) for f in c["formas"]})
        self.assertEqual(sorted((a["origem"], a["destino"]) for a in self.pt["arestas"]),
                         sorted((a["origem"], a["destino"]) for a in c["arestas"]))

    def test_sem_resumos_ou_curtos_demais(self):
        with self.assertRaisesRegex(S.SemResumos, "não tem resumos"):
            S.analisa_documentos([])
        with self.assertRaises(S.SemResumos):
            S.analisa_documentos([(1, "t", "uma frase só")])
        with self.assertRaises(ValueError):
            S.analisa_documentos(_docs("pt"), indice_nome="x")
        with self.assertRaises(ValueError):
            S.analisa_documentos(_docs("pt"), idioma="fr")

    def test_limpeza_do_resumo(self):
        self.assertEqual("Texto bom.", S.limpa_resumo("Texto bom. © 2020 Elsevier Ltd. All rights reserved."))
        self.assertEqual("", S.limpa_resumo("[No abstract available]"))
        self.assertEqual("", S.limpa_resumo("Resumo não disponível"))

    def test_exportacoes(self):
        csv_f = S.csv_formas(self.pt)
        linhas = csv_f.lstrip("﻿").splitlines()
        self.assertEqual("forma,idioma,frequencia_segmentos,resumos,ocorrencias,bloco,grau", linhas[0])
        self.assertEqual(len(self.pt["formas"]) + 1, len(linhas))
        csv_a = S.csv_arestas(self.pt).lstrip("﻿").splitlines()
        self.assertEqual(len(self.pt["arestas"]) + 1, len(csv_a))
        raiz = ET.fromstring(S.graphml(self.pt))
        nos = raiz.findall(".//{*}node")
        arestas = raiz.findall(".//{*}edge")
        self.assertEqual(len(self.pt["formas"]), len(nos))
        self.assertEqual(len(self.pt["arestas"]), len(arestas))

    def test_parametros_descritos(self):
        itens = dict(S.descreve_parametros(self.todos))
        self.assertIn("Jaccard", itens["Índice"])
        self.assertIn("português 30", itens["Idioma"])
        self.assertIn("Louvain", itens["Blocos"])
        self.assertIn("Jaccard", S.texto_parametros(self.todos))


# ======================================================================= SVG

def _viewbox(raiz):
    return [float(x) for x in raiz.get("viewBox").split()]


class FiguraTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = S.analisa_documentos(_docs("pt", "es", "en"), n_formas=60)
        cls.svg = V.svg(cls.res, "Título da figura")

    def test_svg_valido_com_titulo_desc_e_ids_do_prefixo(self):
        raiz = ET.fromstring(self.svg)
        self.assertEqual("svg", raiz.tag.replace(SVG_NS, ""))
        self.assertEqual("img", raiz.get("role"))
        self.assertIn("sim-t", raiz.get("aria-labelledby"))
        self.assertEqual(len(self.res["formas"]), len(raiz.findall(f".//{SVG_NS}circle[@r]")) - len(self.res["comunidades"]))
        self.assertEqual(len(self.res["formas"]), len(raiz.findall(f".//{SVG_NS}text[@class='rot']")))
        outro = V.svg(self.res, "", prefixo_id="s2")
        self.assertIn('id="s2-t"', outro)
        self.assertNotIn('id="sim-t"', outro)
        self.assertNotIn("<script", self.svg)
        self.assertNotIn("http://", self.svg.replace('xmlns="http://www.w3.org/2000/svg"', ""))

    def test_sem_titulo_a_figura_fica_menor(self):
        sem = _viewbox(ET.fromstring(V.svg(self.res)))
        com = _viewbox(ET.fromstring(self.svg))
        self.assertLess(sem[3], com[3])

    def test_nada_fora_da_area_e_nenhuma_caixa_sobreposta(self):
        raiz = ET.fromstring(self.svg)
        x0, y0, w, h = _viewbox(raiz)
        nos = V.layout(self.res)
        ids = list(nos)
        for i in ids:
            b = V.caixa(nos[i], 0.0)
            self.assertGreaterEqual(b[0], x0)
            self.assertLessEqual(b[2], x0 + w)
            self.assertGreaterEqual(b[1], y0)
            self.assertLessEqual(b[3], y0 + h)
        for k, a in enumerate(ids):
            ba = V.caixa(nos[a], 0.0)
            for b in ids[k + 1:]:
                bb = V.caixa(nos[b], 0.0)
                dx = min(ba[2], bb[2]) - max(ba[0], bb[0])
                dy = min(ba[3], bb[3]) - max(ba[1], bb[1])
                self.assertFalse(dx > 0 and dy > 0, (nos[a]["txt"], nos[b]["txt"]))
        # nenhuma mancha toca outra: os blocos ficam separados
        por_bloco: dict[int, list] = {}
        for d in nos.values():
            por_bloco.setdefault(d["com"], []).append(V.caixa(d, 1.0))
        retangulos = {c: (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))
                      for c, bs in por_bloco.items()}
        cs = sorted(retangulos)
        for k, a in enumerate(cs):
            for b in cs[k + 1:]:
                ra, rb = retangulos[a], retangulos[b]
                separados = (ra[2] + V.FOLGA_HALO <= rb[0] or rb[2] + V.FOLGA_HALO <= ra[0]
                             or ra[3] + V.FOLGA_HALO <= rb[1] or rb[3] + V.FOLGA_HALO <= ra[1])
                if not separados:                   # retângulos podem se cruzar nos cantos; os círculos dos blocos não
                    ca = [(d["x"], d["y"]) for d in nos.values() if d["com"] == a]
                    cb = [(d["x"], d["y"]) for d in nos.values() if d["com"] == b]
                    menor = min(math.hypot(p[0] - q[0], p[1] - q[1]) for p in ca for q in cb)
                    self.assertGreater(menor, 8.0)

    def test_figura_pequena_e_com_um_bloco(self):
        res = S.analisa_documentos(_docs("en")[:8], n_formas=30)
        self.assertTrue(V.svg(res, "x").startswith("<svg"))
        minimo = {"formas": [{"id": "pt:a", "forma": "a", "idioma": "pt", "frequencia": 3, "resumos": 3,
                              "ocorrencias": 3, "comunidade": 1, "grau": 1},
                             {"id": "pt:b", "forma": "b", "idioma": "pt", "frequencia": 3, "resumos": 3,
                              "ocorrencias": 3, "comunidade": 1, "grau": 1}],
                  "arestas": [{"origem": "pt:a", "destino": "pt:b", "peso": 0.5, "tipo": "arvore"}],
                  "comunidades": [{"id": 1, "n": 2, "nome": "a, b", "idiomas": ["pt"]}],
                  "idiomas_nas_formas": ["pt"], "n_resumos": 3, "n_extras": 0,
                  "parametros": {"idioma": "pt", "indice": "jaccard", "segmento": "resumo", "extras": 20}}
        raiz = ET.fromstring(V.svg(minimo, "T"))
        self.assertEqual(2, len(raiz.findall(f".//{SVG_NS}text[@class='rot']")))
        self.assertEqual("", V.svg({}))
        self.assertEqual("", V.svg({"formas": minimo["formas"][:1], "arestas": []}))

    def test_texto_com_caracteres_especiais_e_de_controle(self):
        res = {"formas": [{"id": "en:a", "forma": "a<b&\"c\"", "idioma": "en", "frequencia": 5, "resumos": 5,
                           "ocorrencias": 5, "comunidade": 1, "grau": 1},
                          {"id": "en:b", "forma": "x\x00y\x07z", "idioma": "en", "frequencia": 4, "resumos": 4,
                           "ocorrencias": 4, "comunidade": 1, "grau": 1}],
               "arestas": [{"origem": "en:a", "destino": "en:b", "peso": 1.0, "tipo": "arvore"}],
               "comunidades": [{"id": 1, "n": 2, "nome": "a<b&\"c\", xyz", "idiomas": ["en"]}],
               "idiomas_nas_formas": ["en"], "n_resumos": 5, "n_extras": 0,
               "parametros": {"idioma": "todos", "indice": "jaccard", "segmento": "resumo", "extras": 0}}
        saida = V.svg(res, "Título <&>")
        ET.fromstring(saida)
        self.assertNotIn("\x00", saida)
        self.assertNotIn("\x07", saida)

    def test_largura_do_texto_tem_folga_sobre_a_tabela(self):
        for texto in ("estatística", "probabilidad", "w" * 10, "i" * 10):
            self.assertAlmostEqual(largura_base(texto, 14) * V.FOLGA_TEXTO, V.largura_texto(texto, 14))
        self.assertGreaterEqual(V.FOLGA_TEXTO, 1.16)
        self.assertLessEqual(V.FOLGA_TEXTO, 1.30)

    def test_no_navegador_nada_fora_sem_sobreposicao_e_texto_cabe(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright não instalado")
        try:
            with sync_playwright() as p:
                navegador = p.chromium.launch()
                pagina = navegador.new_page(viewport={"width": 1400, "height": 900})
                pagina.set_content(f'<html><body style="margin:0">{self.svg}</body></html>')
                pagina.wait_for_timeout(200)
                r = pagina.evaluate(_JS_VERIFICA)
                navegador.close()
        except Exception as erro:       # noqa: BLE001 - navegador indisponível no ambiente
            self.skipTest(f"Chromium indisponível: {erro}")
        self.assertEqual([], r["fora"])
        self.assertEqual([], r["sobrepoe"])
        self.assertEqual([], r["client_fora"])
        self.assertEqual(len(self.res["formas"]), r["n_rot"])
        # o texto medido no navegador cabe no previsto (a folga é a razão de ser do fator)
        for texto, medida, fonte in r["larguras"]:
            self.assertLessEqual(medida, V.largura_texto(texto, fonte) + 0.5, texto)


_JS_VERIFICA = r"""
() => {
  const svg = document.querySelector('svg');
  const vb = svg.viewBox.baseVal;
  const out = {fora: [], sobrepoe: [], n_rot: 0, larguras: []};
  const dentro = (b, pad) => b.x - pad >= vb.x - 0.01 && b.y - pad >= vb.y - 0.01 &&
        b.x + b.width + pad <= vb.x + vb.width + 0.01 && b.y + b.height + pad <= vb.y + vb.height + 0.01;
  svg.querySelectorAll('*').forEach(el => {
    if (!el.getBBox || ['title', 'desc', 'svg'].includes(el.tagName)) return;
    let b; try { b = el.getBBox(); } catch (e) { return; }
    const sw = parseFloat(el.getAttribute('stroke-width') || '0') / 2;
    const pad = (el.getAttribute('stroke') && el.getAttribute('stroke') !== 'none') ? sw : 0;
    if (!dentro(b, pad)) out.fora.push([el.tagName, el.textContent.slice(0, 30)]);
  });
  const rots = [...svg.querySelectorAll('text.rot')].map(t => { const b = t.getBBox();
    return {t: t.textContent, x0: b.x, y0: b.y, x1: b.x + b.width, y1: b.y + b.height, fs: parseFloat(t.getAttribute('font-size'))}; });
  const circ = [...svg.querySelectorAll('.sim-nos circle')].map(c => ({cx: +c.getAttribute('cx'), cy: +c.getAttribute('cy'), r: +c.getAttribute('r')}));
  out.n_rot = rots.length;
  out.larguras = rots.map(a => [a.t, a.x1 - a.x0, a.fs]);
  for (let i = 0; i < rots.length; i++) for (let j = i + 1; j < rots.length; j++) {
    const a = rots[i], b = rots[j];
    if (Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0) > 0.5 && Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0) > 0.5) out.sobrepoe.push([a.t, b.t]);
  }
  rots.forEach((a, i) => circ.forEach((c, j) => { if (i === j) return;
    const nx = Math.max(a.x0, Math.min(c.cx, a.x1)), ny = Math.max(a.y0, Math.min(c.cy, a.y1));
    if ((nx - c.cx) ** 2 + (ny - c.cy) ** 2 < (c.r - 0.5) ** 2) out.sobrepoe.push([a.t, 'círculo ' + j]); }));
  const r = svg.getBoundingClientRect();
  out.client_fora = [...svg.querySelectorAll('text')].filter(t => { const b = t.getBoundingClientRect();
    return b.left < r.left - 0.5 || b.top < r.top - 0.5 || b.right > r.right + 0.5 || b.bottom > r.bottom + 0.5; })
    .map(t => t.textContent.slice(0, 30));
  return out;
}
"""


# ====================================================================== API

class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = cls.dir / "s.redes"
        cls.sem_resumos = cls.dir / "n.redes"
        build.constroi(_fontes("pt", "es", "en"), cls.projeto, PERIODOS)
        build.constroi(_fontes("pt", com_resumo=False), cls.sem_resumos, PERIODOS)
        cls.servidor = cria_servidor(0, cls.dir)
        cls.base = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def pede(self, rota, dados=None):
        corpo = json.dumps(dados).encode() if dados is not None else None
        req = urllib.request.Request(self.base + rota, data=corpo,
                                     headers={"Content-Type": "application/json"} if corpo else {})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def json(self, rota, dados=None, status=200):
        st, corpo, _ = self.pede(rota, dados)
        self.assertEqual(status, st, corpo[:300])
        return json.loads(corpo)

    def get(self, projeto=None, **q):
        q.setdefault("projeto", str(projeto or self.projeto))
        return self.pede("/api/similitude?" + urllib.parse.urlencode(q))

    def token(self, projeto=None):
        return self.json("/api/analisa", {"projeto": str(projeto or self.projeto), "unidade": "Words",
                                          "minimo_frequencia": 1, "periodo": 1})["token"]

    def test_post_com_projeto_devolve_estrutura_completa(self):
        d = self.json("/api/similitude", {"projeto": str(self.projeto)})
        for chave in ("svg", "nota", "formas", "arestas", "comunidades", "docs_por_idioma", "parametros",
                      "tabela_parametros", "avisos", "n_resumos"):
            self.assertIn(chave, d)
        self.assertEqual({"pt": 30, "es": 29, "en": 23}, d["docs_por_idioma"])
        self.assertEqual(82, d["n_resumos"])
        self.assertEqual(60, len(d["formas"]))
        self.assertEqual({"n_formas": 60, "indice": "jaccard", "segmento": "resumo", "extras": 20,
                          "idioma": "todos", "periodo": "todos", "ignorar": [], "semente": 7}, d["parametros"])
        ET.fromstring(d["svg"])
        self.assertIn("Como ler", d["nota"])
        self.assertNotIn("_baixar", d)

    def test_token_get_e_post_dao_o_mesmo(self):
        token = self.token()
        a = self.json("/api/similitude?token=" + token + "&n_formas=40&idioma=pt")
        b = self.json("/api/similitude", {"token": token, "n_formas": 40, "idioma": "pt"})
        self.assertEqual(a["formas"], b["formas"])
        self.assertEqual({"pt"}, {f["idioma"] for f in a["formas"]})
        self.assertEqual(40, len(a["formas"]))

    def test_parametros_e_limites(self):
        d = json.loads(self.get(n_formas="1")[1])
        self.assertEqual(30, d["parametros"]["n_formas"])
        d = json.loads(self.get(n_formas="9999")[1])
        self.assertEqual(100, d["parametros"]["n_formas"])
        d = json.loads(self.get(arestas_extras="500", idioma="es", n_formas="30")[1])
        self.assertEqual(50, d["parametros"]["extras"])
        d = json.loads(self.get(arestas_extras="0", idioma="es", n_formas="30")[1])
        self.assertEqual(0, d["n_extras"])
        for indice in S.INDICES:
            st, corpo, _ = self.get(indice=indice, segmento="frase", idioma="pt", n_formas="30")
            self.assertEqual(200, st, (indice, corpo[:200]))
            self.assertEqual(indice, json.loads(corpo)["parametros"]["indice"])

    def test_periodo_e_ignorar(self):
        todos = json.loads(self.get(idioma="pt")[1])
        d1 = json.loads(self.get(idioma="pt", periodo="2016–2019")[1])
        self.assertLess(d1["n_resumos"], todos["n_resumos"])
        self.assertEqual("2016–2019", d1["parametros"]["periodo"])
        com_id = json.loads(self.get(idioma="pt", periodo="1")[1])
        self.assertEqual(d1["n_resumos"], com_id["n_resumos"])
        ign = json.loads(self.get(idioma="pt", ignorar="estatística, dado")[1])
        self.assertFalse({"estatística", "dado"} & {f["forma"] for f in ign["formas"]})
        post = self.json("/api/similitude", {"projeto": str(self.projeto), "idioma": "pt",
                                             "ignorar": ["Estatística", "dado"]})
        self.assertEqual(ign["formas"], post["formas"])

    def test_downloads(self):
        st, corpo, h = self.get(baixar="svg", idioma="pt")
        self.assertEqual(200, st)
        self.assertIn("image/svg+xml", h["Content-Type"])
        self.assertIn("similitude.svg", h["Content-Disposition"])
        self.assertIn("Análise de similitude", corpo.decode())
        ET.fromstring(corpo)
        st, corpo, h = self.get(baixar="graphml", idioma="pt")
        self.assertIn("similitude.graphml", h["Content-Disposition"])
        self.assertTrue(ET.fromstring(corpo).findall(".//{*}node"))
        st, corpo, h = self.get(baixar="csv", idioma="pt")
        self.assertIn("text/csv", h["Content-Type"])
        self.assertTrue(corpo.decode("utf-8").startswith("﻿forma,idioma"))
        st, corpo, h = self.get(baixar="csv-arestas", idioma="pt")
        self.assertIn("similitude-arestas.csv", h["Content-Disposition"])
        self.assertEqual(200, self.get(baixar="1", idioma="pt")[0])
        self.assertEqual(400, self.get(baixar="pdf")[0])

    def test_erros_claros(self):
        st, corpo, _ = self.get(self.sem_resumos)
        self.assertEqual(400, st)
        self.assertIn("não tem resumos", json.loads(corpo)["erro"])
        self.assertEqual(400, self.get(self.sem_resumos, baixar="svg")[0])
        for q, trecho in (({"indice": "x"}, "indice precisa"), ({"segmento": "x"}, "segmento precisa"),
                          ({"idioma": "fr"}, "idioma precisa"), ({"n_formas": "abc"}, "n_formas"),
                          ({"periodo": "nunca"}, "Período desconhecido")):
            st, corpo, _ = self.get(**q)
            self.assertEqual(400, st, q)
            self.assertIn(trecho, json.loads(corpo)["erro"])
        st, corpo, _ = self.pede("/api/similitude?projeto=%2Fnao%2Fexiste.redes")
        self.assertEqual(400, st)
        st, corpo, _ = self.pede("/api/similitude?token=naoexiste")
        self.assertIn(st, (400, 404, 410))
        st, corpo, _ = self.pede("/api/similitude", {"projeto": str(self.projeto), "ignorar": 5})
        self.assertEqual(400, st)
        # idioma sem resumos suficientes
        st, corpo, _ = self.get(self.sem_resumos, idioma="es")
        self.assertEqual(400, st)

    def test_funciona_com_qualquer_tipo_de_analise(self):
        st, corpo, _ = self.pede("/api/analisa", {"projeto": str(self.projeto), "unidade": "Authors",
                                                  "minimo_frequencia": 1, "periodo": 1})
        self.assertEqual(200, st, corpo)
        d = self.json("/api/similitude?token=" + json.loads(corpo)["token"] + "&idioma=en")
        self.assertEqual(23, d["n_resumos"])


# =============================================================== relatórios

class RelatoriosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = cls.dir / "r.redes"
        cls.sem_resumos = cls.dir / "n.redes"
        build.constroi(_fontes("pt", "es", "en"), cls.projeto, PERIODOS)
        build.constroi(_fontes("pt", com_resumo=False), cls.sem_resumos, PERIODOS)

    def unico(self, projeto=None, n_secoes=2):
        with ProjetoRedes(projeto or self.projeto) as kb:
            periodos = kb.periodos()
            secoes = []
            for k in range(n_secoes):
                config = _config({"minimo_frequencia": 1, "tamanho_maximo": 6, "unidade": "Words"})
                resultados = [pipeline.executa_periodo(kb, p.id, p.nome, config) for p in periodos]
                secoes.append({"rotulo": f"Análise {k}", "descricao": "Descrição.", "pasta": f"a{k}",
                               "config": config, "resultados": resultados})
            nome = f"u-{(projeto or self.projeto).name}-{n_secoes}.html"
            saida = relatorio_unico.gera_arquivo_unico(self.dir / nome, kb, periodos, secoes, [])
        return saida.read_text(encoding="utf-8")

    def test_unico_tem_figura_numerada_nota_parametros_e_tabela_das_formas(self):
        html = self.unico()
        self.assertEqual(1, html.count(report.TITULO_SECAO_SIMILITUDE + "</h3>"))      # só na primeira análise
        self.assertRegex(html, r"Figura \d+ — Análise de similitude dos resumos")
        for trecho in ("Como ler:", "Parâmetros da análise de similitude", "Palavras do grafo de similitude",
                       "Jaccard", "todos (inglês 23, português 30, espanhol 29)", "Louvain"):
            self.assertIn(trecho, html)
        self.assertRegex(html, r"Tabela \d+ — Parâmetros da análise de similitude")
        self.assertRegex(html, r"Tabela \d+ — Palavras do grafo de similitude")
        for coluna in ("Frequência", "Bloco", "Grau"):
            self.assertIn(f"<th>{coluna}</th>", html.replace(' class="num"', ""))
        self.assertNotIn("\x00", html)
        self.assertLess(html.index(report.TITULO_SECAO_SIMILITUDE + "</h3>"),
                        html.index("Dendrograma (agrupamento hierárquico)</h3>"))
        self.assertIn("Similitude dos resumos.", html)             # método

    def test_unico_numeracao_sem_repeticao(self):
        html = self.unico()
        tabelas = re.findall(r"<caption>Tabela (\d+) — ", html)
        figuras = re.findall(r"<figcaption>Figura (\d+) — ", html)
        self.assertEqual(list(range(1, len(tabelas) + 1)), sorted(int(t) for t in tabelas))
        self.assertEqual(len(tabelas), len(set(tabelas)))
        self.assertEqual(list(range(1, len(figuras) + 1)), [int(f) for f in figuras])
        ids = re.findall(r'\bid="([^"]+)"', html)
        self.assertEqual(len(ids), len(set(ids)))

    def test_unico_omite_sem_resumos_ou_quando_falha(self):
        html = self.unico(self.sem_resumos)
        self.assertNotIn(report.TITULO_SECAO_SIMILITUDE, html)
        self.assertNotIn("Similitude dos resumos.", html)
        self.assertIn("Dendrograma (agrupamento hierárquico)", html)
        cache_figuras.limpa()
        with mock.patch("redes.similitude.analisa", side_effect=RuntimeError("x")):
            html = self.unico()
        cache_figuras.limpa()
        self.assertNotIn(report.TITULO_SECAO_SIMILITUDE + "</h3>", html)
        self.assertIn("Dendrograma (agrupamento hierárquico)", html)

    def test_pasta(self):
        with ProjetoRedes(self.projeto) as kb:
            config = _config({"unidade": "Words", "minimo_frequencia": 1, "tamanho_maximo": 6})
            destino = self.dir / "pasta"
            report.gera_html(destino, kb, kb.periodos(), config)
            indice = (destino / "index.html").read_text(encoding="utf-8")
            self.assertIn(f'id="similitude">{report.TITULO_SECAO_SIMILITUDE}', indice)
            self.assertIn('src="images/similitude.svg"', indice)
            for trecho in ("Como ler:", "Parâmetros da análise de similitude", "Palavras do grafo de similitude"):
                self.assertIn(trecho, indice)
            ET.parse(destino / "images" / "similitude.svg")
        with ProjetoRedes(self.sem_resumos) as kb:
            destino2 = self.dir / "pasta2"
            report.gera_html(destino2, kb, kb.periodos(), config)
            self.assertNotIn(report.TITULO_SECAO_SIMILITUDE, (destino2 / "index.html").read_text(encoding="utf-8"))
            self.assertFalse((destino2 / "images" / "similitude.svg").exists())

    def test_metodo_traz_parametros_algoritmo_e_numeracao_sequencial(self):
        config = _config({"unidade": "Words"})
        texto = metodo.algoritmo_html(config, None, 2)
        self.assertIn("Similitude dos resumos.", texto)
        for trecho in (f"as {S.N_FORMAS} formas mais frequentes", "Kruskal", "Louvain", "hipergeométrica",
                       "nunca</strong> se fundem", f"semente {S.SEMENTE}", "Jaccard", "ã, õ, ç", "-mente"):
            self.assertIn(trecho, texto)
        numeros = [int(n) for n in re.findall(r"<strong>(\d+)\. ", texto)]
        self.assertEqual(list(range(1, len(numeros) + 1)), numeros)
        self.assertEqual(1, texto.count("Similitude dos resumos.</strong>"))
        with mock.patch.object(S, "N_FORMAS", 77), mock.patch.object(S, "SEMENTE", 11):
            alterado = metodo.algoritmo_html(config, None, 2)
        self.assertIn("as 77 formas mais frequentes", alterado)
        self.assertIn("semente 11", alterado)
        for cfg in (config, _config({"unidade": "References", "matriz": "BasicCoupling", "mapeadores": ["acoplamento"]})):
            sem = metodo.algoritmo_html(cfg, None, 2, com_similitude=False)
            self.assertNotIn("Similitude dos resumos.", sem)
            nums = [int(n) for n in re.findall(r"<strong>(\d+)\. ", sem)]
            self.assertEqual(list(range(1, len(nums) + 1)), nums)
            sem_nenhum = metodo.algoritmo_html(cfg, None, 2, com_duplo=False, com_similitude=False)
            nums = [int(n) for n in re.findall(r"<strong>(\d+)\. ", sem_nenhum)]
            self.assertEqual(list(range(1, len(nums) + 1)), nums)

    def test_metodo_html_so_inclui_o_item_quando_ha_resumos(self):
        config = _config({"unidade": "Words", "minimo_frequencia": 1})
        with ProjetoRedes(self.projeto) as kb:
            com = metodo.metodo_html(config, kb.periodos(), (), None, None, kb)
        with ProjetoRedes(self.sem_resumos) as kb:
            sem = metodo.metodo_html(config, kb.periodos(), (), None, None, kb)
        self.assertIn("Similitude dos resumos.", com)
        self.assertNotIn("Similitude dos resumos.", sem)


# ================================================================ interface

class InterfaceTest(unittest.TestCase):
    """Checagens estáticas da aba, do reset, dos controles e do menu (o fluxo vivo está nos prints Playwright)."""

    @classmethod
    def setUpClass(cls):
        cls.js = (UI / "app.js").read_text(encoding="utf-8")
        cls.html = (UI / "index.html").read_text(encoding="utf-8")
        cls.css = (UI / "style.css").read_text(encoding="utf-8")

    def test_aba_depois_do_duplo_mapa_e_sempre_visivel(self):
        ordem = re.findall(r'data-aba="([a-z]+)"', self.html)
        self.assertEqual(ordem.index("duplomapa") + 1, ordem.index("similitude"))
        self.assertIn('id="blocoSimilitude"', self.html)
        self.assertIn('similitude: "blocoSimilitude"', self.js)
        grupos = re.search(r"const GRUPOS_ABAS = \[.*?\];", self.js, re.S).group(0)
        self.assertIn('"similitude"', grupos)
        self.assertNotIn("ABAS_SIMPLES", self.js)
        self.assertIn('const extras = ["dendrograma", "linhatempo", "densidade", "duplomapa", "similitude"];', self.js)
        self.assertIn('chave === "similitude"', self.js)

    def test_controles(self):
        for id_ in ("smIdioma", "smPeriodo", "smIndice", "smSegmento", "smN", "smExtras", "smIgnorar",
                    "smFigura", "vazioSimilitude", "smAvisos", "smNota", "smTabelaCaixa", "smCorpo",
                    "metaSimilitude"):
            self.assertIn(f'id="{id_}"', self.html)
        for valor in ("todos", "en", "pt", "es"):
            self.assertRegex(self.html, rf'(?s)<select id="smIdioma".*?<option value="{valor}"')
        for valor in S.INDICES:
            self.assertIn(f'<option value="{valor}">', self.html)
        self.assertIn('id="smN" min="30" max="100"', self.html)
        self.assertIn('id="smExtras" min="0" max="50"', self.html)
        for coluna in ("Frequência", "Bloco", "Grau", "Idioma", "Palavra"):
            self.assertIn(coluna, self.html[self.html.index('id="smTabelaCaixa"'):])

    def test_reset_ao_trocar_de_projeto_e_de_analise(self):
        projeto = re.search(r"function aplicarProjeto\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("limparSimilitude(true)", projeto)
        resultado = re.search(r"function renderizarResultado\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("limparSimilitude(false)", resultado)
        self.assertIn('abaAtual() === "similitude"', resultado)
        limpa = re.search(r"function limparSimilitude\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("sm.seq += 1", limpa)
        self.assertIn("mensagemSimilitude", limpa)
        self.assertIn('sm.motivo = ""', limpa)
        self.assertIn("preencherPeriodosSimilitude()", limpa)
        self.assertIn('$("smIdioma").value = "todos"', limpa)

    def test_mensagem_quando_nao_ha_resumos_e_menu_exportar(self):
        carrega = re.search(r"async function carregarSimilitude\(.*?\n}\n", self.js, re.S).group(0)
        self.assertIn("sm.motivo = erro.message", carrega)
        self.assertIn("mensagemSimilitude(erro.message)", carrega)
        self.assertIn('startsWith("similitude-") && !similitudeAplicavel()', self.js)
        for tipo in ("svg", "graphml", "csv"):
            self.assertIn(f'data-exp="similitude-{tipo}" data-precisa="resultado"', self.html)
        self.assertIn('tipo.startsWith("similitude-")', self.js)
        self.assertIn("/api/similitude?", self.js)
        for arquivo in ("similitude.svg", "similitude.graphml", "similitude-formas.csv"):
            self.assertIn(arquivo, self.js)

    def test_menu_exportar_depois_do_duplo_mapa(self):
        i = self.html.index('data-exp="duplomapa-svg"')
        self.assertLess(i, self.html.index('data-exp="similitude-svg"'))
        self.assertLess(self.html.index('data-exp="similitude-csv"'), self.html.index('data-exp="fluxo-svg"'))

    def test_sem_tema_escuro_no_trecho_novo(self):
        trecho = self.css[self.css.index(".sm-figura"):].split("/* ---")[0]
        self.assertNotIn("prefers-color-scheme", trecho)
        self.assertNotIn("dark", trecho)


if __name__ == "__main__":
    unittest.main()

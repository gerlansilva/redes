"""Qualidade dos dados importados: palavras, duplicatas, referências, países,
formatos do Zotero e equivalência do agrupamento por centros simples.

Executar com:
    python3 -m unittest discover -s tests -t .
"""

from __future__ import annotations

import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scimatpy.build import Construtor, constroi
from scimatpy.clustering import ConjuntoDeAgrupamentos, centros_simples
from scimatpy.loaders import detecta_formato, le_corpus, ris, zotero
from scimatpy.loaders.base import (DocumentoFonte, decodifica_latex,
                                   remove_duplicatas)
from scimatpy.network import Rede
from scimatpy.paises import pais_da_afiliacao
from scimatpy.references import converte_referencia
from scimatpy.text_utils import mesmo_termo, normaliza_palavra


def _doc(titulo, **campos):
    return DocumentoFonte(titulo=titulo, ano=campos.pop("ano", "2020"), **campos)


class PalavrasTest(unittest.TestCase):

    def test_apostrofo_tipografico_unifica(self):
        self.assertEqual(normaliza_palavra("children’s rights"),
                         normaliza_palavra("children's rights"))
        self.assertEqual("CHILDREN'S-RIGHTS",
                         normaliza_palavra("Children’s  rights"))
        # espaço sem quebra e travessão também
        self.assertEqual("A-B", normaliza_palavra("a b"))
        self.assertEqual("A-B", normaliza_palavra("a–b"))

    def test_apostrofos_viram_uma_palavra_no_projeto(self):
        documentos = [
            _doc("um", palavras_autor=["children’s rights"]),
            _doc("dois", palavras_autor=["Children's Rights"]),
        ]
        construtor = Construtor(documentos)
        construtor.importa()
        self.assertEqual(["CHILDREN'S-RIGHTS"], list(construtor.palavras))
        self.assertEqual([1, 2], construtor.palavras["CHILDREN'S-RIGHTS"].documentos)

    def test_plural_e_acento_em_portugues_e_espanhol(self):
        pares = [
            ("PROFESSOR", "PROFESSORES"),
            ("EDUCAÇÃO", "EDUCACAO"),
            ("EDUCAÇÕES", "EDUCAÇÃO"),
            ("EDUCAÇÕES", "EDUCACAO"),
            ("EDUCACION", "EDUCACIONES"),
            ("ANIMAL", "ANIMAIS"),
            ("PAPEL", "PAPÉIS"),
            ("HOMEM", "HOMENS"),
            ("LÁPIZ", "LÁPICES"),
            ("ESTATÍSTICA", "ESTATISTICA"),
            ("ESTUDANTE-UNIVERSITARIO", "ESTUDANTES-UNIVERSITARIOS"),
            ("ENSINO-DE-ESTATÍSTICA", "ENSINO-DE-ESTATISTICA"),
            ("MODEL", "MODELS"),          # regra original do SciMAT
            ("ATTITUDE", "ATTITUDES"),
            ("COMMUNITY", "COMMUNITIES"),
        ]
        for a, b in pares:
            with self.subTest(a=a, b=b):
                self.assertTrue(mesmo_termo(a, b))
                self.assertTrue(mesmo_termo(b, a))

    def test_termos_diferentes_nao_se_juntam(self):
        for a, b in [("MAL", "MAIS"), ("CHILD", "CHILDREN"), ("ENSINO", "ENSINAR"),
                     ("MATEMATICA", "MATEMATICAS-ENSINO"), ("A-B", "A-C"),
                     ("PAIS", "PAIS-ENSINO")]:
            with self.subTest(a=a, b=b):
                self.assertFalse(mesmo_termo(a, b))

    def test_agrupa_variantes_e_prefere_grafia_acentuada(self):
        documentos = [
            _doc("1", palavras_autor=["educação", "professores"]),
            _doc("2", palavras_autor=["educacao", "professor"]),
            _doc("3", palavras_autor=["educação matemática"]),
            _doc("4", palavras_autor=["Educacao Matematica"]),
        ]
        construtor = Construtor(documentos)
        construtor.importa()
        grupos = {nome: membros for _, nome, membros in construtor.agrupa_palavras()}
        self.assertEqual(3, len(grupos), grupos)
        self.assertIn("EDUCAÇÃO", grupos)           # empate: fica a acentuada
        self.assertIn("EDUCAÇÃO-MATEMÁTICA", grupos)
        self.assertEqual(2, len(grupos["EDUCAÇÃO"]))


class DuplicatasTest(unittest.TestCase):

    def test_junta_por_doi_e_por_titulo_e_ano(self):
        documentos = [
            _doc("Personal Epistemologies", doi="10.1/abc", citacoes=0,
                 palavras_autor=["a"], periodico=""),
            _doc("Outro artigo", doi="https://doi.org/10.1/xyz"),
            _doc("PERSONAL EPISTEMOLOGIES", citacoes=3, palavras_autor=["a", "b"],
                 periodico="Revista"),
            _doc("Outro artigo (cópia)", doi="10.1/XYZ"),
            _doc("Personal Epistemologies", ano="2021"),  # outro ano: fica
        ]
        unicos, removidos = remove_duplicatas(documentos)
        self.assertEqual(3, len(unicos))
        self.assertEqual(2, len(removidos))
        primeiro = unicos[0]
        self.assertEqual(3, primeiro.citacoes)          # maior contagem
        self.assertEqual("Revista", primeiro.periodico)  # preenche o que faltava
        self.assertEqual(["a", "b"], primeiro.palavras_autor)
        self.assertEqual("Personal Epistemologies", primeiro.titulo)  # sem caixa alta

    def test_constroi_informa_e_pode_manter(self):
        documentos = [_doc("Igual"), _doc("igual."), _doc("Diferente")]
        with tempfile.TemporaryDirectory() as pasta:
            resumo = constroi(list(documentos), Path(pasta) / "a.redes")
            self.assertEqual(2, resumo["documentos"])
            self.assertEqual(1, resumo["duplicatas_removidas"])
            resumo = constroi(list(documentos), Path(pasta) / "b.redes",
                              remove_repetidos=False)
            self.assertEqual(3, resumo["documentos"])


class ReferenciasTest(unittest.TestCase):

    def test_inicial_p_nao_vira_pagina(self):
        self.assertEqual(
            "Harris P.L., 2012, Sem fonte, , , Trusting What You're Told",
            converte_referencia("Harris P.L., Trusting What You're Told, (2012)"))
        resultado = converte_referencia(
            "Moyer P.S., Are we having fun yet? How teachers use manipulatives, "
            "Educational Studies in Mathematics, 47, pp. 175-197, (2001)")
        self.assertTrue(resultado.startswith(
            "Moyer P.S., 2001, Educational Studies in Mathematics, V47, P175-197"))
        self.assertTrue(converte_referencia(
            "Laplace P.-S., Philosophical essay, Springer, (1995)"
        ).startswith("Laplace P.-S., 1995, Springer"))

    def test_paginas_romanas_continuam_paginas(self):
        resultado = converte_referencia(
            "Ben-Zvi D., Foreword, Statistics in early childhood, pp. xii-xiii, (2018)")
        self.assertIn("Pxii-xiii", resultado)

    def test_sobrenomes_compostos(self):
        for texto, autor in [
            ("van der Meij H., Learning to code, Computers and Education, 12, pp. 5-9, (2010)",
             "van der Meij H."),
            ("Van den Heuvel-Panhuizen M.; Elia I., Kindergartners, ZDM, 44, pp. 1-9, (2012)",
             "Van den Heuvel-Panhuizen M.; Elia I."),
            ("delMas R.C., Statistical literacy, Journal of Statistics Education, 10, (2002)",
             "delMas R.C."),
            ("De Veaux R.D., Intro Stats, Pearson, (2014)", "De Veaux R.D."),
            ("Dos Santos R.; Karrer M., Probabilidade, Bolema, 3, pp. 1-5, (2020)",
             "Dos Santos R.; Karrer M."),
            ("Da Silva V.A., Estatística, Revista X, 4, pp. 1-5, (2019)",
             "Da Silva V.A."),
        ]:
            with self.subTest(autor=autor):
                self.assertTrue(
                    converte_referencia(texto).startswith(autor + ", 20"),
                    converte_referencia(texto))

    def test_sobrenome_sem_iniciais_em_referencia_antiga(self):
        resultado = converte_referencia(
            "Craik, Theory of the human operator in control systems, "
            "Br. J. Psychol., 38, pp. 56-61, (1974)")
        self.assertEqual(
            "Craik, 1974, Br. J. Psychol., V38, P56-61, "
            "Theory of the human operator in control systems", resultado)

    def test_sobrenome_virgula_iniciais(self):
        self.assertEqual(
            "Lopes C. E., 2019, Bolema, V33, P1-10, Formação de professores",
            converte_referencia(
                "Lopes, C. E., Formação de professores, Bolema, 33, pp. 1-10, (2019)"))

    def test_titulo_de_uma_palavra_nao_vira_autor(self):
        resultado = converte_referencia(
            "Statistics, Learning from data, Journal of Things, 5, (2001)")
        self.assertTrue(resultado.startswith("Sem autor, 2001"))

    def test_so_autor_e_ano_vira_autor_citado(self):
        self.assertEqual("Jones G.A., 1974, Sem fonte, , , ",
                         converte_referencia("Jones G.A., (1974)"))
        self.assertTrue(converte_referencia(
            "Page M.J.; McKenzie J.E.; Bossuyt P.M., (2021)"
        ).startswith("Page M.J.; McKenzie J.E.; Bossuyt P.M., 2021"))

    def test_lista_longa_de_autores(self):
        autores = "; ".join(f"Sobrenome{i} A.B." for i in range(40))
        self.assertGreater(len(autores), 160)
        resultado = converte_referencia(
            f"{autores}, Um estudo grande, Revista X, 5, pp. 1-9, (2020)")
        self.assertTrue(resultado.startswith("Sobrenome0 A.B.; Sobrenome1"))
        self.assertIn("Revista X", resultado)

    def test_autor_com_particula_nao_vira_titulo(self):
        resultado = converte_referencia(
            "van de Wiel M.W.J., Teaching, Learning and Instruction, 7, pp. 1-9, (2010)")
        self.assertTrue(resultado.startswith("van de Wiel M.W.J., 2010"))


class AutoresCitadosTest(unittest.TestCase):

    def _projeto(self, modo):
        documentos = [
            _doc("a", referencias=[
                "Silva A.; Souza B., 2010, Revista X, V1, P1-2, Um",
                "Silva A.; Costa C., 2012, Revista Y, V2, P3-4, Dois"]),
            _doc("b", referencias=["Silva A., 2015, Revista Z, V3, P5-6, Tres"]),
        ]
        for documento in documentos:
            documento.referencias_convertidas = True
        pasta = tempfile.mkdtemp()
        caminho = Path(pasta) / "p.redes"
        constroi(documentos, caminho, autores_referencia=modo)
        conexao = sqlite3.connect(caminho)
        nomes = sorted(r[0] for r in conexao.execute(
            "SELECT authorName FROM AuthorReference"))
        vinculos = conexao.execute(
            "SELECT COUNT(*) FROM AuthorReference_Reference").fetchone()[0]
        conexao.close()
        return nomes, vinculos

    def test_primeiro_autor_junta_o_mesmo_autor_citado(self):
        nomes, vinculos = self._projeto("primeiro")
        self.assertEqual(["Silva A."], nomes)
        self.assertEqual(3, vinculos)

    def test_todos_os_autores(self):
        nomes, vinculos = self._projeto("todos")
        self.assertEqual(["Costa C.", "Silva A.", "Souza B."], nomes)
        self.assertEqual(5, vinculos)

    def test_lista_mantem_comportamento_antigo(self):
        nomes, _ = self._projeto("lista")
        self.assertEqual(3, len(nomes))
        self.assertIn("Silva A.; Souza B.", nomes)

    def test_modo_invalido(self):
        with self.assertRaises(ValueError):
            Construtor([], "nenhum")


class PaisesTest(unittest.TestCase):

    def test_nomes_em_portugues_e_espanhol(self):
        self.assertEqual("Brasil", pais_da_afiliacao(
            "Universidade Federal de Pernambuco, Brasil"))
        self.assertEqual("Espanha", pais_da_afiliacao(
            "Universidad de Granada, Granada, España"))
        self.assertEqual("Peru", pais_da_afiliacao("Hospital, Lima, Perú"))
        self.assertEqual("Reino Unido", pais_da_afiliacao("School, Cambridge, UK"))
        self.assertEqual("Países Baixos", pais_da_afiliacao(
            "Universiteit, Utrecht, The Netherlands"))

    def test_endereco_dos_eua_sem_pais(self):
        self.assertEqual("Estados Unidos", pais_da_afiliacao(
            "Department of Psychology, Davis, CA 95616, 1 Shields Avenue"))
        # a sigla sozinha é ambígua (IN = Indiana ou Índia)
        self.assertEqual("", pais_da_afiliacao("Instituto X, Pune, IN"))


class ZoteroTest(unittest.TestCase):

    def escreve(self, nome, texto):
        pasta = Path(tempfile.mkdtemp())
        caminho = pasta / nome
        caminho.write_text(texto, encoding="utf-8")
        return caminho

    def test_ris_do_zotero(self):
        caminho = self.escreve("zotero.ris", (
            "TY  - JOUR\r\nAU  - Lopes, Celi Espasandin\r\nAU  - Batanero, Carmen\r\n"
            "TI  - Educação estatística e\r\n formação de professores\r\n"
            "T2  - Bolema\r\nDA  - 2021/05/12/\r\nPY  - 2021\r\n"
            "AB  - Resumo do trabalho.\r\nKW  - educação estatística\r\n"
            "KW  - formação de professores; letramento\r\n"
            "UR  - https://doi.org/10.1590/abc-123.\r\n"
            "N1  - Cited By: 12\r\nER  - \r\n\r\n"
            "TY  - CONF\r\nTI  - Segundo trabalho\r\nA1  - Silva, J.\r\nY1  - 2019///\r\nER  -\r\n"))
        self.assertEqual("ris", detecta_formato(caminho))
        documentos, formato = le_corpus(caminho)
        self.assertEqual("ris", formato)
        self.assertEqual(2, len(documentos))
        primeiro = documentos[0]
        self.assertEqual("Educação estatística e formação de professores",
                         primeiro.titulo)
        self.assertEqual(["Lopes, C.E.", "Batanero, C."], primeiro.autores)
        self.assertEqual(["Lopes, Celi Espasandin", "Batanero, Carmen"],
                         primeiro.autores_completos)
        self.assertEqual("2021", primeiro.ano)
        self.assertEqual("Bolema", primeiro.periodico)
        self.assertEqual(["educação estatística", "formação de professores",
                          "letramento"], primeiro.palavras_autor)
        self.assertEqual("10.1590/abc-123", primeiro.doi)
        self.assertEqual(12, primeiro.citacoes)
        self.assertEqual("2019", documentos[1].ano)

    def test_csv_do_zotero(self):
        caminho = self.escreve("zotero.csv", (
            '"Key","Item Type","Publication Year","Author","Title",'
            '"Publication Title","DOI","Abstract Note","Manual Tags",'
            '"Automatic Tags","Date","Extra"\n'
            '"A1","journalArticle","2021","Lopes, Celi Espasandin; Batanero, Carmen",'
            '"Letramento estatístico","Bolema","10.1/xyz","Resumo.",'
            '"letramento; ensino","probabilidade; Ensino","2021-05-12",'
            '"Cited By: 7"\n'
            '"A2","book","","Silva, J.","Livro sem ano","","","","","","1999",""\n'))
        self.assertEqual("zotero", detecta_formato(caminho))
        documentos, formato = le_corpus(caminho, "csv")  # escolha errada é corrigida
        self.assertEqual("zotero", formato)
        self.assertEqual(2, len(documentos))
        primeiro = documentos[0]
        self.assertEqual(["Lopes, C.E.", "Batanero, C."], primeiro.autores)
        self.assertEqual("2021", primeiro.ano)
        self.assertEqual("Bolema", primeiro.periodico)
        self.assertEqual(["letramento", "ensino", "probabilidade"],
                         primeiro.palavras_autor)
        self.assertEqual(7, primeiro.citacoes)
        self.assertEqual("1999", documentos[1].ano)

    def test_zotero_vira_projeto_e_analisa(self):
        caminho = self.escreve("z.csv", (
            '"Item Type","Publication Year","Author","Title","Manual Tags"\n'
            '"journalArticle","2020","Silva, A.","Um","educação; professores"\n'
            '"journalArticle","2021","Souza, B.","Dois","educacao; professor"\n'))
        documentos, _ = le_corpus(caminho)
        with tempfile.TemporaryDirectory() as pasta:
            resumo = constroi(documentos, Path(pasta) / "z.redes")
            self.assertEqual(2, resumo["grupos_palavra"])  # variantes unificadas

    def test_bibtex_do_zotero_com_acentos_latex(self):
        caminho = self.escreve("z.bib", (
            "@article{lopes_educacao_2021,\n"
            "  title = {Educa{\\c{c}}{\\~a}o estat{\\'i}stica},\n"
            "  author = {Lopes, Celi Espasandin and Jos{\\'e}, M{\\\"u}ller},\n"
            "  journal = {Boletim de Educa{\\c{c}}{\\~a}o Matem{\\'a}tica},\n"
            "  year = {2021},\n  keywords = {educa{\\c{c}}{\\~a}o, estat{\\'i}stica}\n}\n"))
        from scimatpy.loaders import bibtex
        documento = bibtex.le(caminho)[0]
        self.assertEqual("Educação estatística", documento.titulo)
        self.assertEqual("Boletim de Educação Matemática", documento.periodico)
        self.assertEqual(["educação", "estatística"], documento.palavras_autor)
        self.assertEqual("José, M.", documento.autores[1])

    def test_decodifica_latex(self):
        self.assertEqual("Schön", decodifica_latex('Sch\\"on'))
        self.assertEqual("Faça", decodifica_latex("Fa{\\c c}a"))
        self.assertEqual("A & B", decodifica_latex("A \\& B"))
        self.assertEqual("sem latex", decodifica_latex("sem latex"))


# --------------------------------------------------- centros simples (paridade)


def _centros_literal(rede: Rede, tamanho_minimo: int, tamanho_maximo: int):
    """Formulação literal do SciMAT: relê a lista inteira a cada extração."""
    resultado = ConjuntoDeAgrupamentos(rede)
    pares = [list(par) for par in rede.arestas()]
    pares.sort(key=lambda par: -par[2])
    contagem: dict[int, int] = {}
    tamanho_atual = tamanho_maximo - 1
    i = 0
    while i < len(pares):
        encontrou = False
        a, b, _ = pares[i]
        contagem[a] = contagem.get(a, 0) + 1
        contagem[b] = contagem.get(b, 0) + 1
        for no in (a, b):
            if contagem[no] == tamanho_atual:
                tema, adicionados, j = [no], 0, i
                while adicionados < tamanho_atual and j >= 0:
                    x, y, _ = pares[j]
                    if x == no:
                        tema.append(y)
                        adicionados += 1
                    elif y == no:
                        tema.append(x)
                        adicionados += 1
                    j -= 1
                conjunto = set(tema)
                pares[:] = [p for p in pares
                            if p[0] not in conjunto and p[1] not in conjunto]
                resultado.adiciona(tema, no)
                encontrou = True
                break
        if encontrou:
            contagem.clear()
            i = 0
        else:
            i += 1
            if i == len(pares) and tamanho_atual > tamanho_minimo - 1:
                contagem.clear()
                i = 0
                tamanho_atual -= 1
        if tamanho_atual < 1:
            break
    return resultado


class CentrosSimplesTest(unittest.TestCase):

    def test_igual_a_formulacao_literal_em_redes_aleatorias(self):
        gerador = random.Random(2026)
        for caso in range(60):
            nos = gerador.randint(4, 60)
            rede = Rede(range(1, nos + 1))
            for _ in range(gerador.randint(1, nos * 4)):
                a, b = gerador.sample(range(1, nos + 1), 2)
                # poucos valores distintos geram muitos empates
                rede.adiciona_aresta(a, b, float(gerador.randint(1, 5)))
            minimo = gerador.randint(1, 4)
            maximo = gerador.randint(minimo, 12)
            esperado = _centros_literal(rede, minimo, maximo)
            obtido = centros_simples(rede, minimo, maximo)
            with self.subTest(caso=caso, nos=nos, minimo=minimo, maximo=maximo):
                self.assertEqual(
                    [(a.nos, a.principal) for a in esperado.agrupamentos],
                    [(a.nos, a.principal) for a in obtido.agrupamentos])

    def test_rede_vazia_e_limites(self):
        self.assertEqual([], centros_simples(Rede([1, 2, 3]), 2, 5).agrupamentos)
        rede = Rede([1, 2])
        rede.adiciona_aresta(1, 2, 3.0)
        for maximo in (1, 2, 3):
            self.assertEqual(
                [(a.nos, a.principal) for a in _centros_literal(rede, 1, maximo).agrupamentos],
                [(a.nos, a.principal) for a in centros_simples(rede, 1, maximo).agrupamentos])


if __name__ == "__main__":
    unittest.main()

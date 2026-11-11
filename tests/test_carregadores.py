"""Testes dos carregadores e da conversão de referências.

Executar com:
    python3 -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path

from redes.api import importa
from redes.references import converte_referencia
from redes.loaders import (bibtex, csv as csv_loader, detecta_formato,
                              openalex, ris, scopus)
from redes.paises import pais_da_afiliacao
from redes.projeto import e_projeto


class ReferenciaTest(unittest.TestCase):

    def test_artigo_com_volume_numero_e_paginas(self):
        self.assertEqual(
            "Bers M.U., 2019, Journal of Computers in Education, V6, P499-528, "
            "Coding as another language",
            converte_referencia(
                "Bers M.U., Coding as another language, Journal of Computers "
                "in Education, 6, 4, pp. 499-528, (2019)"))

    def test_livro_sem_fonte_guarda_o_titulo(self):
        self.assertEqual(
            "Papert S., 1980, Sem fonte, , , "
            "Mindstorms: Children, computers, and powerful ideas",
            converte_referencia(
                "Papert S., Mindstorms: Children, computers, and powerful "
                "ideas, (1980)"))

    def test_obra_sem_autor(self):
        self.assertEqual(
            "Sem autor, 2013, Sem fonte, , , "
            "National curriculum in England: Computing programmes of study",
            converte_referencia(
                "National curriculum in England: Computing programmes of "
                "study, (2013)"))

    def test_fonte_quebrada_em_varias_virgulas(self):
        self.assertEqual(
            "Dagiene V.; Sentance S., 2016, International Conference on "
            "Informatics in Schools: Situation Evolution and Perspectives, , "
            "P28-39, It’s computational thinking!",
            converte_referencia(
                "Dagiene V.; Sentance S., It’s computational thinking!, In "
                "International Conference on Informatics in Schools: "
                "Situation, Evolution, and Perspectives, pp. 28-39, (2016)"))

    def test_virgula_dentro_de_parenteses_nao_quebra_a_fonte(self):
        self.assertEqual(
            "Gallacher L.-A.; Gallagher M., 2008, "
            "Childhood (copenhagen Denmark), V15, P499-516, "
            "Methodological Immaturity in Childhood Research?",
            converte_referencia(
                "Gallacher L.-A.; Gallagher M., Methodological Immaturity in "
                "Childhood Research?, Childhood (copenhagen, Denmark), 15, "
                "pp. 499-516, (2008)"))

    def test_fonte_repetida_com_paginas(self):
        self.assertEqual(
            "Barnett V., 1988, Proceedings of the Second International "
            "Conference on Teaching Statistics, , P303-307, Statistical "
            "consultancy. A basis for teaching R.",
            converte_referencia(
                "Barnett V., Statistical consultancy. A basis for teaching R., "
                "Proceedings of the Second International Conference on Teaching "
                "Statistics, pp. 303-307, Proceedings Of The Second "
                "International Conference On Teaching Statistics Pp. 303-307, "
                "pp. 303-307, (1988)"))

    def test_fonte_repetida_com_volume_e_paginas(self):
        self.assertEqual(
            "Batanero Bernabeu C.; Estepa A.; Godino J.D., 1991, Suma, V9, "
            "P25-31, ",
            converte_referencia(
                "Batanero Bernabeu C., Estepa A., Godino J.D., Suma, 9, "
                "pp. 25-31, Suma 9 Pp. 25-31, 9, pp. 25-31, (1991)"))

    def test_fonte_repetida_com_numero_e_paginas(self):
        self.assertEqual(
            "Batanero Bernabeu C.; Godino J.; Steiner H.G.; Welzelburger E., "
            "1992, Educational Studies in Mathematics, V26, P95-102, ",
            converte_referencia(
                "Batanero Bernabeu C., Godino J., Steiner H.G., Welzelburger "
                "E., Educational Studies in Mathematics, 26, 1, pp. 95-102, "
                "Educational Studies In Mathematics 26 1 Pp. 95-102, 1, "
                "pp. 95-102, (1992)"))

    def test_marcador_de_numeracao_sai_da_referencia(self):
        self.assertEqual(
            "Fisher R.A., 1930, Proceedings Of The Cambridge Philosophical "
            "Society, V26, P528-535, Inverse probability",
            converte_referencia(
                "[18] Fisher R.A., Inverse probability, Proceedings Of The "
                "Cambridge Philosophical Society, 26, pp. 528-535, (1930)"))
        self.assertEqual(
            "Fisher R.A., 1930, Proceedings, V26, P528-535, Inverse probability",
            converte_referencia(
                "12. Fisher R.A., Inverse probability, Proceedings, 26, "
                "pp. 528-535, (1930)"))

    def test_editora_repetida(self):
        self.assertEqual(
            "Benzecri J.P., 1982, Paris: Dunod, , , ",
            converte_referencia("Benzecri J.P., Paris: Dunod, Paris Dunod, (1982)"))

    def test_fonte_abreviada_em_duas_partes(self):
        self.assertEqual(
            "Estepa Castro A., 1990, Univ Granada, , , Concepciones iniciales "
            "sobre la asociacion estadistica",
            converte_referencia(
                "Estepa Castro A., Concepciones iniciales sobre la asociacion "
                "estadistica, Univ, Granada, (1990)"))

    def test_fonte_repetida_de_um_token(self):
        self.assertEqual(
            "Cuadras C.M., 1991, PPU, , , ",
            converte_referencia("Cuadras C.M., PPU, Ppu, (1991)"))

    def test_nome_solto_e_ano_solto_sao_descartados(self):
        self.assertIsNone(converte_referencia("Zacek M."))
        self.assertIsNone(converte_referencia("(2020)"))


class LeitorTest(unittest.TestCase):

    def escreve(self, nome, texto):
        pasta = Path(tempfile.mkdtemp())
        caminho = pasta / nome
        caminho.write_text(texto, encoding="utf-8")
        return caminho

    def test_bibtex(self):
        caminho = self.escreve("teste.bib", """
@article{lopes2020,
  title = {Statistics education and teacher training},
  author = {Lopes, Celi Espasandin and Mendonça, Luzia Aparecida},
  journal = {Boletim de Educação Matemática},
  year = {2020},
  keywords = {statistics education; teacher education}
}
""")
        documentos = bibtex.le(caminho)
        self.assertEqual(1, len(documentos))
        self.assertEqual("Statistics education and teacher training",
                         documentos[0].titulo)
        self.assertEqual(["Lopes, C.E.", "Mendonça, L.A."],
                         documentos[0].autores)
        self.assertEqual("2020", documentos[0].ano)
        self.assertEqual(2, len(documentos[0].palavras_autor))

    def test_ris(self):
        caminho = self.escreve("teste.ris", """TY  - JOUR
AU  - Wee, S.J.
TI  - Culture and teacher education
PY  - 2024
T2  - Journal of Early Childhood Teacher Education
KW  - teacher education
ER  -
""")
        documentos = ris.le(caminho)
        self.assertEqual(1, len(documentos))
        self.assertEqual("Culture and teacher education", documentos[0].titulo)
        self.assertEqual(["Wee, S.J."], documentos[0].autores)
        self.assertEqual("2024", documentos[0].ano)
        self.assertEqual("Journal of Early Childhood Teacher Education",
                         documentos[0].periodico)

    def test_csv(self):
        caminho = self.escreve("teste.csv", (
            "Title,Authors,Year,AuthorKeywords,References\n"
            '"Um artigo","Silva A.//Souza B.",2020,"tema um//tema dois",'
            '"Silva A., Um trabalho, Revista X, 12, pp. 3-4, (2020)"\n'))
        documentos = csv_loader.le(caminho)
        self.assertEqual(1, len(documentos))
        self.assertEqual(["Silva A.", "Souza B."], documentos[0].autores)
        self.assertEqual(["tema um", "tema dois"], documentos[0].palavras_autor)
        self.assertTrue(documentos[0].referencias_convertidas)
        self.assertEqual(1, len(documentos[0].referencias))

    def test_scopus_com_virgula(self):
        caminho = self.escreve("scopus.csv", (
            '"Authors","Author full names","Title","Year","Source title",'
            '"Cited by (since 2021)","DOI","Document Type","Abstract",'
            '"Author Keywords","Index Keywords","References","Affiliations"\n'
            '"Lopes, C.E.; Souza, L.O.","Lopes, Celi; Souza, Luzia",'
            '"Statistics education, teacher training","2020","Bolema",'
            '"7","10.1000/xyz","Article",'
            '"Estudo com\nquebra de linha","Statistics education; Teacher training",'
            '"STATISTICS-EDUCATION; TEACHER-TRAINING",'
            '"Dagiene V.; Sentance S., It’s computational thinking, In '
            'Proceedings, pp. 28-39, (2016); Lopes C.E., Formação de '
            'professores, Bolema, 33, 1, pp. 1-10, (2019)",'
            '"Universidade A; Universidade B"\n'))
        documentos = scopus.le(caminho)
        self.assertEqual(1, len(documentos))
        documento = documentos[0]
        self.assertEqual(["Lopes, C.E.", "Souza, L.O."], documento.autores)
        self.assertEqual("7", str(documento.citacoes))
        self.assertEqual(["Statistics education", "Teacher training"],
                         documento.palavras_autor)
        self.assertEqual(["STATISTICS-EDUCATION", "TEACHER-TRAINING"],
                         documento.palavras_fonte)
        self.assertEqual(2, len(documento.referencias))
        self.assertIn("Dagiene V.; Sentance S., 2016", documento.referencias[0])
        self.assertIn("Lopes C.E., 2019", documento.referencias[1])

    def test_scopus_autor_com_id_numerico(self):
        caminho = self.escreve("scopus-id.csv", (
            '"Author full names";"Title";"Year"\n'
            '"Garrity, Sheila (36967424000); Canavan, John (30667536200)";'
            '"Um artigo";"2018"\n'))
        documentos = scopus.le(caminho)
        self.assertEqual(["Garrity, Sheila", "Canavan, John"],
                         documentos[0].autores)

    def test_scopus_com_ponto_e_virgula(self):
        caminho = self.escreve("scopus-pv.csv", (
            '"Authors";"Title";"Year";"Cited by";"Source title"\n'
            '"Silva, A.";"Um artigo";"2018";"3";"Revista X"\n'))
        documentos = scopus.le(caminho)
        self.assertEqual(1, len(documentos))
        self.assertEqual("Um artigo", documentos[0].titulo)
        self.assertEqual("3", str(documentos[0].citacoes))
        self.assertEqual("Revista X", documentos[0].periodico)

    def test_importacao_reconhece_scopus_com_extensao_csv(self):
        caminho = self.escreve("dados.csv", (
            '"Authors";"Title";"Year";"Author Keywords";"Document Type"\n'
            '"Silva, A.";"Um artigo";"2019";"tema um; tema dois";"Article"\n'))
        pasta = Path(tempfile.mkdtemp())
        resultado = importa(pasta, caminho.read_bytes(), "dados.csv", "auto",
                            "2019-2020", "teste")
        self.assertEqual("scopus", resultado["formato"])
        self.assertEqual(1, resultado["resumo"]["documentos"])
        # Mesmo que o usuário escolha o CSV genérico, o conteúdo manda.
        outro = importa(pasta, caminho.read_bytes(), "dados.csv", "csv",
                        "2019-2020", "teste")
        self.assertEqual("scopus", outro["formato"])

    def test_importacao_corrige_openalex_escolhido_como_scopus(self):
        caminho = self.escreve("batanero.csv", (
            'Authors,Author full names,Title,Year,Source title,OpenAlex ID,'
            'Author Keywords\n'
            '"Silva A., Souza B.","Silva, A.; Souza, B.","Um artigo",2020,'
            '"Revista X","W1","tema um; tema dois"\n'))
        pasta = Path(tempfile.mkdtemp())
        resultado = importa(pasta, caminho.read_bytes(), "batanero.csv",
                            "scopus", "2020-2021", "teste")
        self.assertEqual("openalex", resultado["formato"])
        self.assertEqual(1, resultado["resumo"]["documentos"])
        with __import__("redes.kb", fromlist=["ProjetoScimat"]).ProjetoScimat(
                resultado["projeto"]["caminho"]) as projeto:
            autores = projeto.conexao.execute(
                "SELECT authors FROM Document").fetchone()[0]
        self.assertEqual("Silva A., Souza B.", autores)

    def test_pais_no_fim_da_afiliacao(self):
        self.assertEqual("Espanha", pais_da_afiliacao(
            "Universidad de Granada, Granada, Spain"))
        self.assertEqual("Estados Unidos", pais_da_afiliacao(
            "Harvard University, Cambridge, MA, USA"))
        self.assertEqual("Reino Unido", pais_da_afiliacao(
            "University of Sheffield, Sheffield, United Kingdom"))
        self.assertEqual("", pais_da_afiliacao("Universidade de São Paulo"))

    def test_paises_no_openalex(self):
        caminho = self.escreve("openalex.csv", (
            'Authors,Author full names,Title,Year,Source title,OpenAlex ID,'
            'Affiliations,Country,Author Keywords\n'
            '"Silva A.","Silva, A.","Um artigo",2020,"Revista X","W1",'
            '"Univ. de Granada, Granada, Spain; Univ. de Chile, Santiago, Chile",'
            '"Spain","tema"\n'))
        documentos = openalex.le(caminho)
        self.assertEqual(["Espanha", "Chile"], documentos[0].paises)

    def test_paises_na_scopus(self):
        caminho = self.escreve("scopus.csv", (
            '"Authors";"Title";"Year";"Affiliations";"Document Type"\n'
            '"Silva, A.";"Um artigo";"2020";'
            '"Univ. de Granada, Granada, Spain; Univ. de Londres, London, '
            'United Kingdom";"Article"\n'))
        documentos = scopus.le(caminho)
        self.assertEqual(["Espanha", "Reino Unido"], documentos[0].paises)

    def test_importacao_grava_paises_e_extensao_redes(self):
        caminho = self.escreve("dados.csv", (
            "Title,Authors,Year,AuthorKeywords,Affiliations\n"
            '"Um artigo","Silva A.//Souza B.",2020,"tema",'
            '"Univ. de Granada, Granada, Spain//Univ. de Londres, London, '
            'United Kingdom"\n'))
        pasta = Path(tempfile.mkdtemp())
        resultado = importa(pasta, caminho.read_bytes(), "dados.csv", "auto",
                            "2020-2021", "teste")
        arquivo = Path(resultado["projeto"]["caminho"])
        self.assertEqual("dados.redes", arquivo.name)
        self.assertTrue(e_projeto(arquivo))
        self.assertTrue(e_projeto(arquivo.with_suffix(".scimat")))
        self.assertEqual(2, resultado["resumo"]["paises"])
        self.assertEqual(
            2, resultado["resumo"]["unidades"]["Countries"]["itens"])

    def test_deteccao_pelo_conteudo(self):
        scopus_csv = self.escreve("scopus.csv", (
            '"Authors";"Title";"Year";"Index Keywords";"Document Type"\n'
            '"Silva, A.";"Um artigo";"2018";"TEMA";"Article"\n'))
        self.assertEqual("scopus", detecta_formato(scopus_csv))

        simat = self.escreve("dados.csv", (
            "Title,Authors,Year,AuthorKeywords\n"
            '"Um artigo","Silva A.//Souza B.",2020,"tema um"\n'))
        self.assertEqual("csv", detecta_formato(simat))

        openalex_csv = self.escreve("batanero.csv", (
            "Authors,Author full names,Title,Year,Source title,OpenAlex ID,"
            "Author Keywords\n"
            '"Silva A., Souza B.","Silva, A.; Souza, B.",'
            '"Um artigo",2020,"Revista X","W123","tema um; tema dois"\n'))
        self.assertEqual("openalex", detecta_formato(openalex_csv))

        self.assertEqual("bibtex", detecta_formato(self.escreve(
            "x.csv", "@article{a, title={T}, author={Silva, A.}, year={2020}}")))
        self.assertEqual("ris", detecta_formato(self.escreve(
            "x.txt", "TY  - JOUR\nTI  - T\nER  -\n")))
        self.assertEqual("wos", detecta_formato(self.escreve(
            "x.txt", "FN Clarivate\nVR 1.0\nPT J\nTI T\nER\n")))

    def test_openalex_canonicaliza_palavras_e_extrai_fonte(self):
        caminho = self.escreve("teste.csv", (
            "Title,Authors,Author full names,Source title,Year,Cited by,"
            "Author Keywords,Source Keywords,References\n"
            '"Statistics education","Lopes, C.E.",'
            '"Celi Espasandin Lopes","Bolema",2020,5,'
            '"Statistics Education; statistics education",'
            '"STATISTICS-EDUCATION",'
            '"Lopes, C. E., Formação de professores, Bolema, 33, 1, '
            'pp. 1-10, (2019)"\n'))
        documentos = openalex.le(caminho)
        self.assertEqual(1, len(documentos))
        self.assertEqual(["STATISTICS-EDUCATION"],
                         documentos[0].palavras_autor)
        self.assertEqual(
            "Lopes C. E., 2019, Bolema, V33, P1-10, "
            "Formação de professores", documentos[0].referencias[0])


if __name__ == "__main__":
    unittest.main()

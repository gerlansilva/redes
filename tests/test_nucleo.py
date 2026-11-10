"""Testes do esquema, da grade e das novas opções de análise."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scimatpy import schema
from scimatpy.build import constroi
from scimatpy.grade import grade
from scimatpy.loaders.base import DocumentoFonte
from scimatpy.pipeline import Configuracao
from scimatpy.mappers import MAPEADORES
from scimatpy.kb import ProjetoScimat


def _projeto(destino: Path) -> Path:
    documentos = [
        DocumentoFonte(
            titulo="Um artigo", autores=["Silva, A.", "Costa, B."], ano="2020",
            citacoes=4, periodico="Revista X",
            palavras_autor=["tema um", "tema dois"],
            palavras_fonte=["revista x"],
            referencias=["Silva, A., 2010, Revista Y, 1, 1-10"]),
        DocumentoFonte(
            titulo="Outro artigo", autores=["Silva, A."], ano="2021",
            citacoes=2, periodico="Revista X",
            palavras_autor=["tema dois", "tema tres"],
            palavras_fonte=["revista x"]),
    ]
    constroi(documentos, destino, [("2020–2021", 2020, 2021)])
    return destino


class EsquemaTest(unittest.TestCase):

    def test_estrutura_completa(self):
        caminho = Path(tempfile.mkdtemp()) / "dados.scimat"
        _projeto(caminho)
        conexao = sqlite3.connect(caminho)
        try:
            tabelas = {linha[0] for linha in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
            gatilhos = conexao.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger'"
            ).fetchone()[0]
            versao = conexao.execute(
                "SELECT knowledgeBaseVersion FROM KnowledgeBaseVersion").fetchone()[0]
        finally:
            conexao.close()

        obrigatorias = {
            "KnowledgeBaseVersion", "Affiliation", "Author_Affiliation",
            "Document_Affiliation", "SubjectCategory",
            "Journal_SubjectCategory_PublishDate", "Document", "Word",
            "ReferenceSourceGroup",
        }
        self.assertTrue(obrigatorias.issubset(tabelas))
        self.assertEqual(34, gatilhos)
        self.assertEqual(schema.VERSAO, versao)

    def test_unidade_paises(self):
        caminho = Path(tempfile.mkdtemp()) / "dados.redes"
        constroi([
            DocumentoFonte(titulo="Um", autores=["Silva, A."], ano="2020",
                           paises=["Espanha", "Chile"]),
            DocumentoFonte(titulo="Dois", autores=["Costa, B."], ano="2021",
                           paises=["Espanha"]),
        ], caminho, [("2020–2021", 2020, 2021)])
        with ProjetoScimat(caminho) as projeto:
            periodo = projeto.periodos()[0]
            conjunto = projeto.dataset("Countries", periodo.id)
        self.assertEqual(2, conjunto.quantidade_itens())
        self.assertEqual(2, conjunto.quantidade_documentos())

    def test_projeto_antigo_sem_tabelas_de_pais(self):
        caminho = Path(tempfile.mkdtemp()) / "dados.scimat"
        _projeto(caminho)
        conexao = sqlite3.connect(caminho)
        try:
            conexao.execute("DROP TABLE Document_Country")
            conexao.execute("DROP TABLE Country")
            conexao.execute("DROP TABLE CountryGroup")
            conexao.commit()
        finally:
            conexao.close()
        with ProjetoScimat(caminho) as projeto:
            periodo = projeto.periodos()[0]
            conjunto = projeto.dataset("Countries", periodo.id)
        self.assertEqual(0, conjunto.quantidade_itens())

    def test_coluna_com_nome_do_fork(self):
        caminho = Path(tempfile.mkdtemp()) / "dados.scimat"
        _projeto(caminho)
        conexao = sqlite3.connect(caminho)
        try:
            colunas = [linha[1] for linha in conexao.execute(
                "PRAGMA table_info(ReferenceSource)")]
        finally:
            conexao.close()
        self.assertIn("ReferenceSourceGroup_idReferencesourceGroup", colunas)

    def test_contadores_mantidos_pelos_gatilhos(self):
        caminho = Path(tempfile.mkdtemp()) / "dados.scimat"
        _projeto(caminho)
        conexao = sqlite3.connect(caminho)
        try:
            documento = conexao.execute(
                "SELECT document_wordsCount, authorWordsCount, sourceWordsCount, "
                "document_referencesCount, year FROM Document "
                "WHERE idDocument = 1").fetchone()
            palavra = conexao.execute(
                "SELECT word_documentsCount, roleAuthorCount FROM Word "
                "WHERE wordName = 'TEMA-DOIS'").fetchone()
        finally:
            conexao.close()
        self.assertEqual((3, 2, 1, 1, "2020"), documento)
        self.assertEqual((2, 2), palavra)


class GradeTest(unittest.TestCase):

    def test_162_linhas_distintas(self):
        linhas = list(grade())
        self.assertEqual(162, len(linhas))
        self.assertEqual(162, len(set(linhas)))

    def test_mapeador_e_medida_na_linha(self):
        linhas = [linha for linha in grade() if linha[0] == "MAPEADOR"]
        self.assertEqual(6, len(linhas))
        self.assertTrue(all(linha[9] == "interseccao" for linha in linhas))
        medidas = [linha for linha in grade() if linha[0] == "MEDIDA"]
        self.assertEqual(48, len(medidas))
        self.assertTrue(all(linha[10] for linha in medidas))


class ConfiguracaoTest(unittest.TestCase):

    def test_kcore_aceito(self):
        config = Configuracao(mapeadores=("kcore",))
        config.valida()

    def test_acoplamento_aceito(self):
        self.assertIn("acoplamento", MAPEADORES)
        Configuracao(mapeadores=("acoplamento",)).valida()

    def test_origem_invalida_rejeitada(self):
        with self.assertRaises(ValueError):
            Configuracao(palavras=("resumo",)).valida()

    def test_corte_negativo_rejeitado(self):
        with self.assertRaises(ValueError):
            Configuracao(corte=-1).valida()


class AnaliseTest(unittest.TestCase):

    def test_corte_afeta_aglomeracao(self):
        caminho = Path(tempfile.mkdtemp()) / "dados.scimat"
        _projeto(caminho)
        with ProjetoScimat(caminho) as kb:
            periodo = kb.periodos()[0]
            from scimatpy.pipeline import executa_periodo
            sem_corte = executa_periodo(kb, periodo.id, periodo.nome, Configuracao(
                algoritmo="AverageLink", minimo_frequencia=1, corte=0.0))
            com_corte = executa_periodo(kb, periodo.id, periodo.nome, Configuracao(
                algoritmo="AverageLink", minimo_frequencia=1, corte=1.5))
        self.assertNotEqual(len(sem_corte.grupos), len(com_corte.grupos))

    def test_palavras_por_origem(self):
        caminho = Path(tempfile.mkdtemp()) / "dados.scimat"
        _projeto(caminho)
        with ProjetoScimat(caminho) as kb:
            periodo = kb.periodos()[0]
            todas = kb.dataset("Words", periodo.id, ("autor", "fonte"))
            autor = kb.dataset("Words", periodo.id, ("autor",))
            fonte = kb.dataset("Words", periodo.id, ("fonte",))
        self.assertEqual(4, todas.quantidade_itens())
        self.assertEqual(3, autor.quantidade_itens())
        self.assertEqual(1, fonte.quantidade_itens())

    def test_kcore_mapeia_documentos(self):
        caminho = Path(tempfile.mkdtemp()) / "dados.scimat"
        _projeto(caminho)
        with ProjetoScimat(caminho) as kb:
            periodo = kb.periodos()[0]
            from scimatpy.pipeline import executa_periodo
            resultado = executa_periodo(kb, periodo.id, periodo.nome, Configuracao(
                minimo_frequencia=1, mapeadores=("kcore",), k_core=2))
        self.assertTrue(resultado.grupos)


if __name__ == "__main__":
    unittest.main()

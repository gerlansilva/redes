"""Testes da edição da base: períodos, grupos, substituição e desfazer."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scimatpy import edit, exports
from scimatpy.build import constroi
from scimatpy.loaders.base import DocumentoFonte


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
            palavras_autor=["tema dois", "tema tres"]),
    ]
    constroi(documentos, destino, [("2020–2021", 2020, 2021)])
    return destino


class EdicaoTest(unittest.TestCase):

    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.caminho = _projeto(self.pasta / "dados.scimat")

    def _conexao(self):
        conexao = sqlite3.connect(self.caminho)
        conexao.row_factory = sqlite3.Row
        self.addCleanup(conexao.close)
        return conexao

    def test_periodo_criado_e_excluido(self):
        resumo = edit.cria_periodo(self.caminho, "2022–2023", 2022, 2023)
        self.assertEqual(2, len(resumo["periodos"]))
        criado = [p for p in resumo["periodos"] if p["nome"] == "2022–2023"][0]
        self.assertEqual(0, criado["documentos"])

        resumo = edit.exclui_periodo(self.caminho, criado["id"])
        self.assertEqual(1, len(resumo["periodos"]))

    def test_redistribuir_move_documentos(self):
        periodo = edit.resume(self.caminho)["periodos"][0]
        resumo = edit.redistribui_periodo(self.caminho, periodo["id"], 2020, 2020)
        self.assertEqual(1, resumo["periodos"][0]["documentos"])
        self.assertEqual(1, resumo["periodos"][0]["datas"])

    def test_juntar_grupos_move_itens(self):
        grupos = edit.resume(self.caminho)["grupos"]["palavra"]
        origem, destino = grupos[0], grupos[1]
        resumo = edit.junta_grupos(self.caminho, "palavra",
                                   origem["id"], destino["id"])
        self.assertEqual(len(grupos) - 1, len(resumo["grupos"]["palavra"]))

        conexao = self._conexao()
        itens = conexao.execute(
            "SELECT COUNT(*) FROM Word WHERE WordGroup_idWordGroup = ?",
            (destino["id"],)).fetchone()[0]
        contador = conexao.execute(
            "SELECT itemsCount FROM WordGroup WHERE idWordGroup = ?",
            (destino["id"],)).fetchone()[0]
        self.assertEqual(itens, contador)

    def test_substituir_grafia(self):
        grupos = edit.resume(self.caminho)["grupos"]["palavra"]
        antigo = grupos[0]["nome"]
        resumo = edit.substitui(self.caminho, "palavra", antigo, "TEMA NOVO")
        nomes = [g["nome"] for g in resumo["grupos"]["palavra"]]
        self.assertIn("TEMA NOVO", nomes)
        self.assertNotIn(antigo, nomes)

    def test_desfazer_restaura_arquivo(self):
        antes = self.caminho.read_bytes()
        grupos = edit.resume(self.caminho)["grupos"]["palavra"]
        edit.junta_grupos(self.caminho, "palavra",
                          grupos[0]["id"], grupos[1]["id"])
        self.assertNotEqual(antes, self.caminho.read_bytes())

        edit.desfaz(self.caminho)
        self.assertEqual(antes, self.caminho.read_bytes())

    def test_exportacoes_sao_bem_formadas(self):
        resumo = edit.resume(self.caminho)
        self.assertEqual(2, resumo["documentos"])
        conexao = self._conexao()
        ET.fromstring(exports.grupos_xml(conexao))

    def test_contadores_continuam_consistentes(self):
        grupos = edit.resume(self.caminho)["grupos"]["palavra"]
        edit.junta_grupos(self.caminho, "palavra",
                          grupos[0]["id"], grupos[1]["id"])
        conexao = self._conexao()
        divergencias = conexao.execute(
            "SELECT COUNT(*) FROM WordGroup g WHERE g.itemsCount <> "
            "(SELECT COUNT(*) FROM Word w WHERE "
            " w.WordGroup_idWordGroup = g.idWordGroup)").fetchone()[0]
        self.assertEqual(0, divergencias)


if __name__ == "__main__":
    unittest.main()

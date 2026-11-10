"""Correções do relatório de QA: relatórios, XML/SVG válidos, avisos, projetos soltos."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
import xml.dom.minidom
from collections import OrderedDict
from pathlib import Path

from scimatpy import api, exports
from scimatpy.build import constroi
from scimatpy.kb import ProjetoScimat
from scimatpy.loaders import ris
from scimatpy.loaders.base import DocumentoFonte
from scimatpy.pipeline import Configuracao, executa_periodo
from scimatpy.references import nome_do_grupo
from scimatpy.viz.halo import halo_svg
from scimatpy.viz.strategic import diagrama_svg


def _projeto(pasta: Path, palavras_por_doc, nome="dados.redes") -> Path:
    documentos = [
        DocumentoFonte(titulo=f"Doc {i}", ano="2020", palavras_autor=list(p))
        for i, p in enumerate(palavras_por_doc)]
    caminho = pasta / nome
    constroi(documentos, caminho, [("2020–2020", 2020, 2020)])
    return caminho


class QaTest(unittest.TestCase):

    def test_relatorios_e_ordered_dict(self):
        self.assertIsInstance(api.RELATORIOS, OrderedDict)
        for i in range(8):  # popitem(last=False) quebrava a partir do 6º
            api.RELATORIOS[f"t{i}"] = Path("/tmp")
            while len(api.RELATORIOS) > 5:
                api.RELATORIOS.popitem(last=False)
        self.assertEqual(5, len(api.RELATORIOS))

    def test_grupos_xml_com_aspas_e_e_comercial(self):
        pasta = Path(tempfile.mkdtemp())
        caminho = _projeto(pasta, [['say "hi" & bye', "b"], ['say "hi" & bye', "b"]])
        conexao = sqlite3.connect(caminho)
        texto = exports.grupos_xml(conexao)
        conexao.close()
        xml.dom.minidom.parseString(texto.encode("utf-8"))  # não pode levantar

    def test_svgs_com_e_comercial_sao_xml_valido(self):
        pasta = Path(tempfile.mkdtemp())
        docs = [["R&D teaching", "tests <and> more"]] * 3 + [["a", "b"]] * 3
        caminho = _projeto(pasta, docs)
        with ProjetoScimat(caminho) as kb:
            periodo = kb.periodos()[0]
            resultado = executa_periodo(kb, periodo.id, periodo.nome, Configuracao())
        for svg in (halo_svg(resultado, "Rede R&D \"x\" — {unidade}"),
                    diagrama_svg(resultado, "Estratégico R&D")):
            xml.dom.minidom.parseString(svg.encode("utf-8"))

    def test_aviso_de_termo_generico_e_ignorar(self):
        pasta = Path(tempfile.mkdtemp())
        docs = [["estatistica", f"tema{i % 5}", f"outro{i % 4}"] for i in range(20)]
        caminho = _projeto(pasta, docs)
        resposta = api.analisa({"projeto": str(caminho), "unidade": "Words"})
        codigos = [a["codigo"] for a in resposta["avisos"]]
        self.assertIn("termo_generico", codigos)
        self.assertEqual("ESTATISTICA", resposta["termos_genericos"][0]["rotulo"])

        depois = api.analisa({"projeto": str(caminho), "unidade": "Words",
                              "ignorar": ["Estatística"]})
        self.assertNotIn("termo_generico", [a["codigo"] for a in depois["avisos"]])
        self.assertEqual(resposta["resumo"]["itens_reduzidos"] - 1,
                         depois["resumo"]["itens_reduzidos"])

    def test_aviso_de_grupos_fracos(self):
        pasta = Path(tempfile.mkdtemp())
        # cada documento tem um par exclusivo de palavras: grupos de 1 documento
        docs = [[f"a{i}", f"b{i}"] for i in range(12)]
        caminho = _projeto(pasta, docs)
        resposta = api.analisa({"projeto": str(caminho), "unidade": "Words",
                                "mapeadores": ["nucleo"]})
        self.assertIn("grupos_fracos", [a["codigo"] for a in resposta["avisos"]])

    def test_layout_so_roda_quando_a_tela_pede(self):
        pasta = Path(tempfile.mkdtemp())
        caminho = _projeto(pasta, [["a", "b", "c"]] * 3 + [["d", "e"]] * 3)
        resposta = api.analisa({"projeto": str(caminho), "unidade": "Words"})
        self.assertIsNone(api.ANALISES[resposta["token"]]["rede"])
        rede = api.dados_rede(resposta["token"])
        self.assertEqual(resposta["resumo"]["nos"], len(rede["nos"]))
        self.assertIsNotNone(api.ANALISES[resposta["token"]]["rede"])

    def test_projetos_soltos_na_pasta(self):
        pasta = Path(tempfile.mkdtemp())
        _projeto(pasta, [["a", "b"]], "solto.redes")
        (pasta / "sub").mkdir()
        _projeto(pasta / "sub", [["a", "b"]])
        nomes = sorted(p["nome"] for p in api.lista_projetos(pasta))
        self.assertEqual(["solto", "sub"], nomes)

    def test_mensagem_do_mapa_explica_o_motivo(self):
        pasta = Path(tempfile.mkdtemp())
        caminho = _projeto(pasta, [["a", "b"]] * 3)
        resposta = api.analisa({"projeto": str(caminho), "unidade": "Words"})
        with self.assertRaises(api.ErroApi) as ctx:
            api.dados_do_mapa(resposta["token"])
        self.assertIn("Países", str(ctx.exception))

    def test_ris_usa_ad_para_pais_e_da_para_ano(self):
        pasta = Path(tempfile.mkdtemp())
        arquivo = pasta / "a.ris"
        arquivo.write_text(
            "TY  - JOUR\nTI  - Titulo\nDA  - 2018/03/01\nAD  - Universidade de São Paulo, São Paulo, Brazil\nKW  - a; b\nER  -\n",
            encoding="utf-8")
        doc = ris.le(arquivo)[0]
        self.assertEqual("2018", doc.ano)
        self.assertEqual(["Brasil"], doc.paises)
        self.assertEqual(["a", "b"], doc.palavras_autor)

    def test_nome_de_grupo_de_referencia_nao_e_truncado(self):
        titulo = "Um título muito longo " * 6
        nome = nome_do_grupo(f"Silva A., , Sem fonte, , , {titulo}", set())
        self.assertNotIn("…", nome)


if __name__ == "__main__":
    unittest.main()


class PeriodosAutomaticosTest(unittest.TestCase):
    def test_divide_por_volume(self):
        from scimatpy.build import sugere_periodos
        anos = list(range(2011, 2026)) * 12
        faixas = sugere_periodos(anos)
        self.assertGreaterEqual(len(faixas), 2)
        self.assertEqual(faixas[0][1], 2011)
        self.assertEqual(faixas[-1][2], 2025)
        for (_, _, fim), (_, inicio, _) in zip(faixas, faixas[1:]):
            self.assertEqual(inicio, fim + 1)

    def test_corpus_pequeno_fica_em_um_periodo(self):
        from scimatpy.build import sugere_periodos
        self.assertEqual(len(sugere_periodos([2020, 2021, 2021, 2023])), 1)

    def test_quantidade_pedida(self):
        from scimatpy.build import sugere_periodos
        self.assertEqual(len(sugere_periodos(list(range(2005, 2026)) * 10, 3)), 3)

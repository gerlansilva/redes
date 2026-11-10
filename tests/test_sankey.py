import sqlite3
import tempfile
import unittest
from pathlib import Path

from scimatpy import build, fluxos
from scimatpy.loaders.base import DocumentoFonte
from scimatpy.viz import sankey


def _projeto(documentos):
    pasta = tempfile.TemporaryDirectory()
    destino = Path(pasta.name) / "p.redes"
    build.constroi(documentos, destino, None)
    conexao = sqlite3.connect(destino)
    return pasta, conexao


def _doc(i, autores, afiliacoes, por_autor=None, paises=None):
    metadados = {"Authors with affiliations": por_autor} if por_autor else {}
    return DocumentoFonte(titulo=f"Estudo {i}", ano=str(2015 + i % 4), autores=autores,
                          afiliacoes=afiliacoes, paises=paises or [], metadados=metadados)


def _com_ligacao_por_autor():
    docs = []
    for i in range(6):
        docs.append(_doc(
            i, ["Silva A.", "Souza B."],
            ["Universidade de São Paulo, São Paulo, Brazil", "University of Oxford, Oxford, United Kingdom"],
            "Silva A., Universidade de São Paulo, São Paulo, Brazil; "
            "Souza B., University of Oxford, Oxford, United Kingdom",
            ["Brasil", "Reino Unido"]))
    docs.append(_doc(6, ["Souza B."], ["University of Oxford, Oxford, United Kingdom"],
                     None, ["Reino Unido"]))
    return docs


class FluxoComLigacaoPorAutorTest(unittest.TestCase):
    def setUp(self):
        self.pasta, self.conexao = _projeto(_com_ligacao_por_autor())

    def tearDown(self):
        self.conexao.close()
        self.pasta.cleanup()

    def test_ligacao_exata_e_valores(self):
        dados = fluxos.calcula(self.conexao)
        self.assertEqual(dados["modo"], "autor_pais_ies")
        self.assertEqual(dados["colunas"], ["Autor", "País", "IES"])
        valores = {(l["origem"], l["destino"]): l["valor"] for l in dados["ligacoes"]}
        self.assertEqual(valores[("a:Silva A.", "p:Brasil")], 6)
        self.assertEqual(valores[("a:Souza B.", "p:Reino Unido")], 7)
        self.assertNotIn(("a:Silva A.", "p:Reino Unido"), valores)
        self.assertEqual(valores[("p:Brasil", "i:Universidade de São Paulo")], 6)
        self.assertEqual(dados["cobertura"]["exata"], 6)
        self.assertEqual(dados["cobertura"]["unica"], 1)
        self.assertEqual(dados["qualidade"], "parcial")
        self.assertTrue(any("única instituição" in a for a in dados["avisos"]))

    def test_respeita_grupos_de_autor_e_de_ies(self):
        self.conexao.execute("INSERT INTO AuthorGroup(groupName, stopGroup) VALUES ('Silva, Ana', 0)")
        self.conexao.execute("UPDATE Author SET AuthorGroup_idAuthorGroup = "
                             "(SELECT idAuthorGroup FROM AuthorGroup WHERE groupName='Silva, Ana') "
                             "WHERE authorName = 'Silva A.'")
        self.conexao.execute("CREATE TABLE IF NOT EXISTS InstitutionAlias("
                             "instituicao TEXT PRIMARY KEY, canonico TEXT)")
        self.conexao.execute("INSERT INTO InstitutionAlias VALUES ('Universidade de São Paulo', 'USP')")
        dados = fluxos.calcula(self.conexao)
        nomes = {n["nome"] for n in dados["nos"]}
        self.assertIn("Silva, Ana", nomes)
        self.assertIn("USP", nomes)
        self.assertNotIn("Silva A.", nomes)

    def test_limites_cortam_nos(self):
        dados = fluxos.calcula(self.conexao, limite_autores=1, limite_paises=1, limite_ies=1)
        autores = [n for n in dados["nos"] if n["coluna"] == 0]
        self.assertEqual(len(autores), 1)
        self.assertEqual(len([n for n in dados["nos"] if n["coluna"] == 1]), 1)


class FluxoSemLigacaoPorAutorTest(unittest.TestCase):
    def test_varias_afiliacoes_sem_ligacao_nao_inventa_vinculo(self):
        docs = [_doc(i, ["Silva A.", "Souza B."],
                     ["Universidade de São Paulo, São Paulo, Brazil",
                      "University of Oxford, Oxford, United Kingdom"],
                     None, ["Brasil", "Reino Unido"]) for i in range(5)]
        pasta, conexao = _projeto(docs)
        try:
            dados = fluxos.calcula(conexao)
        finally:
            conexao.close()
            pasta.cleanup()
        self.assertEqual(dados["modo"], "pais_ies")
        self.assertEqual(dados["colunas"], ["País", "IES"])
        self.assertEqual(dados["qualidade"], "indisponivel")
        self.assertFalse([n for n in dados["nos"] if n["id"].startswith("a:")])
        self.assertTrue(any("Falta a ligação autor–instituição" in a for a in dados["avisos"]))

    def test_instituicao_unica_e_aproximada(self):
        docs = [_doc(i, ["Silva A.", "Souza B."],
                     ["Universidade de São Paulo, São Paulo, Brazil"], None, ["Brasil"])
                for i in range(4)]
        pasta, conexao = _projeto(docs)
        try:
            dados = fluxos.calcula(conexao)
        finally:
            conexao.close()
            pasta.cleanup()
        self.assertEqual(dados["modo"], "autor_pais_ies")
        self.assertEqual(dados["qualidade"], "aproximada")
        self.assertTrue(any("aproximada" in a for a in dados["avisos"]))

    def test_sem_afiliacao_nem_pais(self):
        pasta, conexao = _projeto([_doc(i, ["Silva A."], []) for i in range(3)])
        try:
            dados = fluxos.calcula(conexao)
            bloco = fluxos.corpo_sankey_html(conexao)
        finally:
            conexao.close()
            pasta.cleanup()
        self.assertIsNone(dados["modo"])
        self.assertEqual(dados["nos"], [])
        self.assertEqual(sankey.svg(dados), "")
        self.assertIn("O que falta", bloco)
        self.assertNotIn("<svg", bloco)


class SvgTest(unittest.TestCase):
    def setUp(self):
        self.pasta, self.conexao = _projeto(_com_ligacao_por_autor())
        self.dados = fluxos.calcula(self.conexao)

    def tearDown(self):
        self.conexao.close()
        self.pasta.cleanup()

    def test_svg_valido_com_ids_unicos_e_tooltips(self):
        import re
        import xml.dom.minidom
        texto = sankey.svg(self.dados, "Fluxo <teste> & cia")
        xml.dom.minidom.parseString(texto)
        ids = re.findall(r'\bid="([^"]+)"', texto)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("&lt;teste&gt;", texto)
        self.assertIn('role="img"', texto)
        self.assertIn("Silva A. → Brasil: 6 documentos", texto)
        self.assertNotIn("<script", texto)

    def test_ids_distintos_para_dados_distintos(self):
        outro = fluxos.calcula(self.conexao, limite_autores=1)
        a = sankey.svg(self.dados)
        b = sankey.svg(outro)
        self.assertNotEqual(a[a.index('id="'):a.index('id="') + 12], b[b.index('id="'):b.index('id="') + 12])

    def test_ordenacao_sem_cruzamentos_quando_possivel(self):
        nos = [{"id": "a:1", "coluna": 0, "nome": "1", "valor": 5}, {"id": "a:2", "coluna": 0, "nome": "2", "valor": 4},
               {"id": "p:x", "coluna": 1, "nome": "x", "valor": 4}, {"id": "p:y", "coluna": 1, "nome": "y", "valor": 5}]
        ligacoes = [{"origem": "a:1", "destino": "p:y", "valor": 5, "pais": "y"},
                    {"origem": "a:2", "destino": "p:x", "valor": 4, "pais": "x"}]
        ordem = sankey.ordena(nos, ligacoes, 2)
        coluna = {n["id"]: n["coluna"] for n in nos}
        self.assertEqual(sankey._cruzamentos(ordem, ligacoes, coluna), 0)

    def test_bloco_html_numerado(self):
        bloco = fluxos.corpo_sankey_html(self.conexao, numero=7)
        self.assertIn("Figura 7 — ", bloco)
        self.assertIn("<svg", bloco)
        self.assertIn("O que falta", bloco)
        sem_numero = fluxos.corpo_sankey_html(self.conexao)
        self.assertIn("counter(fig-fluxo)", sem_numero)


class RotaTest(unittest.TestCase):
    def test_rota_devolve_dados_e_svg_e_valida_parametros(self):
        from scimatpy import api
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "p.redes"
            build.constroi(_com_ligacao_por_autor(), destino, None)
            dados = api.fluxo_autor_pais_ies({"caminho": str(destino), "autores": "1"})
            self.assertEqual(dados["limites"]["autores"], 3)  # mínimo imposto pela rota
            self.assertTrue(dados["svg"].startswith("<svg"))
            baixado = api.fluxo_autor_pais_ies({"caminho": str(destino), "baixar": "1"})
            self.assertIn("Fluxo Autor → País → IES", baixado["svg"])
            with self.assertRaises(api.ErroApi):
                api.fluxo_autor_pais_ies({"caminho": str(destino), "autores": "muitos"})
            with self.assertRaises(api.ErroApi):
                api.fluxo_autor_pais_ies({"caminho": str(Path(pasta) / "nao.redes")})


if __name__ == "__main__":
    unittest.main()

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scimatpy import bibliometria, build, edit, sugestoes
from scimatpy.loaders.base import DocumentoFonte


def _projeto():
    docs = [
        DocumentoFonte(titulo="A", ano="2015", autores=["Silva G.M."], palavras_autor=["statistics education"],
                       afiliacoes=["Dept. Math, Universidade Federal de São Carlos, São Carlos, Brazil"],
                       paises=["Brazil"], periodico="R"),
        DocumentoFonte(titulo="B", ano="2016", autores=["Silva G."], palavras_autor=["statistics educaton"],
                       afiliacoes=["Federal University of Sao Carlos, Brazil"], paises=["Brasil"], periodico="R"),
        DocumentoFonte(titulo="C", ano="2017", autores=["Souza P.R."], palavras_autor=["statistical literacy"],
                       afiliacoes=["University of Sydney, Australia"], paises=["Australia"], periodico="R"),
        DocumentoFonte(titulo="D", ano="2018", autores=["Souza P.R."], palavras_autor=["statistics education"],
                       afiliacoes=["Western Sydney University, Australia"], paises=["Australia"], periodico="R"),
    ]
    pasta = tempfile.mkdtemp()
    destino = Path(pasta) / "t.redes"
    build.constroi(docs, destino, periodos=[("Todos", 2015, 2018)])
    return destino


class SugestoesTest(unittest.TestCase):
    def test_autor_iniciais_compativeis(self):
        r = sugestoes.sugere(sqlite3.connect(_projeto()), "autor")
        grupos = [[m["nome"] for m in g["membros"]] for g in r["grupos"]]
        self.assertTrue(any({"Silva G.M.", "Silva G."} <= set(g) for g in grupos))
        self.assertTrue(all(g["confianca"] == "media" for g in r["grupos"]
                            if "Silva G." in [m["nome"] for m in g["membros"]]))

    def test_ies_outro_idioma_nao_confunde_sydney(self):
        con = sqlite3.connect(_projeto())
        r = sugestoes.sugere(con, "ies")
        grupos = [{m["nome"] for m in g["membros"]} for g in r["grupos"]]
        self.assertFalse(any("University of Sydney" in g and "Western Sydney University" in g for g in grupos))
        r2 = sugestoes.sugere(con, "ies", "University of Sydney")
        informados = [g for g in r2["grupos"] if g["informada"]]
        self.assertFalse(any("Western Sydney University" in {m["nome"] for m in g["membros"]} for g in informados))

    def test_lista_informada_e_sem_correspondencia(self):
        con = sqlite3.connect(_projeto())
        r = sugestoes.sugere(con, "palavra", "Educação Estatística = statistics education\nNada Parecido Aqui")
        self.assertIn("Nada Parecido Aqui", r["sem_correspondencia"])

    def test_lista_interpretada(self):
        lista = sugestoes.interpreta_lista("# nota\nUFSCar = Univ Fed São Carlos | UFSC\n\nUSP")
        self.assertEqual(lista[0]["apelidos"], ["Univ Fed São Carlos", "UFSC"])
        self.assertEqual(len(lista), 2)

    def test_tipo_invalido(self):
        with self.assertRaises(ValueError):
            sugestoes.sugere(sqlite3.connect(_projeto()), "xyz")


class AgrupamentoTest(unittest.TestCase):
    def test_agrupa_palavras_e_desfaz(self):
        caminho = _projeto()
        con = sqlite3.connect(caminho)
        r = sugestoes.sugere(con, "palavra")
        grupo = next(g for g in r["grupos"]
                     if {"STATISTICS-EDUCATION", "STATISTICS-EDUCATON"} & {m["nome"] for m in g["membros"]}
                     and len(g["membros"]) > 1) if r["grupos"] else None
        con.close()
        self.assertIsNotNone(grupo)
        edit.agrupa_sugestoes(caminho, "palavra", [{"canonico": "Statistics Education",
                                                    "membros": [m["id"] for m in grupo["membros"]]}])
        con = sqlite3.connect(caminho)
        nomes = [l[0] for l in con.execute("SELECT groupName FROM WordGroup")]
        self.assertIn("Statistics Education", nomes)
        edit.desfaz(caminho)

    def test_agrupa_paises(self):
        caminho = _projeto()
        con = sqlite3.connect(caminho)
        ids = [l[0] for l in con.execute("SELECT idCountryGroup FROM CountryGroup")]
        con.close()
        self.assertGreaterEqual(len(ids), 2)
        edit.agrupa_sugestoes(caminho, "pais", [{"canonico": "Países juntos", "membros": ids[:2]}])
        con = sqlite3.connect(caminho)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM CountryGroup WHERE groupName='Países juntos'").fetchone()[0], 1)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM CountryGroup").fetchone()[0], len(ids) - 1)

    def test_agrupa_ies_vira_apelido_e_afeta_ranking(self):
        caminho = _projeto()
        con = sqlite3.connect(caminho)
        antes = {i["nome"] for i in bibliometria.calcula(con)["instituicoes"]}
        con.close()
        nomes = [n for n in antes if "Carlos" in n]
        self.assertEqual(len(nomes), 2)
        edit.agrupa_sugestoes(caminho, "ies", [{"canonico": "UFSCar", "membros": nomes}])
        con = sqlite3.connect(caminho)
        depois = {i["nome"]: i["documentos"] for i in bibliometria.calcula(con)["instituicoes"]}
        self.assertEqual(depois["UFSCar"], 2)
        edit.desfaz(caminho)
        con = sqlite3.connect(caminho)
        self.assertIn(nomes[0], {i["nome"] for i in bibliometria.calcula(con)["instituicoes"]})

    def test_exige_dois_itens(self):
        caminho = _projeto()
        con = sqlite3.connect(caminho)
        i = con.execute("SELECT idCountryGroup FROM CountryGroup").fetchone()[0]
        con.close()
        with self.assertRaises(ValueError):
            edit.agrupa_sugestoes(caminho, "pais", [{"canonico": "X", "membros": [i]}])


class PluralELacunasTest(unittest.TestCase):
    def test_plural_analysis_analyses(self):
        from scimatpy.text_utils import mesmo_termo
        self.assertTrue(mesmo_termo("BIBLIOMETRIC-ANALYSIS", "BIBLIOMETRIC-ANALYSES"))
        self.assertTrue(mesmo_termo("ANALYSIS", "ANALYSES"))
        self.assertFalse(mesmo_termo("BOIS", "BOES"))  # radical curto demais

    def test_lacunas_listadas(self):
        caminho = _projeto()
        con = sqlite3.connect(caminho)
        d = bibliometria.calcula(con)
        texto = " ".join(d["lacunas"])
        self.assertIn("referências", texto)
        self.assertNotIn("Sem países", texto)


class RelatorioCompletoTest(unittest.TestCase):
    def test_gera_secoes_e_explica_o_que_falta(self):
        from scimatpy import api
        docs = [DocumentoFonte(
            titulo=f"Doc {i}", ano=str(2015 + i % 6), periodico="R",
            autores=[f"Autor {i % 5} A.", f"Autor {i % 3 + 5} B.", "Autor Z Z."],
            palavras_autor=[f"tema {i % 4}", f"tema {i % 3 + 4}", "geral"]) for i in range(40)]
        caminho = Path(tempfile.mkdtemp()) / "c.redes"
        build.constroi(docs, caminho, periodos=[("A", 2015, 2017), ("B", 2018, 2020)])
        r = api.gera_relatorio_completo({"projeto": str(caminho)})
        self.assertTrue(r["secoes"])
        self.assertTrue(any("referências" in i["motivo"] for i in r["ignoradas"]))
        pasta = api.RELATORIOS[r["token"]]
        index = (pasta / "index.html").read_text(encoding="utf-8")
        self.assertIn("Relatório completo", index)
        self.assertIn("Por período", index)
        self.assertTrue((pasta / "bibliometria.html").exists())
        self.assertIn("Relatório completo", (pasta / "conceitual" / "period0.html").read_text(encoding="utf-8")
                      if (pasta / "conceitual" / "period0.html").exists() else "Relatório completo")


if __name__ == "__main__":
    unittest.main()

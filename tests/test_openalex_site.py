import tempfile
import unittest
from pathlib import Path

from redes.loaders import detecta_formato, le_corpus

CSV = (
    "Title,Author,Year,Citation count,Open access,Author IDs,Country,Abstract\n"
    'Um estudo,Natália Desconsi de ANDRADE|Taciana Camera Segat,2016,3,Open Access,A1|A2,BR||,'
    '"Resumo do trabalho. Palavras-chave: educação infantil, gestão escolar."\n'
    "Outro,Taciana Camera Segat,2018,0,Open Access,A2,,Sem palavras.\n"
)


class OpenAlexSiteTest(unittest.TestCase):
    def test_exportacao_do_site(self):
        arquivo = Path(tempfile.mkdtemp()) / "works.csv"
        arquivo.write_text(CSV, encoding="utf-8")
        self.assertEqual(detecta_formato(arquivo), "openalex")
        docs, formato = le_corpus(arquivo, "auto")
        self.assertEqual(formato, "openalex")
        self.assertEqual(docs[0].autores, ["Andrade, N.D.", "Segat, T.C."])
        self.assertEqual(docs[0].paises, ["Brasil"])
        self.assertEqual(docs[0].citacoes, 3)
        self.assertEqual(len(docs[0].palavras_autor), 2)
        self.assertEqual(docs[1].autores, ["Segat, T.C."])
        self.assertEqual(docs[1].palavras_autor, [])


if __name__ == "__main__":
    unittest.main()

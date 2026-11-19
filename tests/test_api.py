"""Testes da interface web local (API HTTP e trabalhos em segundo plano)."""

from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from redes.api import cria_servidor
from redes.build import constroi
from redes.loaders.base import DocumentoFonte


def _projeto(workspace: Path) -> Path:
    documentos = [
        DocumentoFonte(
            titulo="Statistics education and teacher training",
            autores=["Lopes, C.E.", "Mendonça, L.A."],
            ano="2020",
            palavras_autor=["statistics education", "teacher education",
                            "probability"],
        ),
        DocumentoFonte(
            titulo="Probability teaching with technology",
            autores=["Santos, M."],
            ano="2021",
            palavras_autor=["probability", "teaching", "technology"],
        ),
    ]
    caminho = workspace / "teste" / "dados.redes"
    constroi(documentos, caminho, [("2020\u20132021", 2020, 2021)])
    return caminho


class ApiTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workspace = Path(tempfile.mkdtemp())
        cls.projeto = _projeto(cls.workspace)
        cls.servidor = cria_servidor(0, cls.workspace)
        cls.porta = cls.servidor.server_address[1]
        cls.thread = threading.Thread(target=cls.servidor.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.porta}"

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def pede(self, caminho, dados=None, metodo=None):
        corpo = None
        cabecalhos = {}
        if dados is not None:
            corpo = json.dumps(dados).encode("utf-8")
            cabecalhos["Content-Type"] = "application/json"
        pedido = urllib.request.Request(self.base + caminho, data=corpo,
                                        headers=cabecalhos,
                                        method=metodo or ("POST" if corpo else "GET"))
        with urllib.request.urlopen(pedido, timeout=120) as resposta:
            return resposta.status, resposta.read(), resposta.headers

    def test_lista_e_abre_projeto(self):
        _, corpo, _ = self.pede("/api/projetos")
        dados = json.loads(corpo)
        caminhos = [projeto["caminho"] for projeto in dados["projetos"]]
        self.assertIn(str(self.projeto.resolve()), caminhos)

        _, corpo, _ = self.pede("/api/abrir",
                                {"caminho": str(self.projeto)})
        projeto = json.loads(corpo)
        self.assertEqual(2, projeto["documentos"])
        self.assertEqual(1, len(projeto["periodos"]))

    def test_analisa_e_serve_figura(self):
        _, corpo, _ = self.pede("/api/analisa", {
            "projeto": str(self.projeto),
            "unidade": "Words",
            "minimo_frequencia": 1,
        })
        resultado = json.loads(corpo)
        self.assertGreater(resultado["resumo"]["grupos"], 0)
        self.assertEqual(resultado["resumo"]["documentos"], 2)
        self.assertIn("halo", resultado["figuras"])

        _, figura, cabecalhos = self.pede(resultado["figuras"]["halo"])
        self.assertIn("image/svg+xml", cabecalhos["Content-Type"])
        self.assertTrue(figura.startswith(b"<svg"))

        _, corpo, _ = self.pede(
            f"/api/grupo?token={resultado['token']}&selo=1")
        detalhe = json.loads(corpo)
        self.assertEqual(1, detalhe["grupo"]["selo"])
        self.assertTrue(detalhe["itens"])
        self.assertTrue(detalhe["documentos"])
        self.assertIn("titulo", detalhe["documentos"][0])

        _, corpo, _ = self.pede(f"/api/rede?token={resultado['token']}")
        rede = json.loads(corpo)
        self.assertEqual(resultado["resumo"]["nos"], len(rede["nos"]))
        self.assertEqual(resultado["resumo"]["grupos"], len(rede["grupos"]))
        self.assertIn("selo_x", rede["grupos"][0])
        for no in rede["nos"]:
            self.assertIn(no["grupo"], range(len(rede["grupos"])))

    def test_indices_documentos_e_exportacoes(self):
        _, corpo, _ = self.pede("/api/analisa", {
            "projeto": str(self.projeto),
            "unidade": "Words",
            "minimo_frequencia": 1,
            "mapeadores": ["nucleo", "interseccao"],
        })
        resultado = json.loads(corpo)
        token = resultado["token"]
        self.assertIn("medidas", resultado["grupos"][0])
        self.assertIn("nucleo", resultado["grupos"][0]["medidas"])

        _, corpo, _ = self.pede(
            f"/api/grupo?token={token}&selo=1")
        detalhe = json.loads(corpo)
        self.assertTrue(detalhe["medidas"])
        self.assertIn("nucleo", detalhe["documentos_por_mapeador"])

        _, corpo, _ = self.pede(
            f"/api/documentos?token={token}&busca=probability")
        documentos = json.loads(corpo)
        self.assertEqual(1, documentos["total"])

        for tipo in ("indices-tsv", "rede-pajek", "rede-graphml",
                     "grupos-xml", "documentos-tsv"):
            estado, dados, cabecalhos = self.pede(
                f"/api/exportar?token={token}&tipo={tipo}")
            self.assertEqual(200, estado)
            self.assertTrue(dados, tipo)
            self.assertIn("attachment", cabecalhos["Content-Disposition"])

        _, corpo, _ = self.pede("/api/relatorio", {
            "projeto": str(self.projeto),
            "unidade": "Words",
            "minimo_frequencia": 1,
            "formato": "html",
            "estendido": True,
        })
        relatorio = json.loads(corpo)
        estado, pagina, _ = self.pede(relatorio["url"])
        self.assertEqual(200, estado)
        self.assertIn(b"Relat", pagina)
        estado, figura, cabecalhos = self.pede(
            relatorio["indice"].replace(
                "index.html",
                "images/strategicDiagram-period0-nucleo-documentos.svg"))
        self.assertEqual(200, estado)
        self.assertIn("image/svg+xml", cabecalhos["Content-Type"])

    def test_mapa_longitudinal(self):
        documentos = [
            DocumentoFonte(
                titulo="Um", autores=["Silva, A."], ano="2010",
                palavras_autor=["tema um", "tema dois"]),
            DocumentoFonte(
                titulo="Dois", autores=["Silva, A."], ano="2011",
                palavras_autor=["tema um", "tema tres"]),
            DocumentoFonte(
                titulo="Tres", autores=["Costa, B."], ano="2020",
                palavras_autor=["tema um", "tema quatro"]),
            DocumentoFonte(
                titulo="Quatro", autores=["Costa, B."], ano="2021",
                palavras_autor=["tema um", "tema cinco"]),
        ]
        caminho = self.workspace / "longitudinal" / "dados.redes"
        constroi(documentos, caminho, [("2010–2011", 2010, 2011),
                                       ("2020–2021", 2020, 2021)])

        _, corpo, _ = self.pede("/api/longitudinal", {
            "projeto": str(caminho),
            "unidade": "Words",
            "minimo_frequencia": 1,
        })
        mapa = json.loads(corpo)
        self.assertEqual(2, len(mapa["periodos"]))
        self.assertEqual(2, len(mapa["sobreposicao"]))
        self.assertGreater(mapa["nos"], 0)

        _, figura, cabecalhos = self.pede(mapa["figuras"]["evolucao"])
        self.assertIn("image/svg+xml", cabecalhos["Content-Type"])
        self.assertTrue(figura.startswith(b"<svg"))

    def test_grade_conclui_e_baixa_tsv(self):
        _, corpo, _ = self.pede("/api/grade", {"projeto": str(self.projeto)})
        trabalho = json.loads(corpo)
        self.assertEqual(162, trabalho["total"])

        limite = time.time() + 120
        while time.time() < limite:
            _, corpo, _ = self.pede(f"/api/trabalho/{trabalho['id']}")
            estado = json.loads(corpo)
            if estado["estado"] != "executando":
                break
            time.sleep(0.2)

        self.assertEqual("concluido", estado["estado"], estado.get("erro"))
        self.assertEqual(162, estado["resultado"]["analises"])

        _, tsv, _ = self.pede(estado["resultado"]["download"])
        linhas = tsv.decode("utf-8").strip().splitlines()
        self.assertEqual(163, len(linhas))

    def test_importa_csv_e_analisa(self):
        csv = (
            "Title,Authors,Year,AuthorKeywords\n"
            '"Um artigo","Silva A.//Souza B.",2020,"tema um//tema dois"\n'
            '"Outro artigo","Silva A.",2021,"tema um"\n'
        ).encode("utf-8")
        pedido = urllib.request.Request(
            self.base + "/api/importar?formato=csv&periodos=2020-2021&nome=importado",
            data=csv,
            headers={"X-Nome-Arquivo": "corpus.csv"},
            method="POST")
        with urllib.request.urlopen(pedido, timeout=120) as resposta:
            dados = json.loads(resposta.read())

        self.assertEqual(2, dados["resumo"]["documentos"])
        _, corpo, _ = self.pede("/api/analisa", {
            "projeto": dados["projeto"]["caminho"],
            "unidade": "Words",
            "minimo_frequencia": 1,
        })
        self.assertGreater(json.loads(corpo)["resumo"]["grupos"], 0)


if __name__ == "__main__":
    unittest.main()

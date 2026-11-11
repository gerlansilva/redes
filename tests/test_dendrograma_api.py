"""Rota /api/dendrograma (servidor em processo, como em test_api)."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from redes.api import cria_servidor
from redes.build import constroi
from redes.loaders.base import DocumentoFonte

TEMAS = [["estatistica", "probabilidade", "ensino", "graficos", "media"],
         ["formacao", "professores", "docencia", "curriculo", "pratica"],
         ["tecnologia", "software", "dados", "simulacao", "planilha"]]


def _projeto(workspace: Path) -> Path:
    documentos = []
    for i in range(18):
        palavras = list(TEMAS[i % 3])
        if i % 6 == 0:
            palavras.append(TEMAS[(i + 1) % 3][0])
        documentos.append(DocumentoFonte(
            titulo=f"Documento {i}", autores=[f"Autor, {i}."],
            ano=str(2020 + i % 2), palavras_autor=palavras))
    caminho = workspace / "dend" / "dados.scimat"
    constroi(documentos, caminho, [("2020–2021", 2020, 2021)])
    return caminho


class DendrogramaApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = Path(tempfile.mkdtemp())
        cls.projeto = _projeto(cls.workspace)
        cls.servidor = cria_servidor(0, cls.workspace)
        cls.base = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def pede(self, rota, dados=None):
        corpo = json.dumps(dados).encode() if dados is not None else None
        req = urllib.request.Request(
            self.base + rota, data=corpo,
            headers={"Content-Type": "application/json"} if corpo else {})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def pedido(self, **extra):
        return {"projeto": str(self.projeto), "unidade": "Words",
                "minimo_frequencia": 1, "periodo": 1, **extra}

    def test_post_devolve_estrutura(self):
        st, corpo, _ = self.pede("/api/dendrograma", self.pedido(ligacao="completa"))
        self.assertEqual(200, st)
        d = json.loads(corpo)
        for chave in ("svg", "n_grupos", "n_grupos_sugerido", "coph",
                      "comparacao", "frases", "omitidos"):
            self.assertIn(chave, d)
        self.assertTrue(d["svg"].lstrip().startswith("<svg"))
        self.assertTrue(d["frases"])
        self.assertEqual(d["n_grupos"], d["n_grupos_sugerido"])

    def test_n_grupos_e_limite(self):
        _, corpo, _ = self.pede("/api/dendrograma", self.pedido(n_grupos=2, limite=10))
        d = json.loads(corpo)
        self.assertEqual(2, d["n_grupos"])
        self.assertLessEqual(d["n_nos"], 10)
        self.assertGreater(d["omitidos"], 0)

    def test_token_e_download_get(self):
        _, corpo, _ = self.pede("/api/analisa", self.pedido())
        token = json.loads(corpo)["token"]
        q = urllib.parse.urlencode({"token": token, "ligacao": "simples", "n_grupos": 3})
        st, corpo, _ = self.pede(f"/api/dendrograma?{q}")
        self.assertEqual(200, st)
        self.assertEqual(3, json.loads(corpo)["n_grupos"])
        st, svg, cab = self.pede(f"/api/dendrograma?{q}&baixar=1")
        self.assertEqual(200, st)
        self.assertIn("image/svg+xml", cab["Content-Type"])
        self.assertIn("attachment", cab["Content-Disposition"])
        self.assertTrue(svg.lstrip().startswith(b"<svg"))

    def test_erros(self):
        for extra, trecho in ((dict(ligacao="xis"), "Ligação inválida"),
                              (dict(n_grupos="abc"), "n_grupos"),
                              (dict(n_grupos=0), "pelo menos 1"),
                              (dict(limite="x"), "limite"),
                              (dict(unidade="Nada"), "Unidade")):
            st, corpo, _ = self.pede("/api/dendrograma", self.pedido(**extra))
            self.assertEqual(400, st, extra)
            self.assertIn(trecho, json.loads(corpo)["erro"])
        st, corpo, _ = self.pede("/api/dendrograma", {})
        self.assertEqual(400, st)
        st, _, _ = self.pede("/api/dendrograma?token=inexistente")
        self.assertEqual(410, st)


if __name__ == "__main__":
    unittest.main()

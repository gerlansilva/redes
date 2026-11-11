"""Robustez da API: tokens antigos, parâmetros vazios e mensagens em português."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from redes import api
from redes.build import constroi
from redes.loaders.base import DocumentoFonte


def _projeto(workspace: Path) -> Path:
    documentos = [
        DocumentoFonte(
            titulo=f"Documento {i}", autores=[f"Autor, A{i % 3}."],
            ano=str(2019 + i % 3),
            palavras_autor=["estatistica", f"tema{i % 4}", "ensino"],
            referencias=[f"Silva J., 2010, Revista X, V{i % 5}, P1-9, Titulo {i % 5}"])
        for i in range(12)
    ]
    caminho = workspace / "robusto" / "dados.redes"
    constroi(documentos, caminho, [("2019–2021", 2019, 2021)])
    return caminho


class RobustezApiTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workspace = Path(tempfile.mkdtemp())
        cls.projeto = _projeto(cls.workspace)
        cls.servidor = api.cria_servidor(0, cls.workspace)
        cls.base = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def pede(self, caminho, dados=None):
        corpo = json.dumps(dados).encode() if dados is not None else None
        pedido = urllib.request.Request(
            self.base + caminho, data=corpo,
            headers={"Content-Type": "application/json"} if corpo else {},
            method="POST" if corpo else "GET")
        try:
            with urllib.request.urlopen(pedido, timeout=120) as resposta:
                return resposta.status, json.loads(resposta.read())
        except urllib.error.HTTPError as erro:
            return erro.code, json.loads(erro.read())

    def analisa(self, **extra):
        pedido = {"projeto": str(self.projeto), "unidade": "Words"}
        pedido.update(extra)
        codigo, dados = self.pede("/api/analisa", pedido)
        self.assertEqual(200, codigo, dados)
        return dados

    def test_tokens_antigos_continuam_servindo_rede_e_diagrama(self):
        primeira = self.analisa()
        for _ in range(api.ANALISES_PESADAS + 2):
            self.analisa(unidade="References")

        # A primeira teve a rede liberada da memória, mas é recalculada.
        self.assertIsNone(api.ANALISES[primeira["token"]]["rede"])
        codigo, rede = self.pede(f"/api/rede?token={primeira['token']}")
        self.assertEqual(200, codigo, rede)
        self.assertEqual(primeira["resumo"]["nos"], len(rede["nos"]))

        codigo, diagrama = self.pede(
            f"/api/estrategico?token={primeira['token']}")
        self.assertEqual(200, codigo, diagrama)

        codigo, docs = self.pede(f"/api/documentos?token={primeira['token']}")
        self.assertEqual(200, codigo)
        self.assertEqual(12, docs["total"])

    def test_exportar_analise_antiga_recalcula(self):
        primeira = self.analisa()
        for _ in range(api.ANALISES_PESADAS + 1):
            self.analisa(unidade="Authors")
        with urllib.request.urlopen(
                f"{self.base}/api/exportar?token={primeira['token']}"
                "&tipo=rede-pajek", timeout=60) as resposta:
            self.assertEqual(200, resposta.status)
            self.assertIn(b"*Vertices", resposta.read())

    def test_token_ausente_e_desconhecido_tem_mensagem_clara(self):
        for consulta in ("", "token=", "token=null", "token=undefined"):
            codigo, dados = self.pede(f"/api/estrategico?{consulta}")
            self.assertEqual(400, codigo)
            self.assertIn("Pré-visualizar", dados["erro"])

        codigo, dados = self.pede("/api/rede?token=naoexiste")
        self.assertEqual(410, codigo)
        self.assertTrue(dados["expirada"])
        self.assertIn("Pré-visualizar", dados["erro"])

        codigo, dados = self.pede("/api/documentos?token=naoexiste")
        self.assertEqual(410, codigo)

    def test_campos_vazios_valem_o_padrao(self):
        dados = self.analisa(minimo_frequencia="", corte="", mapeadores=None,
                             palavras=None, indices=None, k_core=None,
                             tamanho_maximo="15", periodo={"id": 1})
        self.assertEqual(1, dados["parametros"]["minimo_frequencia"])
        self.assertEqual(15, dados["parametros"]["tamanho_maximo"])

    def test_numero_invalido_diz_qual_campo_e_o_valor(self):
        codigo, dados = self.pede("/api/analisa", {
            "projeto": str(self.projeto), "minimo_frequencia": "abc"})
        self.assertEqual(400, codigo)
        self.assertIn("minimo_frequencia", dados["erro"])
        self.assertIn("abc", dados["erro"])

        codigo, dados = self.pede("/api/analisa", {
            "projeto": str(self.projeto), "minimo_frequencia": 0})
        self.assertEqual(400, codigo)
        self.assertIn("pelo menos 1", dados["erro"])

    def test_periodo_com_nome_numerico_nao_confunde_com_id(self):
        with api.ProjetoScimat(self.projeto) as kb:
            periodo = kb.periodos()[0]
            self.assertEqual(periodo.id, api._periodo(kb, periodo.id).id)
            self.assertEqual(periodo.id, api._periodo(kb, periodo.nome).id)
            self.assertEqual(periodo.id, api._periodo(kb, str(periodo.id)).id)
            with self.assertRaises(api.ErroApi) as ctx:
                api._periodo(kb, "1850")
            self.assertIn("Períodos do projeto", str(ctx.exception))

    def test_agrupamento_inexistente_informa_faixa(self):
        analise = self.analisa()
        codigo, dados = self.pede(f"/api/grupo?token={analise['token']}&selo=9999")
        self.assertEqual(400, codigo)
        self.assertIn("agrupamento", dados["erro"].lower())

    def test_todas_as_combinacoes_de_unidade_e_matriz_rodam(self):
        for unidade in api.UNIDADES:
            for matriz in api.MATRIZES:
                with self.subTest(unidade=unidade, matriz=matriz):
                    self.analisa(unidade=unidade, matriz=matriz)


if __name__ == "__main__":
    unittest.main()

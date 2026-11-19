"""Correções do teste de estresse: equivalência das versões rápidas, cancelamento e validações.

As implementações literais (lentas) do agrupamento ficam aqui como referência:
as versões de `redes.clustering` precisam dar exatamente o mesmo resultado.
"""

from __future__ import annotations

import json
import math
import random
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from redes import api, clustering
from redes.build import constroi
from redes.clustering import (Cancelado, _arestas_internas, _divide,
                                 _no_principal, centros_simples,
                                 ConjuntoDeAgrupamentos)
from redes.loaders.base import DocumentoFonte
from redes.network import Rede
from redes.pipeline import (MATRIZES, Configuracao, executa_periodo)

PASTA_T = Path("/home/claude/t")


# ------------------------------------------------------------ referências literais


def _antigo_valor_entre(rede, grupo_a, grupo_b):
    valores = [rede.valor(a, b) for a in grupo_a for b in grupo_b
               if rede.contem_aresta(a, b)]
    if not valores:
        return None
    return sum(valores), sum(valores) / len(valores), min(valores), max(valores)


def _antigo_ligacao(rede, tamanho_minimo, tamanho_maximo, criterio, corte=0.0):
    resultado = ConjuntoDeAgrupamentos(rede)
    grupos = [[no] for no in rede.nos]
    while True:
        melhor = None
        melhor_valor = -1.0
        for i in range(len(grupos)):
            for j in range(i + 1, len(grupos)):
                medidas = _antigo_valor_entre(rede, grupos[i], grupos[j])
                if medidas is None:
                    continue
                soma, media, minimo, maximo = medidas
                valor = {"soma": soma, "media": media,
                         "completa": minimo, "simples": maximo}[criterio]
                if valor > melhor_valor and valor >= corte:
                    melhor_valor = valor
                    melhor = (i, j)
        if melhor is None:
            break
        i, j = melhor
        if len(grupos[i]) + len(grupos[j]) > tamanho_maximo:
            break
        grupos[i] = grupos[i] + grupos[j]
        grupos.pop(j)
    for grupo in grupos:
        if len(grupo) >= tamanho_minimo:
            resultado.adiciona(grupo, _no_principal(rede, grupo))
    return resultado


def _antigo_componentes(grupo, arestas, removidas):
    pai = {no: no for no in grupo}

    def raiz(no):
        while pai[no] != no:
            no = pai[no]
        return no

    for a, b, _ in arestas:
        if f"{a}:{b}" in removidas:
            continue
        raiz_a, raiz_b = raiz(a), raiz(b)
        if raiz_a != raiz_b:
            pai[max(raiz_a, raiz_b)] = min(raiz_a, raiz_b)
    por_raiz = {}
    for no in grupo:
        por_raiz.setdefault(raiz(no), []).append(no)
    return list(por_raiz.values())


def _antigo_divide(grupo, grafo, maximo, cancelado=None):
    resultado = []
    arestas = _arestas_internas(grupo, grafo)
    removidas = set()
    while True:
        componentes = _antigo_componentes(grupo, arestas, removidas)
        if len(componentes) > 1:
            for componente in componentes:
                if len(componente) > maximo:
                    resultado.extend(_antigo_divide(componente, grafo, maximo))
                else:
                    resultado.append(componente)
            return resultado
        if not arestas or len(removidas) == len(arestas):
            return [[no] for no in grupo]
        removidas.add(f"{arestas[len(removidas)][0]}:{arestas[len(removidas)][1]}")


def _antigo_centros(rede, tamanho_minimo, tamanho_maximo, corte=0.0):
    """Formulação anterior: começa em `tamanho_maximo - 1` sem limitar ao grau."""
    resultado = ConjuntoDeAgrupamentos(rede)
    pares = [list(par) for par in rede.arestas()]
    pares.sort(key=lambda par: -par[2])
    total = len(pares)
    origem = [par[0] for par in pares]
    destino = [par[1] for par in pares]
    vivo = [True] * total
    pares_do_no = {}
    for indice in range(total):
        pares_do_no.setdefault(origem[indice], []).append(indice)
        pares_do_no.setdefault(destino[indice], []).append(indice)
    contagem = {}
    tamanho_atual = tamanho_maximo - 1
    restantes = total
    i = 0
    while restantes > 0 and tamanho_atual >= 1:
        semente = -1
        posicao = -1
        while i < total:
            if vivo[i]:
                a = origem[i]
                b = destino[i]
                contagem[a] = contagem.get(a, 0) + 1
                contagem[b] = contagem.get(b, 0) + 1
                if contagem[a] == tamanho_atual:
                    semente, posicao = a, i
                    break
                if contagem[b] == tamanho_atual:
                    semente, posicao = b, i
                    break
            i += 1
        if semente < 0:
            if tamanho_atual > tamanho_minimo - 1:
                contagem.clear()
                i = 0
                tamanho_atual -= 1
                continue
            break
        tema = [semente]
        for indice in reversed(pares_do_no[semente]):
            if indice > posicao or not vivo[indice]:
                continue
            tema.append(destino[indice] if origem[indice] == semente
                        else origem[indice])
        resultado.adiciona(tema, semente)
        for no in tema:
            for indice in pares_do_no.get(no, ()):
                if not vivo[indice]:
                    continue
                vivo[indice] = False
                restantes -= 1
                if indice <= posicao:
                    contagem[origem[indice]] -= 1
                    contagem[destino[indice]] -= 1
        i = posicao + 1
    return resultado


# ------------------------------------------------------------------------ apoio


def _rede_aleatoria(semente, nos=40, densidade=0.2, inteiros=False, isolados=3):
    gerador = random.Random(semente)
    rede = Rede(range(10, 10 + nos))
    ids = rede.nos[:-isolados] if isolados else rede.nos
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if gerador.random() < densidade:
                if inteiros:
                    rede.adiciona_aresta(a, b, float(gerador.randint(1, 4)))
                else:
                    rede.adiciona_aresta(a, b, gerador.random())
    return rede


def _forma(conjunto):
    return [(list(a.nos), a.principal) for a in conjunto.agrupamentos]


def _forma_exata(conjunto):
    """Como `_forma`, mas na ordem em que os nós foram guardados (não ordenada)."""
    return [(a.nos, a.principal) for a in conjunto.agrupamentos]


# ------------------------------------------------------------------- hierárquico


class LigacaoEquivalenciaTest(unittest.TestCase):

    def test_equivalente_em_redes_sinteticas(self):
        algoritmos = {"media": clustering.ligacao_media,
                      "completa": clustering.ligacao_completa,
                      "simples": clustering.ligacao_simples,
                      "soma": clustering.ligacao_soma}
        casos = 0
        for semente in range(8):
            for inteiros in (False, True):
                rede = _rede_aleatoria(semente, nos=36, densidade=0.25,
                                       inteiros=inteiros)
                for criterio, funcao in algoritmos.items():
                    for minimo, maximo, corte in ((2, 15, 0.0), (1, 4, 0.0),
                                                  (3, 8, 0.3), (2, 36, 0.5)):
                        esperado = _antigo_ligacao(rede, minimo, maximo,
                                                   criterio, corte)
                        obtido = funcao(rede, minimo, maximo, corte)
                        self.assertEqual(_forma_exata(esperado),
                                         _forma_exata(obtido),
                                         (semente, inteiros, criterio, minimo,
                                          maximo, corte))
                        casos += 1
        self.assertGreater(casos, 200)

    def test_empates_em_rede_de_pesos_iguais(self):
        rede = Rede(range(1, 21))
        for a in range(1, 21):
            for b in range(a + 1, 21):
                if (a + b) % 3:
                    rede.adiciona_aresta(a, b, 1.0)
        for criterio in ("media", "completa", "simples", "soma"):
            esperado = _antigo_ligacao(rede, 2, 6, criterio)
            obtido = clustering._ligacao(rede, 2, 6, criterio)
            self.assertEqual(_forma_exata(esperado), _forma_exata(obtido))

    def test_rede_vazia_e_sem_arestas(self):
        for rede in (Rede([]), Rede([1, 2, 3])):
            for criterio in ("media", "soma"):
                self.assertEqual(
                    _forma_exata(_antigo_ligacao(rede, 1, 5, criterio)),
                    _forma_exata(clustering._ligacao(rede, 1, 5, criterio)))

    def test_rede_grande_termina_rapido(self):
        rede = _rede_aleatoria(1, nos=900, densidade=0.08, isolados=0)
        inicio = time.time()
        conjunto = clustering.ligacao_completa(rede, 2, 15)
        self.assertLess(time.time() - inicio, 10)
        self.assertGreater(len(conjunto.agrupamentos), 0)

    @unittest.skipUnless((PASTA_T / "segat.redes").exists(), "projeto de teste ausente")
    def test_equivalente_em_projeto_real(self):
        from redes.kb import ProjetoRedes
        from redes.aggregate import Agregado  # noqa: F401 - garante importação
        from redes.network import rede_coocorrencia
        from redes.similarity import normaliza_coocorrencia
        with ProjetoRedes(PASTA_T / "segat.redes") as kb:
            periodo = kb.periodos()[0]
            for unidade in ("Words", "Authors", "ReferenceSources"):
                dataset = kb.dataset(unidade, periodo.id, ("autor", "fonte"))
                dataset.filtra_itens_por_frequencia(2)
                rede = rede_coocorrencia(dataset)
                rede.filtra_por_valor(1)
                normaliza_coocorrencia(dataset, rede, "EquivalenceIndex")
                if rede.quantidade_nos() > 400:
                    continue
                for criterio in ("media", "completa", "simples", "soma"):
                    self.assertEqual(
                        _forma_exata(_antigo_ligacao(rede, 2, 15, criterio)),
                        _forma_exata(clustering._ligacao(rede, 2, 15, criterio)),
                        (unidade, criterio))


# ------------------------------------------------------------------------ Louvain


class DivideEquivalenciaTest(unittest.TestCase):

    def _grafo(self, rede):
        return {no: dict(rede.adjacencia[no]) for no in rede.nos}

    def test_divide_equivalente(self):
        casos = 0
        for semente in range(40):
            for inteiros in (False, True):
                rede = _rede_aleatoria(semente, nos=30, densidade=0.12 + semente % 5 * 0.05,
                                       inteiros=inteiros, isolados=semente % 4)
                grafo = self._grafo(rede)
                grupo = list(rede.nos)
                for maximo in (1, 3, 6, 12):
                    self.assertEqual(_antigo_divide(grupo, grafo, maximo),
                                     _divide(grupo, grafo, maximo),
                                     (semente, inteiros, maximo))
                    casos += 1
        self.assertGreater(casos, 300)

    def test_divide_grupos_pequenos_e_sem_arestas(self):
        grafo = {1: {}, 2: {}, 3: {2: 1.0}, 4: {}}
        grafo[2][3] = 1.0
        for grupo in ([1], [1, 2], [2, 3], [1, 2, 3, 4], []):
            sub = {no: {v: p for v, p in grafo[no].items()} for no in grafo}
            self.assertEqual(_antigo_divide(grupo, sub, 1), _divide(grupo, sub, 1))

    def test_louvain_completo_equivalente(self):
        original = clustering._divide
        try:
            for semente in range(10):
                rede = _rede_aleatoria(semente, nos=60, densidade=0.1)
                clustering._divide = _antigo_divide
                esperado = clustering.louvain(rede, 2, 5)
                clustering._divide = original
                obtido = clustering.louvain(rede, 2, 5)
                self.assertEqual(_forma_exata(esperado), _forma_exata(obtido))
        finally:
            clustering._divide = original

    def test_grupo_grande_termina_rapido(self):
        rede = _rede_aleatoria(3, nos=500, densidade=0.15, isolados=0)
        grafo = self._grafo(rede)
        inicio = time.time()
        pedacos = _divide(list(rede.nos), grafo, 15)
        self.assertLess(time.time() - inicio, 10)
        self.assertEqual(sorted(n for p in pedacos for n in p), list(rede.nos))


# ------------------------------------------------------------------ centros simples


class CentrosSimplesTest(unittest.TestCase):

    def test_equivalente_ao_anterior(self):
        for semente in range(20):
            for inteiros in (False, True):
                rede = _rede_aleatoria(semente, nos=45, densidade=0.1 + semente % 4 * 0.06,
                                       inteiros=inteiros)
                for minimo, maximo in ((2, 15), (1, 4), (3, 8), (4, 4), (2, 2),
                                       (5, 3), (2, 60), (6, 90)):
                    self.assertEqual(
                        _forma_exata(_antigo_centros(rede, minimo, maximo)),
                        _forma_exata(centros_simples(rede, minimo, maximo)),
                        (semente, inteiros, minimo, maximo))

    def test_maximo_acima_do_grau_equivale_ao_limite_do_grau(self):
        rede = _rede_aleatoria(8, nos=50, densidade=0.15)
        grau = max(rede.grau(no) for no in rede.nos)
        for minimo in (1, 2, 4):
            self.assertEqual(
                _forma_exata(_antigo_centros(rede, minimo, grau + 1)),
                _forma_exata(centros_simples(rede, minimo, 10 ** 9)))

    def test_tamanho_maximo_muito_alto_nao_reescaneia(self):
        rede = _rede_aleatoria(5, nos=300, densidade=0.05)
        inicio = time.time()
        conjunto = centros_simples(rede, 2, 10 ** 12)
        self.assertLess(time.time() - inicio, 5)
        self.assertEqual(_forma_exata(conjunto),
                         _forma_exata(centros_simples(rede, 2, 40)))


# --------------------------------------------------------------------- cancelamento


class CancelamentoTest(unittest.TestCase):

    def test_algoritmos_param_com_callback(self):
        rede = _rede_aleatoria(2, nos=300, densidade=0.1, isolados=0)
        for nome, funcao in clustering.ALGORITMOS.items():
            with self.assertRaises(Cancelado, msg=nome):
                funcao(rede, 2, 15, 0.0, cancelado=lambda: True)

    def test_cancela_no_meio_do_agrupamento_em_poucos_segundos(self):
        rede = _rede_aleatoria(4, nos=1200, densidade=0.2, isolados=0)
        for nome in ("CompleteLink", "AverageLink", "Louvain", "CentersSimples"):
            marca = time.time() + 0.3
            inicio = time.time()
            try:
                clustering.ALGORITMOS[nome](rede, 2, 10 ** 6, 0.0,
                                            cancelado=lambda: time.time() > marca)
            except Cancelado:
                pass
            self.assertLess(time.time() - inicio, 5, nome)

    def test_pipeline_levanta_cancelado(self):
        workspace = Path(tempfile.mkdtemp())
        projeto = _projeto_pequeno(workspace)
        from redes.kb import ProjetoRedes
        with ProjetoRedes(projeto) as kb:
            periodo = kb.periodos()[0]
            config = Configuracao(unidade="Words", minimo_frequencia=1)
            with self.assertRaises(Cancelado):
                executa_periodo(kb, periodo.id, periodo.nome, config,
                                cancelado=lambda: True)
            # sem callback continua funcionando
            self.assertTrue(executa_periodo(kb, periodo.id, periodo.nome, config).rede)

    def test_cancelar_a_grade_interrompe_a_etapa_pesada(self):
        workspace = Path(tempfile.mkdtemp())
        projeto = _projeto_pequeno(workspace)
        rede = _rede_aleatoria(6, nos=1500, densidade=0.2, isolados=0)

        def pesada(kb, periodo_id, periodo_nome, config, cancelado=None):
            clustering.ligacao_completa(rede, 2, 10 ** 6, 0.0, cancelado)
            raise AssertionError("não devia terminar")

        original = api.executa_periodo
        api.executa_periodo = pesada
        try:
            trabalho = api.Trabalho("grade", 10)
            api.TRABALHOS[trabalho.id] = trabalho
            fio = threading.Thread(target=api._executa_grade,
                                   args=(trabalho, {"projeto": str(projeto)}))
            fio.start()
            time.sleep(0.5)
            inicio = time.time()
            api.cancela_trabalho(trabalho.id)
            fio.join(10)
            self.assertFalse(fio.is_alive())
            self.assertLess(time.time() - inicio, 5)
            self.assertEqual(trabalho.estado, "cancelado")
        finally:
            api.executa_periodo = original


def _projeto_pequeno(workspace: Path) -> Path:
    documentos = [
        DocumentoFonte(
            titulo=f"Documento {i}", autores=[f"Autor, A{i % 3}."],
            ano=str(2019 + i % 3),
            palavras_autor=["estatistica", f"tema{i % 4}", "ensino"],
            referencias=[f"Silva J., 2010, Revista X, V{i % 5}, P1-9, Titulo {i % 5}"])
        for i in range(12)
    ]
    caminho = workspace / "estresse" / "dados.redes"
    constroi(documentos, caminho, [("2019–2021", 2019, 2021)])
    return caminho


# ------------------------------------------------------------------------ validações


class ValidacaoTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workspace = Path(tempfile.mkdtemp())
        cls.projeto = _projeto_pequeno(cls.workspace)
        cls.servidor = api.cria_servidor(0, cls.workspace)
        cls.base = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def pede(self, caminho, dados):
        pedido = urllib.request.Request(
            self.base + caminho, data=json.dumps(dados).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(pedido, timeout=120) as resposta:
                return resposta.status, json.loads(resposta.read())
        except urllib.error.HTTPError as erro:
            return erro.code, json.loads(erro.read())

    def test_mapeador_acoplamento_so_com_acoplamento_basico(self):
        mapeadores = ("nucleo", "interseccao", "uniao", "secundarios", "kcore",
                      "acoplamento")
        for unidade in api.UNIDADES:
            for matriz in MATRIZES:
                for mapeador in mapeadores:
                    dados = {"unidade": unidade, "matriz": matriz,
                             "mapeadores": [mapeador]}
                    deve_falhar = mapeador == "acoplamento" and matriz != "BasicCoupling"
                    if deve_falhar:
                        with self.assertRaises(api.ErroApi) as ctx:
                            api._config(dados)
                        self.assertIn("acoplamento", str(ctx.exception))
                        with self.assertRaises(ValueError):
                            Configuracao(unidade=unidade, matriz=matriz,
                                         mapeadores=(mapeador,)).valida()
                    else:
                        api._config(dados)
                        Configuracao(unidade=unidade, matriz=matriz,
                                     mapeadores=(mapeador,)).valida()

    def test_mapeador_acoplamento_junto_de_outros_tambem_falha(self):
        with self.assertRaises(api.ErroApi):
            api._config({"matriz": "CoOccurrence",
                         "mapeadores": ["nucleo", "acoplamento"]})

    def test_http_400_em_vez_de_500(self):
        for matriz in ("CoOccurrence", "AggregatedCouplingBasedOnAuthor",
                       "AggregatedCouplingBasedOnJournal"):
            codigo, corpo = self.pede("/api/analisa", {
                "projeto": str(self.projeto), "unidade": "Words", "matriz": matriz,
                "mapeadores": ["acoplamento"]})
            self.assertEqual(codigo, 400, (matriz, corpo))
            self.assertIn("acoplamento", corpo["erro"])
        codigo, corpo = self.pede("/api/analisa", {
            "projeto": str(self.projeto), "unidade": "References",
            "matriz": "BasicCoupling", "mapeadores": ["acoplamento"]})
        self.assertEqual(codigo, 200, corpo)

    def test_interface_oculta_a_opcao(self):
        ui = Path(api.__file__).parent / "ui"
        html = (ui / "index.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'<option value="acoplamento" disabled hidden>')
        js = (ui / "app.js").read_text(encoding="utf-8")
        self.assertIn("function ajustarMapeadores", js)
        self.assertGreaterEqual(js.count("ajustarMapeadores()"), 3)

    def test_corte_precisa_ser_finito(self):
        for ruim in (float("inf"), float("nan"), "inf", "nan", "-inf", "Infinity",
                     "1e999", -1, "-0,5"):
            with self.assertRaises(api.ErroApi, msg=repr(ruim)):
                api._config({"corte": ruim})
        for ruim in (float("inf"), float("nan"), -1.0):
            with self.assertRaises(ValueError):
                Configuracao(corte=ruim).valida()
        self.assertEqual(api._config({"corte": "0,25"}).corte, 0.25)
        self.assertEqual(api._config({"corte": ""}).corte, 0.0)

    def test_http_corte_infinito_da_400(self):
        corpo = ('{"projeto": %s, "unidade": "Words", "corte": Infinity}'
                 % json.dumps(str(self.projeto))).encode()
        pedido = urllib.request.Request(
            self.base + "/api/analisa", data=corpo,
            headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(pedido, timeout=60)
        self.assertEqual(ctx.exception.code, 400)
        self.assertIn("finito", json.loads(ctx.exception.read())["erro"])

    def test_outros_numeros_nao_finitos(self):
        for campo in ("minimo_frequencia", "minimo_coocorrencia", "tamanho_minimo",
                      "tamanho_maximo", "k_core", "componente_minimo"):
            for ruim in (float("inf"), float("nan"), "inf", "nan", "1e999"):
                with self.assertRaises(api.ErroApi, msg=(campo, ruim)):
                    api._config({campo: ruim})

    def test_edicao_com_infinito_da_400(self):
        codigo, corpo = self.pede("/api/base", {
            "projeto": str(self.projeto), "acao": "criar-periodo",
            "nome": "x", "inicio": float("inf"), "fim": 2020})
        self.assertEqual(codigo, 400, corpo)

    def test_tamanho_maximo_enorme_funciona(self):
        config = api._config({"tamanho_maximo": 10 ** 12})
        self.assertEqual(config.tamanho_maximo, 10 ** 12)
        codigo, corpo = self.pede("/api/analisa", {
            "projeto": str(self.projeto), "unidade": "Words",
            "tamanho_maximo": 10 ** 12})
        self.assertEqual(codigo, 200, corpo)

    def test_um_so_periodico_tem_mensagem_propria(self):
        codigo, corpo = self.pede("/api/analisa", {
            "projeto": str(self.projeto), "unidade": "Words",
            "matriz": "AggregatedCouplingBasedOnJournal"})
        self.assertEqual(codigo, 200, corpo)
        textos = [a["mensagem"] for a in corpo["avisos"]
                  if a["codigo"] == "um_periodico"]
        self.assertEqual(len(textos), 1, corpo["avisos"])
        self.assertIn("o corpus tem um só periódico", textos[0].lower())


# ------------------------------------------------------------- cliente que desiste


class ClienteQueDesisteTest(unittest.TestCase):

    def test_aborto_nao_imprime_traceback(self):
        import contextlib
        import io
        import socket
        workspace = Path(tempfile.mkdtemp())
        projeto = _projeto_pequeno(workspace)
        servidor = api.cria_servidor(0, workspace)
        porta = servidor.server_address[1]
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        erro = io.StringIO()
        try:
            with contextlib.redirect_stderr(erro):
                for _ in range(15):
                    s = socket.create_connection(("127.0.0.1", porta))
                    s.sendall(b"GET /api/projetos HTTP/1.1\r\nHost: x\r\n\r\n")
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                 b"\x01\x00\x00\x00\x00\x00\x00\x00")
                    s.close()          # RST com a resposta ainda a caminho
                time.sleep(0.5)
        finally:
            servidor.shutdown()
            servidor.server_close()
        self.assertNotIn("Traceback", erro.getvalue())
        self.assertNotIn("BrokenPipe", erro.getvalue())

    def test_handle_error_ignora_abortos(self):
        import contextlib
        import io
        servidor = api.cria_servidor(0, Path(tempfile.mkdtemp()))
        try:
            erro = io.StringIO()
            with contextlib.redirect_stderr(erro):
                try:
                    raise BrokenPipeError()
                except BrokenPipeError:
                    servidor.handle_error(None, ("127.0.0.1", 1))
                try:
                    raise ConnectionResetError()
                except ConnectionResetError:
                    servidor.handle_error(None, ("127.0.0.1", 1))
            self.assertEqual(erro.getvalue(), "")
        finally:
            servidor.server_close()

    def test_json_seguro_engole_aborto(self):
        class Falso(api.Manipulador):
            def __init__(self):
                pass

            def _json(self, codigo, dados):
                raise BrokenPipeError()

        Falso()._json_seguro(500, {"erro": "x"})


if __name__ == "__main__":
    unittest.main()

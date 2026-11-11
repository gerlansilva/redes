"""Desempenho do relatório completo: as versões rápidas dão a mesma saída que as literais."""

import heapq
import math
import os
import random
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from redes import api, build, cache_figuras, measures, metodo, paralelo, pipeline, report
from redes.api import ProjetoScimat, _config
from redes.loaders.base import DocumentoFonte
from redes.network import Rede

SERJ = Path("/home/claude/t/serj_auto.redes")


def _docs(n=60):
    return [DocumentoFonte(
        titulo=f"Doc {i}", ano=str(2015 + i % 6), periodico=f"R{i % 3}",
        autores=[f"Autor {i % 5} A.", f"Autor {i % 3 + 5} B.", "Autor Z Z."],
        palavras_autor=[f"tema {i % 4}", f"tema {i % 3 + 4}", "geral", f"x{i % 9}"],
        citacoes=i % 7) for i in range(n)]


def _intermediacao_literal(rede: Rede) -> dict[int, float]:
    """Brandes como no laço original (dicionários), para conferir a versão com listas."""
    centralidade = {no: 0.0 for no in rede.nos}
    for origem in rede.nos:
        predecessores: dict[int, list[int]] = {}
        distancia = {no: math.inf for no in rede.nos}
        caminhos = {no: 0.0 for no in rede.nos}
        pilha: list[int] = []
        fila: list[tuple[float, int]] = []
        distancia[origem] = 0.0
        caminhos[origem] = 1.0
        heapq.heappush(fila, (0.0, origem))
        while fila:
            atual, no = heapq.heappop(fila)
            if atual > distancia[no]:
                continue
            pilha.append(no)
            for vizinho, peso in rede.adjacencia[no].items():
                nova = distancia[no] + measures._custo(peso)
                if nova < distancia[vizinho] - 1e-10:
                    distancia[vizinho] = nova
                    heapq.heappush(fila, (nova, vizinho))
                    caminhos[vizinho] = caminhos[no]
                    predecessores[vizinho] = [no]
                elif abs(nova - distancia[vizinho]) <= 1e-10:
                    caminhos[vizinho] += caminhos[no]
                    predecessores.setdefault(vizinho, []).append(no)
        dependencia = {no: 0.0 for no in rede.nos}
        while pilha:
            w = pilha.pop()
            for v in predecessores.get(w, []):
                if caminhos[w] > 0:
                    dependencia[v] += caminhos[v] / caminhos[w] * (1.0 + dependencia[w])
            if w != origem:
                centralidade[w] += dependencia[w]
    return {no: valor / 2.0 for no, valor in centralidade.items()}


class IntermediacaoTest(unittest.TestCase):
    def test_igual_ao_laco_literal_bit_a_bit(self):
        azar = random.Random(11)
        for _ in range(40):
            n = azar.randint(1, 80)
            ids = azar.sample(range(1, 3000), n)
            rede = Rede(ids)
            for _ in range(azar.randint(0, n * 3) if n > 1 else 0):
                a, b = azar.sample(ids, 2)
                rede.adiciona_aresta(a, b, azar.choice([0.5, 1, 1, 2, 0.25, azar.random() + 0.01]))
            esperado = _intermediacao_literal(rede)
            obtido = measures.intermediacao(rede)
            self.assertEqual(list(esperado.items()), list(obtido.items()))

    def test_rede_vazia_e_de_um_no(self):
        self.assertEqual({}, measures.intermediacao(Rede([])))
        self.assertEqual({7: 0.0}, measures.intermediacao(Rede([7])))


class CacheFigurasTest(unittest.TestCase):
    def setUp(self):
        cache_figuras.limpa()
        escopo = cache_figuras.escopo()
        escopo.__enter__()
        self.addCleanup(escopo.__exit__)

    def test_acerto_falha_e_excecao(self):
        chamadas = []
        for _ in range(3):
            self.assertEqual("v", cache_figuras.obtem(("a", 1), lambda: chamadas.append(1) or "v"))
        self.assertEqual(1, len(chamadas))

        def falha():
            raise ValueError("x")
        with self.assertRaises(ValueError):
            cache_figuras.obtem(("b",), falha)
        self.assertFalse(cache_figuras.tem(("b",)))     # exceção não é guardada

    def test_interruptor_de_comparacao(self):
        with mock.patch.dict(os.environ, {"REDES_SEM_CACHE": "1"}):
            n = []
            cache_figuras.obtem(("c",), lambda: n.append(1) or "v")
            cache_figuras.obtem(("c",), lambda: n.append(1) or "v")
        self.assertEqual(2, len(n))
        self.assertFalse(cache_figuras.tem(("c",)))

    def test_limite_de_bytes_descarta_os_mais_antigos(self):
        with mock.patch.object(cache_figuras, "LIMITE_BYTES", 5000):
            for i in range(10):
                cache_figuras.obtem(("g", i), lambda: "x" * 1000)
        self.assertFalse(cache_figuras.tem(("g", 0)))
        self.assertTrue(cache_figuras.tem(("g", 9)))

    def test_delta_e_incorpora(self):
        cache_figuras.obtem(("antes",), lambda: "a")
        marca = cache_figuras.chaves()
        cache_figuras.obtem(("novo",), lambda: "n")
        delta = cache_figuras.delta(marca)
        self.assertEqual({("novo",): "n"}, delta)
        cache_figuras.limpa()
        cache_figuras.incorpora(delta)
        self.assertTrue(cache_figuras.tem(("novo",)))


class ImpressaoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = cls.dir / "c.redes"
        build.constroi(_docs(), cls.projeto,
                       periodos=[("A", 2015, 2017), ("B", 2018, 2020)])
        cls.kb = ProjetoScimat(cls.projeto)
        cls.config = _config({"unidade": "Words", "minimo_frequencia": 2})

    @classmethod
    def tearDownClass(cls):
        cls.kb.fecha()

    def resultado(self, config=None):
        p = self.kb.periodos()[0]
        return pipeline.executa_periodo(self.kb, p.id, p.nome, config or self.config)

    def test_impressao_repete_para_o_mesmo_conteudo_e_muda_com_ele(self):
        a, b = self.resultado(), self.resultado()
        self.assertEqual(cache_figuras.base(a), cache_figuras.base(b))
        c = self.resultado(_config({"unidade": "Words", "minimo_frequencia": 3}))
        self.assertNotEqual(cache_figuras.base(a), cache_figuras.base(c))
        # alterar a rede muda a impressão (a guardada no objeto não engana)
        d = self.resultado()
        a1, b1, _ = d.rede.arestas()[0]
        d.rede.remove_aresta(a1, b1)
        d.__dict__.pop("_impressao", None)
        self.assertNotEqual(cache_figuras.base(a), cache_figuras.base(d))

    def test_siglas_registradas_mudam_a_chave(self):
        from redes import texto
        r = self.resultado()
        antes = cache_figuras.base(r)
        try:
            texto.registra_siglas("ZZZQ")
            self.assertNotEqual(antes, cache_figuras.base(r))
        finally:
            texto.esquece_siglas()
        self.assertEqual(antes, cache_figuras.base(r))

    def test_halo_cacheado_igual_ao_direto(self):
        from redes.viz.halo import halo_svg
        r = self.resultado()
        novos = metodo.rotulos_do_resultado(self.kb, r)
        direto = halo_svg(r, f"Rede completa — {r.periodo}", rotulos=novos,
                          pivos=metodo.pivos_para_halo(self.kb, r))
        cache_figuras.limpa()
        with cache_figuras.escopo():
            self.assertEqual(direto, report.halo_cacheado(self.kb, r, novos))
            acertos = cache_figuras.estatisticas()["acertos"]
            self.assertEqual(direto, report.halo_cacheado(self.kb, r, novos))
            self.assertEqual(acertos + 1, cache_figuras.estatisticas()["acertos"])
        # fora do escopo nada é guardado nem reaproveitado
        cache_figuras.limpa()
        report.halo_cacheado(self.kb, r, novos)
        self.assertEqual(0, cache_figuras.estatisticas()["entradas"])

    def test_guarda_compartilha_entre_objetos_do_mesmo_conteudo(self):
        cache_figuras.limpa()
        a, b = self.resultado(), self.resultado()
        with cache_figuras.escopo():
            self.assertIsNotNone(metodo.pivos_do_resultado(self.kb, a))
            falhas = cache_figuras.estatisticas()["falhas"]
            self.assertIsNotNone(metodo.pivos_do_resultado(self.kb, b))
            self.assertEqual(falhas, cache_figuras.estatisticas()["falhas"])

    def test_constante_alterada_esvazia_o_cache_e_fora_do_escopo_nao_guarda(self):
        from redes import pivos
        cache_figuras.limpa()
        with cache_figuras.escopo():
            cache_figuras.obtem(("k",), lambda: "v")
        with cache_figuras.escopo():
            self.assertTrue(cache_figuras.tem(("k",)))
        with mock.patch.object(pivos, "LIMITE_NOS", 3):
            with cache_figuras.escopo():
                self.assertFalse(cache_figuras.tem(("k",)))
        cache_figuras.limpa()
        cache_figuras.obtem(("fora",), lambda: "v")
        self.assertFalse(cache_figuras.tem(("fora",)))

    def test_rajadas_em_cache_devolvem_copia(self):
        from redes import rajadas
        cache_figuras.limpa()
        with cache_figuras.escopo():
            um = rajadas.calcula(self.kb.conexao, "palavras", limite=5, minimo_documentos=1)
            um["rajadas"].append("lixo")
            dois = rajadas.calcula(self.kb.conexao, "palavras", limite=5, minimo_documentos=1)
        self.assertNotIn("lixo", dois["rajadas"])
        self.assertEqual(1, cache_figuras.estatisticas()["acertos"])


def _sem_data(texto: str) -> str:
    return re.sub(r"\d{1,2} de [a-zç]+ de \d{4}", "", texto)


class RelatorioCompletoTest(unittest.TestCase):
    """Saída igual com e sem cache, em um processo e em paralelo; o único não gera pasta."""

    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.projeto = cls.dir / "c.redes"
        build.constroi(_docs(80), cls.projeto,
                       periodos=[("A", 2015, 2016), ("B", 2017, 2018), ("C", 2019, 2020)])

    prontas = None

    def gera(self, formato, **ambiente):
        cache_figuras.limpa()
        original = paralelo.Aquecedor.espera
        guardadas = []

        def espera(aquecedor):
            guardadas.append(original(aquecedor))
            return guardadas[-1]

        with mock.patch.dict(os.environ, ambiente), \
                mock.patch.object(paralelo.Aquecedor, "espera", espera):
            r = api.gera_relatorio_completo({"projeto": str(self.projeto), "formato": formato})
        self.prontas = guardadas[-1]
        return api.CACHE / f"rel-{r['token']}"

    def test_unico_igual_com_e_sem_cache_e_em_paralelo(self):
        base = self.gera("unico", REDES_SEM_CACHE="1", REDES_PARALELO="0")
        com_cache = self.gera("unico", REDES_PARALELO="0")
        paralelo_ = self.gera("unico", REDES_PARALELO="forca", REDES_TRABALHADORES="2")
        self.assertGreaterEqual(self.prontas, 2)      # os trabalhadores de fato trabalharam
        texto = _sem_data((base / "relatorio-completo.html").read_text("utf-8"))
        self.assertEqual(texto, _sem_data((com_cache / "relatorio-completo.html").read_text("utf-8")))
        self.assertEqual(texto, _sem_data((paralelo_ / "relatorio-completo.html").read_text("utf-8")))
        for pasta in (base, com_cache, paralelo_):
            self.assertEqual(["relatorio-completo.html"], sorted(p.name for p in pasta.iterdir()))

    def test_pastas_igual_em_paralelo(self):
        serie = self.gera("pastas", REDES_SEM_CACHE="1", REDES_PARALELO="0")
        par = self.gera("pastas", REDES_PARALELO="forca", REDES_TRABALHADORES="2")
        self.assertGreaterEqual(self.prontas, 2)
        arquivos = sorted(p.relative_to(serie) for p in serie.rglob("*") if p.is_file())
        self.assertEqual(arquivos, sorted(p.relative_to(par) for p in par.rglob("*") if p.is_file()))
        for rel in arquivos:
            self.assertEqual(_sem_data((serie / rel).read_text("utf-8", errors="replace")),
                             _sem_data((par / rel).read_text("utf-8", errors="replace")), str(rel))

    def test_trabalhador_que_falha_nao_derruba_o_relatorio(self):
        with mock.patch.object(paralelo._Trabalhador, "executa", return_value=False):
            pasta = self.gera("unico", REDES_PARALELO="forca", REDES_TRABALHADORES="2")
        self.assertEqual(0, self.prontas)
        referencia = self.gera("unico", REDES_PARALELO="0")
        self.assertEqual(_sem_data((referencia / "relatorio-completo.html").read_text("utf-8")),
                         _sem_data((pasta / "relatorio-completo.html").read_text("utf-8")))

    def test_paralelo_desligado_por_ambiente_e_base_pequena(self):
        with ProjetoScimat(self.projeto) as kb:
            with mock.patch.dict(os.environ, {"REDES_PARALELO": "0"}):
                self.assertEqual(0, paralelo.numero_de_trabalhadores(kb))
            with mock.patch.dict(os.environ, {"REDES_PARALELO": "", "REDES_TRABALHADORES": "3"}):
                self.assertEqual(0, paralelo.numero_de_trabalhadores(kb))   # 80 documentos
            with mock.patch.dict(os.environ, {"REDES_PARALELO": "forca", "REDES_TRABALHADORES": "3"}):
                self.assertEqual(3, paralelo.numero_de_trabalhadores(kb))


@unittest.skipUnless(SERJ.exists(), "projeto serj_auto ausente")
class SerjDesempenhoTest(unittest.TestCase):
    def test_unico_em_paralelo_igual_ao_de_um_processo(self):
        cache_figuras.limpa()
        with mock.patch.dict(os.environ, {"REDES_PARALELO": "0", "REDES_SEM_CACHE": "1"}):
            a = api.gera_relatorio_completo({"projeto": str(SERJ), "formato": "unico"})
        cache_figuras.limpa()
        with mock.patch.dict(os.environ, {"REDES_PARALELO": "forca", "REDES_TRABALHADORES": "2"}):
            b = api.gera_relatorio_completo({"projeto": str(SERJ), "formato": "unico"})
        ler = lambda r: _sem_data((api.CACHE / f"rel-{r['token']}" / "relatorio-completo.html")
                                  .read_text("utf-8"))
        self.assertEqual(ler(a), ler(b))


if __name__ == "__main__":
    unittest.main()

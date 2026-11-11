"""Geração paralela das figuras e cálculos pesados do relatório completo.

O gargalo do relatório completo é o desenho (halo, diagrama, agrupamentos,
densidade, linha do tempo) e o que o alimenta (pontos de virada, rótulos). Cada
análise é independente, então cada uma vai para um processo trabalhador
(`redes.trabalhador`, processos que ficam vivos entre as análises), que recebe os resultados já calculados, produz tudo
no cache compartilhado (`cache_figuras`) e devolve as entradas criadas. O
processo principal as incorpora e monta o documento depois, só com acertos.

Nada aqui muda a saída: o trabalhador executa o mesmo código sobre os mesmos
resultados, e as chaves do cache são de conteúdo. Qualquer falha de um
trabalhador (processo que morre, tempo esgotado, impressão diferente) só faz o
processo principal calcular aquela análise sozinho, como sempre fez.

Controle por ambiente: `REDES_PARALELO=0` desliga; `REDES_PARALELO=forca` liga
mesmo em bases pequenas; `REDES_TRABALHADORES=N` fixa o número de processos.
"""

from __future__ import annotations

import concurrent.futures
import os
import pickle
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from . import cache_figuras

MAXIMO_TRABALHADORES = 4
TEMPO_MAXIMO = 900          # segundos por análise; depois disso o principal assume


DOCUMENTOS_MINIMOS = 120    # abaixo disso (e de LIMIAR_NOS) o processo único é mais rápido


def _documentos(kb) -> int:
    try:
        return int(kb.conexao.execute("SELECT COUNT(*) FROM Document").fetchone()[0])
    except Exception:  # noqa: BLE001
        return 0


def numero_de_trabalhadores(kb) -> int:
    """Quantos processos abrir; 0 = tudo no processo principal."""
    modo = os.environ.get("REDES_PARALELO", "").strip().lower()
    if modo in ("0", "nao", "não", "off", "false"):
        return 0
    try:
        pedido = int(os.environ.get("REDES_TRABALHADORES", "0"))
    except ValueError:
        pedido = 0
    n = pedido if pedido > 0 else min(os.cpu_count() or 1, MAXIMO_TRABALHADORES)
    if modo == "forca":
        return max(n, 1)
    if n < 2 or _documentos(kb) < DOCUMENTOS_MINIMOS:
        return 0
    return n


class _Trabalhador:
    """Processo filho de vida longa: lê linhas "entrada saida" e responde "ok" ou "erro".

    Ficar vivo entre análises poupa o custo de importar NumPy e NetworkX a cada uma.
    """

    def __init__(self) -> None:
        ambiente = dict(os.environ)
        raiz = str(Path(__file__).resolve().parent.parent)
        ambiente["PYTHONPATH"] = raiz + os.pathsep + ambiente.get("PYTHONPATH", "")
        ambiente["REDES_PARALELO"] = "0"          # o trabalhador nunca abre outros
        self.processo = subprocess.Popen(
            [sys.executable, "-m", "redes.trabalhador"],
            env=ambiente, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)

    def executa(self, entrada: str, saida: str) -> bool:
        try:
            self.processo.stdin.write(f"{entrada}\t{saida}\n")
            self.processo.stdin.flush()
            return self.processo.stdout.readline().strip() == "ok"
        except Exception:  # noqa: BLE001
            return False

    def encerra(self) -> None:
        try:
            self.processo.stdin.close()
            self.processo.wait(timeout=10)
        except Exception:  # noqa: BLE001
            self.processo.kill()
        finally:
            try:
                self.processo.stdout.close()
            except Exception:  # noqa: BLE001
                pass


def _roda(trabalhador: "_Trabalhador", secao: dict, formato: str, kb, medida: str,
          destino: Path | None, pasta_tmp: str, indice: int, parte: str = "tudo") -> dict | None:
    from . import texto

    entrada = os.path.join(pasta_tmp, f"in{indice}.pkl")
    saida = os.path.join(pasta_tmp, f"out{indice}.pkl")
    carga = {
        "projeto": kb.caminho, "formato": formato, "medida": medida, "parte": parte,
        "destino": str(destino) if destino else "",
        "siglas": sorted(getattr(texto, "_extras", ())),
        "secao": {k: secao[k] for k in ("rotulo", "descricao", "pasta", "config", "resultados")
                  if k in secao},
        "esperado": [cache_figuras.base(r) for r in secao["resultados"]],
        "digesto": cache_figuras.digesto_de_constantes(),
    }
    try:
        with open(entrada, "wb") as f:
            pickle.dump(carga, f, protocol=4)
        if not trabalhador.executa(entrada, saida) or not os.path.exists(saida):
            return None
        with open(saida, "rb") as f:
            return pickle.load(f)
    except Exception:  # noqa: BLE001 - o principal refaz o que faltar
        return None


def _custo_estimado(secao: dict, parte: str) -> float:
    """Palpite de custo para começar pelas maiores (o desenho cresce mais que linearmente)."""
    nos = sum(len(r.rede.nos) ** 1.6 + 5 * len(r.grupos) for r in secao["resultados"])
    return nos * (0.7 if parte == "corpo" else 1.0)


class Aquecedor:
    """Manda cada análise pronta para um trabalhador, enquanto o principal segue analisando.

    ``submete(secao)`` volta na hora; ``espera()`` junta o que veio. Os
    trabalhadores pegam sempre a tarefa mais cara entre as que já estão na fila.
    Com 0 trabalhadores (base pequena, um só núcleo, `REDES_PARALELO=0`) não faz
    nada e o relatório é gerado inteiro no processo principal.
    """

    def __init__(self, kb, formato: str, medida: str, destino: Path | None = None) -> None:
        self.kb, self.formato, self.medida, self.destino = kb, formato, medida, destino
        self.n = numero_de_trabalhadores(kb)
        self._fila: queue.PriorityQueue = queue.PriorityQueue()
        self._tarefas: list[tuple[dict, concurrent.futures.Future]] = []
        self._threads: list[threading.Thread] = []
        self._tmp = None
        self.prontas = 0

    def _laco(self) -> None:
        trabalhador = _Trabalhador()
        try:
            while True:
                _, _, item = self._fila.get()
                if item is None:
                    return
                secao, parte, indice, futuro = item
                try:
                    futuro.set_result(_roda(trabalhador, secao, self.formato, self.kb,
                                            self.medida, self.destino, self._tmp.name,
                                            indice, parte))
                except Exception as erro:  # noqa: BLE001
                    futuro.set_exception(erro)
        finally:
            trabalhador.encerra()

    def submete(self, secao: dict) -> None:
        """Agenda a análise. No arquivo único ela vira duas tarefas (figuras do corpus
        completo e figuras por período), para balancear melhor entre os processos."""
        if not self.n:
            return
        if self._tmp is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="redes-trab-")
            for _ in range(self.n):
                fio = threading.Thread(target=self._laco, daemon=True)
                fio.start()
                self._threads.append(fio)
        partes = ("corpo", "periodos") if self.formato == "unico" else ("tudo",)
        for parte in partes:
            indice = len(self._tarefas)
            futuro: concurrent.futures.Future = concurrent.futures.Future()
            self._tarefas.append((secao, futuro))
            self._fila.put((-_custo_estimado(secao, parte), indice, (secao, parte, indice, futuro)))

    def espera(self) -> int:
        """Incorpora o que os trabalhadores fizeram; devolve quantas análises ficaram prontas."""
        try:
            for _ in self._threads:      # sentinelas: passam depois de todas as tarefas
                self._fila.put((float("inf"), 10 ** 9, None))
            for secao, futuro in self._tarefas:
                try:
                    resposta = futuro.result()
                except Exception:  # noqa: BLE001
                    resposta = None
                if resposta is None:
                    continue
                cache_figuras.incorpora(resposta["entradas"])
                if resposta.get("pronta"):
                    secao["pronta_em_pasta"] = self.formato == "pastas"
                    self.prontas += 1
        finally:
            for fio in self._threads:
                fio.join(timeout=30)
            if self._tmp is not None:
                self._tmp.cleanup()
            self._tmp = None
            self._threads = []
            self._tarefas = []
        return self.prontas

"""Cache de figuras e cálculos pesados, compartilhado entre os relatórios.

A chave é o *conteúdo* da análise (impressão digital do resultado do período,
que cobre configuração, rede, agrupamentos e nomes) mais o que muda o desenho
(título, rótulos, tipo de figura). Dois relatórios que pedem a mesma figura
(`report.py` em pastas e `relatorio_unico.py`, ou a mesma geração repetida)
desenham uma vez só. Um acerto nunca muda a saída: a chave só repete quando
tudo o que entra no cálculo é igual; qualquer dúvida vira uma falha de cache.

O cache só vale dentro de `escopo()` (a geração de um relatório). É do processo, limitado em bytes (os mais antigos saem primeiro) e
protegido por trava. Os processos filhos da geração paralela devolvem as
entradas que criaram (`delta`) e o pai as incorpora (`incorpora`).
"""

from __future__ import annotations

import collections
import hashlib
import os
import pickle
import threading
from pathlib import Path

LIMITE_BYTES = 256 * 1024 * 1024

_TRAVA = threading.RLock()
_DADOS: "collections.OrderedDict[tuple, tuple[object, int]]" = collections.OrderedDict()
_BYTES = [0]
_CONTADORES = {"acertos": 0, "falhas": 0}


def _tamanho(valor) -> int:
    """Estimativa barata do peso de um valor em memória (texto domina)."""
    if isinstance(valor, str):
        return len(valor) + 64
    if isinstance(valor, (list, tuple)):
        return 64 + sum(_tamanho(v) for v in valor)
    if isinstance(valor, dict):
        return 64 + sum(_tamanho(k) + _tamanho(v) for k, v in valor.items())
    return 64


def _insere(chave, valor) -> None:
    peso = _tamanho(valor)
    with _TRAVA:
        if chave in _DADOS:
            _BYTES[0] -= _DADOS.pop(chave)[1]
        _DADOS[chave] = (valor, peso)
        _BYTES[0] += peso
        while _BYTES[0] > LIMITE_BYTES and len(_DADOS) > 1:
            _, (_, antigo) = _DADOS.popitem(last=False)
            _BYTES[0] -= antigo


_ESCOPO = [0]
_DIGESTO = [None]


# Módulos cujos limiares e textos fixos entram no que o relatório calcula e desenha.
_MODULOS_DO_CALCULO = (
    "areas", "clustering", "dendro_helper", "dendrograma", "duplo_mapa", "fluxos", "ies",
    "linha_do_tempo", "longitudinal", "measures", "metodo", "network", "pipeline", "pivos",
    "qualidade", "rajadas", "relatorio_unico", "report", "rotulos", "similarity", "similitude", "termos",
    "text_utils", "texto", "viz.cluster", "viz.dendrograma", "viz.densidade", "viz.duplo_mapa",
    "viz.halo", "viz.linha_do_tempo", "viz.similitude", "viz.strategic")


def digesto_de_constantes() -> str:
    """Resumo das constantes de módulo (LETRAS_MAIÚSCULAS simples) do cálculo.

    Os limiares e limites do cálculo fazem parte do resultado. Se mudarem entre
    duas gerações (um teste que troca um limite, por exemplo), o cache é esvaziado;
    um trabalhador com constantes diferentes das do processo principal é dispensado.
    A lista é fixa (não depende de quais módulos o processo já importou).
    """
    import importlib
    itens = []
    for nome_modulo in _MODULOS_DO_CALCULO:
        try:
            modulo = importlib.import_module(f"scimatpy.{nome_modulo}")
        except Exception:  # noqa: BLE001
            continue
        for nome, valor in list(vars(modulo).items()):
            if (nome.isupper() or nome.replace("_", "").isupper()) and isinstance(
                    valor, (int, float, str, bool, tuple, frozenset, type(None))):
                itens.append((nome_modulo, nome, repr(valor) if not isinstance(valor, frozenset)
                              else repr(sorted(valor, key=repr))))
    itens.sort()
    return hashlib.sha1(repr(itens).encode("utf-8")).hexdigest()


class escopo:
    """Liga o cache durante uma geração de relatório (`with cache_figuras.escopo(): ...`).

    Fora de um escopo `obtem` sempre calcula: funções chamadas soltas (na interface ou
    em testes) nunca recebem valor guardado de outra chamada. Ao entrar, se alguma
    constante do pacote mudou desde o escopo anterior, o cache é esvaziado.
    """

    def __enter__(self):
        with _TRAVA:
            if _ESCOPO[0] == 0:
                atual = digesto_de_constantes()
                if _DIGESTO[0] is not None and atual != _DIGESTO[0]:
                    _DADOS.clear()
                    _BYTES[0] = 0
                _DIGESTO[0] = atual
            _ESCOPO[0] += 1
        return self

    def __exit__(self, *_):
        with _TRAVA:
            _ESCOPO[0] = max(0, _ESCOPO[0] - 1)


def obtem(chave: tuple, construtor):
    """Valor guardado em `chave` ou, se não houver, `construtor()` (que é guardado).

    Exceções do construtor passam adiante e nada é guardado.
    """
    if not _ESCOPO[0] or os.environ.get("REDES_SEM_CACHE"):   # fora de um escopo, ou depuração
        return construtor()
    with _TRAVA:
        if chave in _DADOS:
            _DADOS.move_to_end(chave)
            _CONTADORES["acertos"] += 1
            return _DADOS[chave][0]
    valor = construtor()
    with _TRAVA:
        _CONTADORES["falhas"] += 1
    _insere(chave, valor)
    return valor


def tem(chave: tuple) -> bool:
    with _TRAVA:
        return chave in _DADOS


def limpa() -> None:
    with _TRAVA:
        _DADOS.clear()
        _BYTES[0] = 0
        _CONTADORES.update(acertos=0, falhas=0)


def estatisticas() -> dict:
    with _TRAVA:
        return {"entradas": len(_DADOS), "bytes": _BYTES[0], **_CONTADORES}


def chaves() -> set:
    with _TRAVA:
        return set(_DADOS)


def delta(antes: set) -> dict:
    """Entradas criadas depois de `antes` (conjunto de `chaves()`), para o pai incorporar."""
    with _TRAVA:
        return {c: v[0] for c, v in _DADOS.items() if c not in antes}


def incorpora(entradas: dict) -> None:
    for chave, valor in entradas.items():
        _insere(chave, valor)


# ------------------------------------------------------------------ impressões


def impressao(resultado) -> str:
    """Impressão digital do conteúdo de um `ResultadoPeriodo` (guardada no objeto).

    Cobre todos os atributos públicos (configuração, rede, agrupamentos, nomes,
    índices); só os caches privados (`_cache_*`) ficam de fora. Se algo não puder
    ser serializado, devolve uma marca única do objeto: nada é compartilhado.
    """
    guardada = resultado.__dict__.get("_impressao")
    if guardada:
        return guardada
    try:
        estado = {k: v for k, v in resultado.__dict__.items() if not k.startswith("_")}
        impressao_ = "p" + hashlib.sha1(
            pickle.dumps(estado, protocol=4)).hexdigest()
    except Exception:  # noqa: BLE001 - sem impressão confiável, não compartilha
        impressao_ = f"u{id(resultado)}-{os.getpid()}"
    resultado.__dict__["_impressao"] = impressao_
    return impressao_


def ambiente() -> str:
    """Estado global que muda a exibição dos termos (lista de siglas), como texto estável.

    Estável entre processos (não usa `hash`): os trabalhadores da geração
    paralela e o processo principal chegam à mesma chave.
    """
    try:
        from . import texto
        return hashlib.sha1("|".join(sorted(texto.siglas())).encode("utf-8")).hexdigest()[:12]
    except Exception:  # noqa: BLE001
        return "-"


def base(resultado) -> str:
    """Impressão do resultado somada ao ambiente de exibição: raiz de toda chave."""
    return f"{impressao(resultado)}~{ambiente()}"


def selo_projeto(kb) -> str:
    """Marca do estado do arquivo do projeto (caminho, tamanho e mtime, com WAL).

    Sem arquivo real (objeto de teste, por exemplo) a marca é única do objeto:
    nada é compartilhado entre dois `kb` diferentes.
    """
    if kb is None:
        return "sem-kb"
    base = str(getattr(kb, "caminho", "") or "")
    try:
        st = os.stat(base)
    except OSError:
        return f"u{id(kb)}-{os.getpid()}"
    partes = [os.path.abspath(base), f"{st.st_size}:{st.st_mtime_ns}"]
    for sufixo in ("-wal", "-journal"):
        try:
            sx = os.stat(base + sufixo)
            partes.append(f"{sx.st_size}:{sx.st_mtime_ns}")
        except OSError:
            partes.append("-")
    return "|".join(partes)


def selo_configuracao(config) -> str:
    """Todos os campos da `Configuracao` (o repr do dataclass os traz)."""
    return repr(config)


def selo_conexao(conexao) -> str | None:
    """Mesma marca de `selo_projeto`, a partir de uma conexão sqlite; None se não há arquivo."""
    try:
        caminho = next((linha[2] for linha in conexao.execute("PRAGMA database_list")
                        if linha[1] == "main"), "")
    except Exception:  # noqa: BLE001
        return None
    if not caminho:
        return None

    class _Arquivo:
        pass

    arquivo = _Arquivo()
    arquivo.caminho = caminho
    selo = selo_projeto(arquivo)
    return None if selo.startswith("u") else selo


def chave_da_secao(kb, config, resultados, extra: str = "") -> str:
    """Chave de conteúdo de uma análise inteira (todos os períodos, configuração e projeto)."""
    corpo = "|".join([selo_projeto(kb), selo_configuracao(config), ambiente(), extra]
                     + [base(r) for r in resultados])
    return hashlib.sha1(corpo.encode("utf-8")).hexdigest()

"""Medidas de rede, de desempenho e de centralidade dos nós."""

from __future__ import annotations

from collections.abc import Mapping

import heapq
import math

from .dataset import Dataset
from .network import Rede


# ------------------------------------------------------------------ diagrama estratégico


def centralidade_callon(rede: Rede, nos) -> float:
    """Centralidade de Callon: 10 × soma dos vínculos externos do grupo."""
    return 10.0 * sum(valor for _, _, valor in rede.pares_externos(nos))


def densidade_callon(rede: Rede, nos) -> float:
    """Densidade de Callon: 100 × soma interna dividida pelo número de nós."""
    nos = list(nos)
    if not nos:
        return 0.0
    return 100.0 * sum(valor for _, _, valor in rede.pares_internos(nos)) / len(nos)


def faixa_normalizada(valores: list[float]) -> list[float]:
    """Posição relativa de cada grupo na medida (1..n)/n, com empates estáveis."""
    ordenados = sorted(range(len(valores)), key=lambda i: valores[i])
    faixas = [0.0] * len(valores)
    for posicao, indice in enumerate(ordenados):
        faixas[indice] = (1.0 + posicao) / len(valores)
    return faixas


# ------------------------------------------------------------------------ desempenho


def indice_h(citacoes: list[int]) -> int:
    valores = sorted((c for c in citacoes if c > 0), reverse=True)
    h = 0
    for posicao, valor in enumerate(valores):
        if valor < posicao + 1:
            return posicao
        h = posicao + 1
    return h


def indice_g(citacoes: list[int]) -> int:
    valores = sorted((c for c in citacoes if c > 0), reverse=True)
    soma = 0
    g = 0
    for posicao, valor in enumerate(valores):
        soma += valor
        if soma >= (posicao + 1) ** 2:
            g += 1
        else:
            break
    return g


def indice_hg(citacoes: list[int]) -> float:
    return math.sqrt(indice_h(citacoes) * indice_g(citacoes))


def indice_q2(citacoes: list[int]) -> float:
    valores = sorted((c for c in citacoes if c > 0), reverse=True)
    if not valores:
        return 0.0
    h = indice_h(valores)
    if h == 0:
        return 0.0
    if h % 2 == 1:
        mediana = valores[(h + 1) // 2 - 1]
    else:
        mediana = valores[h // 2 - 1]
    return math.sqrt(h * mediana)


def conta_documentos(dataset: Dataset, documentos) -> int:
    return sum(1 for doc in documentos if doc in dataset.documentos)


def media_citacoes(dataset: Dataset, documentos) -> float:
    documentos = list(documentos)
    if not documentos:
        return 0.0
    return sum(dataset.citacoes(doc) for doc in documentos) / len(documentos)


def soma_citacoes(dataset: Dataset, documentos) -> int:
    return sum(dataset.citacoes(doc) for doc in documentos)


def maximo_citacoes(dataset: Dataset, documentos) -> int:
    return max((dataset.citacoes(doc) for doc in documentos), default=0)


def minimo_citacoes(dataset: Dataset, documentos) -> int:
    return min((dataset.citacoes(doc) for doc in documentos), default=0)


def citacoes_de(dataset: Dataset, documentos) -> list[int]:
    return [dataset.citacoes(doc) for doc in documentos]


# ------------------------------------------------------------------------ centralidade


def grau_ponderado(rede: Rede) -> dict[int, float]:
    return {no: sum(rede.adjacencia[no].values()) for no in rede.nos}


def _custo(peso: float) -> float:
    return 1.0 / peso if peso > 0 else 1e308 / 4.0


def _distancias(rede: Rede, origem: int) -> dict[int, float]:
    distancia = {no: math.inf for no in rede.nos}
    distancia[origem] = 0.0
    fila = [(0.0, origem)]
    while fila:
        atual, no = heapq.heappop(fila)
        if atual > distancia[no]:
            continue
        for vizinho, peso in rede.adjacencia[no].items():
            nova = distancia[no] + _custo(peso)
            if nova < distancia[vizinho] - 1e-10:
                distancia[vizinho] = nova
                heapq.heappush(fila, (nova, vizinho))
    return distancia


def intermediacao(rede: Rede) -> dict[int, float]:
    """Betweenness de Brandes com custo 1/peso, como no Bibliomapa.

    Mesma conta, mesma ordem de somas e mesmo desempate do laço literal (o
    resultado é idêntico bit a bit; `tests/test_desempenho_relatorio.py` compara
    com a formulação literal): só troca dicionários por listas indexadas e
    calcula o custo de cada aresta uma vez.
    """
    nos = rede.nos
    n = len(nos)
    indice = {no: i for i, no in enumerate(nos)}
    adjacentes = [[(indice[v], v, _custo(peso)) for v, peso in rede.adjacencia[no].items()]
                  for no in nos]
    infinito = math.inf
    centralidade = [0.0] * n
    empurra = heapq.heappush
    retira = heapq.heappop

    for s in range(n):
        origem = nos[s]
        predecessores: dict[int, list[int]] = {}
        distancia = [infinito] * n
        caminhos = [0.0] * n
        pilha: list[int] = []

        distancia[s] = 0.0
        caminhos[s] = 1.0
        fila = [(0.0, origem)]

        while fila:
            atual, no = retira(fila)
            i = indice[no]
            if atual > distancia[i]:
                continue
            pilha.append(i)
            base = distancia[i]

            for j, vizinho, custo in adjacentes[i]:
                nova = base + custo
                alvo = distancia[j]
                if nova < alvo - 1e-10:
                    distancia[j] = nova
                    empurra(fila, (nova, vizinho))
                    caminhos[j] = caminhos[i]
                    predecessores[j] = [i]
                elif abs(nova - alvo) <= 1e-10:
                    caminhos[j] += caminhos[i]
                    lista = predecessores.get(j)
                    if lista is None:
                        predecessores[j] = [i]
                    else:
                        lista.append(i)

        dependencia = [0.0] * n
        while pilha:
            w = pilha.pop()
            anteriores = predecessores.get(w)
            if anteriores:
                caminhos_w = caminhos[w]
                if caminhos_w > 0:
                    for v in anteriores:
                        dependencia[v] += caminhos[v] / caminhos_w * (1.0 + dependencia[w])
            if w != s:
                centralidade[w] += dependencia[w]

    return {no: centralidade[i] / 2.0 for i, no in enumerate(nos)}


def proximidade(rede: Rede) -> dict[int, float]:
    resultado = {}
    for origem in rede.nos:
        distancias = _distancias(rede, origem)
        alcancados = [d for no, d in distancias.items() if no != origem and d < math.inf]
        soma = sum(alcancados)
        resultado[origem] = len(alcancados) / soma if alcancados and soma > 0 else 0.0
    return resultado


def autovetor(rede: Rede) -> dict[int, float]:
    total = max(1, len(rede.nos))
    atual = {no: 1.0 / total for no in rede.nos}

    for _ in range(500):
        proximo = {}
        norma = 0.0
        for no in rede.nos:
            soma = atual[no]
            for vizinho, peso in rede.adjacencia[no].items():
                soma += peso * atual[vizinho]
            proximo[no] = soma
            norma += soma * soma
        norma = math.sqrt(norma)

        if norma < 1e-10:
            return {no: 0.0 for no in rede.nos}

        diferenca = 0.0
        for no in rede.nos:
            proximo[no] /= norma
            diferenca += abs(proximo[no] - atual[no])
        atual = proximo
        if diferenca < 1e-10:
            break

    return atual


def pagerank(rede: Rede) -> dict[int, float]:
    total = len(rede.nos)
    if total == 0:
        return {}
    graus = grau_ponderado(rede)
    atual = {no: 1.0 / total for no in rede.nos}

    for _ in range(500):
        proximo = {}
        for no in rede.nos:
            soma = 0.0
            for vizinho, peso in rede.adjacencia[no].items():
                if graus[vizinho] > 0:
                    soma += peso / graus[vizinho] * atual[vizinho]
            proximo[no] = 0.15 / total + 0.85 * soma

        diferenca = sum(abs(proximo[no] - atual[no]) for no in rede.nos)
        atual = proximo
        if diferenca < 1e-10:
            break

    return atual


CENTRALIDADES = {
    "grau": grau_ponderado,
    "intermediacao": intermediacao,
    "proximidade": proximidade,
    "autovetor": autovetor,
    "pagerank": pagerank,
}


class Centralidades(Mapping):
    """Mapa de centralidades calculado sob demanda.

    A intermediação de Brandes custa caro em redes com milhares de nós; só é
    calculada quando alguém pede, e o resultado fica guardado.
    """

    def __init__(self, rede: Rede) -> None:
        self._rede = rede
        self._cache: dict[str, dict[int, float]] = {}

    def __getitem__(self, nome: str) -> dict[int, float]:
        if nome not in self._cache:
            if nome not in CENTRALIDADES:
                raise KeyError(nome)
            self._cache[nome] = CENTRALIDADES[nome](self._rede)
        return self._cache[nome]

    def __iter__(self):
        return iter(CENTRALIDADES)

    def __len__(self) -> int:
        return len(CENTRALIDADES)

    def get(self, nome, padrao=None):
        try:
            return self[nome]
        except KeyError:
            return padrao

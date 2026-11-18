"""Medidas de similaridade diretas e normalizadores.

`SaltonCosine` usa a co-ocorrência ao quadrado no numerador (por isso não fica
limitada a 1) e `EquivalenceIndex` também eleva a co-ocorrência ao quadrado.
"""

from __future__ import annotations

import math

from .dataset import Dataset
from .network import Rede


def equivalencia(freq_i: int, freq_j: int, cooc: float) -> float:
    return (cooc * cooc) / (freq_i * freq_j)


def forca_associacao(freq_i: int, freq_j: int, cooc: float) -> float:
    return cooc / (freq_i * freq_j)


def inclusao(freq_i: int, freq_j: int, cooc: float) -> float:
    return cooc / min(freq_i, freq_j)


def jaccard(freq_i: int, freq_j: int, cooc: float) -> float:
    return cooc / (freq_i + freq_j - cooc)


def salton(freq_i: int, freq_j: int, cooc: float) -> float:
    return (cooc * cooc) / math.sqrt(freq_i * freq_j)


MEDIDAS = {
    "AssociationStrength": forca_associacao,
    "EquivalenceIndex": equivalencia,
    "InclusionIndex": inclusao,
    "JaccardIndex": jaccard,
    "SaltonCosine": salton,
}


def normaliza_coocorrencia(dataset: Dataset, rede: Rede, medida: str) -> None:
    """Substitui cada aresta pelo índice de similaridade (mutação in place)."""
    funcao = MEDIDAS[medida]
    for a, b, valor in rede.arestas():
        rede.adiciona_aresta(
            a, b, funcao(dataset.frequencia_item(a), dataset.frequencia_item(b), valor))


def normaliza_acoplamento(dataset, rede: Rede, medida: str) -> None:
    """Normaliza o acoplamento pela frequência documental dos nós."""
    funcao = MEDIDAS[medida]
    for a, b, valor in rede.arestas():
        rede.adiciona_aresta(
            a, b, funcao(dataset.frequencia_documento_item(a),
                         dataset.frequencia_documento_item(b), valor))

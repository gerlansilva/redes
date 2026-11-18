"""Mapeadores de documentos.

Cada mapeador recebe os nós de um agrupamento e devolve o conjunto de
documentos que lhe corresponde. Os mapeadores são núcleo, interseção, secundário
(diferença simétrica acumulada), k-core, união e acoplamento.
"""

from __future__ import annotations

from .dataset import Dataset
from .network import Rede


def _documentos(dataset, item_id: int) -> set[int]:
    if hasattr(dataset, "documentos_do_alto_nivel"):
        return set(dataset.documentos_do_alto_nivel(item_id))
    return set(dataset.documentos_do_item(item_id))


def nucleo(rede: Rede, dataset, nos) -> set[int]:
    """Documentos presentes em pelo menos um par interno do agrupamento."""
    resultado: set[int] = set()
    for a, b, _ in rede.pares_internos(nos):
        resultado |= _documentos(dataset, a) & _documentos(dataset, b)
    return resultado


def secundarios(rede: Rede, dataset, nos) -> set[int]:
    """Diferença simétrica acumulada dos documentos dos nós."""
    nos = list(nos)
    if not nos:
        return set()

    acumulado = set(_documentos(dataset, nos[0]))
    for item_id in nos[1:]:
        anterior = set(acumulado)
        acumulado |= _documentos(dataset, item_id)
        acumulado -= anterior & _documentos(dataset, item_id)
    return acumulado


def k_core(dataset, nos, k: int) -> set[int]:
    """Documentos que aparecem em pelo menos k nós do agrupamento."""
    contagem: dict[int, int] = {}
    for item_id in nos:
        for doc in _documentos(dataset, item_id):
            contagem[doc] = contagem.get(doc, 0) + 1
    return {doc for doc, quantidade in contagem.items() if quantidade >= k}


def interseccao(rede: Rede, dataset, nos) -> set[int]:
    """Documentos comuns a todos os nós do agrupamento."""
    nos = list(nos)
    if not nos:
        return set()
    resultado = set(_documentos(dataset, nos[0]))
    for item_id in nos[1:]:
        resultado &= _documentos(dataset, item_id)
    return resultado


def uniao(rede: Rede, dataset, nos) -> set[int]:
    """Todos os documentos de todos os nós do agrupamento."""
    resultado: set[int] = set()
    for item_id in nos:
        resultado |= _documentos(dataset, item_id)
    return resultado


def acoplamento(rede: Rede, dataset, nos) -> set[int]:
    """Mapeador do acoplamento básico: os nós já são documentos.

    No acoplamento básico os nós da rede são os próprios documentos, então o
    conjunto é o dos identificadores dos nós, como em
    `CouplingDocumentMapper`.
    """
    return {int(no) for no in nos}


MAPEADORES = {
    "nucleo": nucleo,
    "secundarios": secundarios,
    "kcore": k_core,
    "interseccao": interseccao,
    "uniao": uniao,
    "acoplamento": acoplamento,
}

"""Modelo de dados do Redes: documentos, itens e citações.

A ordem de inserção é preservada, porque a ordem dos itens define os
identificadores dos nós e, com isso, o desempate dos algoritmos de
agrupamento.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class Documento:
    """Documento com os itens que contém, na ordem em que entraram."""

    doc_id: int
    citacoes: int = 0
    itens: list[int] = field(default_factory=list)

    def contem(self, item_id: int) -> bool:
        return item_id in self.itens

    def adiciona(self, item_id: int) -> bool:
        if item_id in self.itens:
            return False
        self.itens.append(item_id)
        return True


class Dataset:
    """Conjunto documento × item de uma unidade de análise e de um período."""

    def __init__(self) -> None:
        self.documentos: dict[int, Documento] = {}
        self.itens: dict[int, str] = {}
        self.docs_por_item: dict[int, list[int]] = {}

    # ------------------------------------------------------------------ cópia

    def clone(self) -> "Dataset":
        novo = Dataset()
        for doc_id, doc in self.documentos.items():
            novo.documentos[doc_id] = Documento(doc_id, doc.citacoes, list(doc.itens))
        novo.itens = dict(self.itens)
        novo.docs_por_item = {k: list(v) for k, v in self.docs_por_item.items()}
        return novo

    # -------------------------------------------------------------- documentos

    def adiciona_documento(self, doc_id: int, citacoes: int = 0) -> bool:
        if doc_id in self.documentos:
            return False
        self.documentos[doc_id] = Documento(doc_id, citacoes)
        return True

    def remove_documento(self, doc_id: int) -> None:
        doc = self.documentos.pop(doc_id, None)
        if doc is None:
            raise KeyError(f"documento {doc_id} não existe")
        for item_id in list(doc.itens):
            lista = self.docs_por_item.get(item_id, [])
            if doc_id in lista:
                lista.remove(doc_id)

    def lista_documentos(self) -> list[int]:
        # Documentos e itens são lidos na ordem do id.
        return sorted(self.documentos)

    def quantidade_documentos(self) -> int:
        return len(self.documentos)

    def citacoes(self, doc_id: int) -> int:
        return self.documentos[doc_id].citacoes

    def itens_do_documento(self, doc_id: int) -> list[int]:
        return list(self.documentos[doc_id].itens)

    # -------------------------------------------------------------------- itens

    def adiciona_item_ao_documento(self, doc_id: int, item_id: int, rotulo: str) -> bool:
        doc = self.documentos.get(doc_id)
        if doc is None:
            raise KeyError(f"documento {doc_id} não existe")

        if item_id not in self.itens:
            self.itens[item_id] = rotulo
            self.docs_por_item[item_id] = []

        if doc.adiciona(item_id):
            self.docs_por_item[item_id].append(doc_id)
            return True
        return False

    def remove_item(self, item_id: int) -> None:
        if item_id not in self.itens:
            raise KeyError(f"item {item_id} não existe")
        for doc_id in list(self.docs_por_item.get(item_id, [])):
            doc = self.documentos.get(doc_id)
            if doc and item_id in doc.itens:
                doc.itens.remove(item_id)
        self.itens.pop(item_id, None)
        self.docs_por_item.pop(item_id, None)

    def lista_itens(self) -> list[int]:
        return sorted(self.itens)

    def quantidade_itens(self) -> int:
        return len(self.itens)

    def rotulo_item(self, item_id: int) -> str:
        return self.itens[item_id]

    def documentos_do_item(self, item_id: int) -> list[int]:
        return list(self.docs_por_item.get(item_id, []))

    def frequencia_item(self, item_id: int) -> int:
        return len(self.docs_por_item.get(item_id, []))

    def frequencia_documento(self, doc_id: int) -> int:
        return len(self.documentos[doc_id].itens)

    def frequencia_documento_item(self, doc_id: int) -> int:
        """Número de itens do documento (frequência documental do acoplamento)."""
        return len(self.documentos[doc_id].itens)

    # ------------------------------------------------------------------ filtros

    def filtra_itens_por_frequencia(self, minimo: int) -> None:
        """Remove itens com menos documentos que o mínimo (mutação in place)."""
        for item_id in self.lista_itens():
            if self.frequencia_item(item_id) < minimo:
                self.remove_item(item_id)

    def filtra_documentos_por_itens(self, minimo: int) -> None:
        for doc_id in self.lista_documentos():
            if self.frequencia_documento(doc_id) < minimo:
                self.remove_documento(doc_id)

    def filtra_documentos_por_citacoes(self, minimo: int) -> None:
        for doc_id in self.lista_documentos():
            if self.citacoes(doc_id) < minimo:
                self.remove_documento(doc_id)

    # ------------------------------------------------------------------ leitura

    def pares_documento_item(self) -> Iterable[tuple[int, int]]:
        for doc_id, doc in self.documentos.items():
            for item_id in doc.itens:
                yield doc_id, item_id

    def __len__(self) -> int:
        return len(self.documentos)

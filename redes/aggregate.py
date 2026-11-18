"""Conjunto agregado por autor ou por periódico (acoplamento agregado).

Mantém os documentos do conjunto original e, por
cima deles, itens de alto nível que agrupam documentos.
"""

from __future__ import annotations

import sqlite3

from .dataset import Dataset

_SQL_AUTORES_DO_DOCUMENTO = (
    "SELECT a.idAuthor, a.authorName FROM Document_Author da, Author a "
    "WHERE da.Document_idDocument = ? AND da.Author_idAuthor = a.idAuthor;"
)

_SQL_PERIODICO_DO_DOCUMENTO = (
    "SELECT j.idJournal, j.source FROM Document d, Journal j "
    "WHERE d.idDocument = ? AND d.Journal_idJournal = j.idJournal;"
)


class Agregado:
    """Itens de alto nível (autor ou periódico) com seus documentos."""

    def __init__(self, dataset: Dataset) -> None:
        self.dataset = dataset
        self.altos: dict[int, str] = {}
        self.documentos: dict[int, list[int]] = {}

    def adiciona(self, alto_id: int, rotulo: str, doc_id: int) -> None:
        if alto_id not in self.altos:
            self.altos[alto_id] = rotulo
            self.documentos[alto_id] = []
        if doc_id not in self.documentos[alto_id]:
            self.documentos[alto_id].append(doc_id)

    def lista_alto_nivel(self) -> list[int]:
        return sorted(self.altos)

    def documentos_do_alto_nivel(self, alto_id: int) -> list[int]:
        return list(self.documentos.get(alto_id, []))

    def frequencia_documento_item(self, alto_id: int) -> int:
        return len(self.documentos.get(alto_id, []))

    def citacoes(self, doc_id: int) -> int:
        return self.dataset.citacoes(doc_id)

    def __len__(self) -> int:
        return len(self.altos)

    # ------------------------------------------------------------- construtores

    @classmethod
    def por_autor(cls, conexao: sqlite3.Connection, dataset: Dataset) -> "Agregado":
        agregado = cls(dataset)
        for doc_id in dataset.lista_documentos():
            for linha in conexao.execute(_SQL_AUTORES_DO_DOCUMENTO, (doc_id,)):
                agregado.adiciona(linha["idAuthor"], linha["authorName"], doc_id)
        return agregado

    @classmethod
    def por_periodico(cls, conexao: sqlite3.Connection, dataset: Dataset) -> "Agregado":
        agregado = cls(dataset)
        for doc_id in dataset.lista_documentos():
            linha = conexao.execute(_SQL_PERIODICO_DO_DOCUMENTO, (doc_id,)).fetchone()
            if linha is not None:
                agregado.adiciona(linha["idJournal"], linha["source"], doc_id)
        return agregado

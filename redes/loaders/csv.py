"""Leitor do CSV que o importador do SciMAT usa.

Colunas obrigatórias: Title, Authors, Year. As listas vêm separadas por ``//``.
É o formato produzido pelos conversores do repositório (Scopus e OpenAlex) e o
mesmo consumido pelo programa Java.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..paises import paises_de
from .base import DocumentoFonte


def _campo(linha: dict, nome: str) -> str:
    return (linha.get(nome) or "").strip()


def _lista(valor: str) -> list[str]:
    return [item.strip() for item in (valor or "").split("//") if item.strip()]


def _citacoes(valor: str) -> int:
    try:
        return int(float((valor or "0").replace(",", ".")))
    except ValueError:
        return 0


def le(caminho: str | Path) -> list[DocumentoFonte]:
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        registros = list(csv.DictReader(arquivo))

    documentos = []
    for linha in registros:
        titulo = _campo(linha, "Title").replace("\n", " ")
        if not titulo:
            continue

        afiliacoes = _lista(_campo(linha, "Affiliations"))
        documentos.append(DocumentoFonte(
            titulo=titulo,
            autores=_lista(_campo(linha, "Authors")),
            ano=_campo(linha, "Year"),
            citacoes=_citacoes(_campo(linha, "Citations")),
            periodico=_campo(linha, "Journal"),
            doi=_campo(linha, "Doi"),
            tipo=_campo(linha, "Type"),
            resumo=_campo(linha, "Abstract").replace("\n", " "),
            afiliacoes=afiliacoes,
            paises=paises_de(afiliacoes),
            palavras_autor=_lista(_campo(linha, "AuthorKeywords")),
            palavras_fonte=_lista(_campo(linha, "SourceKeywords")),
            referencias=_lista(_campo(linha, "References")),
            referencias_convertidas=True,
        ))

    return documentos

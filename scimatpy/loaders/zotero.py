"""Leitor do CSV exportado pelo Zotero ("Exportar biblioteca → CSV").

O Zotero grava uma linha por item, com cabeçalhos em inglês: ``Item Type``,
``Publication Year``, ``Author`` (``Sobrenome, Nome; Sobrenome, Nome``),
``Title``, ``Publication Title``, ``DOI``, ``Abstract Note``, ``Manual Tags`` e
``Automatic Tags`` (separadas por ``;``) e ``Extra`` (onde a Scopus e o
OpenAlex deixam "Cited By: n"). O RIS do Zotero passa pelo leitor RIS.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from .base import (DocumentoFonte, abrevia_autor, acha_doi, citacoes_em_texto,
                   divide_termos)

COLUNAS_DISTINTIVAS = {"item type", "publication year", "manual tags",
                       "automatic tags", "publication title"}


def _texto(caminho: str | Path) -> str:
    dados = Path(caminho).read_bytes()
    for codificacao in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return dados.decode(codificacao)
        except UnicodeError:
            continue
    return dados.decode("utf-8", errors="replace")


def _campo(linha: dict, *nomes: str) -> str:
    minusculas = {(k or "").strip().lower(): (v or "") for k, v in linha.items()}
    for nome in nomes:
        valor = minusculas.get(nome.lower(), "").strip()
        if valor:
            return valor
    return ""


def _autores(valor: str) -> list[str]:
    return [n.strip() for n in re.split(r";", valor or "") if n.strip()]


def le(caminho: str | Path) -> list[DocumentoFonte]:
    texto = _texto(caminho)
    registros = csv.DictReader(io.StringIO(texto, newline=""))

    documentos = []
    for linha in registros:
        titulo = re.sub(r"\s+", " ", _campo(linha, "Title")).strip()
        if not titulo:
            continue

        ano = _campo(linha, "Publication Year", "Year")
        if not re.fullmatch(r"\d{4}", ano):
            achado = re.search(r"\d{4}", _campo(linha, "Date") or ano)
            ano = achado.group(0) if achado else ""

        completos = _autores(_campo(linha, "Author"))
        extra = _campo(linha, "Extra")
        tags = divide_termos(_campo(linha, "Manual Tags")) + [
            t for t in divide_termos(_campo(linha, "Automatic Tags"))]
        vistos: set[str] = set()
        palavras = []
        for termo in tags:
            if termo.lower() not in vistos:
                vistos.add(termo.lower())
                palavras.append(termo)

        documentos.append(DocumentoFonte(
            titulo=titulo,
            autores=[abrevia_autor(n) for n in completos],
            autores_completos=completos,
            ano=ano,
            citacoes=citacoes_em_texto(extra, _campo(linha, "Notes")),
            periodico=_campo(linha, "Publication Title", "Proceedings Title",
                             "Conference Name", "Publisher"),
            doi=_campo(linha, "DOI") or acha_doi(_campo(linha, "Url"), extra),
            tipo=_campo(linha, "Item Type").lower(),
            resumo=re.sub(r"\s+", " ", _campo(linha, "Abstract Note")).strip(),
            palavras_autor=palavras,
            palavras_fonte=[],
            referencias=[],
            referencias_convertidas=False,
        ))

    return documentos

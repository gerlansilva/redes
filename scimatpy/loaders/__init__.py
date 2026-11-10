"""Carregadores de corpus: CSV SciMAT, BibTeX, RIS, OpenAlex, WoS e Scopus."""

from __future__ import annotations

import re
from pathlib import Path

from .base import DocumentoFonte

__all__ = ["DocumentoFonte", "FORMATOS", "detecta_formato", "le_corpus"]

FORMATOS = ("csv", "bibtex", "ris", "openalex", "wos", "scopus", "zotero")


def _texto(caminho: str | Path) -> str:
    dados = Path(caminho).read_bytes()
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return dados.decode("utf-8", errors="replace")


def _colunas(linha: str) -> list[str]:
    return [coluna.strip().strip('"').lower() for coluna in
            re.split(r"[,;\t]", linha)]


def detecta_formato(caminho: str | Path) -> str:
    """Reconhece o formato pelo conteúdo; a extensão é só o último recurso.

    Um CSV da Scopus que se chama ``scopus.csv`` não pode cair no leitor CSV do
    SciMAT: os autores, as palavras e as citações seriam lidos errado.
    """
    caminho = Path(caminho)
    texto = _texto(caminho)
    amostra = texto[:65536]
    extensao = caminho.suffix.lower().lstrip(".")

    if re.search(r"(?m)^TY\s{2}-", amostra):
        return "ris"
    if re.search(r"(?m)^@\w+\s*\{", amostra):
        return "bibtex"
    if re.search(r"(?m)^PT\s+[A-Z]", amostra):
        return "wos"

    primeira = amostra.splitlines()[0] if amostra else ""
    colunas = set(_colunas(primeira))
    # OpenAlex antes da Scopus: a exportação enriquecida repete "Author full
    # names" e "Author Keywords", mas tem "OpenAlex ID" e não tem as colunas
    # exclusivas da Scopus ("Index Keywords", "Document Type", "EID").
    # O CSV do Zotero tem "Item Type" e "Publication Year" (e não tem "Authors").
    if "item type" in colunas and ({"publication year", "manual tags",
                                    "publication title"} & colunas):
        return "zotero"
    if "openalex id" in colunas or "source keywords" in colunas:
        return "openalex"
    if ("index keywords" in colunas or "document type" in colunas
            or "author(s) id" in colunas or "eid" in colunas):
        return "scopus"
    if "author full names" in colunas:
        return "openalex"
    if {"authorkeywords", "sourcekeywords", "citations"} & colunas:
        return "csv"
    if "title" in colunas and ("authors" in colunas or "year" in colunas):
        return "csv"
    if extensao in ("bib", "bibtex"):
        return "bibtex"
    if extensao == "ris":
        return "ris"
    if extensao == "txt":
        return "wos"
    return "csv"


def le_corpus(caminho: str | Path, formato: str = "auto",
              sinonimos: str | Path | None = None):
    """Lê um corpus no formato pedido e devolve ``(documentos, formato)``.

    Com ``auto``, ou quando o conteúdo mostra que o formato escolhido era outro
    entre os tabulares (CSV SciMAT, Scopus, OpenAlex, Zotero), vale o formato
    reconhecido pelo conteúdo. É o ponto único usado pela linha de comando e
    pela interface web.
    """
    from . import bibtex, csv as csv_loader, openalex, ris, scopus, wos, zotero

    if formato not in FORMATOS and formato != "auto":
        raise ValueError(f"formato desconhecido: {formato}")
    detectado = detecta_formato(caminho)
    tabulares = ("csv", "scopus", "openalex", "zotero")
    if formato == "auto" or (formato in tabulares and detectado in tabulares):
        formato = detectado

    if formato == "csv":
        documentos = csv_loader.le(caminho)
    elif formato == "bibtex":
        documentos = bibtex.le(caminho)
    elif formato == "ris":
        documentos = ris.le(caminho)
    elif formato == "wos":
        documentos = wos.le(caminho)
    elif formato == "scopus":
        documentos = scopus.le(caminho)
    elif formato == "zotero":
        documentos = zotero.le(caminho)
    else:
        documentos = openalex.le(caminho, sinonimos)
    return documentos, formato

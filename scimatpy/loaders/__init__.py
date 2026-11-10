"""Carregadores de corpus: CSV SciMAT, BibTeX, RIS, OpenAlex, WoS e Scopus."""

from __future__ import annotations

import re
from pathlib import Path

from .base import DocumentoFonte

__all__ = ["DocumentoFonte", "detecta_formato"]


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

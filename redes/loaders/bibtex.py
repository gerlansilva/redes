"""Leitor BibTeX.

Lê entradas ``@article``, ``@inproceedings``, ``@book`` e semelhantes, com
campos entre chaves ou aspas e chaves de fechamento equilibradas. Autores no
formato ``Sobrenome, Nome and ...`` são convertidos para ``Sobrenome, I.``.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import (DocumentoFonte, abrevia_autor, acha_doi, citacoes_em_texto,
                   decodifica_latex)

_CABECALHO = re.compile(r"@(\w+)\s*\{([^,]*),", re.IGNORECASE)
_CAMPO = re.compile(r"(\w+)\s*=\s*", re.IGNORECASE)


def _valor(texto: str, inicio: int) -> tuple[str, int]:
    """Lê o valor de um campo a partir de `inicio`, respeitando chaves e aspas."""
    i = inicio
    while i < len(texto) and texto[i] in " \t\r\n":
        i += 1

    if i >= len(texto):
        return "", i

    if texto[i] == "{":
        profundidade = 0
        j = i
        while j < len(texto):
            if texto[j] == "{":
                profundidade += 1
            elif texto[j] == "}":
                profundidade -= 1
                if profundidade == 0:
                    return texto[i + 1:j], j + 1
            j += 1
        return texto[i + 1:], j

    if texto[i] == '"':
        j = i + 1
        while j < len(texto) and texto[j] != '"':
            j += 1
        return texto[i + 1:j], j + 1

    j = i
    while j < len(texto) and texto[j] not in ",\n}":
        j += 1
    return texto[i:j].strip(), j


def _entradas(texto: str):
    posicao = 0
    while True:
        achado = _CABECALHO.search(texto, posicao)
        if not achado:
            return
        tipo = achado.group(1).lower()
        corpo_inicio = achado.end()
        profundidade = 1
        i = corpo_inicio
        while i < len(texto) and profundidade:
            if texto[i] == "{":
                profundidade += 1
            elif texto[i] == "}":
                profundidade -= 1
            i += 1
        yield tipo, texto[corpo_inicio:i - 1]
        posicao = i


def _campos(corpo: str) -> dict[str, str]:
    campos = {}
    posicao = 0
    while True:
        achado = _CAMPO.search(corpo, posicao)
        if not achado:
            break
        nome = achado.group(1).lower()
        valor, posicao = _valor(corpo, achado.end())
        campos.setdefault(nome, valor.strip())
    return campos


def _autores(valor: str) -> list[str]:
    nomes = [n.strip() for n in re.split(r"\s+and\s+", valor or "") if n.strip()]
    return [abrevia_autor(decodifica_latex(n)) for n in nomes]


def _palavras(valor: str) -> list[str]:
    return [decodifica_latex(p).strip()
            for p in re.split(r"[;,]", valor or "") if p.strip()]


def le(caminho: str | Path) -> list[DocumentoFonte]:
    texto = Path(caminho).read_text(encoding="utf-8-sig", errors="replace")
    documentos = []

    for tipo, corpo in _entradas(texto):
        campos = _campos(corpo)
        titulo = re.sub(r"\s+", " ", campos.get("title", "")).strip()
        if not titulo:
            continue

        ano = (campos.get("year") or "").strip()
        if not ano:
            achado = re.search(r"\d{4}", campos.get("date", ""))
            ano = achado.group(0) if achado else ""

        documentos.append(DocumentoFonte(
            titulo=decodifica_latex(titulo),
            autores=_autores(campos.get("author", "")),
            ano=ano,
            citacoes=citacoes_em_texto(campos.get("note", ""),
                                       campos.get("annote", "")),
            periodico=decodifica_latex(
                campos.get("journal") or campos.get("journaltitle")
                or campos.get("booktitle") or campos.get("publisher") or ""),
            doi=campos.get("doi", "").strip() or acha_doi(campos.get("url", "")),
            tipo=tipo,
            resumo=decodifica_latex(
                re.sub(r"\s+", " ", campos.get("abstract", "")).strip()),
            palavras_autor=_palavras(campos.get("keywords", "")),
            palavras_fonte=[],
            referencias=[],
            referencias_convertidas=False,
        ))

    return documentos

"""Leitor do formato de texto do ISI Web of Science.

O arquivo é a exportação "Plain Text" do WoS: blocos de registros começando em
``PT`` e terminando em ``ER``, com campos de duas letras. Campos que se repetem
(autores, palavras-chave, referências citadas) aparecem em linhas consecutivas.

A correspondência é a do importador do fork (``ISIWoSLoader.addWord``):
``DE`` (author keywords) → palavras do autor; ``ID`` (keywords plus) →
palavras da fonte.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..paises import paises_de
from .base import DocumentoFonte

_INICIO = re.compile(r"^([A-Z][A-Z0-9]) (.*)$")

# Campos que se repetem em linhas próprias; os demais continuam o texto.
_REPETIDOS = {"AU", "AF", "CR", "C1", "DE", "ID", "EM", "OI", "FU", "SU"}


def _divide(palavras: str) -> list[str]:
    return [item.strip() for item in re.split(r"[;|]", palavras or "")
            if item.strip()]


def _citacoes(valor: str) -> int:
    try:
        return int(float(valor.strip() or 0))
    except ValueError:
        return 0


def le(caminho: str | Path) -> list[DocumentoFonte]:
    texto = Path(caminho).read_text(encoding="utf-8-sig", errors="replace")
    registros: list[dict[str, list[str]]] = []
    atual: dict[str, list[str]] | None = None
    campo = None

    for linha in texto.splitlines():
        if linha.startswith("PT "):
            atual = {}
            campo = None
        if atual is None:
            continue
        encontrado = _INICIO.match(linha)
        if encontrado:
            campo = encontrado.group(1)
            atual.setdefault(campo, []).append(encontrado.group(2).strip())
        elif linha.startswith("   ") and campo:
            if campo in _REPETIDOS:
                atual[campo].append(linha.strip())
            else:
                atual[campo][-1] += " " + linha.strip()
        if linha.startswith("ER"):
            registros.append(atual)
            atual = None
            campo = None

    documentos = []
    for registro in registros:
        def primeiro(nome: str) -> str:
            return (registro.get(nome) or [""])[0].strip()

        titulo = primeiro("TI").replace("\n", " ")
        if not titulo:
            continue

        autores = [nome.strip() for nome in registro.get("AU", []) if nome.strip()]
        referencias = [ref.strip() for ref in registro.get("CR", []) if ref.strip()]

        afiliacoes = [item.strip() for item in registro.get("C1", [])
                      if item.strip()]
        documentos.append(DocumentoFonte(
            titulo=titulo,
            autores=autores,
            ano=primeiro("PY") or primeiro("PD")[:4],
            citacoes=_citacoes(primeiro("TC")),
            periodico=primeiro("SO"),
            doi=primeiro("DI"),
            tipo=primeiro("DT"),
            resumo=primeiro("AB").replace("\n", " "),
            afiliacoes=afiliacoes,
            paises=paises_de(afiliacoes),
            palavras_autor=_divide("; ".join(registro.get("DE", []))),
            palavras_fonte=_divide("; ".join(registro.get("ID", []))),
            referencias=referencias,
        ))
    return documentos

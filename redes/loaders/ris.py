"""Leitor RIS (inclusive o RIS exportado pelo Zotero e pelo EndNote).

Cada registro começa em ``TY`` e termina em ``ER``. Tags aproveitadas: TI/T1
(título), AU/A1 (autores), PY/Y1/DA (ano), JO/JF/T2/J2 (periódico ou evento),
KW (palavras-chave, uma por linha ou separadas por ``;``), DO (DOI, ou o
endereço em UR), AB/N2 (resumo), N1 (notas, de onde sai "Cited By: n"), C1
(afiliação) e TY (tipo).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..paises import paises_de
from .base import (DocumentoFonte, abrevia_autor, acha_doi, citacoes_em_texto,
                   divide_termos)

_TAG = re.compile(r"^([A-Z][A-Z0-9])\s{2}-\s?(.*)$")


def _texto(caminho: str | Path) -> str:
    dados = Path(caminho).read_bytes()
    for codificacao in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return dados.decode(codificacao)
        except UnicodeError:
            continue
    return dados.decode("utf-8", errors="replace")


def _registros(texto: str) -> list[dict[str, list[str]]]:
    registros = []
    atual: dict[str, list[str]] = {}
    ultima = None

    for linha in texto.replace("\x00", "").splitlines():
        achado = _TAG.match(linha.rstrip())
        if achado:
            tag, valor = achado.group(1), achado.group(2).strip()
        else:
            if ultima and linha.strip():
                atual[ultima][-1] += " " + linha.strip()
            continue

        if tag == "TY":
            if atual:  # registro sem ER antes do próximo TY
                registros.append(atual)
            atual = {}
        elif tag == "ER":
            if atual:
                registros.append(atual)
            atual = {}
            ultima = None
            continue

        atual.setdefault(tag, []).append(valor)
        ultima = tag

    if atual:
        registros.append(atual)
    return registros


def _ano(registro: dict[str, list[str]]) -> str:
    for tag in ("PY", "Y1", "DA", "Y2"):
        achado = re.search(r"\d{4}", " ".join(registro.get(tag, [])))
        if achado:
            return achado.group(0)
    return ""


def le(caminho: str | Path) -> list[DocumentoFonte]:
    documentos = []
    for registro in _registros(_texto(caminho)):
        titulo = " ".join(registro.get("TI") or registro.get("T1") or []).strip()
        if not titulo:
            continue

        nomes = [n for n in registro.get("AU", []) + registro.get("A1", [])
                 if n.strip()]
        periodico = " ".join(registro.get("JO") or registro.get("JF")
                             or registro.get("T2") or registro.get("JA")
                             or registro.get("J2") or []).strip()
        palavras = []
        for valor in registro.get("KW", []):
            palavras.extend(divide_termos(valor))

        afiliacoes = registro.get("C1", []) + registro.get("AD", [])
        notas = " ".join(registro.get("N1", []))
        doi = " ".join(registro.get("DO", [])).strip() or acha_doi(
            " ".join(registro.get("UR", [])), " ".join(registro.get("L3", [])),
            notas)
        documentos.append(DocumentoFonte(
            titulo=re.sub(r"\s+", " ", titulo),
            autores=[abrevia_autor(n) for n in nomes],
            autores_completos=[n.strip() for n in nomes],
            ano=_ano(registro),
            citacoes=citacoes_em_texto(notas),
            periodico=periodico,
            doi=doi,
            tipo=" ".join(registro.get("TY", [])).strip().lower(),
            resumo=" ".join(registro.get("AB") or registro.get("N2") or []).strip(),
            afiliacoes=afiliacoes,
            paises=paises_de(afiliacoes),
            palavras_autor=palavras,
            palavras_fonte=[],
            referencias=[],
            referencias_convertidas=False,
        ))

    return documentos

"""Leitor RIS.

Cada registro começa em ``TY`` e termina em ``ER``. Tags aproveitadas: TI/T1
(título), AU/A1 (autores), PY/Y1 (ano), JO/JF/T2 (periódico ou evento), KW
(palavras-chave), DO (DOI), AB (resumo), C1 (afiliação) e TY (tipo).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..paises import paises_de
from .base import DocumentoFonte, abrevia_autor

_TAG = re.compile(r"^([A-Z][A-Z0-9])\s{2}-\s?(.*)$")


def le(caminho: str | Path) -> list[DocumentoFonte]:
    registros = []
    atual: dict[str, list[str]] = {}
    ultima = None

    for linha in Path(caminho).read_text(encoding="utf-8-sig", errors="replace").splitlines():
        achado = _TAG.match(linha.rstrip())
        if achado:
            tag, valor = achado.group(1), achado.group(2).strip()
        else:
            if ultima and linha.strip():
                atual[ultima][-1] += " " + linha.strip()
            continue

        if tag == "TY":
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

    documentos = []
    for registro in registros:
        titulo = " ".join(registro.get("TI") or registro.get("T1") or []).strip()
        if not titulo:
            continue

        autores = [abrevia_autor(n) for n in
                   registro.get("AU", []) + registro.get("A1", []) if n.strip()]
        ano = " ".join(registro.get("PY") or registro.get("Y1") or []).strip()
        achado = re.search(r"\d{4}", ano)
        periodico = " ".join(registro.get("JO") or registro.get("JF")
                             or registro.get("T2") or registro.get("JA") or []).strip()

        afiliacoes = registro.get("C1", [])
        documentos.append(DocumentoFonte(
            titulo=re.sub(r"\s+", " ", titulo),
            autores=autores,
            ano=achado.group(0) if achado else "",
            citacoes=0,
            periodico=periodico,
            doi=" ".join(registro.get("DO", [])).strip(),
            tipo=" ".join(registro.get("TY", [])).strip().lower(),
            resumo=" ".join(registro.get("AB", [])).strip(),
            afiliacoes=afiliacoes,
            paises=paises_de(afiliacoes),
            palavras_autor=[p.strip() for p in registro.get("KW", []) if p.strip()],
            palavras_fonte=[],
            referencias=[],
            referencias_convertidas=False,
        ))

    return documentos

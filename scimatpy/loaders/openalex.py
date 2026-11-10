"""Leitor de exportações CSV do OpenAlex.

O OpenAlex usa nomes de coluna diferentes do SciMAT e grafa a lista de autores
como ``Sobrenome, Iniciais, Sobrenome, Iniciais``. As palavras-chave são
canonicalizadas (uma grafia por termo, com sinônimos opcionais) e as
referências passam pelo mesmo interpretador do Scopus.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from ..references import converte_referencia, limpa_texto, SEPARADOR_REFERENCIA
from ..text_utils import chave
from ..words import Canonicalizador, Sinonimos
from ..paises import paises_de
from .base import DocumentoFonte

INICIAIS = re.compile(r"^[A-Z](?:\.?-?[A-Z])*\.?$")

# Colunas que viram campos estruturados. As demais ficam em DocumentMetadata,
# para que nenhum dado da exportação seja perdido.
ESTRUTURADAS = {
    "Authors", "Author full names", "Title", "Year", "Source title", "DOI",
    "Affiliations", "Abstract", "Author Keywords", "Source Keywords",
    "References", "Cited by", "Type",
}


def _autores(curto: str, completo: str) -> list[str]:
    """Separa "Sobrenome, Iniciais, Sobrenome, Iniciais" em nomes."""
    completos = [n.strip() for n in (completo or "").split(";") if n.strip()]
    partes = [p.strip() for p in (curto or "").split(",") if p.strip()]
    nomes = []
    atual: list[str] = []

    for parte in partes:
        if not atual:
            atual = [parte]
        elif INICIAIS.match(parte):
            atual.append(parte)
            nomes.append(", ".join(atual))
            atual = []
        else:
            nomes.append(", ".join(atual))
            atual = [parte]

    if atual:
        nomes.append(", ".join(atual))

    if completos and len(completos) != len(nomes):
        return completos
    return nomes or completos


def _autores_completos(valor: str) -> list[str]:
    return [n.strip() for n in (valor or "").split(";") if n.strip()]


def _metadados(registro: dict) -> dict[str, str]:
    return {
        chave: limpa_texto(valor)
        for chave, valor in registro.items()
        if chave not in ESTRUTURADAS and limpa_texto(valor)
    }


def _citacoes(valor: str) -> int:
    try:
        return int(float((valor or "0").replace(",", ".")))
    except ValueError:
        return 0


def le(caminho: str | Path, sinonimos: str | Path | None = None) -> list[DocumentoFonte]:
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        registros = [r for r in csv.DictReader(arquivo) if limpa_texto(r.get("Title"))]

    palavras = Canonicalizador(Sinonimos(sinonimos))
    for registro in registros:
        palavras.registra([limpa_texto(p) for p in (registro.get("Author Keywords") or "").split(";")
                           if limpa_texto(p)])
        palavras.registra([limpa_texto(p) for p in (registro.get("Source Keywords") or "").split(";")
                           if limpa_texto(p)])

    autores = Canonicalizador()
    for registro in registros:
        autores.registra(_autores(registro.get("Authors"), registro.get("Author full names")))

    # A forma canônica é global (grafias equivalentes viram uma referência só),
    # mas o vínculo é por documento: a mesma referência citada por dois
    # documentos precisa aparecer nos dois.
    canonicas: dict[str, str] = {}
    documentos = []

    for registro in registros:
        referencias_do_documento: set[str] = set()
        afiliacoes = [limpa_texto(a) for a in (registro.get("Affiliations") or "").split(";") if limpa_texto(a)]
        referencias = []
        referencias_brutas = []
        for bruta in SEPARADOR_REFERENCIA.split(registro.get("References") or ""):
            item = converte_referencia(bruta)
            if not item:
                continue
            k = chave(item)
            if k in canonicas:
                item = canonicas[k]
            else:
                canonicas[k] = item
            if item in referencias_do_documento:
                continue
            referencias_do_documento.add(item)
            referencias.append(item)
            referencias_brutas.append(limpa_texto(bruta))

        documentos.append(DocumentoFonte(
            titulo=limpa_texto(registro.get("Title")),
            autores=autores.aplica(_autores(registro.get("Authors"),
                                            registro.get("Author full names"))),
            autores_completos=_autores_completos(registro.get("Author full names")),
            ano=limpa_texto(registro.get("Year")),
            citacoes=_citacoes(registro.get("Cited by")),
            periodico=limpa_texto(registro.get("Source title")),
            doi=limpa_texto(registro.get("DOI")),
            tipo=limpa_texto(registro.get("Type")) or "article",
            resumo=limpa_texto(registro.get("Abstract")),
            afiliacoes=afiliacoes,
            paises=paises_de(afiliacoes, registro.get("Country")),
            palavras_autor=palavras.aplica([limpa_texto(p) for p in
                                            (registro.get("Author Keywords") or "").split(";")
                                            if limpa_texto(p)]),
            palavras_fonte=palavras.aplica([limpa_texto(p) for p in
                                            (registro.get("Source Keywords") or "").split(";")
                                            if limpa_texto(p)]),
            referencias=referencias,
            referencias_brutas=referencias_brutas,
            referencias_convertidas=True,
            metadados=_metadados(registro),
        ))

    return documentos

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
from ..siglas_paises import SIGLAS_PAISES
from .base import DocumentoFonte, abrevia_autor

INICIAIS = re.compile(r"^[A-Z](?:\.?-?[A-Z])*\.?$")

# Colunas que viram campos estruturados. As demais ficam em DocumentMetadata,
# para que nenhum dado da exportação seja perdido.
ESTRUTURADAS = {
    "Authors", "Author full names", "Title", "Year", "Source title", "DOI",
    "Affiliations", "Abstract", "Author Keywords", "Source Keywords",
    "References", "Cited by", "Type",
    # Exportação do site do OpenAlex (autores e países separados por barra).
    "Author", "Citation count",
}

_PALAVRAS_NO_RESUMO = re.compile(
    r"(?:palavras?[\s\-]*chaves?|palabras?[\s\-]*claves?|keywords?|mots[\s\-]*cl[ée]s)\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.DOTALL)


def _nomes_do_site(registro: dict) -> tuple[list[str], list[str]] | None:
    """Autores da exportação do site do OpenAlex: nomes completos separados por `|`."""
    if registro.get("Authors") or "Author" not in registro:
        return None
    completos = [n.strip() for n in (registro.get("Author") or "").split("|") if n.strip()]
    return [_abrevia_nome_do_site(n) for n in completos], completos


_PARTICULAS = frozenset("de da do das dos e di del della van von der den la le y".split())


def _abrevia_nome_do_site(nome: str) -> str:
    """"Natália Desconsi de ANDRADE" → "Andrade, N.D." (sem partículas, sobrenome em caixa normal)."""
    partes = [p for p in nome.split() if p]
    if len(partes) < 2:
        return nome.strip()
    sobrenome = partes[-1]
    if sobrenome.isupper() and len(sobrenome) > 1:
        sobrenome = sobrenome.capitalize()
    resto = [p for p in partes[:-1] if p.lower() not in _PARTICULAS]
    return abrevia_autor(f"{sobrenome}, {' '.join(resto)}") if resto else sobrenome


def _paises_por_sigla(valor: str) -> list[str]:
    achados: list[str] = []
    for parte in re.split(r"[|;,]", valor or ""):
        nome = SIGLAS_PAISES.get(parte.strip().upper(), "")
        if nome and nome not in achados:
            achados.append(nome)
    return achados


def _palavras_do_resumo(resumo: str) -> list[str]:
    """Palavras-chave que o resumo traz no fim ("Palavras-chave: a, b, c.")."""
    achado = _PALAVRAS_NO_RESUMO.search(resumo or "")
    if not achado:
        return []
    texto = achado.group(1).strip().rstrip(".")
    return [limpa_texto(p) for p in re.split(r"[;,]", texto) if limpa_texto(p)]


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


def _palavras_autor_registro(registro: dict) -> list[str]:
    dadas = [limpa_texto(p) for p in (registro.get("Author Keywords") or "").split(";")
             if limpa_texto(p)]
    return dadas or _palavras_do_resumo(registro.get("Abstract"))


def le(caminho: str | Path, sinonimos: str | Path | None = None) -> list[DocumentoFonte]:
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        registros = [r for r in csv.DictReader(arquivo) if limpa_texto(r.get("Title"))]

    palavras = Canonicalizador(Sinonimos(sinonimos))
    for registro in registros:
        palavras.registra(_palavras_autor_registro(registro))
        palavras.registra([limpa_texto(p) for p in (registro.get("Source Keywords") or "").split(";")
                           if limpa_texto(p)])

    def curtos_e_completos(registro):
        site = _nomes_do_site(registro)
        if site:
            return site
        return (_autores(registro.get("Authors"), registro.get("Author full names")),
                _autores_completos(registro.get("Author full names")))

    autores = Canonicalizador()
    for registro in registros:
        autores.registra(curtos_e_completos(registro)[0])

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

        curtos, completos = curtos_e_completos(registro)
        documentos.append(DocumentoFonte(
            titulo=limpa_texto(registro.get("Title")),
            autores=autores.aplica(curtos),
            autores_completos=completos,
            ano=limpa_texto(registro.get("Year")),
            citacoes=_citacoes(registro.get("Cited by") or registro.get("Citation count")),
            periodico=limpa_texto(registro.get("Source title")),
            doi=limpa_texto(registro.get("DOI")),
            tipo=limpa_texto(registro.get("Type")) or "article",
            resumo=limpa_texto(registro.get("Abstract")),
            afiliacoes=afiliacoes,
            paises=(paises_de(afiliacoes, registro.get("Country"))
                    or _paises_por_sigla(registro.get("Country"))),
            palavras_autor=palavras.aplica(_palavras_autor_registro(registro)),
            palavras_fonte=palavras.aplica([limpa_texto(p) for p in
                                            (registro.get("Source Keywords") or "").split(";")
                                            if limpa_texto(p)]),
            referencias=referencias,
            referencias_brutas=referencias_brutas,
            referencias_convertidas=True,
            metadados=_metadados(registro),
        ))

    return documentos

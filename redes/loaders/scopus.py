"""Leitor do CSV exportado pela Scopus.

A Scopus exporta um CSV com cabeçalhos em inglês; os nomes mudam um pouco entre
versões ("Cited by", "Cited by (since 2016)", "Cited by (since 2021)"). O leitor
aceita as variantes e usa o mesmo mapeamento de palavras do importador do fork:
"Author Keywords" → palavras do autor; "Index Keywords" → palavras da fonte.

O arquivo pode vir com vírgula, ponto e vírgula ou tabulação como separador,
dependendo de como foi salvo, e as referências citadas usam ``;`` também entre
autores — por isso elas são separadas pelo fim do ano entre parênteses, como no
leitor do OpenAlex.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from ..references import SEPARADOR_REFERENCIA, converte_referencia, limpa_texto
from ..paises import paises_de
from .base import DocumentoFonte


def _campo(linha: dict, *nomes: str) -> str:
    for nome in nomes:
        for chave, valor in linha.items():
            if chave and chave.strip().lower() == nome.lower():
                return (valor or "").strip()
    return ""


def _campo_prefixo(linha: dict, prefixo: str) -> str:
    """Casa "Cited by", "Cited by (since 2016)", "Cited by (since 2021)"."""
    prefixo = prefixo.lower()
    for chave, valor in linha.items():
        if chave and chave.strip().lower().startswith(prefixo):
            return (valor or "").strip()
    return ""


def _lista(valor: str) -> list[str]:
    texto = (valor or "").replace("\n", " ")
    partes = [item.strip() for item in texto.split(";")]
    return [item for item in partes if item]


_ID_AUTOR = re.compile(r"\s*\(\d+\)\s*$")


def _autores(linha: dict) -> tuple[list[str], list[str]]:
    """Autores abreviados e completos, sem os IDs numéricos da Scopus."""
    completos = [_ID_AUTOR.sub("", nome).strip()
                 for nome in _lista(_campo(linha, "Author full names"))]
    abreviados = [_ID_AUTOR.sub("", nome).strip()
                  for nome in _lista(_campo(linha, "Authors"))]
    return abreviados or completos, completos or abreviados


# Colunas que viram campos estruturados. As demais ficam em DocumentMetadata,
# para que nenhum dado da exportação seja perdido.
ESTRUTURADAS = {
    "authors", "author full names", "title", "year", "source title", "source",
    "doi", "affiliations", "abstract", "author keywords", "index keywords",
    "references", "document type", "type",
}


def _metadados(linha: dict) -> dict[str, str]:
    dados = {}
    for chave, valor in linha.items():
        if not chave:
            continue
        nome = chave.strip()
        minusculo = nome.lower()
        if minusculo in ESTRUTURADAS or minusculo.startswith("cited by"):
            continue
        if limpa_texto(valor):
            dados[nome] = limpa_texto(valor)
    return dados


def _referencias(valor: str) -> tuple[list[str], list[str]]:
    """Separa citações pelo ano entre parênteses, preservando autores com ``;``."""
    convertidas = []
    brutas = []
    for bruta in SEPARADOR_REFERENCIA.split((valor or "").replace("\n", " ")):
        item = converte_referencia(limpa_texto(bruta))
        if item and item not in convertidas:
            convertidas.append(item)
            brutas.append(limpa_texto(bruta))
    return convertidas, brutas


def _citacoes(valor: str) -> int:
    try:
        return int(float((valor or "0").strip() or 0))
    except ValueError:
        return 0


def _texto(caminho: str | Path) -> str:
    dados = Path(caminho).read_bytes()
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return dados.decode("utf-8", errors="replace")


def _delimitador(cabecalho: str) -> str:
    """Escolhe o separador pela linha de cabeçalho, que não tem texto livre."""
    contagem = {separador: cabecalho.count(separador)
                for separador in (",", ";", "\t")}
    return max(contagem, key=contagem.get) if max(contagem.values()) else ","


def le(caminho: str | Path) -> list[DocumentoFonte]:
    texto = _texto(caminho)
    cabecalho = texto.splitlines()[0] if texto else ""
    registros = csv.DictReader(io.StringIO(texto),
                               delimiter=_delimitador(cabecalho))

    documentos = []
    for linha in registros:
        titulo = _campo(linha, "Title").replace("\n", " ")
        if not titulo:
            continue

        autores, autores_completos = _autores(linha)
        afiliacoes = _lista(_campo(linha, "Affiliations"))
        referencias, referencias_brutas = _referencias(_campo(linha, "References"))
        documentos.append(DocumentoFonte(
            titulo=titulo,
            autores=autores,
            autores_completos=autores_completos,
            ano=_campo(linha, "Year"),
            citacoes=_citacoes(_campo_prefixo(linha, "Cited by")),
            periodico=_campo(linha, "Source title", "Source"),
            doi=_campo(linha, "DOI"),
            tipo=_campo(linha, "Document Type"),
            resumo=_campo(linha, "Abstract").replace("\n", " "),
            afiliacoes=afiliacoes,
            paises=paises_de(afiliacoes),
            palavras_autor=_lista(_campo(linha, "Author Keywords")),
            palavras_fonte=_lista(_campo(linha, "Index Keywords")),
            referencias=referencias,
            referencias_brutas=referencias_brutas,
            referencias_convertidas=True,
            metadados=_metadados(linha),
        ))
    return documentos

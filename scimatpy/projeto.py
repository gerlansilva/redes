"""Extensão e nomes dos arquivos de projeto do Redes.

O projeto é um banco SQLite. Até a versão anterior ele usava a extensão
``.scimat``, herdada do formato do SciMAT. Os projetos gravados pelo Redes
passam a usar ``.redes``; arquivos ``.scimat`` continuam abrindo para não
perder bases já construídas.
"""

from __future__ import annotations

from pathlib import Path

EXTENSAO = ".redes"
EXTENSOES = (".redes", ".scimat")
NOME_PADRAO = f"dados{EXTENSAO}"


def e_projeto(caminho: str | Path) -> bool:
    """Verdadeiro quando o caminho tem extensão de projeto reconhecida."""
    return Path(caminho).suffix.lower() in EXTENSOES


def nome_de_projeto(caminho: str | Path) -> bool:
    """Verdadeiro para o arquivo padrão ``dados.redes`` (ou ``dados.scimat``)."""
    return Path(caminho).stem == "dados"


def com_extensao(caminho: str | Path) -> Path:
    """Acrescenta ``.redes`` quando o caminho não tem extensão de projeto."""
    destino = Path(caminho)
    if e_projeto(destino):
        return destino
    return destino.with_name(destino.name + EXTENSAO)

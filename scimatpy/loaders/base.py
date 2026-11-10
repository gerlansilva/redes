"""Estrutura comum dos carregadores de corpus."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

INICIAIS = re.compile(r"^[A-Z](?:\.?-?[A-Z])*\.?$")


@dataclass
class DocumentoFonte:
    """Um registro importado, antes de virar linhas do armazenamento."""

    titulo: str
    autores: list[str] = field(default_factory=list)
    autores_completos: list[str] = field(default_factory=list)
    ano: str = ""
    citacoes: int = 0
    periodico: str = ""
    doi: str = ""
    tipo: str = ""
    resumo: str = ""
    afiliacoes: list[str] = field(default_factory=list)
    paises: list[str] = field(default_factory=list)
    palavras_autor: list[str] = field(default_factory=list)
    palavras_fonte: list[str] = field(default_factory=list)
    referencias: list[str] = field(default_factory=list)
    referencias_brutas: list[str] = field(default_factory=list)
    referencias_convertidas: bool = False
    metadados: dict[str, str] = field(default_factory=dict)


def abrevia_autor(nome: str) -> str:
    """"Lopes, Celi Espasandin" → "Lopes, C.E." (formato do SciMAT)."""
    nome = (nome or "").strip()
    if not nome:
        return ""

    if "," in nome:
        sobrenome, resto = nome.split(",", 1)
    else:
        partes = nome.split()
        if len(partes) < 2:
            return nome
        sobrenome, resto = partes[-1], " ".join(partes[:-1])

    tokens = [p for p in re.split(r"[\s\-]+", resto.strip()) if p]
    if tokens and all(INICIAIS.match(p) for p in tokens):
        return f"{sobrenome.strip()}, {''.join(tokens)}"

    iniciais = [p[0].upper() + "." for p in tokens if p[0].isalpha()]
    if not iniciais:
        return sobrenome.strip()

    return f"{sobrenome.strip()}, {''.join(iniciais)}"

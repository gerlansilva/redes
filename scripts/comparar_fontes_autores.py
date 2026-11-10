#!/usr/bin/env python3
"""Compara os mapas de Sources e Authors do VOSviewer com o projeto Redes.

Uso:
    python3 scripts/comparar_fontes_autores.py \
        ~/Desktop/sourcebatanero.csv.json \
        ~/Desktop/autoresbatanero.csv.json \
        ~/scimatpy-projetos/batanero-auditoria/dados.redes
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

NUMERACAO = re.compile(r"^\s*\[\d+\]\s*")


def norm(texto: str) -> str:
    """Minúsculas, sem acento e sem pontuação."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = texto.encode("ascii", "ignore").decode().lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def limpa_fonte(rotulo: str) -> str:
    """Remove páginas, volume, ano e URL que o VOSviewer cola no nome da fonte."""
    texto = re.sub(r"https?://\S+", "", rotulo)
    texto = re.sub(r"\bdoi\.?\s*org\S*", "", texto)
    texto = re.sub(r"\bpp?\.\s*[\d\-–]+", "", texto)
    texto = re.sub(r"\(\d{4}\)", "", texto)
    texto = re.sub(r"\b(19|20)\d{2}\b", "", texto)
    partes = [p for p in re.split(r"[,\s]+", texto) if p]
    while partes and not re.search(r"[a-z]{2,}", partes[-1]):
        partes.pop()
    return norm(" ".join(partes))


def rotulos(caminho: Path) -> list[str]:
    dados = json.loads(caminho.read_text(encoding="utf-8-sig"), strict=False)
    return [item["label"] for item in dados["network"]["items"]]


def fontes_do_projeto(banco: Path) -> set[str]:
    con = sqlite3.connect(banco)
    return {norm(r[0]) for r in con.execute("SELECT source FROM ReferenceSource") if r[0]}


def autores_do_projeto(banco: Path) -> set[str]:
    con = sqlite3.connect(banco)
    nomes: set[str] = set()
    for (lista,) in con.execute("SELECT authorName FROM AuthorReference"):
        for autor in (lista or "").split(";"):
            autor = autor.strip().strip(".,")
            if autor and autor.lower() != "sem autor":
                nomes.add(norm(autor))
    return nomes


def compara_fontes(caminho: Path, fontes: set[str]) -> dict:
    itens = rotulos(caminho)
    dentro = [l for l in itens if norm(l) in fontes]
    fora = [l for l in itens if norm(l) not in fontes]
    limpos = {limpa_fonte(l) for l in itens} - {""}
    return {
        "itens": len(itens),
        "casam": len(dentro),
        "fora": len(fora),
        "fora_com_paginas": sum(1 for l in fora if re.search(r"\bpp?\.\s*\d", l)),
        "distintos_apos_limpar": len(limpos),
        "limpos_que_casam": sum(1 for l in limpos if l in fontes),
    }


def compara_autores(caminho: Path, autores: set[str]) -> dict:
    itens = rotulos(caminho)
    sem_numero = [NUMERACAO.sub("", l).strip() for l in itens]
    dentro = [l for l in sem_numero if norm(l) in autores]
    fora = [l for l in sem_numero if norm(l) not in autores]
    lixo = [l for l in fora if not re.search(r"[a-z]{3,}", l)]
    return {
        "itens": len(itens),
        "casam": len(dentro),
        "fora": len(fora),
        "lixo": len(lixo),
        "exemplos_lixo": lixo[:8],
        "exemplos_fora": fora[:8],
    }


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__)
        return 2
    origem_fontes, origem_autores, banco = Path(argv[1]), Path(argv[2]), Path(argv[3])
    fontes = fontes_do_projeto(banco)
    autores = autores_do_projeto(banco)

    r = compara_fontes(origem_fontes, fontes)
    print("FONTES")
    print(f"  Redes (nomes distintos): {len(fontes)}")
    print(f"  VOSviewer (itens): {r['itens']}")
    print(f"  itens que são exatamente uma fonte do Redes: {r['casam']}")
    print(f"  itens fora: {r['fora']} (com páginas no rótulo: {r['fora_com_paginas']})")
    print(f"  distintos após remover páginas/volume/ano/URL: {r['distintos_apos_limpar']}")
    print(f"  desses, casam com o Redes: {r['limpos_que_casam']}")

    a = compara_autores(origem_autores, autores)
    print("\nAUTORES")
    print(f"  Redes (autores individuais): {len(autores)}")
    print(f"  VOSviewer (itens): {a['itens']}")
    print(f"  itens que são um autor do Redes (sem numeração): {a['casam']}")
    print(f"  itens fora: {a['fora']} (lixo evidente: {a['lixo']})")
    print(f"  exemplos de lixo: {a['exemplos_lixo']}")
    print(f"  exemplos fora: {a['exemplos_fora']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

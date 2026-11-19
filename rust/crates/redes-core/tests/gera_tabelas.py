#!/usr/bin/env python3
"""Gera `src/tabelas.rs` a partir das tabelas do Python (países e palavras vazias).

Uso (a partir da raiz do repositório):
    python3 rust/crates/redes-core/tests/gera_tabelas.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))

from redes import paises, rotulos, termos  # noqa: E402

SAIDA = Path(__file__).resolve().parents[1] / "src" / "tabelas.rs"


def lit(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def lista(nome: str, itens, tipo="&str") -> str:
    corpo = ",\n".join(f"    {lit(i)}" for i in itens)
    return f"pub static {nome}: &[{tipo}] = &[\n{corpo},\n];\n\n"


def pares(nome: str, itens) -> str:
    corpo = ",\n".join(f"    ({lit(a)}, {lit(b)})" for a, b in itens)
    return f"pub static {nome}: &[(&str, &str)] = &[\n{corpo},\n];\n\n"


saida = ["//! Tabelas geradas por `tests/gera_tabelas.py` (não editar à mão).\n\n"]
saida.append("/// Índice de países: chave normalizada (`paises._chave`) e nome canônico, em ordem de chave.\n")
saida.append(pares("INDICE_PAISES", sorted(paises._INDICE.items())))
saida.append("/// Siglas de estado dos EUA.\n")
saida.append(lista("SIGLAS_EUA", sorted(paises._SIGLAS_EUA)))
saida.append("/// Palavras vazias (pt, es, en), sem acento e em minúsculas.\n")
saida.append(lista("VAZIAS", sorted(termos._VAZIAS_SEM_ACENTO)))
saida.append("/// Palavras genéricas de títulos acadêmicos, sem acento e em minúsculas.\n")
saida.append(lista("ACADEMICAS", sorted(termos._ACADEMICAS_SEM_ACENTO)))
saida.append("/// Termos de resumo \"de praxe\" (`rotulos.PALAVRAS_DE_RESUMO`).\n")
saida.append(lista("PALAVRAS_DE_RESUMO", sorted(rotulos.PALAVRAS_DE_RESUMO)))
SAIDA.write_text("".join(saida), encoding="utf-8")
print(f"{SAIDA}: {len(paises._INDICE)} países, {len(termos._VAZIAS_SEM_ACENTO)} vazias")

"""Normalizações de texto usadas na importação e no agrupamento.

Porta `NameVariants` (comparação de grafias de autores e fontes), a regra de
plural de `FindSimilarItemsByPlurals` e a normalização de palavras do
importador CSV (`maiúsculas`, espaço → hífen).
"""

from __future__ import annotations

import re
import unicodedata

LIGACOES = frozenset(
    "of the and for in on a an to with from by at as de da do das dos e y".split())


def sem_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def chave(nome: str) -> str:
    """Chave de comparação: caixa, acento, pontuação e espaço não contam."""
    texto = sem_acentos(nome or "").lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", texto)


def normaliza_palavra(nome: str) -> str:
    """Forma guardada pelo importador: maiúsculas e hífen no lugar do espaço."""
    return (nome or "").strip().upper().replace(" ", "-")


def partes_abreviadas(nome: str) -> list[str]:
    """Palavras de uma abreviação pontuada ("Comput. Educ." → comput, educ)."""
    if not nome:
        return []
    palavras = nome.strip().split()
    if len(palavras) < 2:
        return []

    partes = []
    for palavra in palavras:
        if not palavra.endswith(".") or palavra == ".":
            return []
        limpa = sem_acentos(palavra[:-1]).lower().strip()
        if not limpa:
            return []
        partes.append(limpa)
    return partes


def parece_abreviacao(nome: str) -> bool:
    return bool(partes_abreviadas(nome))


def palavras_significativas(nome: str) -> list[str]:
    texto = sem_acentos(nome or "").lower()
    return [p for p in re.split(r"[^a-z0-9]+", texto) if p and p not in LIGACOES]


def abreviacao_de(partes, alvo) -> bool:
    if not partes or len(partes) != len(alvo):
        return False
    return all(parte and completa.startswith(parte)
               for parte, completa in zip(partes, alvo))


def mesmo_plural(a: str, b: str) -> bool:
    """Regra do SciMAT: o mesmo termo no singular e no plural."""
    return ((a + "S") == b or (a + "ES") == b
            or (a.endswith("Y") and a[:-1] + "IES" == b)
            or (a + "s") == b or (a + "es") == b
            or (a.endswith("y") and a[:-1] + "ies" == b)
            or (b + "S") == a or (b + "ES") == a
            or (b.endswith("Y") and b[:-1] + "IES" == a)
            or (b + "s") == a or (b + "es") == a
            or (b.endswith("y") and b[:-1] + "ies" == a))

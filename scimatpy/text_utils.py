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


_APOSTROFES = str.maketrans({
    "\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u00b4": "'", "`": "'",
    "\u2032": "'", "\u201b": "'",
})
_TRAVESSOES = str.maketrans({
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
    "\u2014": "-", "\u2212": "-",
})


def limpa_termo(nome: str) -> str:
    """Uniformiza a tipografia de um termo: apóstrofo, travessão e espaços.

    "children\u2019s" e "children's" são o mesmo termo, assim como "a\u2013b" e
    "a-b" e um espaço sem quebra e um espaço comum.
    """
    texto = unicodedata.normalize("NFC", nome or "")
    texto = texto.translate(_APOSTROFES).translate(_TRAVESSOES)
    return re.sub(r"\s+", " ", texto).strip()


def normaliza_palavra(nome: str) -> str:
    """Forma guardada pelo importador: maiúsculas e hífen no lugar do espaço."""
    return limpa_termo(nome).upper().replace(" ", "-")


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


# Plurais irregulares do português e do espanhol, já sem acento e em maiúsculas:
# educação/educações, homem/homens, animal/animais, papel/papéis, lápiz/lápices.
_SUFIXOS_IRREGULARES = (
    ("AO", "OES"), ("AO", "AES"), ("AO", "AOS"),
    ("M", "NS"),
    ("AL", "AIS"), ("EL", "EIS"), ("OL", "OIS"), ("UL", "UIS"),
    ("Z", "CES"),
)


def _plural_irregular(singular: str, plural: str) -> bool:
    # O radical mínimo evita casar palavras curtas e distintas (mal/mais).
    if len(singular) < 5:
        return False
    for fim_singular, fim_plural in _SUFIXOS_IRREGULARES:
        if (singular.endswith(fim_singular) and plural.endswith(fim_plural)
                and singular[:-len(fim_singular)] == plural[:-len(fim_plural)]):
            return True
    return False


def _mesmo_plural_token(a: str, b: str) -> bool:
    return (a == b or mesmo_plural(a, b)
            or _plural_irregular(a, b) or _plural_irregular(b, a))


def mesmo_termo(a: str, b: str) -> bool:
    """Singular e plural ou grafia sem acento, palavra por palavra.

    Estende `mesmo_plural` (regra do SciMAT, mantida para o inglês) ao português
    e ao espanhol: "PROFESSORES"/"PROFESSOR", "EDUCAÇÃO"/"EDUCACAO",
    "EDUCAÇÕES"/"EDUCACAO", "ENSINO-DE-ESTATÍSTICA"/"ENSINO-DE-ESTATISTICA" e
    termos compostos em que só uma das palavras está no plural
    ("ESTUDANTES-UNIVERSITARIOS"/"ESTUDANTE-UNIVERSITARIO").
    """
    if a == b:
        return False
    if mesmo_plural(a, b):
        return True
    sa = sem_acentos(a).upper()
    sb = sem_acentos(b).upper()
    if sa == sb:
        return True
    ta, tb = sa.split("-"), sb.split("-")
    if len(ta) != len(tb):
        return False
    return all(_mesmo_plural_token(x, y) for x, y in zip(ta, tb))


def chave_de_bloco(nome: str) -> str:
    """Bloco de comparação de `mesmo_termo`: nº de palavras e primeira letra.

    Variantes de plural e de acento preservam as duas coisas, o que permite
    comparar cada termo só com os do seu bloco em vez de com todos.
    """
    sem = sem_acentos(nome).upper()
    return f"{sem.count('-')}{sem[:1]}"

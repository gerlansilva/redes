"""Grade de análises: combinações usadas na avaliação do CELII.

Cada linha da grade acrescenta um eixo ao caso base (unidade de análise,
coocorrência, centros simples, índice de equivalência, frequência 2,
coocorrência 1, rede 2–15). O último eixo da grade antiga misturava um
mapeador de documentos (interseção) com oito medidas de desempenho; aqui cada
linha declara qual dos dois ela varia, e o TSV mostra o mapeador usado e o
valor da medida, de modo que nenhuma linha é cópia de outra.
"""

from __future__ import annotations

UNIDADES = ("Words", "Authors", "References", "AuthorsReference",
            "ReferenceSources", "Countries")
MATRIZES = ("CoOccurrence", "BasicCoupling", "AggregatedCouplingBasedOnAuthor",
            "AggregatedCouplingBasedOnJournal")
ALGORITMOS = ("CentersSimples", "AverageLink", "CompleteLink", "SingleLink",
              "SumLink", "Louvain")
MEDIDAS = ("AssociationStrength", "EquivalenceIndex", "InclusionIndex",
           "JaccardIndex", "SaltonCosine")
# Eixo final do script do CELII: um mapeador e oito medidas de desempenho.
RECORTES = ("interseccao", "h", "g", "hg", "q2", "media", "soma", "minimo", "maximo")


def grade():
    """Gera (eixo, unidade, matriz, algoritmo, similaridade, freq, cooc, min, max, mapeador, medida)."""
    for unidade in UNIDADES:
        yield ("BASE", unidade, "CoOccurrence", "CentersSimples",
               "EquivalenceIndex", 2, 1, 2, 15, "nucleo", None)

    for unidade in UNIDADES:
        for matriz in MATRIZES:
            if matriz != "CoOccurrence":
                yield ("MATRIZ", unidade, matriz, "CentersSimples",
                       "EquivalenceIndex", 2, 1, 2, 15, "nucleo", None)

    for unidade in UNIDADES:
        for algoritmo in ALGORITMOS:
            if algoritmo != "CentersSimples":
                yield ("ALGORITMO", unidade, "CoOccurrence", algoritmo,
                       "EquivalenceIndex", 2, 1, 2, 15, "nucleo", None)

    for unidade in UNIDADES:
        for medida in MEDIDAS:
            if medida != "EquivalenceIndex":
                yield ("SIMILARIDADE", unidade, "CoOccurrence", "CentersSimples",
                       medida, 2, 1, 2, 15, "nucleo", None)

    for unidade in UNIDADES:
        yield ("REDUCAO", unidade, "CoOccurrence", "CentersSimples",
               "EquivalenceIndex", 1, 1, 2, 15, "nucleo", None)
        yield ("REDUCAO", unidade, "CoOccurrence", "CentersSimples",
               "EquivalenceIndex", 3, 2, 2, 15, "nucleo", None)

    for unidade in UNIDADES:
        for minimo, maximo in ((3, 8), (4, 10), (4, 4)):
            yield ("REDE", unidade, "CoOccurrence", "CentersSimples",
                   "EquivalenceIndex", 2, 1, minimo, maximo, "nucleo", None)

    for unidade in UNIDADES:
        for recorte in RECORTES:
            if recorte == "interseccao":
                yield ("MAPEADOR", unidade, "CoOccurrence", "CentersSimples",
                       "EquivalenceIndex", 2, 1, 2, 15, "interseccao", None)
            else:
                yield ("MEDIDA", unidade, "CoOccurrence", "CentersSimples",
                       "EquivalenceIndex", 2, 1, 2, 15, "nucleo", recorte)

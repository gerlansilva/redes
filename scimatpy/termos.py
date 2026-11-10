"""Termos principais de títulos e palavras-chave, para a nuvem de palavras.

Os títulos são quebrados em palavras, sem artigos, preposições, conjunções e
outras palavras vazias de português, inglês e espanhol, nem os termos
genéricos da escrita acadêmica ("estudo", "analysis", "research"). Singular,
plural e acento são unidos com as mesmas regras da base, e as expressões de
duas palavras que se repetem ("statistical thinking") são contadas à parte.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .text_utils import mesmo_termo, sem_acentos

# --------------------------------------------------------------- palavras vazias

_PT = """
a o as os um uma uns umas de da do das dos em na no nas nos por para pelo pela pelos pelas com sem sob sobre
entre até ate ao aos à às e ou mas nem que se como quando onde porque pois então entao assim também tambem
já ja mais menos muito muita muitos muitas pouco poucos só apenas ainda sempre nunca este esta estes estas
esse essa esses essas isto isso aquilo aquele aquela aqueles aquelas seu sua seus suas meu minha nosso nossa
ser é são sao foi era está estão estao tem têm ter há ha pode podem deve devem desde durante após apos antes
depois contra cada outro outra outros outras mesmo mesma todo toda todos todas qual quais quem cujo
"""

_ES = """
el la los las un una unos unas de del en con sin sobre entre hasta desde por para al y o u pero ni que si
como cuando donde porque pues entonces así asi también tambien ya más mas menos muy mucho mucha muchos muchas
poco pocos solo sólo aún aun siempre nunca este esta estos estas ese esa esos esas esto eso aquel aquella su
sus mi mis nuestro nuestra ser es son fue era está están tiene tienen tener hay puede pueden debe deben
durante después despues antes contra cada otro otra otros otras mismo misma todo toda todos todas cual cuales
quien cuyo se lo le les
"""

_EN = """
a an the and or but nor of in on at to for from by with without within into onto over under between among
through during before after about against as than that this these those it its is are was were be been being
has have had do does did not no can could may might must shall should will would their there here which who
whom whose what when where why how all any both each few more most other some such only own same so too very
just also via per vs versus his her he she they them we our us you your i my me one two
"""

# Palavras muito comuns em títulos de artigos, que não dizem sobre o que é o estudo.
_ACADEMICAS = """
study studies analysis analyses research review reviews approach approaches case cases using use used based
towards toward new effect effects impact role development evaluation exploring exploration investigation
investigating understanding perspective perspectives framework model models paper article theory practice
practices application applications overview comparison comparative examining examination assessment
estudo estudos análise analise pesquisa revisão revisao abordagem abordagens caso casos uso usando
baseado novo nova efeito efeitos papel desenvolvimento avaliação avaliacao investigação investigacao
compreensão compreensao perspectiva perspectivas modelo modelos artigo teoria prática pratica práticas
praticas aplicação aplicacao aplicações aplicaciones visão visao comparação comparacao
estudio estudios análisis investigación revisión enfoque enfoques nuevo nueva efecto efectos papel
desarrollo evaluación evaluacion perspectiva marco teoría teoria práctica prácticas aplicación
"""


def _conjunto(texto: str) -> frozenset[str]:
    return frozenset(texto.split())


PALAVRAS_VAZIAS = _conjunto(_PT) | _conjunto(_ES) | _conjunto(_EN)
PALAVRAS_ACADEMICAS = _conjunto(_ACADEMICAS)

_PALAVRA = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)


def _normaliza(palavra: str) -> str:
    return sem_acentos(palavra).lower()


_VAZIAS_SEM_ACENTO = frozenset(_normaliza(p) for p in PALAVRAS_VAZIAS)
_ACADEMICAS_SEM_ACENTO = frozenset(_normaliza(p) for p in PALAVRAS_ACADEMICAS)


def quebra_titulo(titulo: str, tirar_academicas: bool = True,
                  ocultar: frozenset[str] = frozenset()) -> list[str | None]:
    """Palavras do título; `None` marca onde havia uma palavra descartada.

    O marcador impede que duas palavras separadas por um artigo virem uma
    expressão ("teaching of statistics" não vira "teaching statistics").
    """
    saida: list[str | None] = []
    for palavra in _PALAVRA.findall(titulo or ""):
        palavra = re.sub(r"['’]s$", "", palavra)
        base = _normaliza(palavra.replace("’", "'"))
        if (len(base) < 3 or base in _VAZIAS_SEM_ACENTO or base in ocultar
                or (tirar_academicas and base in _ACADEMICAS_SEM_ACENTO)):
            saida.append(None)
        else:
            saida.append(palavra.lower())
    return saida


def _unifica(contagem: Counter) -> Counter:
    """Une singular/plural e acento, mantendo a grafia mais frequente."""
    baldes: dict[str, list[str]] = defaultdict(list)
    for termo in contagem:
        baldes[_normaliza(termo)[:4]].append(termo)
    destino: dict[str, str] = {}
    for termos in baldes.values():
        termos.sort(key=lambda t: (-contagem[t], t))
        representantes: list[str] = []
        for termo in termos:
            for representante in representantes:
                if mesmo_termo(termo.upper(), representante.upper()):
                    destino[termo] = representante
                    break
            else:
                representantes.append(termo)
                destino[termo] = termo
    resultado: Counter = Counter()
    for termo, vezes in contagem.items():
        resultado[destino[termo]] += vezes
    return resultado


def termos_dos_titulos(titulos: list[str], tirar_academicas: bool = True,
                       ocultar: list[str] | tuple[str, ...] = (),
                       minimo_expressao: int = 2) -> dict:
    """Contagem de palavras e de expressões de duas palavras nos títulos.

    A contagem é de documentos: cada termo vale 1 por título, por mais que se
    repita nele.
    """
    ocultos = frozenset(_normaliza(o) for o in ocultar if o and o.strip())
    palavras: Counter = Counter()
    expressoes: Counter = Counter()
    for titulo in titulos:
        pedacos = quebra_titulo(titulo, tirar_academicas, ocultos)
        presentes = {p for p in pedacos if p}
        palavras.update(presentes)
        pares = {f"{a} {b}" for a, b in zip(pedacos, pedacos[1:]) if a and b}
        expressoes.update(pares)
    palavras = _unifica(palavras)
    expressoes = Counter({k: v for k, v in expressoes.items() if v >= minimo_expressao})
    return {"palavras": palavras, "expressoes": expressoes}


def ordena(contagem: Counter, limite: int) -> list[tuple[str, int]]:
    return sorted(contagem.items(), key=lambda par: (-par[1], par[0]))[:limite]


_SQL_PALAVRAS_AUTOR = (
    "SELECT dw.Document_idDocument, COALESCE(g.groupName, w.wordName) "
    "FROM Document_Word dw JOIN Word w ON w.idWord = dw.Word_idWord "
    "LEFT JOIN WordGroup g ON g.idWordGroup = w.WordGroup_idWordGroup "
    "WHERE dw.isAuthorWord = 1 AND COALESCE(g.stopGroup, 0) = 0")


def _rotulo_legivel(nome: str) -> str:
    """Palavra-chave guardada como `STATISTICS-EDUCATION` vira `statistics education`."""
    return nome.replace("-", " ").lower()


def nuvem_dados(conexao, fonte: str = "palavras", ocultar=(), limite: int = 70,
                tirar_academicas: bool = True, expressoes: bool = False) -> dict:
    """Termos da nuvem: palavras-chave dos autores ou palavras dos títulos."""
    ocultos = {_normaliza(o) for o in ocultar if o and o.strip()}
    if fonte == "palavras":
        por_termo: Counter = Counter()
        for _, nome in set(conexao.execute(_SQL_PALAVRAS_AUTOR)):
            legivel = _rotulo_legivel(nome or "")
            if legivel and _normaliza(legivel) not in ocultos:
                por_termo[legivel] += 1
        termos = ordena(por_termo, limite)
        total = len(por_termo)
        extras: list = []
    elif fonte == "titulos":
        titulos = [linha[0] for linha in conexao.execute("SELECT title FROM Document") if linha[0]]
        contagens = termos_dos_titulos(titulos, tirar_academicas, tuple(ocultos))
        alvo = contagens["expressoes"] if expressoes else contagens["palavras"]
        termos = ordena(alvo, limite)
        total = len(alvo)
        extras = ordena(contagens["expressoes"], 15) if not expressoes else []
    else:
        raise ValueError("fonte da nuvem desconhecida: use palavras ou titulos")
    return {"fonte": fonte, "termos": [{"termo": t, "documentos": v} for t, v in termos],
            "distintos": total, "expressoes": [{"termo": t, "documentos": v} for t, v in extras]}

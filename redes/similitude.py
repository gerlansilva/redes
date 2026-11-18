"""Análise de similitude dos resumos.

Mostra, num grafo, quais palavras dos resumos aparecem juntas. Passos:

1. **Texto.** Resumos do projeto (opcionalmente de um período), sem rótulos de
   direitos autorais. O **idioma é detectado por resumo** (en, pt, es) por
   palavras funcionais e caracteres; frases claramente de outro idioma (resumos
   bilíngues) ficam de fora. Palavras vazias e palavras genéricas de resumo
   ("objetivo", "results", "resultados") saem nos três idiomas.
2. **Lematização leve**, sem rede nem bibliotecas externas: plural e gênero,
   particípios, gerúndios e algumas formas verbais (-ar/-er/-ir), advérbios em
   -mente/-ly, -ção/-ções, -dade/-dad. Formas de **idiomas diferentes não se
   fundem**. Conservadora: só une quando a forma mais simples aparece no corpus.
3. **Formas ativas**: as ``n_formas`` mais frequentes (em segmentos). Com vários
   idiomas, cada idioma recebe uma cota proporcional ao seu número de resumos.
4. **Coocorrência** em segmentos (o resumo inteiro ou grupos de frases) e um
   **índice** de associação: Jaccard (padrão), cosseno, binomial ou coocorrência.
5. **Árvore máxima** (Kruskal, empate decidido pelo nome da forma): só os laços
   mais fortes que mantêm tudo conectado; mais uma proporção de **arestas extras**
   (as mais fortes fora da árvore, tracejadas) só para legibilidade.
6. **Comunidades** pelo método de Louvain sobre a árvore, com semente fixa.

Tudo é determinístico: a mesma entrada dá o mesmo grafo.
"""
from __future__ import annotations

import csv
import io
import math
import re
import sqlite3
from collections import Counter, defaultdict

import networkx as nx
import numpy as np

from . import termos
from .rotulos import _COPYRIGHT, PALAVRAS_DE_RESUMO
from .text_utils import sem_acentos

IDIOMAS = ("en", "pt", "es")
NOME_IDIOMA = {"en": "inglês", "pt": "português", "es": "espanhol"}
SIGLA_IDIOMA = {"en": "EN", "pt": "PT", "es": "ES"}

N_FORMAS = 60
LIMITE_N_FORMAS = (30, 100)
INDICES = ("jaccard", "cosseno", "binomial", "cooc")
INDICE_PADRAO = "jaccard"
NOME_INDICE = {"jaccard": "Jaccard", "cosseno": "cosseno (Salton)",
               "binomial": "binomial (hipergeométrica)", "cooc": "coocorrência"}
SEGMENTOS = ("resumo", "frase")
NOME_SEGMENTO = {"resumo": "resumo inteiro", "frase": "grupos de frases"}
EXTRAS_PADRAO = 20            # % de arestas extras sobre (formas - 1)
LIMITE_EXTRAS = (0, 50)
MINIMO_PALAVRAS = 15          # resumos mais curtos que isto não entram
MINIMO_DF = 3                 # a forma precisa aparecer em ao menos 3 segmentos
MINIMO_DF_POUCOS = 2          # ... ou 2, quando o idioma tem menos de 12 segmentos
MINIMO_RESUMOS_IDIOMA = 5     # idioma com menos resumos não forma blocos
COTA_MINIMA_IDIOMA = 10       # formas garantidas a cada idioma (modo "todos")
FORMAS_POR_SEGMENTO = 14      # tamanho alvo (formas) de um segmento no modo "frase"
SEMENTE = 7
RESOLUCAO = 1.0
LIMITE_IGNORAR = 200

TITULO = "Análise de similitude dos resumos"
NOTA = (
    "Como ler: cada ponto é uma palavra (já reduzida à forma básica: plural, gênero e "
    "conjugações unidos) que aparece em muitos resumos; quanto maior o ponto, em mais "
    "resumos ela aparece. A linha cheia liga palavras que costumam aparecer juntas: é a "
    "árvore máxima, que guarda só os laços mais fortes necessários para manter tudo "
    "conectado, e quanto mais grossa a linha, mais forte o laço. As linhas tracejadas são "
    "laços extras, um pouco mais fracos, mostrados apenas para facilitar a leitura. As cores "
    "e as manchas marcam blocos temáticos (comunidades de palavras, pelo método de Louvain): "
    "palavras do mesmo bloco costumam ser usadas juntas. A posição na página é só para "
    "desenhar sem sobreposição; o que vale é quem está ligado a quem e a qual bloco pertence. "
    "Palavras de idiomas diferentes nunca se juntam: um resumo é lido no seu próprio idioma, "
    "detectado automaticamente. A tabela traz a frequência, o bloco e o grau de cada palavra.")

MENSAGEM_SEM_RESUMOS = (
    "Este projeto não tem resumos (ou eles são curtos demais) para a análise de similitude. "
    "Importe uma base com resumos, como o Scopus, o Web of Science ou o OpenAlex.")


class SemResumos(ValueError):
    """Não há texto suficiente para a análise (a mensagem serve para a tela)."""


# ============================================================ palavras vazias

_EXTRA_EN = """whether while whereas although though however therefore thus hence since because upon toward towards
being become becomes became get gets got make makes made making take takes took taking give gives given
well often even still yet rather quite less least much most many various several certain
first second third one two three four five six seven eight nine ten
found find finds show shows showed shown suggest suggests suggested indicate indicates indicated
report reports reported reporting identify identified identifies conducted conduct conducts
examine examined examines explore explored explores investigate investigated investigates
compare compared compares comparing include included includes including
paper article authors author present presents presented presenting
using used uses use based whereby among amongst across within without
may might could would should must also per via
participants participant sample samples
significant significantly
focus focused support supported work works worked need needs needed level levels process processes years year help helps helped
improve improved improving improvement implications implication context contexts experience experiences develop developed developing
development provide provides provided role roles result results resulting aim aims purpose approach approaches
important importance understanding understand effect effects impact impacts increase increased factor factors related relation
relationship relationships different difference differences general ability abilities potential current recent high higher low
time way ways case cases part new number type types control group groups key main specific particular
previous final required implemented address involving consider revealed evaluate evaluated assess assessed assessing
discuss discussed discusses highlight highlights highlighted challenge challenges
abstract introduction background objective objectives method methods methodology conclusion conclusions finding findings
research study studies analysis analyses review reviews theory theoretical
analyze analyzed analyzes analyzing analyse analysed analyses analysing propose proposed proposes proposing
describe described describes describing argue argued argues reveal reveals revealed allow allowed allows tend tends
tended seem seems seemed several often overall like lower greater further total large small out""".split()

_EXTRA_PT = """eu tu ele ela nós vós eles elas você vocês me te lhe lhes si mim ti consigo comigo contigo conosco
nosso nossa nossos nossas meu minha meus minhas teu tua seu sua seus suas dele dela deles delas
disso disto daquilo nisso nesse nessa nesses nessas neste nesta nestes nestas nele nela neles nelas
desse dessa desses dessas deste desta destes destas daquele daquela daqueles daquelas
pelo pela pelos pelas num numa nuns numas ao aos
ser sou és somos sido sendo eram fui foram fora seja sejam seria seriam será serão
estar estou estamos estava estavam esteve estiveram estando estado estejam
ter tenho temos tinha tinham teve tiveram tendo tido tenha tenham terá terão
haver havia houve haja houver hão ir vou vai vamos vão ia iam fosse fossem indo ido
poder podia podiam poderia poderiam possa possam puder pôde
dever devia deveria deva devam fazer faz fazem fez fizeram feito fazendo ver viu visto vir vem vêm veio vieram
porém contudo todavia entretanto portanto logo porquanto embora conforme segundo enquanto quanto quanta quantos quantas
cujo cuja cujos cujas sim já ainda também apenas somente outro outra outros outras cada tudo nada algo alguém
algum alguma alguns algumas nenhum nenhuma ninguém qualquer quaisquer vários várias bastante demais
tão tanto tanta aqui ali lá aí cá agora hoje ontem jamais perante trás através diante ante mediante via
um dois duas três quatro cinco seis sete oito nove dez primeiro primeira segunda terceiro terceira
mal bem melhor pior tal tais próprio própria próprios próprias
""".split()

_EXTRA_ES = """yo tú él ella nosotros nosotras vosotros vosotras ellos ellas usted ustedes me te le les nos os
mí ti sí consigo conmigo contigo mío mía míos mías tuyo tuya suyo suya nuestro nuestra nuestros nuestras
vuestro vuestra mis tus esto eso aquello estos estas esos esas aquel aquella aquellos aquellas
ser soy eres somos sois sido siendo era eran fui fueron fuera sea sean sería serían será serán
estar estoy estás estamos estaba estaban estuvo estuvieron estando estado estén
tener tengo tienes tenemos tenía tenían tuvo tuvieron teniendo tenido tenga tengan tendrá tendrán
haber hay había hubo haya habrá han hemos ha he has
ir voy vas va vamos van iba iban fuese fuesen
poder podía podían podría podrían pueda puedan pudo
deber debía debería deba deban hacer hace hacen hizo hicieron hecho haciendo ver vio visto venir viene vienen vino
pero sino aunque mientras conforme según cuyo cuya cuyos cuyas sí ya aún aun solo sólo solamente
otro otra otros otras cada todo nada algo alguien algún alguno alguna algunos algunas ningún ninguno ninguna
nadie cualquier cualesquiera varios varias bastante demasiado tan tanto tanta aquí ahí allí allá ahora hoy
ayer jamás ante bajo tras mediante vía durante
uno dos tres cuatro cinco seis siete ocho nueve diez primero primera segundo segunda tercero tercera
mal bien mejor peor tal tales propio propia propios propias
""".split()

# Palavras de resumo que não dizem sobre o que é o estudo (além de `rotulos.PALAVRAS_DE_RESUMO`).
_GENERICAS_PT = """estudo estudos pesquisa pesquisas objetivo objetivos objetiva resultado resultados conclusão conclusões
conclui concluiu concluem método métodos metodologia metodologias artigo artigos trabalho trabalhos texto textos
análise análises analisar analisa analisam analisou analisaram analisando discute discutir discutem discutiu discutimos
discussão apresenta apresentar apresentam apresentou apresentamos aborda abordar abordam abordagem abordagens
busca buscou buscar buscamos investiga investigar investigou investigamos proposta propostas propõe propor propomos
propôs descreve descrever descrevem descreveu relata relatar relatam relato mostra mostrar mostram mostrou revela
revelam revelou indica indicam indicou evidencia evidenciam evidenciou possui possuem forma formas parte partes tipo
tipos caso casos meio base baseado baseada baseados baseadas diferentes diferente diversos diversas importante
importantes principal principais seguinte seguintes além fim finalidade tema temas questão questões contexto contextos
aspecto aspectos elemento elementos número números novo nova novos novas geral gerais específico específicos específica
uso usos usar utiliza utilizar utilizando utilizado utilizada utilizou utilizam realizado realizada realizou realizar
realizamos verificou verificar identificar identificou identificamos considerando considera contribuir contribui
contribuição contribuições permite permitem permitir possibilita possibilitar visa visando resumo palavras-chave
introdução desenvolvimento desenvolvido desenvolvida desenvolver partir podem sendo através
analisamos discutimos apresentamos investigamos descrevemos relatamos propomos propusemos defendemos sugerimos
constatamos identificamos observamos verificamos buscamos demonstrar demonstrou demonstraram demonstram aponta apontam
apontou sugere sugerem sugeriu defende argumenta argumentamos constata constatou observa observou destaca destacam
destacou apoiado apoiados apoiada apoiadas mostraram indicaram revelou revelaram conduzida conduzido
autor autora autores autoras apresentado apresentados apresentada apresentadas""".split()

_GENERICAS_ES = """estudio estudios investigación investigaciones objetivo objetivos resultado resultados conclusión conclusiones
concluye concluyó método métodos metodología metodologías artículo artículos trabajo trabajos texto textos
análisis analizar analiza analizan analizó analizaron analizando discute discutir discuten discutió discusión
presenta presentar presentan presentó aborda abordar abordan abordaje enfoque enfoques busca buscó buscar buscamos
investiga investigar investigó propuesta propuestas propone proponer proponemos propuso describe describir describen
describió relata relato muestra mostrar muestran mostró revela revelan reveló indica indican indicó evidencia
evidencian evidenció posee poseen forma formas parte partes tipo tipos caso casos medio base basado basada basados
basadas diferentes diferente diversos diversas importante importantes principal principales siguiente siguientes además
fin finalidad tema temas cuestión cuestiones contexto contextos aspecto aspectos elemento elementos número números nuevo
nueva nuevos nuevas general generales específico específicos específica uso usos usar utiliza utilizar utilizando
utilizado utilizada utilizó utilizan realizado realizada realizó realizar realizamos verificó verificar identificar
identificó identificamos considerando considera contribuir contribuye contribución contribuciones permite permiten
permitir posibilita posibilitar resumen palabras-clave introducción desarrollo desarrollado desarrollar partir
puede pueden siendo través
analizamos discutimos presentamos investigamos describimos relatamos proponemos defendemos sugerimos constatamos
identificamos observamos verificamos buscamos demostrar demostró demostraron demuestran señala señalan sugiere sugieren
sugirió defiende argumenta argumentamos constata constató observa observó destaca destacan destacó apoyado apoyados
apoyada apoyadas mostraron indicaron reveló revelaron realizaron
autor autora autores autoras presentado presentados presentada presentadas""".split()


def _normaliza(palavra: str) -> str:
    return sem_acentos(palavra).lower()


def _conj(*listas) -> frozenset[str]:
    saida: set[str] = set()
    for lista in listas:
        saida.update(_normaliza(p) for p in lista)
    return frozenset(saida)


VAZIAS = {
    "en": _conj(termos._EN.split(), _EXTRA_EN),
    "pt": _conj(termos._PT.split(), _EXTRA_PT, _GENERICAS_PT),
    "es": _conj(termos._ES.split(), _EXTRA_ES, _GENERICAS_ES),
}
_GERAIS = frozenset(termos._ACADEMICAS_SEM_ACENTO) | PALAVRAS_DE_RESUMO


# ====================================================== detecção de idioma

_MARCADORES = {
    "en": """the of and in to with that this for was were are is on by as from which these their has have been be an or
        not it its at than between among also into over under both such more most only our we they who can may will
        would could should those there when where while after before during through about against within without no""",
    "pt": """o a os as um uma uns umas de do da dos das em no na nos nas num numa por para pelo pela pelos pelas com sem
        sob sobre entre até ao aos à às e ou mas se que não nao como mais muito também ainda já só foi são sao é está
        estão ser tem têm há seu sua seus suas ele ela eles elas isso essa esse este esta neste nesta quando então
        onde cujo seja sendo pois porém além através dele dela""",
    "es": """el la los las un una unos unas de del en con por para sin sobre entre hasta desde al y u pero si que no se
        lo le les su sus más muy también ya fue son es está están ser hay como cuando donde entonces eso esa ese este
        esta además través cuyo sea siendo pues aunque según""",
}
_PESO_MARCADOR: dict[str, dict[str, float]] = {l: {} for l in IDIOMAS}
for _l, _txt in _MARCADORES.items():
    for _w in _txt.split():
        _k = _normaliza(_w)
        _donos = [l for l in IDIOMAS if _k in {_normaliza(x) for x in _MARCADORES[l].split()}]
        _PESO_MARCADOR[_l][_k] = 1.0 / len(_donos)

_SUFIXOS = {
    "pt": (("ção", "ções", "ões", "ão", "mente"), 2.0),
    "es": (("ción", "ciones", "sión", "ía", "ñ"), 2.0),
    "en": (("tion", "tions", "ing", "ness", "ity", "ies", "ed"), 1.0),
}
_CARACTERES = {"pt": "ãõç", "es": "ñ¿¡"}


def pontua_idiomas(palavras: list[str]) -> dict[str, float]:
    """Pontos de cada idioma para uma lista de palavras (minúsculas, com acento).

    Palavras funcionais valem 1 (ou 1/2 quando existem em dois idiomas, como "de");
    caracteres exclusivos (ã, õ, ç; ñ, ¿, ¡) e terminações típicas (-ção, -ción, -tion,
    -ing) valem 2 ou 1.
    """
    pontos = {l: 0.0 for l in IDIOMAS}
    for p in palavras:
        k = _normaliza(p)
        for l in IDIOMAS:
            pontos[l] += _PESO_MARCADOR[l].get(k, 0.0)
        for l, letras in _CARACTERES.items():
            if any(c in p for c in letras):
                pontos[l] += 2.0
        if len(p) < 4:
            continue
        for l, (sufixos, peso) in _SUFIXOS.items():
            if p.endswith(sufixos) and not (l == "en" and p.endswith("ed") and len(p) < 6):
                pontos[l] += peso * 0.5
    return pontos


def _decide(pontos: dict[str, float], minimo: float = 2.0, razao: float = 1.2) -> str | None:
    ordem = sorted(IDIOMAS, key=lambda l: (-pontos[l], IDIOMAS.index(l)))
    melhor, segundo = ordem[0], ordem[1]
    if pontos[melhor] < minimo or pontos[melhor] <= pontos[segundo] * razao:
        return None
    return melhor


def detecta_idioma(texto: str | list[str]) -> str:
    """Idioma do texto: ``"en"``, ``"pt"`` ou ``"es"`` (``"en"`` quando não dá para decidir)."""
    palavras = texto if isinstance(texto, list) else [p.lower() for p in termos._PALAVRA.findall(texto or "")]
    pontos = pontua_idiomas(palavras)
    decidido = _decide(pontos, 1.0)
    if decidido:
        return decidido
    # empate ou pouca evidência: o de mais pontos; sem nenhum, inglês
    ordem = sorted(IDIOMAS, key=lambda l: (-pontos[l], IDIOMAS.index(l)))
    return ordem[0] if pontos[ordem[0]] > 0 else "en"


# ============================================================== lematização

_IRREGULARES = {
    "en": {"children": "child", "people": "person", "men": "man", "women": "woman", "analyses": "analysis",
           "hypotheses": "hypothesis", "criteria": "criterion", "phenomena": "phenomenon", "media": "medium",
           "indices": "index", "matrices": "matrix", "data": "data", "taught": "teach", "thought": "think",
           "statistical": "statistics", "mathematical": "mathematics", "probabilistic": "probability",
           "statistic": "statistics"},
    "pt": {"estatistico": "estatística", "matematico": "matemática", "probabilistico": "probabilidade",
           "meses": "mês", "paises": "país"},
    "es": {"estadistico": "estadística", "matematico": "matemática", "probabilistico": "probabilidad",
           "redes": "red", "meses": "mes", "paises": "país", "matrices": "matriz"},
}
_PROTEGIDAS_EN = frozenset("""bias focus status series species physics this has was does lens gas alias canvas atlas
news analysis basis thesis hypothesis emphasis synthesis diagnosis crisis class process access success progress
business consensus stimulus virus campus bonus census always perhaps across plus thus""".split())
_VOGAIS = "aeiouáéíóúâêôãõàü"


def _singular_en(w: str) -> str:
    if len(w) <= 3 or w in _PROTEGIDAS_EN or w.endswith(("ss", "us", "is", "ics")):
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("sses", "xes", "ches", "shes", "zzes")):
        return w[:-2]
    if w.endswith("s") and not w.endswith("'s"):
        return w[:-1]
    return w


def _singular_pt(w: str) -> str:
    if len(w) < 4 or w.endswith("mos"):
        return w
    if re.search(r"[çc][õo]es$", w):
        return w[:-4] + "ção"
    if len(w) > 5 and re.search(r"[õo]es$", w):
        return w[:-3] + "ão"
    if len(w) > 5 and re.search(r"[ãa]es$", w):
        return w[:-3] + "ão"
    if w.endswith("ãos"):
        return w[:-1]
    if w.endswith(("úteis", "uteis")):
        return w[:-5] + "útil"
    if len(w) > 5 and re.search(r"ceis$", w):
        return w[:-4] + "cil"
    if len(w) > 4 and w.endswith("ais"):
        return w[:-3] + "al"
    if len(w) > 5 and re.search(r"[eé]is$", w):
        return w[:-3] + "el"
    if len(w) > 4 and w.endswith("ns"):
        return w[:-2] + "m"
    if len(w) > 7 and w.endswith("eses"):
        return w[:-4] + "ês"
    if w.endswith("íses"):
        return w[:-4] + "ís"
    if re.search(r"[aeiouáéíóúâêôãõ][rz]es$", w) and len(w) > 4:
        return w[:-2]
    if w.endswith(("ois", "uis")):
        return w[:-1]
    if w.endswith("s") and len(w) > 3 and w[-2] in _VOGAIS and not w.endswith(("is", "us", "ás", "és", "ís", "ós", "ús")):
        return w[:-1]
    return w


def _singular_es(w: str) -> str:
    if len(w) < 4 or w.endswith("mos"):
        return w
    if re.search(r"(á|a)genes$", w):
        return w[:-6] + "agen"
    if re.search(r"(í|i)genes$", w):
        return w[:-6] + "igen"
    if len(w) > 5 and w.endswith("ones"):
        return w[:-4] + "ón"
    if w.endswith("ades") or w.endswith("udes"):
        return w[:-2]
    if w.endswith("yes") and len(w) > 4:
        return w[:-2]
    if re.search(r"[aeiouáéíóú]ces$", w) and not w.endswith("ices"):
        return w[:-3] + "z"
    if w.endswith("ices"):
        return w[:-1]
    if re.search(r"bles$", w):
        return w[:-1]
    if re.search(r"[aeiouáéíóú][lr]es$", w) and len(w) > 4:
        return w[:-2]
    if re.search(r"[aeiouáéíóú]nes$", w) and len(w) > 4:
        return sem_acentos(w[:-2])
    if w.endswith("íses"):
        return w[:-4] + "ís"
    if w.endswith("s") and len(w) > 3 and w[-2] in _VOGAIS and not w.endswith(("is", "us", "ás", "és", "ís", "ós", "ús")):
        return w[:-1]
    return w


_SINGULAR = {"en": _singular_en, "pt": _singular_pt, "es": _singular_es}


def singulariza(palavra: str, idioma: str) -> str:
    """Forma singular (regras conservadoras, sem vocabulário), mantendo os acentos que couberem."""
    w = palavra.lower()
    irregulares = _IRREGULARES.get(idioma, {})
    if _normaliza(w) in irregulares:
        return irregulares[_normaliza(w)]
    s = _SINGULAR[idioma](w)
    return irregulares.get(_normaliza(s), s)


def _irreg(idioma: str, chave: str) -> str | None:
    destino = _IRREGULARES.get(idioma, {}).get(chave)
    return _normaliza(destino) if destino else None


def _verbos_romance(chave: str, idioma: str) -> list[tuple[str, bool]]:
    """Infinitivos possíveis (chave, forte) para particípio, gerúndio e 3ª pessoa do plural/pretérito.

    "forte" (gerúndio e particípio em -ado) aceita o infinitivo mesmo que ele não apareça no corpus,
    desde que duas formas diferentes apontem para ele; as demais só valem se o infinitivo existir.
    """
    n = len(chave)
    c: list[tuple[str, bool]] = []
    if n < 6:
        return c
    pt = idioma == "pt"
    if chave.endswith("ando"):
        c.append((chave[:-4] + "ar", True))
    if pt and chave.endswith("endo"):
        c.append((chave[:-4] + "er", True))
    if pt and chave.endswith("indo"):
        c.append((chave[:-4] + "ir", True))
    if not pt and chave.endswith("iendo"):
        c += [(chave[:-5] + "er", True), (chave[:-5] + "ir", True)]
    if not pt and chave.endswith("yendo"):
        c.append((chave[:-5] + "ir", True))
    if chave.endswith(("ado", "ada")):
        c.append((chave[:-3] + "ar", True))
    if chave.endswith(("ido", "ida")):
        c += [(chave[:-3] + "er", False), (chave[:-3] + "ir", False)]
    if pt:
        if chave.endswith("aram"):
            c.append((chave[:-4] + "ar", False))
        elif chave.endswith("am"):
            c.append((chave[:-2] + "ar", False))
        if chave.endswith("ou"):
            c.append((chave[:-2] + "ar", False))
        if chave.endswith(("eu", "iu")):
            c += [(chave[:-2] + "er", False), (chave[:-2] + "ir", False)]
        if chave.endswith("em") and not chave.endswith("gem"):
            c += [(chave[:-2] + "er", False), (chave[:-2] + "ir", False)]
    else:
        if chave.endswith("aron"):
            c.append((chave[:-4] + "ar", False))
        elif chave.endswith("an"):
            c.append((chave[:-2] + "ar", False))
        if chave.endswith("ieron"):
            c += [(chave[:-5] + "er", False), (chave[:-5] + "ir", False)]
        elif chave.endswith("en") and not chave.endswith(("gen", "men")):
            c += [(chave[:-2] + "er", False), (chave[:-2] + "ir", False)]
    return c


def _verbos_en(chave: str) -> list[tuple[str, bool]]:
    n = len(chave)
    c: list[tuple[str, bool]] = []
    if chave.endswith("ing") and n > 5:
        stem = chave[:-3]
        c += [(stem, False), (stem + "e", False)]
        if len(stem) > 2 and stem[-1] == stem[-2]:
            c.append((stem[:-1], False))
    if chave.endswith("ied") and n > 5:
        c.append((chave[:-3] + "y", False))
    if chave.endswith("ed") and n > 4:
        stem = chave[:-2]
        c += [(stem, False), (chave[:-1], False)]
        if len(stem) > 2 and stem[-1] == stem[-2]:
            c.append((stem[:-1], False))
    if chave.endswith(("ization", "isation")) and n > 8:
        c.append((chave[:-7] + "e", False))
    return c


def _adverbios(chave: str, idioma: str) -> list[tuple[str, bool]]:
    c: list[tuple[str, bool]] = []
    if idioma == "en":
        if chave.endswith("ally") and len(chave) > 7:
            c += [(chave[:-2], False), (chave[:-4], False)]
        elif chave.endswith("ily") and len(chave) > 6:
            c.append((chave[:-3] + "y", False))
        elif chave.endswith("ly") and len(chave) > 5:
            c.append((chave[:-2], False))
        return c
    if chave.endswith("mente") and len(chave) > 8:
        base = chave[:-5]
        if base.endswith("a"):
            c.append((base[:-1] + "o", False))
        c.append((base, False))
    return c


_PARES_GENERO = (("osa", "oso"), ("iva", "ivo"), ("ana", "ano"), ("una", "uno"), ("eira", "eiro"),
                 ("uda", "udo"), ("ora", "or"),
                 ("ada", "ado"), ("ida", "ido"), ("mna", "mno"))


def _genero(chave: str) -> list[tuple[str, bool]]:
    if len(chave) < 5:
        return []
    return [(chave[:-len(f)] + m, False) for f, m in _PARES_GENERO if chave.endswith(f)]


def _etapa(contagem: Counter, gera, razao: float = 0.0) -> dict[str, str]:
    """Une cada chave a um candidato que existe no corpus (ou apontado por 2+ formas fortes)."""
    propostas = {k: gera(k) for k in contagem}
    suporte: dict[str, set[str]] = defaultdict(set)
    for k, lista in propostas.items():
        for ck, forte in lista:
            if forte:
                suporte[ck].add(k)
    destino: dict[str, str] = {}
    for k in sorted(contagem):
        escolha = None
        for ck, _ in propostas[k]:
            if ck != k and len(ck) >= 4 and ck in contagem and contagem[ck] >= razao * contagem[k]:
                escolha = ck
                break
        if escolha is None:
            for ck, forte in propostas[k]:
                if forte and ck != k and len(ck) >= 5 and ck not in contagem and len(suporte[ck]) >= 2:
                    escolha = ck
                    break
        if escolha is not None:
            destino[k] = escolha
    return destino


def _lemas_do_idioma(idioma: str, vocab: Counter, rep: dict[str, str], nivel: int = 2) -> dict[str, tuple[str, str]]:
    """chave da palavra -> (chave do lema, grafia do lema) para um idioma."""
    # 1) plural e irregulares
    k1: dict[str, str] = {}
    exib_gerada: dict[str, str] = {}
    for k in vocab:
        s = singulariza(rep[k], idioma) if nivel >= 1 else rep[k]
        ks = _normaliza(s)
        k1[k] = ks
        exib_gerada.setdefault(ks, s)
    c1: Counter = Counter()
    for k, n in vocab.items():
        c1[k1[k]] += n
    atual = {k: k1[k] for k in vocab}
    if nivel >= 2:
        if idioma == "en":
            etapas = [(lambda k: [(_irreg(idioma, ck) or ck, f) for ck, f in _verbos_en(k)], 0.3),
                      (lambda k: [(_irreg(idioma, ck) or ck, f) for ck, f in _adverbios(k, idioma)], 0.0)]
        else:
            etapas = [(lambda k: _verbos_romance(k, idioma), 0.0),
                      (lambda k: [(_irreg(idioma, ck) or ck, f) for ck, f in _adverbios(k, idioma)], 0.0),
                      (_genero, 0.0)]
        for gera, razao in etapas:
            destino = _etapa(c1, gera, razao)
            if not destino:
                continue
            novo: Counter = Counter()
            for k, n in c1.items():
                novo[destino.get(k, k)] += n
            for k in atual:
                atual[k] = destino.get(atual[k], atual[k])
            for ck in destino.values():
                exib_gerada.setdefault(ck, ck)
            c1 = novo
    # grafia do lema: a do próprio lema se existir no corpus; senão a gerada pelas regras
    saida: dict[str, tuple[str, str]] = {}
    for k in vocab:
        lema = atual[k]
        grafia = rep[lema] if lema in vocab else exib_gerada.get(lema, lema)
        saida[k] = (lema, grafia)
    return saida


def lematiza(palavras: list[str], idioma: str, nivel: int = 2) -> dict[str, str]:
    """Lema (grafia) de cada palavra de uma lista, tratando-a como o vocabulário de um corpus.

    Útil para conferir as regras: ``lematiza(["alunos", "aluna"], "pt")`` -> ``{"alunos": "aluno", ...}``.
    A união por vocabulário só acontece com as formas que a lista traz.
    """
    vocab: Counter = Counter()
    rep: dict[str, str] = {}
    for p in palavras:
        k = _normaliza(p)
        vocab[k] += 1
        rep.setdefault(k, p.lower())
    mapa = _lemas_do_idioma(idioma, vocab, rep, nivel)
    return {p: mapa[_normaliza(p)][1] for p in palavras}


# ============================================================ leitura e prepara

_PLACEHOLDER = re.compile(
    r"\[?\s*(no abstract available|resumo n[aã]o dispon[ií]vel|sin resumen|abstract not available)\s*\]?", re.I)
_FRASES = re.compile(r"(?<=[.?!;:])\s+")


def limpa_resumo(texto: str) -> str:
    return _PLACEHOLDER.sub(" ", _COPYRIGHT.sub("", texto or "")).strip()


def le_resumos(conexao: sqlite3.Connection, periodo_id: int | None = None) -> list[tuple[int, str, str]]:
    """``(id, título, resumo)`` dos documentos com resumo (do período, se pedido)."""
    if periodo_id is None:
        linhas = conexao.execute("SELECT idDocument, title, docAbstract FROM Document ORDER BY idDocument")
    else:
        linhas = conexao.execute(
            "SELECT d.idDocument, d.title, d.docAbstract FROM Document d "
            "JOIN PublishDate_Period pp ON pp.PublishDate_idPublishDate = d.PublishDate_idPublishDate "
            "WHERE pp.Period_idPeriod = ? ORDER BY d.idDocument", (periodo_id,))
    saida = []
    for linha in linhas:
        resumo = limpa_resumo(linha[2])
        if len(resumo.split()) >= MINIMO_PALAVRAS:
            saida.append((linha[0], linha[1] or "", resumo))
    return saida


def _ignorados(ignorar) -> frozenset[str]:
    """Aceita lista ou texto (vírgula, ponto e vírgula ou quebra de linha)."""
    if not ignorar:
        return frozenset()
    if isinstance(ignorar, str):
        ignorar = re.split(r"[,;\n]+", ignorar)
    return frozenset(_normaliza(p.strip().replace("’", "'")) for p in list(ignorar)[:LIMITE_IGNORAR]
                     if p and p.strip())


def analisa_idiomas(texto: str) -> tuple[str, list[tuple[str | None, list[str]]]]:
    """Idioma principal do resumo e, por frase, ``(idioma ou None se incerto, palavras)``."""
    frases_txt = [f for f in _FRASES.split(texto) if f.strip()]
    palavras_frase = [[p.lower().replace("’", "'") for p in termos._PALAVRA.findall(f)] for f in frases_txt]
    principal = detecta_idioma([p for fr in palavras_frase for p in fr])
    frases = []
    for palavras in palavras_frase:
        idi = _decide(pontua_idiomas(palavras), 3.0, 1.6) if len(palavras) >= 6 else None
        frases.append((idi, palavras))
    return principal, frases


def _idioma_do_resumo(principal: str, frases, preferido: str) -> str:
    """Resumo bilíngue: fica a versão no idioma preferido, se ela tiver ao menos 2 frases claras."""
    if preferido != principal and sum(1 for i, _ in frases if i == preferido) >= 2:
        return preferido
    return principal


def tokeniza_frases(frases, idioma: str, ignorar: frozenset[str] = frozenset()):
    """Frases (só as que não são claramente de outro idioma) como listas de ``(chave, grafia)``.

    Devolve ``(frases, descartadas)``.
    """
    vazias = VAZIAS[idioma]
    saida_frases: list[list[tuple[str, str]]] = []
    descartadas = 0
    for idi, palavras in frases:
        if idi and idi != idioma:
            descartadas += 1
            continue
        saida = []
        for p in palavras:
            p = re.sub(r"'s$", "", p)
            k = _normaliza(p)
            if len(k) < 3 or k in vazias or k in ignorar or k in _GERAIS:
                continue
            saida.append((k, p))
        saida_frases.append(saida)
    return saida_frases, descartadas


def tokeniza_resumo(texto: str, ignorar: frozenset[str] = frozenset(), preferido: str | None = None):
    """``(idioma, frases, descartadas)`` de um resumo isolado (atalho para testes e usos simples)."""
    principal, frases = analisa_idiomas(texto)
    idioma = _idioma_do_resumo(principal, frases, preferido or principal)
    saida, desc = tokeniza_frases(frases, idioma, ignorar)
    return idioma, saida, desc


def prepara(documentos: list[tuple[int, str, str]], segmento: str = "resumo", idioma: str = "todos",
            ignorar=(), nivel_lema: int = 2) -> dict:
    """Segmentos de lemas por idioma. Devolve estrutura usada pelas etapas seguintes."""
    ign = _ignorados(ignorar)
    analisados = [(doc_id, *analisa_idiomas(resumo)) for doc_id, _, resumo in documentos]
    if idioma == "todos":
        contagem = Counter(p for _, p, _ in analisados)
        preferido = sorted(IDIOMAS, key=lambda l: (-contagem[l], IDIOMAS.index(l)))[0]
    else:
        preferido = idioma
    lidos = []
    por_idioma_docs: Counter = Counter()
    descartadas = 0
    for doc_id, principal, frases in analisados:
        idi = _idioma_do_resumo(principal, frases, preferido)
        por_idioma_docs[idi] += 1
        if idioma != "todos" and idi != idioma:
            continue
        toks, desc = tokeniza_frases(frases, idi, ign)
        descartadas += desc
        lidos.append((doc_id, idi, toks))
    vocab: dict[str, Counter] = {l: Counter() for l in IDIOMAS}
    grafias: dict[str, dict[str, Counter]] = {l: defaultdict(Counter) for l in IDIOMAS}
    for _, idi, frases in lidos:
        for fr in frases:
            for k, p in fr:
                vocab[idi][k] += 1
                grafias[idi][k][p] += 1
    rep = {l: {k: sorted(g.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for k, g in grafias[l].items()}
           for l in IDIOMAS}
    mapa = {l: _lemas_do_idioma(l, vocab[l], rep[l], nivel_lema) for l in IDIOMAS if vocab[l]}
    segmentos: list[list[str]] = []
    meta: list[tuple[int, str]] = []
    exib: dict[str, Counter] = defaultdict(Counter)
    for doc_id, idi, frases in lidos:
        por_frase = []
        for fr in frases:
            lemas = []
            for k, _ in fr:
                lema, graf = mapa[idi][k]
                if lema in ign or _normaliza(graf) in ign:
                    continue
                no = f"{idi}:{lema}"
                lemas.append(no)
                exib[no][graf] += 1
            if lemas:
                por_frase.append(lemas)
        if not por_frase:
            continue
        if segmento == "resumo":
            segs = [[w for fr in por_frase for w in fr]]
        else:
            segs, atual = [], []
            for fr in por_frase:
                atual += fr
                if len(atual) >= FORMAS_POR_SEGMENTO:
                    segs.append(atual)
                    atual = []
            if atual:
                if segs and len(atual) < 6:
                    segs[-1] += atual
                else:
                    segs.append(atual)
        for s in segs:
            segmentos.append(s)
            meta.append((doc_id, idi))
    rotulo = {no: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for no, c in exib.items()}
    return {"segmentos": segmentos, "meta": meta, "rotulo": rotulo,
            "docs_por_idioma": dict(por_idioma_docs), "frases_descartadas": descartadas,
            "docs_usados": len({m[0] for m in meta}), "docs_lidos": len(documentos)}


# ================================================================== formas

def _cotas(candidatas: dict[str, list], docs: dict[str, int], n: int) -> dict[str, int]:
    """Formas por idioma: mínimo garantido e o resto proporcional aos resumos (restos maiores)."""
    idiomas = [l for l in IDIOMAS if candidatas.get(l)]
    cota = {l: min(COTA_MINIMA_IDIOMA, len(candidatas[l])) for l in idiomas}
    if len(idiomas) == 1:
        return {idiomas[0]: min(n, len(candidatas[idiomas[0]]))}
    while sum(cota.values()) > n:
        cota[max(cota, key=lambda l: (cota[l], IDIOMAS.index(l)))] -= 1
    sobra = n - sum(cota.values())
    while sobra > 0:
        livres = [l for l in idiomas if cota[l] < len(candidatas[l])]
        if not livres:
            break
        total = sum(docs.get(l, 0) for l in livres) or 1
        ideal = {l: sobra * docs.get(l, 0) / total for l in livres}
        dado = 0
        for l in livres:
            q = min(int(ideal[l]), len(candidatas[l]) - cota[l])
            cota[l] += q
            dado += q
        if dado == 0:
            l = max(livres, key=lambda x: (ideal[x] - int(ideal[x]), docs.get(x, 0), -IDIOMAS.index(x)))
            cota[l] += 1
            dado = 1
        sobra -= dado
    return cota


def formas_ativas(prep: dict, n_formas: int = N_FORMAS) -> tuple[list[str], Counter, Counter]:
    """Formas escolhidas (ordem: idioma, frequência) e contagens de segmentos e de ocorrências."""
    df: Counter = Counter()
    freq: Counter = Counter()
    for s in prep["segmentos"]:
        df.update(set(s))
        freq.update(s)
    segs_idioma = Counter(i for _, i in prep["meta"])
    candidatas: dict[str, list] = {l: [] for l in IDIOMAS}
    for no, d in df.items():
        idi = no.split(":", 1)[0]
        minimo = MINIMO_DF if segs_idioma[idi] >= 12 else MINIMO_DF_POUCOS
        if d >= minimo:
            candidatas[idi].append(no)
    for l in IDIOMAS:
        candidatas[l].sort(key=lambda f: (-df[f], -freq[f], f))
    cotas = _cotas(candidatas, Counter(prep["docs_por_idioma"]), n_formas)
    escolhidas = []
    for l in IDIOMAS:
        escolhidas += candidatas[l][:cotas.get(l, 0)]
    escolhidas.sort(key=lambda f: (-df[f], -freq[f], f))
    return escolhidas, df, freq


# ================================================================== índices

def coocorrencia(segmentos: list[list[str]], formas: list[str]) -> np.ndarray:
    idx = {f: k for k, f in enumerate(formas)}
    M = np.zeros((len(segmentos), len(formas)), dtype=np.int32)
    for r, s in enumerate(segmentos):
        for f in set(s):
            if f in idx:
                M[r, idx[f]] = 1
    return M.T @ M


def _log_comb(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def _peso_binomial(c: int, di: int, dj: int, n: int) -> float:
    """-log10 de P(X >= c) para X hipergeométrica (população n, di marcados, amostra dj)."""
    kmax = min(di, dj)
    if c <= 0 or c > kmax or n < max(di, dj):
        return 0.0
    base = _log_comb(n, dj)
    termos_ = []
    for k in range(c, kmax + 1):
        if dj - k < 0 or dj - k > n - di:
            continue
        termos_.append(_log_comb(di, k) + _log_comb(n - di, dj - k) - base)
    if not termos_:
        return 0.0
    m = max(termos_)
    lp = m + math.log(sum(math.exp(t - m) for t in termos_))
    return max(0.0, -lp / math.log(10))


def indice(C: np.ndarray, d: np.ndarray, n_por_forma: np.ndarray, nome: str) -> np.ndarray:
    """Matriz de pesos (diagonal zero) pelo índice pedido."""
    if nome not in INDICES:
        raise ValueError(f"índice desconhecido: {nome}")
    off = C.astype(float).copy()
    np.fill_diagonal(off, 0)
    di = d[:, None].astype(float)
    dj = d[None, :].astype(float)
    if nome == "cooc":
        return off
    if nome == "jaccard":
        W = off / np.maximum(di + dj - off, 1)
    elif nome == "cosseno":
        W = off / np.sqrt(np.maximum(di * dj, 1))
    else:
        m = len(d)
        W = np.zeros((m, m))
        for i in range(m):
            for j in range(i + 1, m):
                if C[i, j] > 0:
                    W[i, j] = W[j, i] = _peso_binomial(int(C[i, j]), int(d[i]), int(d[j]), int(n_por_forma[i]))
    np.fill_diagonal(W, 0)
    return W


# ============================================================ grafo e blocos

def arvore_maxima(G: nx.Graph) -> nx.Graph:
    """Floresta geradora máxima (Kruskal); empates pela ordem dos nomes (determinística)."""
    arestas = sorted(G.edges(data="weight"), key=lambda e: (-e[2], min(e[0], e[1]), max(e[0], e[1])))
    T = nx.Graph()
    T.add_nodes_from(sorted(G.nodes(data=True), key=lambda n: n[0]))
    pai = {n: n for n in G}

    def raiz(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x

    for u, v, w in arestas:
        ru, rv = raiz(u), raiz(v)
        if ru != rv:
            pai[max(ru, rv)] = min(ru, rv)
            T.add_edge(u, v, weight=w)
    return T


def arestas_extras(G: nx.Graph, T: nx.Graph, percentual: int) -> list[tuple[str, str, float]]:
    """As mais fortes fora da árvore: ``percentual``% do número de arestas da árvore."""
    k = int(round(percentual / 100 * max(T.number_of_edges(), 0)))
    if k <= 0:
        return []
    fora = [(min(u, v), max(u, v), w) for u, v, w in G.edges(data="weight") if not T.has_edge(u, v)]
    fora.sort(key=lambda e: (-e[2], e[0], e[1]))
    return fora[:k]


def comunidades(T: nx.Graph, df: Counter) -> dict[str, int]:
    """Louvain sobre a árvore; blocos numerados do maior para o menor (1, 2, ...)."""
    if T.number_of_edges() == 0:
        blocos = [{n} for n in sorted(T.nodes)]
    else:
        blocos = nx.community.louvain_communities(T, weight="weight", resolution=RESOLUCAO, seed=SEMENTE)
    blocos.sort(key=lambda c: (-len(c), -sum(df[n] for n in c), sorted(c)[0]))
    return {n: k + 1 for k, c in enumerate(blocos) for n in c}


def _rotulos_legiveis(nos: list[str], rotulo: dict[str, str], varios_idiomas: bool) -> dict[str, str]:
    """Texto de cada forma; com vários idiomas, repetidos ganham o idioma entre parênteses."""
    base = {n: rotulo.get(n, n.split(":", 1)[1]) for n in nos}
    if not varios_idiomas:
        return base
    por_texto: dict[str, set[str]] = defaultdict(set)
    for n, t in base.items():
        por_texto[_normaliza(t)].add(n.split(":", 1)[0])
    return {n: (f"{t} ({n.split(':', 1)[0]})" if len(por_texto[_normaliza(t)]) > 1 else t) for n, t in base.items()}


def analisa_documentos(documentos: list[tuple[int, str, str]], n_formas: int = N_FORMAS,
                       indice_nome: str = INDICE_PADRAO, segmento: str = "resumo",
                       extras: int = EXTRAS_PADRAO, idioma: str = "todos", ignorar=(),
                       periodo: str = "todos", nivel_lema: int = 2) -> dict:
    """Análise completa a partir de ``(id, título, resumo)``. Levanta `SemResumos` sem texto."""
    if idioma != "todos" and idioma not in IDIOMAS:
        raise ValueError("idioma precisa ser todos, en, pt ou es")
    if indice_nome not in INDICES:
        raise ValueError(f"indice precisa ser um de: {', '.join(INDICES)}")
    if segmento not in SEGMENTOS:
        raise ValueError(f"segmento precisa ser um de: {', '.join(SEGMENTOS)}")
    if not documentos:
        raise SemResumos(MENSAGEM_SEM_RESUMOS)
    prep = prepara(documentos, segmento, idioma, ignorar, nivel_lema)
    avisos: list[str] = []
    docs_idioma = prep["docs_por_idioma"]
    if idioma != "todos":
        if docs_idioma.get(idioma, 0) < MINIMO_RESUMOS_IDIOMA:
            raise SemResumos(
                f"Há só {docs_idioma.get(idioma, 0)} resumo(s) em {NOME_IDIOMA[idioma]}: poucos para a "
                f"análise (mínimo {MINIMO_RESUMOS_IDIOMA}). Escolha \"todos\" ou outro idioma.")
    else:
        pequenos = [l for l in IDIOMAS if 0 < docs_idioma.get(l, 0) < MINIMO_RESUMOS_IDIOMA]
        if pequenos:
            ign = [f"{docs_idioma[l]} em {NOME_IDIOMA[l]}" for l in pequenos]
            avisos.append(f"Idiomas com menos de {MINIMO_RESUMOS_IDIOMA} resumos não formam blocos "
                          f"próprios; esses resumos ficaram de fora ({'; '.join(ign)}).")
            prep = _sem_idiomas(prep, set(pequenos))
    if not prep["segmentos"]:
        raise SemResumos(MENSAGEM_SEM_RESUMOS)
    formas, df, freq = formas_ativas(prep, n_formas)
    if len(formas) < 3:
        raise SemResumos("O vocabulário dos resumos é pequeno demais para o grafo (menos de 3 palavras "
                         "repetidas). Use mais resumos, ou reduza a lista de palavras ignoradas.")
    C = coocorrencia(prep["segmentos"], formas)
    d = np.array([df[f] for f in formas])
    segs_idioma = Counter(i for _, i in prep["meta"])
    n_forma = np.array([segs_idioma[f.split(":", 1)[0]] for f in formas])
    W = indice(C, d, n_forma, indice_nome)
    G = nx.Graph()
    G.add_nodes_from(formas)
    for i in range(len(formas)):
        for j in range(i + 1, len(formas)):
            if W[i, j] > 0:
                G.add_edge(formas[i], formas[j], weight=float(W[i, j]))
    T = arvore_maxima(G)
    ex = arestas_extras(G, T, extras)
    com = comunidades(T, df)
    usados = [l for l in IDIOMAS if any(f.startswith(l + ":") for f in formas)]
    rot = _rotulos_legiveis(formas, prep["rotulo"], len(usados) > 1)
    grau: Counter = Counter()
    for u, v in T.edges:
        grau[u] += 1
        grau[v] += 1
    for u, v, _ in ex:
        grau[u] += 1
        grau[v] += 1
    docs_forma: dict[str, set[int]] = defaultdict(set)
    forma_set = set(formas)
    for s, (doc_id, _) in zip(prep["segmentos"], prep["meta"]):
        for f in set(s) & forma_set:
            docs_forma[f].add(doc_id)
    linhas = [{"id": f, "forma": rot[f], "idioma": f.split(":", 1)[0], "frequencia": df[f],
               "resumos": len(docs_forma[f]), "ocorrencias": freq[f], "comunidade": com[f],
               "grau": grau[f]} for f in formas]
    arestas = [{"origem": u, "destino": v, "peso": w, "tipo": "arvore"} for u, v, w in
               sorted(((min(a, b), max(a, b), w) for a, b, w in T.edges(data="weight")),
                      key=lambda e: (-e[2], e[0], e[1]))]
    arestas += [{"origem": u, "destino": v, "peso": w, "tipo": "extra"} for u, v, w in ex]
    nomes_com = {}
    for k in sorted(set(com.values())):
        mem = sorted((f for f in formas if com[f] == k), key=lambda f: (-df[f], f))
        nomes_com[k] = mem
    comunidades_info = [{"id": k, "n": len(mem), "nome": ", ".join(rot[f] for f in mem[:3]),
                         "idiomas": sorted({f.split(":", 1)[0] for f in mem})} for k, mem in nomes_com.items()]
    componentes = nx.number_connected_components(T)
    if componentes > 1 and len(usados) <= 1:
        avisos.append(f"As palavras escolhidas formam {componentes} grupos desconexos: algumas não "
                      "aparecem junto das demais em nenhum resumo.")
    if prep["frases_descartadas"]:
        avisos.append(f"{prep['frases_descartadas']} frase(s) de resumos bilíngues, em idioma diferente do "
                      "do resumo, foram desconsideradas.")
    return {
        "parametros": {"n_formas": n_formas, "indice": indice_nome, "segmento": segmento, "extras": extras,
                       "idioma": idioma, "periodo": periodo, "ignorar": sorted(_ignorados(ignorar)),
                       "semente": SEMENTE},
        "n_resumos": prep["docs_usados"], "n_lidos": prep["docs_lidos"],
        "n_segmentos": len(prep["segmentos"]),
        "docs_por_idioma": {l: docs_idioma.get(l, 0) for l in IDIOMAS if docs_idioma.get(l)},
        "idiomas_nas_formas": usados,
        "formas": linhas, "arestas": arestas, "comunidades": comunidades_info,
        "n_arvore": T.number_of_edges(), "n_extras": len(ex), "componentes": componentes,
        "avisos": avisos,
    }


def _sem_idiomas(prep: dict, fora: set[str]) -> dict:
    manter = [k for k, (_, i) in enumerate(prep["meta"]) if i not in fora]
    novo = dict(prep)
    novo["segmentos"] = [prep["segmentos"][k] for k in manter]
    novo["meta"] = [prep["meta"][k] for k in manter]
    novo["docs_usados"] = len({m[0] for m in novo["meta"]})
    return novo


def analisa(conexao: sqlite3.Connection, periodo_id: int | None = None, periodo: str = "todos", **kw) -> dict:
    """Lê os resumos do projeto e roda a análise (ver `analisa_documentos`)."""
    return analisa_documentos(le_resumos(conexao, periodo_id), periodo=periodo, **kw)


# ============================================================== exportações

def descreve_parametros(res: dict) -> list[tuple[str, str]]:
    p = res["parametros"]
    idioma = "todos (" + ", ".join(f"{NOME_IDIOMA[l]} {n}" for l, n in res["docs_por_idioma"].items()) + ")" \
        if p["idioma"] == "todos" else NOME_IDIOMA[p["idioma"]]
    itens = [
        ("Resumos usados", f"{res['n_resumos']} de {res['n_lidos']} com resumo; {res['n_segmentos']} segmento(s)"),
        ("Idioma", idioma),
        ("Período", str(p["periodo"])),
        ("Formas ativas", str(len(res["formas"]))),
        ("Índice", NOME_INDICE[p["indice"]]),
        ("Segmento", NOME_SEGMENTO[p["segmento"]]),
        ("Arestas", f"árvore máxima ({res['n_arvore']})" + (f" + {res['n_extras']} extras ({p['extras']}%)"
                                                            if res["n_extras"] else "")),
        ("Blocos", f"{len(res['comunidades'])} (Louvain, semente {p['semente']})"),
    ]
    if p["ignorar"]:
        itens.append(("Palavras ignoradas", ", ".join(p["ignorar"])))
    return itens


def texto_parametros(res: dict) -> str:
    """Uma linha para o rodapé da figura."""
    p = res["parametros"]
    idi = "todos os idiomas" if p["idioma"] == "todos" else NOME_IDIOMA[p["idioma"]]
    return (f"{res['n_resumos']} resumos · {idi} · {len(res['formas'])} palavras · índice: "
            f"{NOME_INDICE[p['indice']]} · segmento: {NOME_SEGMENTO[p['segmento']]} · árvore máxima"
            f"{' + ' + str(p['extras']) + '% de arestas extras' if res['n_extras'] else ''} · "
            f"blocos: Louvain ({len(res['comunidades'])})")


def grafo(res: dict) -> nx.Graph:
    G = nx.Graph()
    for f in res["formas"]:
        G.add_node(f["id"], forma=f["forma"], idioma=f["idioma"], frequencia=f["frequencia"],
                   resumos=f["resumos"], ocorrencias=f["ocorrencias"], comunidade=f["comunidade"], grau=f["grau"])
    for a in res["arestas"]:
        G.add_edge(a["origem"], a["destino"], peso=a["peso"], tipo=a["tipo"])
    return G


def graphml(res: dict) -> str:
    return "\n".join(nx.generate_graphml(grafo(res), named_key_ids=True)) + "\n"


def csv_formas(res: dict) -> str:
    saida = io.StringIO()
    w = csv.writer(saida, lineterminator="\n")
    w.writerow(["forma", "idioma", "frequencia_segmentos", "resumos", "ocorrencias", "bloco", "grau"])
    for f in sorted(res["formas"], key=lambda f: (f["comunidade"], -f["frequencia"], f["forma"])):
        w.writerow([f["forma"], f["idioma"], f["frequencia"], f["resumos"], f["ocorrencias"],
                    f["comunidade"], f["grau"]])
    return "﻿" + saida.getvalue()


def csv_arestas(res: dict) -> str:
    nome = {f["id"]: f["forma"] for f in res["formas"]}
    saida = io.StringIO()
    w = csv.writer(saida, lineterminator="\n")
    w.writerow(["origem", "destino", "peso", "tipo"])
    for a in res["arestas"]:
        w.writerow([nome[a["origem"]], nome[a["destino"]], f"{a['peso']:.6f}",
                    "árvore" if a["tipo"] == "arvore" else "extra"])
    return "﻿" + saida.getvalue()


def aplicavel(conexao: sqlite3.Connection) -> bool:
    """Há ao menos um resumo utilizável?"""
    for (r,) in conexao.execute("SELECT docAbstract FROM Document WHERE docAbstract IS NOT NULL"):
        if len(limpa_resumo(r).split()) >= MINIMO_PALAVRAS:
            return True
    return False

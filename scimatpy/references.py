"""Interpretação de referências citadas em texto livre.

Mesmo parser dos conversores do repositório (`tools/scopus-para-simat.py` e
`ReferenceParser.java`): a referência vira
``AUTOR, ANO, FONTE, Vvolume, Ppáginas, Título``, com o título no fim, porque o
importador lê os campos pela posição depois da vírgula.

O nome curto de cada grupo de referências segue `ReferenceGrouping.java`.
"""

from __future__ import annotations

import html
import re

SEM_AUTOR = "Sem autor"
SEM_FONTE = "Sem fonte"

SEPARADOR_REFERENCIA = re.compile(r"(?<=\));\s*")
ANO_FIM = re.compile(r"[,\s]*\(\s*(\d{4}[a-z]?)\s*\)\s*$", re.IGNORECASE)
PAGINAS_FIM = re.compile(
    r",\s*p{1,2}\.\s*([^\s,]+(?:\s*[-–—]\s*[^\s,]+)?)\s*$", re.IGNORECASE)
PAGINAS_INTERNA = re.compile(
    r"(?:^|\s)p{1,2}\.\s*([^\s,]+(?:\s*[-–—]\s*[^\s,]+)?)\s*$",
    re.IGNORECASE)
DOI_FIM = re.compile(
    r",\s*(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?10\.\d{4,9}/\S+\s*$", re.IGNORECASE)
INICIAIS_FIM = re.compile(r"^[^\W\d_][^,;]*\s(?:[A-Z]\.?-?)+$", re.UNICODE)
TAG = re.compile(r"<[^>]+>")

PALAVRAS_DE_TITULO = frozenset("of the and for in on a an to with from by at as".split())

PALAVRAS_DE_FONTE = (
    "journal", "proceedings", "conference", "congress", "symposium", "workshop",
    "transaction", "review", "quarterly", "bulletin", "annals", "letters",
    "magazine", "press", "publishing", "springer", "elsevier", "wiley",
    "routledge", "sage", "acm", "ieee", "association", "society", "education",
    "educational", "science", "sciences", "computing", "computer", "psychology",
    "learning", "technology", "research", "studies", "international",
    "university", "handbook", "books", "educ",
)
INICIO_DE_FONTE = frozenset((
    "proceedings", "conference", "journal", "transaction", "transactions",
    "symposium", "workshop", "annals", "bulletin",
))
# Abreviações e nomes genéricos que iniciam uma fonte em duas partes:
# "Univ, Granada", "Psychol, Monogr", "Editorial, ...".
INICIO_DE_FONTE_ABREVIADO = frozenset((
    "univ", "univ.", "universidad", "universidade", "university", "editorial",
    "publisher", "psychol", "psychol.", "monogr", "monogr.", "rev", "rev.",
    "revista",
))
CONECTORES = frozenset((
    "and", "of", "for", "in", "on", "with", "by", "at", "as", "to", "from",
    "de", "da", "do", "das", "dos", "e", "y", "und", "et",
))


def limpa_texto(valor: str) -> str:
    texto = html.unescape(valor or "")
    texto = TAG.sub("", texto)
    texto = texto.replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", texto).strip()


def parece_autor(segmento: str) -> bool:
    segmento = segmento.strip()
    if not segmento or len(segmento) > 160:
        return False

    if ";" in segmento:
        partes = [p.strip() for p in segmento.split(";") if p.strip()]
        if not partes or len(partes) > 30:
            return False
        return all(len(p.split()) <= 5 for p in partes)

    if INICIAIS_FIM.match(segmento):
        palavras = segmento.split()
        if len(palavras) > 6:
            return False
        # "Statistical consultancy. A basis for teaching R." termina em "R.",
        # mas as palavras minúsculas mostram que é título, não nome de autor.
        if any(p[:1].islower() and p.lower() not in CONECTORES
               for p in palavras):
            return False
        return True

    palavras = segmento.split()
    if not 2 <= len(palavras) <= 4 or len(segmento) > 45:
        return False
    if any(p.lower() in PALAVRAS_DE_TITULO for p in palavras):
        return False
    return all(p[:1].isupper() for p in palavras)


def _autor_com_iniciais(segmento: str) -> bool:
    """Autor com iniciais no fim, sem confundir título ou editora.

    "Godino J.D." e "Inhelder B." passam; "Etnografia D.C.E.L.E.",
    "Probabilidad I.C." e "Paris: PUF" não.
    """
    if not parece_autor(segmento) or ":" in segmento:
        return False
    if re.search(r"\b[A-Z]\.(?:[A-Z]\.){2,}", segmento):
        return False
    ultimo = segmento.split()[-1]
    return bool(re.fullmatch(r"[A-Z]\.?(?:[A-Z]\.?)?", ultimo))


def parece_fonte(texto: str) -> bool:
    minusculo = texto.lower()
    return any(palavra in minusculo for palavra in PALAVRAS_DE_FONTE)


def _limpa_campo(valor: str) -> str:
    texto = re.sub(r"\s+", " ", valor or "")
    texto = texto.replace("//", "/").replace(",", " ")
    return re.sub(r"\s+", " ", texto).strip()


def _limpa_titulo(valor: str) -> str:
    return re.sub(r"\s+", " ", valor or "").replace("//", "/").strip()


def _tokens(texto: str) -> list[str]:
    """Tokens alfanuméricos, sem acentos, para comparar segmentos."""
    import unicodedata

    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    return re.findall(r"[a-z0-9]+", texto)


_RUIDO_DE_DUPLICATA = frozenset((
    "p", "pp", "v", "vol", "volume", "n", "no", "issue", "numero",
))


def _ruido(token: str) -> bool:
    return token.isdigit() or token in _RUIDO_DE_DUPLICATA


def _encontra_repeticao(segmentos: list[str]) -> tuple[int, int] | None:
    """Localiza a fonte repetida dentro da referência.

    A exportação enriquecida pelo NotebookLM repete o trecho da fonte no fim:
    ``Suma, 9, pp. 25-31, Suma 9 Pp. 25-31, 9``. A busca compara a cauda com
    uma janela anterior; o casamento exige pelo menos dois tokens e só aceita
    números ou marcadores de volume/página sobrando no fim. Devolve o intervalo
    ``(início, fim)`` da primeira ocorrência limpa.
    """
    tokens = [_tokens(segmento) for segmento in segmentos]

    for j in range(1, len(segmentos)):
        cauda = [token for parte in tokens[j:] for token in parte]
        if not cauda:
            continue
        for k in range(j):
            janela = [token for parte in tokens[k:j] for token in parte]
            if not janela:
                continue
            if len(janela) == 1:
                # Editoras repetidas: "Aldine, Aldine", "PPU, Ppu".
                if (len(cauda) == 1 and janela == cauda
                        and len(janela[0]) >= 3):
                    return k, j
                continue
            if cauda[:len(janela)] != janela:
                continue
            resto = cauda[len(janela):]
            if all(_ruido(token) for token in resto):
                return k, j
    return None


def _separa_paginas(segmentos: list[str], paginas: str) -> tuple[list[str], str]:
    """Tira ``pp. 25-31`` de qualquer segmento, não só do fim."""
    restantes = []
    for segmento in segmentos:
        achado = PAGINAS_INTERNA.search(segmento)
        if achado:
            if not paginas:
                paginas = achado.group(1)
            segmento = segmento[:achado.start()].strip(" ,")
        if segmento:
            restantes.append(segmento)
    return restantes, paginas


def _segmentos(texto: str) -> list[str]:
    """Divide por vírgulas fora de parênteses e colchetes.

    A fonte pode trazer o país entre parênteses, como
    "Childhood (copenhagen, Denmark)"; a vírgula interna não separa campos.
    """
    partes = []
    atual = []
    profundidade = 0
    for caractere in texto:
        if caractere in "([":
            profundidade += 1
        elif caractere in ")]":
            profundidade = max(0, profundidade - 1)
        if caractere == "," and profundidade == 0:
            parte = "".join(atual).strip()
            if parte:
                partes.append(parte)
            atual = []
        else:
            atual.append(caractere)
    parte = "".join(atual).strip()
    if parte:
        partes.append(parte)
    return partes


MARCADOR_INICIAL = re.compile(r"^(?:\[\s*\d+\s*\]|\(\s*\d+\s*\)|\d{1,3}\.)\s*")


def converte_referencia(bruta: str) -> str | None:
    """Referência do Scopus/OpenAlex no formato do importador do SciMAT."""
    texto = re.sub(r"\s+", " ", bruta or "").strip().rstrip(";").strip()
    # Numeração da lista de referências ("[18] ", "12. ") não faz parte da obra.
    texto = MARCADOR_INICIAL.sub("", texto).strip()
    if not texto:
        return None

    ano = ""
    achado = ANO_FIM.search(texto)
    if achado:
        ano = achado.group(1)
        texto = texto[:achado.start()].strip().rstrip(",").strip()

    paginas = ""
    achado = PAGINAS_FIM.search(texto)
    if achado:
        paginas = achado.group(1)
        texto = texto[:achado.start()].strip().rstrip(",").strip()

    texto = DOI_FIM.sub("", texto).strip().rstrip(",").strip()
    if not texto:
        return None

    segmentos = _segmentos(texto)
    if not segmentos:
        return None

    if len(segmentos) == 1 and not ano:
        return None

    if not ano and len(segmentos) >= 3 and re.fullmatch(r"\d{4}[a-z]?", segmentos[1]):
        ano = segmentos[1]
        segmentos = [segmentos[0]] + segmentos[2:]

    segmentos, paginas = _separa_paginas(segmentos, paginas)

    autores = []
    while len(segmentos) > 1 and parece_autor(segmentos[0]):
        if autores and not (_autor_com_iniciais(segmentos[0])
                            or ";" in segmentos[0]):
            break
        autores.append(segmentos.pop(0))
    autor = "; ".join(autores)

    repeticao = _encontra_repeticao(segmentos)
    if repeticao:
        inicio, fim = repeticao
        janela = segmentos[inicio:fim]
        numeros = []
        while janela and re.fullmatch(r"\d{1,6}", janela[-1]):
            numeros.insert(0, janela.pop())
        for parte in segmentos[fim:]:
            if re.fullmatch(r"\d{1,6}", parte) and parte not in numeros:
                numeros.append(parte)
        fonte = ", ".join(janela)
        titulo = ", ".join(segmentos[:inicio])
        segmentos = []
    else:
        numeros = []
        while segmentos:
            ultimo = segmentos[-1]
            if re.fullmatch(r"\d{1,6}", ultimo):
                numeros.insert(0, segmentos.pop())
                continue
            anterior = segmentos[-2] if len(segmentos) >= 2 else ""
            parece_numero = (
                re.fullmatch(r"\d{1,6}\s*[-–—]\s*\d{1,6}", ultimo)
                or re.fullmatch(r"[A-Z]", ultimo)
                or re.fullmatch(r"(?:Suppl\.?|S|Pt\.?)\s*\d{1,3}", ultimo, re.IGNORECASE))
            if parece_numero and re.fullmatch(r"\d{1,6}", anterior):
                numeros.insert(0, segmentos.pop())
                continue
            break

        if not segmentos:
            return None

        tem_ancora = bool(numeros) or bool(paginas)
        fonte = ""
        titulo = ", ".join(segmentos)

        if len(segmentos) == 1 and not tem_ancora:
            # Só um trecho: título de obra sem fonte ou nome de evento que veio
            # como único dado (anais sem páginas).
            primeira = segmentos[0].split(" ")[0].lower().strip(",")
            if primeira in INICIO_DE_FONTE:
                fonte = segmentos.pop()
                titulo = ""
        elif (tem_ancora
              or (parece_fonte(segmentos[-1])
                  and (segmentos[-1][:1].isupper()
                       or segmentos[-1][:1].isdigit())
                  and segmentos[-1].split(" ")[0].lower() not in CONECTORES)
              or (len(segmentos) >= 2
                  and segmentos[-2].lower().strip(",")
                  in INICIO_DE_FONTE_ABREVIADO)):
            # Nomes de fonte que o Scopus quebrou em mais de um trecho, como
            # "Proceedings ... on Teaching, Assessment and Learning ...", voltam a
            # ser um só.
            primeira = True
            primeira_ultimo = segmentos[-1].split(" ")[0].lower().strip(",")

            while len(segmentos) >= 2:
                anterior = segmentos[-2]
                ultimo = segmentos[-1]
                primeira_anterior = anterior.split(" ")[0].lower().strip(",")

                continua_fonte = (
                    primeira_anterior in INICIO_DE_FONTE
                    or primeira_anterior in INICIO_DE_FONTE_ABREVIADO
                    or (primeira and primeira_ultimo in CONECTORES)
                    or (primeira_anterior in CONECTORES and parece_fonte(anterior)))

                if continua_fonte:
                    segmentos[-2:] = [anterior + ", " + ultimo]
                    primeira = False
                else:
                    break

            fonte = segmentos.pop()
            titulo = ", ".join(segmentos)

            if fonte.lower().startswith("in "):
                fonte = fonte[3:].strip()

    if not titulo and not fonte:
        return None

    if not autor:
        autor = SEM_AUTOR
    if not fonte:
        fonte = SEM_FONTE

    campos = [
        _limpa_campo(autor) or SEM_AUTOR,
        ano,
        _limpa_campo(fonte) or SEM_FONTE,
        "V" + _limpa_campo(numeros[0]) if numeros else "",
        "P" + _limpa_campo(paginas) if paginas else "",
        _limpa_titulo(titulo),
    ]

    return ", ".join(campos)


def nome_do_grupo(referencia_completa: str, nomes_usados: set[str]) -> str:
    """Nome curto e único do grupo de referências (autor, ano e fonte)."""
    campos = referencia_completa.split(",", 6)
    autor = campos[0].strip() if len(campos) > 0 else ""
    ano = campos[1].strip() if len(campos) > 1 else ""
    fonte = campos[2].strip() if len(campos) > 2 else ""
    volume = campos[3].strip() if len(campos) > 3 else ""
    paginas = campos[4].strip() if len(campos) > 4 else ""
    titulo = campos[5].strip() if len(campos) > 5 else ""

    if ";" in autor:
        autor = autor[:autor.index(";")].strip() + " et al."

    base = autor
    if ano:
        base = base + ", " + ano

    if fonte and fonte.lower() != SEM_FONTE.lower() and len(fonte) <= 30:
        base = base + ", " + fonte
    elif not ano and fonte and fonte.lower() != SEM_FONTE.lower():
        base = base + ", " + _recorta(fonte, 30)
    elif not ano and titulo:
        base = base + ", " + _recorta(titulo, 30)

    tentativas = [base]
    if volume:
        tentativas.append(base + ", " + volume)
        if paginas:
            tentativas.append(base + ", " + volume + ", " + paginas)
    tentativas.append(referencia_completa)

    for tentativa in tentativas:
        nome = _recorta(tentativa, 60)
        if nome not in nomes_usados:
            return nome

    resumo = _recorta(base, 50)
    numero = 2
    while True:
        nome = f"{resumo} ({numero})"
        if nome not in nomes_usados:
            return nome
        numero += 1


def _recorta(texto: str, limite: int) -> str:
    if len(texto) <= limite:
        return texto
    return texto[:limite - 1] + "…"

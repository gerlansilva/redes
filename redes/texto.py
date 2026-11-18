"""Apresentação dos termos: a caixa dos termos guardados em maiúsculas.

As palavras-chave guardadas pelo Redes e as que vêm da Scopus ficam guardadas em caixa alta e
com hífen no lugar do espaço (``STATISTICAL-REASONING``). O dado guardado, os
identificadores e as chaves de agrupamento não mudam nunca; só a **exibição**
passa por `termo_legivel`, a única função de apresentação do programa. Todas as
saídas visíveis dos termos (interface, figuras, tabelas, relatórios,
exportações e rótulos de agrupamento) a usam.

Regra:

* só muda o termo escrito inteiramente em maiúsculas (letras); o que já tem
  caixa mista ou minúscula fica como está;
* o termo vira minúsculo com a primeira letra maiúscula
  (``STATISTICAL-REASONING`` → ``Statistical reasoning``);
* o hífen entre palavras vira espaço quando os dois trechos têm 2 ou mais
  letras; hífen com um trecho de uma letra ou sem letras fica
  (``E-LEARNING`` → ``E-learning``, ``COVID-19`` → ``COVID-19``);
* as siglas conhecidas (`SIGLAS_PADRAO`, mais as que o usuário registrar)
  continuam em maiúsculas onde aparecem, como ``SPSS``, ``PISA`` ou ``TIMSS``;
* a caixa de um token com algarismo e letra (``GT12``, ``COVID19``) não se reescreve;
  nomes com maiúscula interna conhecidos (`NOMES_PROPRIOS`) voltam à grafia própria
  (``GEOGEBRA`` → ``GeoGebra``);
* numerais romanos (``II``, ``IV``, ``XIII``) ficam em maiúsculas quando o termo tem mais
  de uma palavra (``WORLD WAR II`` → ``World war II``); `restaura_romanos` faz o mesmo em
  títulos já em caixa de título (``Anais do Iv Seminario`` → ``Anais do IV Seminario``).

O termo curto de uma palavra só (``PISA``) fica em maiúsculas apenas se for uma
sigla da lista; as demais caem na regra geral (``Pisa``). A lista é pequena de
propósito e configurável: ``registra_siglas`` e a variável de ambiente
``REDES_SIGLAS`` (separadas por vírgula).
"""

from __future__ import annotations

import os
import re

# Siglas frequentes em educação estatística e matemática, de 2 a 5 letras.
SIGLAS_PADRAO = frozenset("""
SPSS PISA ICME TIMSS PIRLS TALIS ENEM SAEB SAEP BNCC TIC TICS ICT NCTM GAISE STEM STEAM
PCK TPACK IASE ICOTS ANOVA IRT RME PNAIC PNLD PCN LDB EJA IDEB MOOC MOOCS COVID CAQDAS
SIPEM IRAMUTEQ SBEM
""".split())

# Nomes com maiúscula interna: o dado guardado vem em caixa alta, então a grafia própria
# precisa de uma lista (chave em maiúsculas).
NOMES_PROPRIOS = {
    "GEOGEBRA": "GeoGebra", "WHATSAPP": "WhatsApp", "YOUTUBE": "YouTube",
    "RSTUDIO": "RStudio", "NVIVO": "NVivo", "MAXQDA": "MAXQDA", "POWERPOINT": "PowerPoint",
    "GITHUB": "GitHub", "SCRATCH": "Scratch",
}

_ROMANO = re.compile(r"^(?=[IVX])X{0,3}(IX|IV|V?I{0,3})$")


def e_romano(pedaco: str) -> bool:
    """Numeral romano de I a XXXIX (só com I, V e X), em maiúsculas ou em caixa de título."""
    return bool(pedaco) and len(pedaco) > 1 and bool(_ROMANO.match(pedaco.upper())) \
        and (pedaco.isupper() or pedaco == pedaco.capitalize())

# Siglas que também são palavras comuns: só se restauram quando o termo veio em
# maiúsculas, nunca num texto que já estava em minúsculas (título, resumo).
SIGLAS_AMBIGUAS = frozenset("STEM STEAM TIC TICS EJA".split())

_extras: set[str] = set()


def _do_ambiente() -> set[str]:
    bruto = os.environ.get("REDES_SIGLAS", "")
    return {p.strip().upper() for p in re.split(r"[,;\s]+", bruto) if p.strip()}


def siglas() -> frozenset[str]:
    """Siglas que ficam em maiúsculas: a lista padrão, as registradas e as do ambiente."""
    return SIGLAS_PADRAO | frozenset(_extras) | frozenset(_do_ambiente())


def registra_siglas(*itens: str) -> None:
    """Acrescenta siglas à lista (palavras de 2 a 6 letras, sem hífen)."""
    for item in itens:
        for parte in re.split(r"[,;\s]+", item or ""):
            if parte.strip():
                _extras.add(parte.strip().upper())


def esquece_siglas() -> None:
    """Remove as siglas registradas (a lista padrão e a do ambiente permanecem)."""
    _extras.clear()


def e_caixa_alta(texto: str) -> bool:
    """Verdadeiro se o texto tem letras e nenhuma delas é minúscula."""
    letras = [c for c in texto if c.isalpha()]
    return bool(letras) and not any(c.islower() for c in letras)


def _letras(pedaco: str) -> int:
    return sum(1 for c in pedaco if c.isalpha())


def _palavra(pedaco: str, lista: frozenset[str], varias_palavras: bool = False) -> str:
    if pedaco in lista:
        return pedaco
    if pedaco in NOMES_PROPRIOS:
        return NOMES_PROPRIOS[pedaco]
    if any(c.isdigit() for c in pedaco) and any(c.isalpha() for c in pedaco):
        return pedaco              # GT12, COVID19: a caixa não se reescreve
    if varias_palavras and e_romano(pedaco) and pedaco.isupper():
        return pedaco              # World war II
    return pedaco.lower()


def restaura_romanos(texto) -> str:
    """Numerais romanos em maiúsculas num título em caixa de título (``Iv`` → ``IV``).

    Só muda tokens inteiros de 2 ou mais letras formados por I, V e X; o resto do texto
    não é tocado (nomes de fontes e títulos de obras vêm da base com a caixa que tinham).
    """
    if texto is None:
        return ""
    bruto = str(texto)
    return re.sub(r"(?<![\w])[IiVvXx]{2,}(?![\w])",
                  lambda m: m.group(0).upper() if e_romano(m.group(0)) else m.group(0), bruto)


def _converte(texto: str) -> str:
    lista = siglas()
    saida: list[str] = []
    varias = " " in texto.strip()
    for palavra in texto.split(" "):
        pedacos = palavra.split("-")
        partes = [_palavra(p, lista, varias) for p in pedacos]
        resultado = partes[0]
        for i in range(1, len(partes)):
            ligacao = " " if _letras(pedacos[i - 1]) >= 2 and _letras(pedacos[i]) >= 2 else "-"
            resultado += ligacao + partes[i]
        saida.append(resultado)
    frase = " ".join(saida)
    # A primeira letra do termo fica maiúscula (a sigla já está).
    for i, c in enumerate(frase):
        if c.isalpha():
            return frase[:i] + c.upper() + frase[i + 1:]
        if not c.isdigit() and c not in "-'\"(“¿¡":
            break
    return frase


def termo_legivel(texto) -> str:
    """Forma de exibição de um termo; o que não está todo em maiúsculas não muda."""
    if texto is None:
        return ""
    bruto = str(texto)
    base = re.sub(r"\s+", " ", bruto).strip()
    if not base or not e_caixa_alta(base):
        return bruto
    return _converte(base)


def exibe_termo(unidade: str | None, texto) -> str:
    """`termo_legivel` só para palavras-chave; autores, países, IES, periódicos e
    referências mantêm o texto como veio."""
    if unidade == "Words":
        return termo_legivel(texto)
    if unidade in ("ReferenceSources", "References", "Institutions"):
        return restaura_romanos(texto)
    return "" if texto is None else str(texto)


def em_frase(texto: str) -> str:
    """Termo no meio de uma frase: minúscula inicial, menos siglas e nomes."""
    if not texto:
        return texto
    primeira = texto.split(" ", 1)[0]
    if sum(1 for c in primeira if c.isupper()) > 1 or texto[:1] in "0123456789":
        return texto
    return texto[:1].lower() + texto[1:]


def texto_de_busca(texto) -> str:
    """Chave de busca sem caixa nem acento, igual para a forma exibida e o original
    (``Statistical reasoning`` e ``STATISTICAL-REASONING`` casam)."""
    import unicodedata
    base = unicodedata.normalize("NFD", str(texto or ""))
    base = "".join(c for c in base if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", base).strip()


def termo_de_rotulo(termo: str) -> str:
    """Termo de um rótulo automático (já em minúsculas): inicial maiúscula e siglas.

    Os rótulos por tema saem de palavras-chave e de títulos em minúsculas;
    aqui só se põe a inicial maiúscula e se restauram as siglas conhecidas
    (``pisa`` → ``PISA``), menos as que também são palavras comuns.
    """
    texto = " ".join(str(termo or "").split())
    if not texto:
        return ""
    lista = siglas() - SIGLAS_AMBIGUAS

    def palavra(m: "re.Match[str]") -> str:
        maiuscula = m.group(0).upper()
        if maiuscula in NOMES_PROPRIOS:
            return NOMES_PROPRIOS[maiuscula]
        return maiuscula if maiuscula in lista else m.group(0)

    texto = re.sub(r"[^\W\d_]+", palavra, texto)
    for i, c in enumerate(texto):
        if c.isalpha():
            return texto[:i] + c.upper() + texto[i + 1:]
        if not c.isdigit() and c not in "-'\"(":
            break
    return texto


def rotulo_legivel(texto: str, separador: str = " · ") -> str:
    """`termo_de_rotulo` em cada termo de um rótulo "termo · termo · termo"."""
    return separador.join(termo_de_rotulo(p) for p in str(texto or "").split(separador))

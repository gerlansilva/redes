"""Apresentação dos termos: a caixa dos termos em maiúsculas do SciMAT.

As palavras-chave que vêm do SciMAT e do Scopus ficam guardadas em caixa alta e
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
  continuam em maiúsculas onde aparecem, como ``SPSS``, ``PISA`` ou ``TIMSS``.

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
""".split())

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


def _palavra(pedaco: str, lista: frozenset[str]) -> str:
    return pedaco if pedaco in lista else pedaco.lower()


def _converte(texto: str) -> str:
    lista = siglas()
    saida: list[str] = []
    for palavra in texto.split(" "):
        pedacos = palavra.split("-")
        partes = [_palavra(p, lista) for p in pedacos]
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
        return m.group(0).upper() if m.group(0).upper() in lista else m.group(0)

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

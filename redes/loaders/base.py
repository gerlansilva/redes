"""Estrutura comum dos carregadores de corpus."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

INICIAIS = re.compile(r"^[A-Z](?:\.?-?[A-Z])*\.?$")


@dataclass
class DocumentoFonte:
    """Um registro importado, antes de virar linhas do armazenamento."""

    titulo: str
    autores: list[str] = field(default_factory=list)
    autores_completos: list[str] = field(default_factory=list)
    ano: str = ""
    # None = "Cited by" vazio na origem (ausente, diferente de zero citações)
    citacoes: int | None = 0
    periodico: str = ""
    doi: str = ""
    tipo: str = ""
    resumo: str = ""
    afiliacoes: list[str] = field(default_factory=list)
    paises: list[str] = field(default_factory=list)
    palavras_autor: list[str] = field(default_factory=list)
    palavras_fonte: list[str] = field(default_factory=list)
    referencias: list[str] = field(default_factory=list)
    referencias_brutas: list[str] = field(default_factory=list)
    referencias_convertidas: bool = False
    metadados: dict[str, str] = field(default_factory=dict)


def abrevia_autor(nome: str) -> str:
    """"Lopes, Celi Espasandin" → "Lopes, C.E." (formato abreviado)."""
    nome = (nome or "").strip()
    if not nome:
        return ""

    if "," in nome:
        sobrenome, resto = nome.split(",", 1)
    else:
        partes = nome.split()
        if len(partes) < 2:
            return nome
        sobrenome, resto = partes[-1], " ".join(partes[:-1])

    tokens = [p for p in re.split(r"[\s\-]+", resto.strip()) if p]
    if tokens and all(INICIAIS.match(p) for p in tokens):
        return f"{sobrenome.strip()}, {''.join(tokens)}"

    iniciais = [p[0].upper() + "." for p in tokens if p[0].isalpha()]
    if not iniciais:
        return sobrenome.strip()

    return f"{sobrenome.strip()}, {''.join(iniciais)}"


# ------------------------------------------------------------------ duplicatas


def _chave_doi(doi: str) -> str:
    texto = (doi or "").strip().lower()
    texto = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", texto)
    return texto.strip().rstrip(".")


def _chave_titulo(titulo: str, ano: str) -> str:
    texto = unicodedata.normalize("NFKD", titulo or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r"[^a-z0-9]+", "", texto)
    achado = re.match(r"\d{4}", (ano or "").strip())
    return f"{texto}|{achado.group(0) if achado else ''}" if texto else ""


def _completude(documento: DocumentoFonte) -> int:
    return (len(documento.referencias) + len(documento.palavras_autor)
            + len(documento.palavras_fonte) + len(documento.afiliacoes)
            + len(documento.autores) + (3 if documento.resumo else 0)
            + (2 if documento.doi else 0))


def _titulo_todo_maiusculo(titulo: str) -> bool:
    letras = [c for c in titulo if c.isalpha()]
    return len(letras) > 3 and all(c.isupper() for c in letras)


def _une(base: DocumentoFonte, outro: DocumentoFonte) -> DocumentoFonte:
    """Preenche o que falta em ``base`` com os dados de ``outro``."""
    for campo in ("ano", "periodico", "doi", "tipo", "resumo"):
        if not getattr(base, campo) and getattr(outro, campo):
            setattr(base, campo, getattr(outro, campo))
    if len(outro.resumo) > len(base.resumo):
        base.resumo = outro.resumo
    if _titulo_todo_maiusculo(base.titulo) and not _titulo_todo_maiusculo(outro.titulo):
        base.titulo = outro.titulo
    if base.citacoes is None or outro.citacoes is None:
        base.citacoes = base.citacoes if outro.citacoes is None else (
            outro.citacoes if base.citacoes is None else base.citacoes)
    else:
        base.citacoes = max(base.citacoes, outro.citacoes)
    for campo in ("autores", "autores_completos", "afiliacoes", "paises",
                  "palavras_autor", "palavras_fonte"):
        lista = getattr(base, campo)
        if not lista:
            setattr(base, campo, list(getattr(outro, campo)))
    for campo in ("palavras_autor", "palavras_fonte"):
        lista = getattr(base, campo)
        vistos = {termo.lower() for termo in lista}
        for termo in getattr(outro, campo):
            if termo.lower() not in vistos:
                lista.append(termo)
                vistos.add(termo.lower())
    if not base.referencias and outro.referencias:
        base.referencias = list(outro.referencias)
        base.referencias_brutas = list(outro.referencias_brutas)
        base.referencias_convertidas = outro.referencias_convertidas
    for chave, valor in outro.metadados.items():
        base.metadados.setdefault(chave, valor)
    return base


def remove_duplicatas(documentos: list[DocumentoFonte]
                      ) -> tuple[list[DocumentoFonte], list[tuple[str, str]]]:
    """Junta registros repetidos (mesmo DOI ou mesmo título e ano).

    Exportações combinadas da Scopus, do OpenAlex ou do Zotero repetem o mesmo
    artigo, às vezes com o título em caixa alta e sem DOI. O registro mais
    completo vira a base, mantém a posição do primeiro e recebe o que faltava
    (palavras-chave, afiliações, maior contagem de citações). Devolve a lista
    sem repetições e os pares ``(título, motivo)`` dos descartados.
    """
    indice: dict[str, int] = {}
    resultado: list[DocumentoFonte] = []
    removidos: list[tuple[str, str]] = []

    for documento in documentos:
        chaves = []
        doi = _chave_doi(documento.doi)
        if doi:
            chaves.append(("doi", "doi:" + doi))
        titulo = _chave_titulo(documento.titulo, documento.ano)
        if titulo:
            chaves.append(("título e ano", "titulo:" + titulo))

        posicao = None
        motivo = ""
        for rotulo, chave in chaves:
            if chave in indice:
                posicao, motivo = indice[chave], rotulo
                break

        if posicao is None:
            posicao = len(resultado)
            resultado.append(documento)
        else:
            existente = resultado[posicao]
            if _completude(documento) > _completude(existente):
                resultado[posicao] = _une(documento, existente)
            else:
                _une(existente, documento)
            removidos.append((documento.titulo, motivo))
        for _, chave in chaves:
            indice.setdefault(chave, posicao)

    return resultado, removidos


# ------------------------------------------------------------ texto utilitário

_ACENTOS_LATEX = {
    "'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303",
    '"': "\u0308", "=": "\u0304", ".": "\u0307", "c": "\u0327",
    "v": "\u030c", "u": "\u0306", "H": "\u030b", "k": "\u0328",
    "r": "\u030a",
}
_LETRAS_LATEX = {
    "ss": "ß", "o": "ø", "O": "Ø", "aa": "å", "AA": "Å", "ae": "æ",
    "AE": "Æ", "oe": "œ", "OE": "Œ", "l": "ł", "L": "Ł", "i": "i", "j": "j",
}
_ACENTO_LATEX = re.compile(
    r"\\(['`^~\"=.])\s*(?:\{\s*(\\?[A-Za-z])\s*\}|(\\?[A-Za-z]))"
    r"|\\([cvuHkr])(?:\s*\{\s*([A-Za-z])\s*\}|\s+([A-Za-z]))")
_LETRA_LATEX = re.compile(r"\\(ss|aa|AA|ae|AE|oe|OE|o|O|l|L)(?![A-Za-z])\s?")


def decodifica_latex(texto: str) -> str:
    """Converte acentos LaTeX do BibTeX ("Educa{\\c{c}}{\\~a}o") em Unicode."""
    if not texto or "\\" not in texto and "{" not in texto:
        return texto or ""

    def acento(achado):
        marca = achado.group(1) or achado.group(4)
        letra = (achado.group(2) or achado.group(3) or achado.group(5)
                 or achado.group(6))
        if letra.startswith("\\"):  # \\i e \\j (sem pingo) viram i e j
            letra = letra[1:]
        return unicodedata.normalize("NFC", letra + _ACENTOS_LATEX[marca])

    texto = _ACENTO_LATEX.sub(acento, texto)
    texto = _LETRA_LATEX.sub(lambda m: _LETRAS_LATEX[m.group(1)], texto)
    texto = re.sub(r"\\([&%$#_{}])", r"\1", texto)
    texto = texto.replace("{", "").replace("}", "")
    return unicodedata.normalize("NFC", texto)


_CITACOES = re.compile(
    r"(?:cited\s+by|citations?|times\s+cited|citado\s+por|citas?)\s*[:=]?\s*(\d+)",
    re.IGNORECASE)


def citacoes_em_texto(*textos: str) -> int:
    """Contagem de citações escrita em notas ("Cited By: 12", "Citations: 3")."""
    for texto in textos:
        achado = _CITACOES.search(texto or "")
        if achado:
            return int(achado.group(1))
    return 0


def acha_doi(*textos: str) -> str:
    for texto in textos:
        achado = re.search(r"10\.\d{4,9}/[^\s\"<>]+", texto or "")
        if achado:
            return achado.group(0).rstrip(".,;)")
    return ""


def divide_termos(valor: str) -> list[str]:
    """Palavras-chave separadas por ``;`` (ou ``|``), sem itens vazios."""
    return [t.strip() for t in re.split(r"[;|]", valor or "") if t.strip()]

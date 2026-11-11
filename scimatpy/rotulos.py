"""Rótulos automáticos de agrupamentos, a partir do texto dos documentos.

Para cada agrupamento, os termos que o distinguem dos demais documentos do
mesmo período, por razão de verossimilhança de Dunning (LLR).

* Documentos do agrupamento: o núcleo (``Grupo.documentos_nucleo``).
* Contraste: os outros documentos do período (``dataset_original``).
* Termos: palavras do título, palavras-chave dos autores (expressão inteira)
  e só pares de palavras (bigramas) do resumo; palavras soltas do resumo
  são genéricas demais.
* Singular/plural e acento são unidos (``text_utils.mesmo_termo``); palavras
  vazias e acadêmicas vêm de ``termos``; os termos de resumo "de praxe"
  ("results", "objetivo") estão aqui. Nada é traduzido.
* Termos que aparecem em menos de 2 documentos do agrupamento são descartados.
* Menos de 5 documentos, agrupamento que cobre mais de 70% do período ou
  documentos sem título, resumo nem palavras-chave: sem rótulo.
"""
from __future__ import annotations

import math
import os
import re
import threading
from collections import Counter, OrderedDict, defaultdict

from . import termos
from .text_utils import mesmo_termo

MINIMO_DOCUMENTOS = 5
LIMITE_INDICATIVO = 10          # abaixo disso (5..9) o rótulo é indicativo
COBERTURA_MAXIMA = 0.70
MINIMO_NO_GRUPO = 2

# Termos de resumo que não dizem sobre o que é o estudo.
_PRAXE = """abstract available aim aims aimed purpose purposes objective objectives
method methods methodology result results conclusion conclusions background introduction finding findings present presents
presented discuss discusses discussed show shows showed shown suggest suggests suggested found according additional positive
significant significantly provide provides provided describe describes described examined examine addition including include
includes included across various however thus well three four five six two many several different important importance potential
indicate indicates indicated within among also may can will present current recent increasingly main key analyzed analysed
resumen resumo objetivo objetivos metodo metodologia resultados conclusiones conclusoes palabras palavras chave clave
elsevier springer wiley rights reserved copyright taylor francis publishers academic press bmj sage"""
PALAVRAS_DE_RESUMO = frozenset(termos._normaliza(w) for w in _PRAXE.split())

_COPYRIGHT = re.compile(r"(©|\(c\)|copyright|all rights reserved|published by).*$",
                        re.I | re.S)
_LOTE = 500


# ------------------------------------------------------------------ corpus


def _canonico(unigramas: Counter) -> dict[str, str]:
    """Palavra → representante (mesma regra de `termos._unifica`)."""
    baldes: dict[str, list[str]] = defaultdict(list)
    for t in unigramas:
        baldes[termos._normaliza(t)[:4]].append(t)
    destino: dict[str, str] = {}
    for ts in baldes.values():
        ts.sort(key=lambda t: (-unigramas[t], t))
        reps: list[str] = []
        for t in ts:
            for r in reps:
                if mesmo_termo(t.upper(), r.upper()):
                    destino[t] = r
                    break
            else:
                reps.append(t)
                destino[t] = t
    return destino


def _palavras_chave(kb, ids: set[int]) -> dict[int, set[str]]:
    try:
        linhas = list(kb.conexao.execute(termos._SQL_PALAVRAS_AUTOR))
    except Exception:
        return {}
    kws: dict[int, set[str]] = defaultdict(set)
    for doc, nome in linhas:
        if doc in ids and nome:
            legivel = " ".join(termos._rotulo_legivel(str(nome)).split())
            if legivel:
                kws[doc].add(legivel)
    return kws


def _textos(kb, ids: list[int]) -> dict[int, tuple[str, str]]:
    docs: dict[int, tuple[str, str]] = {}
    for i in range(0, len(ids), _LOTE):
        lote = ids[i:i + _LOTE]
        marcas = ",".join("?" * len(lote))
        try:
            linhas = kb.conexao.execute(
                f"SELECT idDocument, title, docAbstract FROM Document "
                f"WHERE idDocument IN ({marcas})", lote)
            for doc, titulo, resumo in linhas:
                docs[doc] = (str(titulo or ""), str(resumo or ""))
        except Exception:
            return docs
    return docs


class _Corpus:
    """Termos por documento e frequência de documentos de cada termo."""

    def __init__(self, kb, ids) -> None:
        ids = list(dict.fromkeys(ids))
        textos = _textos(kb, ids)
        kws = _palavras_chave(kb, set(textos))
        pedacos: dict[int, tuple[list, list]] = {}
        uni: Counter = Counter()
        for doc in sorted(textos):
            titulo, resumo = textos[doc]
            resumo = _COPYRIGHT.sub("", resumo)
            pt = termos.quebra_titulo(titulo, ocultar=PALAVRAS_DE_RESUMO)
            pa = (termos.quebra_titulo(resumo, ocultar=PALAVRAS_DE_RESUMO)
                  if resumo.strip() else [])
            pedacos[doc] = (pt, pa)
            uni.update({p for p in pt + pa if p})
        self.canonico = _canonico(uni)
        self.termos: dict[int, set[str]] = {}
        for doc, (pt, pa) in pedacos.items():
            conjunto: set[str] = set()
            for k, lista in enumerate((pt, pa)):
                ped = [self.canonico.get(p, p) if p else None for p in lista]
                if k == 0:                       # unigramas só do título
                    conjunto |= {p for p in ped if p}
                conjunto |= {f"{a} {b}" for a, b in zip(ped, ped[1:]) if a and b}
            conjunto |= kws.get(doc, set())
            if conjunto:                         # documento sem texto não informa
                self.termos[doc] = conjunto
        self.df: Counter = Counter()
        for conjunto in self.termos.values():
            self.df.update(conjunto)
        self.n = len(self.termos)

    def chave(self, termo: str) -> frozenset[str]:
        return frozenset(termos._normaliza(self.canonico.get(w, w))
                         for w in termo.split())


# ------------------------------------------------------------------ cache

_CACHE_MAXIMO = 4
_cache_corpus: "OrderedDict[tuple, _Corpus]" = OrderedDict()
_trava_cache = threading.Lock()


def limpa_cache() -> None:
    """Esquece os corpora guardados (chamar após editar ou trocar de projeto)."""
    with _trava_cache:
        _cache_corpus.clear()


def _chave_cache(kb, universo: list[int]):
    """Chave do cache ou None (sem cache) quando o banco não é um arquivo conhecido.

    Combina o caminho real do banco, um marcador de versão (data de modificação e
    tamanho do arquivo, mais o número e o maior id de documentos) e os documentos
    do período: outro projeto, base editada ou outro período nunca casam.
    """
    caminho = getattr(kb, "caminho", None)
    if not caminho or str(caminho) == ":memory:":
        return None
    try:
        estado = os.stat(caminho)
        marcador = tuple(kb.conexao.execute(
            "SELECT COUNT(*), COALESCE(MAX(idDocument), 0) FROM Document").fetchone())
        return (os.path.realpath(caminho), estado.st_mtime_ns, estado.st_size,
                marcador, tuple(dict.fromkeys(universo)))
    except Exception:
        return None


def _corpus_do_periodo(kb, universo: list[int]) -> "_Corpus":
    chave = _chave_cache(kb, universo)
    if chave is None:
        return _Corpus(kb, universo)
    with _trava_cache:
        achado = _cache_corpus.get(chave)
        if achado is not None:
            _cache_corpus.move_to_end(chave)
            return achado
    corpus = _Corpus(kb, universo)
    with _trava_cache:
        _cache_corpus[chave] = corpus
        while len(_cache_corpus) > _CACHE_MAXIMO:
            _cache_corpus.popitem(last=False)
    return corpus


# ------------------------------------------------------------------ medida


def _xlx(x: float) -> float:
    return x * math.log(x) if x > 0 else 0.0


def llr(a: int, n_grupo: int, b: int, n_resto: int) -> float:
    """Razão de verossimilhança de Dunning (G²) da tabela 2×2."""
    k = [a, n_grupo - a, b, n_resto - b]
    n = sum(k)
    lin1, lin2, col1, col2 = n_grupo, n_resto, a + b, n - a - b
    return 2.0 * (sum(_xlx(x) for x in k) + _xlx(n)
                  - _xlx(lin1) - _xlx(lin2) - _xlx(col1) - _xlx(col2))


def _ranking(corpus: _Corpus, docs: set[int]) -> list[tuple[str, float]]:
    cont: Counter = Counter()
    for d in docs:
        cont.update(corpus.termos[d])
    nc = len(docs)
    nr = corpus.n - nc
    if nc == 0 or nr <= 0:
        return []
    pontos = []
    for t, a in cont.items():
        if a < MINIMO_NO_GRUPO:
            continue
        b = corpus.df[t] - a
        if a / nc <= b / nr:                     # só termos mais frequentes no grupo
            continue
        pontos.append((t, llr(a, nc, b, nr)))
    pontos.sort(key=lambda kv: (-kv[1], kv[0]))
    return pontos


def _escolhe(corpus: _Corpus, ranking, k: int) -> list[str]:
    """Os k melhores sem repetir ideia (um termo contido em outro é descartado)."""
    escolhidos: list[str] = []
    chaves: list[frozenset] = []
    for t, pontos in ranking:
        if pontos <= 0:
            break
        c = corpus.chave(t)
        if any(c <= x or x <= c for x in chaves):
            continue
        escolhidos.append(t)
        chaves.append(c)
        if len(escolhidos) == k:
            break
    return escolhidos


# ------------------------------------------------------------------ API


def _documentos_do_grupo(resultado, grupo) -> set[int]:
    docs = grupo.documentos.get("nucleo")
    if docs is None:
        from .mappers import nucleo
        fonte = resultado.agregado if resultado.agregado is not None else resultado.dataset
        try:
            docs = nucleo(resultado.rede, fonte, grupo.nos)
        except Exception:
            docs = set()
    return set(docs)


def rotula_grupos(kb, resultado, n_termos: int = 3,
                  minimo_documentos: int = MINIMO_DOCUMENTOS) -> dict[int, dict]:
    """Rótulo por termos distintivos para cada agrupamento com base suficiente.

    Chave = índice em ``resultado.grupos``. Valor: ``{"termos", "rotulo",
    "indicativo", "documentos"}``. Agrupamentos sem rótulo defensável ficam
    ausentes. Com menos de 10 documentos o rótulo é só indicativo.
    """
    try:
        universo = list(resultado.dataset_original.lista_documentos())
    except Exception:
        return {}
    if not universo or not resultado.grupos or n_termos < 1:
        return {}
    corpus = _corpus_do_periodo(kb, universo)
    if corpus.n == 0:
        return {}
    saida: dict[int, dict] = {}
    for indice, grupo in enumerate(resultado.grupos):
        docs = {d for d in _documentos_do_grupo(resultado, grupo) if d in corpus.termos}
        n = len(docs)
        if n < minimo_documentos or n < 1:
            continue
        if n / corpus.n > COBERTURA_MAXIMA:
            continue
        escolhidos = _escolhe(corpus, _ranking(corpus, docs), n_termos)
        if not escolhidos:
            continue
        saida[indice] = {"termos": escolhidos, "rotulo": " · ".join(escolhidos),
                         "indicativo": n < LIMITE_INDICATIVO, "documentos": n}
    return saida

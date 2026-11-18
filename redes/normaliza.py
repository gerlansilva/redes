"""Normalizações opcionais aplicadas aos documentos importados, antes da gravação.

Nenhuma delas é ligada por padrão:

- sinônimos para autores, instituições, periódicos, países e palavras-chave;
- autor identificado pelo nome completo (coluna "Author full names");
- palavras-chave unidas pelo radical ("statistics education" = "statistical education").
"""

from __future__ import annotations

import re
from collections import defaultdict

from .loaders.base import DocumentoFonte
from .sugestoes import instituicao_da_afiliacao
from .text_utils import chave, sem_acentos
from .words import Sinonimos

UNIDADES_SINONIMOS = ("palavras", "autores", "instituicoes", "periodicos", "paises")


def aplica_sinonimos(documentos: list[DocumentoFonte], sinonimos: Sinonimos,
                     unidades=("palavras",)) -> dict[str, int]:
    """Aplica o mapa de sinônimos a cada unidade pedida; devolve substituições por unidade."""
    unidades = set(UNIDADES_SINONIMOS if "todas" in unidades else unidades)
    desconhecidas = unidades - set(UNIDADES_SINONIMOS)
    if desconhecidas:
        raise ValueError(f"unidade de sinônimos desconhecida: {', '.join(sorted(desconhecidas))}")
    feitas: dict[str, int] = defaultdict(int)
    if not sinonimos.canonico:
        return dict(feitas)

    def troca(nome: str, unidade: str) -> str:
        novo = sinonimos.aplica(nome) if nome else None
        if novo and novo != nome:
            feitas[unidade] += 1
            return novo
        return nome

    def sem_repetir(lista):
        return list(dict.fromkeys(lista))

    for doc in documentos:
        if "autores" in unidades:
            doc.autores = sem_repetir(troca(a, "autores") for a in doc.autores)
        if "periodicos" in unidades:
            doc.periodico = troca(doc.periodico, "periodicos")
        if "paises" in unidades:
            doc.paises = sem_repetir(troca(p, "paises") for p in doc.paises)
        if "palavras" in unidades:
            doc.palavras_autor = sem_repetir(troca(p, "palavras") for p in doc.palavras_autor)
            doc.palavras_fonte = sem_repetir(troca(p, "palavras") for p in doc.palavras_fonte)
        if "instituicoes" in unidades:
            trocas: dict[str, str] = {}
            novas = []
            for afiliacao in doc.afiliacoes:
                nova, par = _troca_ies(afiliacao, sinonimos)
                if par:
                    trocas[par[0]] = par[1]
                    feitas["instituicoes"] += 1
                novas.append(nova)
            doc.afiliacoes = sem_repetir(novas)
            valor = doc.metadados.get("Authors with affiliations")
            if valor and trocas:
                # mantém o vínculo autor-afiliação coerente com as instituições trocadas
                for velho, novo in trocas.items():
                    valor = valor.replace(velho, novo)
                doc.metadados["Authors with affiliations"] = valor
    return dict(feitas)


def _troca_ies(afiliacao: str, sinonimos: Sinonimos):
    """Troca a instituição dentro da afiliação ("Depto, Univ X, Cidade, País").

    Devolve (afiliação nova, (trecho antigo, trecho novo) ou None).
    """
    inteira = sinonimos.aplica(afiliacao)
    if inteira:
        return inteira, ((afiliacao, inteira) if inteira != afiliacao else None)
    nome = instituicao_da_afiliacao(afiliacao)
    novo = sinonimos.aplica(nome) if nome else None
    if novo and novo != nome:
        return afiliacao.replace(nome, novo, 1), (nome, novo)
    return afiliacao, None


# ------------------------------------------------------------------ autores


def autor_por_nome_completo(documentos: list[DocumentoFonte]) -> int:
    """Usa "Author full names" como identificador do autor quando existir.

    Só troca quando o documento tem tantos nomes completos quanto autores (a
    correspondência é por posição). Devolve quantos documentos foram alterados.
    """
    alterados = 0
    for doc in documentos:
        completos = [n.strip() for n in doc.autores_completos if n and n.strip()]
        if completos and len(completos) == len(doc.autores):
            doc.autores = list(dict.fromkeys(completos))
            alterados += 1
    return alterados


# ------------------------------------------------------------ palavras (radical)

_SUFIXOS = (
    # inglês
    ("ical", "ic"), ("ically", "ic"), ("ional", "ion"), ("ions", "ion"),
    # português e espanhol
    ("icas", "ic"), ("icos", "ic"), ("ica", "ic"), ("ico", "ic"),
    ("ional", "ion"), ("acoes", "acao"), ("aciones", "acion"),
)


def radical(palavra: str) -> str:
    """Radical simples de uma palavra (sem acentos, caixa baixa)."""
    p = sem_acentos(palavra or "").lower()
    p = re.sub(r"[^a-z0-9]", "", p)
    if len(p) <= 3:
        return p
    for sufixo, troca in _SUFIXOS:
        if p.endswith(sufixo) and len(p) - len(sufixo) >= 3:
            p = p[:-len(sufixo)] + troca
            break
    if p.endswith("ies") and len(p) > 4:
        p = p[:-3] + "y"
    elif p.endswith("es") and len(p) > 5 and not p.endswith("ses"):
        p = p[:-2]
    elif p.endswith("s") and len(p) > 3 and not p.endswith(("ss", "us", "is")):
        p = p[:-1]
    if p.endswith("al") and len(p) > 5:
        p = p[:-2]
    return p


def chave_radical(termo: str) -> str:
    partes = re.split(r"[\s\-_/]+", sem_acentos(termo or "").lower())
    return " ".join(radical(p) for p in partes if p)


def normaliza_palavras_por_radical(documentos: list[DocumentoFonte]) -> dict[str, list[str]]:
    """Une palavras-chave cujo radical, palavra a palavra, é igual.

    A grafia adotada é a mais frequente (empate: a mais curta e a ordem
    alfabética). Devolve {adotada: [variantes unidas]} para auditoria.
    """
    contagem: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for doc in documentos:
        for termo in list(doc.palavras_autor) + list(doc.palavras_fonte):
            k = chave_radical(termo)
            if k:
                contagem[k][termo] += 1
    adotada = {k: sorted(v.items(), key=lambda par: (-par[1], len(par[0]), par[0]))[0][0]
               for k, v in contagem.items()}
    for doc in documentos:
        doc.palavras_autor = list(dict.fromkeys(
            adotada.get(chave_radical(t), t) for t in doc.palavras_autor))
        doc.palavras_fonte = list(dict.fromkeys(
            adotada.get(chave_radical(t), t) for t in doc.palavras_fonte))
    return {adotada[k]: sorted(v) for k, v in contagem.items() if len(v) > 1}

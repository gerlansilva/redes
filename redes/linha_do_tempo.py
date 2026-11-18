"""Linha do tempo dos agrupamentos: dados da figura.

Uma faixa por agrupamento; cada item (palavra, autor, referência...) vira um nó
posicionado no ano médio dos documentos em que aparece (nas referências, no ano
da própria referência). O desenho está em ``viz.linha_do_tempo``.

A rede é a do corpus completo: todos os documentos do projeto, sem criar período
nem gravar nada (a base é aberta só para leitura). O agrupamento usa a mesma
configuração e o mesmo algoritmo da análise.

Limites da figura: no máximo ``max_nos`` nós (os mais frequentes, escolhidos
globalmente) e ``por_faixa`` por faixa. Arcos: só ligações internas à faixa
(as 3 mais fortes por nó) e as 6 ligações entre faixas mais fortes.
Rajadas: só as de pelo menos 3 documentos entre as 10 mais fortes do corpus.
"""
from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict

from . import pivos, rajadas
from .dataset import Dataset
from .pipeline import Configuracao, executa_periodo
from .text_utils import chave

MAX_NOS = 40
POR_FAIXA = 8
LIGACOES_POR_NO = 3
LIGACOES_CRUZADAS = 6
RAJADAS_MAXIMAS = 10
RAJADA_MIN_DOCUMENTOS = 3

_CONTROLES = re.compile(
    "[\x00-\x1f\x7f-\x9f‎‏‪-‮⁦-⁩﻿￾￿"
    "\ud800-\udfff]")


def limpa(texto) -> str:
    """Texto de uma linha, sem controles nem marcas bidirecionais."""
    if texto is None:
        return ""
    return " ".join(_CONTROLES.sub(" ", str(texto)).split())


class _TodosOsDocumentos:
    """Visão do projeto cujo ``dataset`` cobre todos os documentos."""

    def __init__(self, kb) -> None:
        self._kb = kb

    def __getattr__(self, nome):
        return getattr(self._kb, nome)

    def dataset(self, unidade: str, periodo_id=None,
                palavras: tuple[str, ...] = ("autor", "fonte")) -> Dataset:
        kb = self._kb
        construtor = getattr(kb, f"_unidade_{unidade}")
        ds = Dataset()
        vistos: set[int] = set()
        datas = [linha[0] for linha in kb.conexao.execute(
            "SELECT idPublishDate FROM PublishDate ORDER BY idPublishDate")]
        grupos = [kb._documentos(d) for d in datas]
        grupos.append(kb.conexao.execute(
            "SELECT * FROM Document WHERE PublishDate_idPublishDate IS NULL "
            "ORDER BY idDocument").fetchall())
        for documentos in grupos:
            for documento in documentos:
                doc_id = documento["idDocument"]
                if doc_id in vistos:
                    continue
                vistos.add(doc_id)
                ds.adiciona_documento(doc_id, documento["citationsCount"] or 0)
                if unidade == "Words":
                    kb._unidade_Words(ds, doc_id, palavras)
                else:
                    construtor(ds, doc_id)
        return ds


def _anos_das_referencias(conexao, teto: int | None) -> dict[int, int]:
    por_grupo: dict[int, list[int]] = defaultdict(list)
    try:
        linhas = conexao.execute(
            "SELECT ReferenceGroup_idReferenceGroup, year FROM Reference").fetchall()
    except Exception:
        return {}
    for grupo, ano in linhas:
        if grupo is None:
            continue
        try:
            valor = int(str(ano).strip()[:4])
        except (TypeError, ValueError):
            continue
        if 1400 <= valor <= (teto if teto else 2100):
            por_grupo[grupo].append(valor)
    return {g: statistics.median_low(v) for g, v in por_grupo.items()}


def _finito(valor) -> bool:
    try:
        return math.isfinite(float(valor))
    except (TypeError, ValueError, OverflowError):
        return False


def _arredonda(valor: float) -> int:
    return int(math.floor(valor + 0.5))


def _vazio(unidade: str, aviso: str, **extra) -> dict:
    dados = {"unidade": unidade, "faixas": [], "ligacoes": [], "anos": [],
             "atividade": False, "avisos": [aviso],
             "omitidos": {"itens": 0, "agrupamentos": 0, "sem_ano": 0, "descritores": 0}}
    dados.update(extra)
    return dados


def constroi(kb, config: Configuracao, max_nos: int = MAX_NOS,
             por_faixa: int = POR_FAIXA) -> dict:
    """Dados serializáveis da linha do tempo do corpus completo.

    Devolve ``faixas`` (``indice`` = posição em ``ResultadoPeriodo.grupos``;
    ``rotulo``; ``frequencia_total``; ``itens_total``; ``nos``), ``ligacoes``,
    ``anos`` ([min, max] dos nós ou ``[]``), ``atividade`` (se o ano do nó é um
    ano médio e há linha de atividade), ``avisos``, ``omitidos`` e ``unidade``.
    """
    max_nos = max(1, int(max_nos))
    por_faixa = max(1, int(por_faixa))
    resultado = executa_periodo(_TodosOsDocumentos(kb), 0, "Corpus", config)
    unidade = config.unidade
    conexao = kb.conexao

    if not resultado.grupos:
        return _vazio(unidade, "Nenhum agrupamento se formou no corpus completo com "
                               "estes parâmetros; não há o que mostrar na linha do tempo.")

    anos_doc = rajadas._anos_dos_documentos(conexao)
    por_documento = config.matriz != "CoOccurrence"
    referencias = unidade == "References" and not por_documento
    anos_ref = (_anos_das_referencias(conexao, max(anos_doc.values()) + 1 if anos_doc else None)
                if referencias else {})
    teto_ref = max(anos_doc.values()) + 1 if anos_doc else 2100
    atividade = not referencias and not por_documento

    # Termos-descritor (em mais da metade dos documentos): descrevem o corpus, não um
    # tema; ficam de fora, como nos pontos de virada.
    descritores: set[int] = set()
    if not por_documento:
        base = getattr(resultado, "dataset_original", None) or resultado.dataset
        total_docs = base.quantidade_documentos()
        if total_docs:
            descritores = {no for no, f in resultado.frequencia_nos.items()
                           if f / total_docs > pivos.PROPORCAO_DESCRITOR}
    posicao = "referencia" if referencias else "documento" if por_documento else "media"

    def anos_do_item(no: int) -> list[int]:
        if por_documento:
            return [anos_doc[no]] if no in anos_doc else []
        return [anos_doc[d] for d in resultado.dataset.docs_por_item.get(no, [])
                if d in anos_doc]

    # Rajadas: as 10 mais fortes do corpus, com 3 documentos ou mais.
    tipo_rajada = None if por_documento else {"Words": "palavras",
                                              "References": "referencias"}.get(unidade)
    forte: dict[str, dict] = {}
    if tipo_rajada:
        for linha in rajadas.calcula(conexao, tipo_rajada, limite=RAJADAS_MAXIMAS,
                                     minimo_documentos=RAJADA_MIN_DOCUMENTOS)["rajadas"]:
            if linha["documentos"] >= RAJADA_MIN_DOCUMENTOS:
                forte[chave(linha["termo"])] = linha

    candidatos = []                 # (indice, no_dict)
    sem_ano = 0
    omitidos_descritor = 0
    itens_por_faixa: dict[int, int] = {}
    frequencia_por_faixa: dict[int, int] = {}
    for indice, grupo in enumerate(resultado.grupos):
        itens_por_faixa[indice] = len(grupo.nos)
        frequencia_por_faixa[indice] = sum(
            int(resultado.frequencia_nos.get(n, 0)) for n in grupo.nos)
        for no in grupo.nos:
            if no in descritores:
                omitidos_descritor += 1
                continue
            if referencias:
                ano = anos_ref.get(no)
                primeiro = ultimo = ano
            else:
                ys = anos_do_item(no)
                ano = _arredonda(sum(ys) / len(ys)) if ys else None
                primeiro, ultimo = (min(ys), max(ys)) if ys else (None, None)
            if ano is None:
                sem_ano += 1
                continue
            nome = limpa(resultado.rotulo(no)) or f"Item {no}"
            # `forte` usa a chave (sem caixa nem pontuação): o nome exibido é legível,
            # o termo da rajada vem como está guardado.
            raj = forte.get(chave(nome)) if not por_documento else None
            candidatos.append((indice, {
                "id": int(no), "rotulo": nome, "ano": int(ano),
                "frequencia": int(resultado.frequencia_nos.get(no, 1)),
                "rajada": bool(raj),
                "rajada_inicio": int(raj["inicio"]) if raj and atividade else None,
                "rajada_fim": int(raj["fim"]) if raj and atividade else None,
                "primeiro": int(primeiro), "ultimo": int(ultimo)}))

    # Seleção global pelos mais frequentes, respeitando o teto por faixa.
    candidatos.sort(key=lambda c: (-c[1]["frequencia"], c[1]["rotulo"], c[1]["id"]))
    escolhidos: dict[int, list[dict]] = defaultdict(list)
    total = 0
    for indice, no in candidatos:
        if total >= max_nos:
            break
        if len(escolhidos[indice]) >= por_faixa:
            continue
        escolhidos[indice].append(no)
        total += 1

    faixas = []
    for indice in sorted(escolhidos, key=lambda i: (-frequencia_por_faixa[i], i)):
        nos = sorted(escolhidos[indice],
                     key=lambda n: (n["ano"], -n["frequencia"], n["rotulo"], n["id"]))
        faixas.append({"indice": indice,
                       "rotulo": limpa(resultado.grupos[indice].exibicao)
                       or f"Agrupamento {indice + 1}",
                       "frequencia_total": frequencia_por_faixa[indice],
                       "itens_total": itens_por_faixa[indice], "nos": nos})

    avisos: list[str] = []
    itens_total = sum(itens_por_faixa.values())
    itens_de_fora = itens_total - total - sem_ano - omitidos_descritor
    grupos_de_fora = len(resultado.grupos) - len(faixas)
    if omitidos_descritor:
        avisos.append(
            f"{omitidos_descritor} {'termo-descritor omitido' if omitidos_descritor == 1 else 'termos-descritor omitidos'}"
            f" (presentes em mais de {pivos.PROPORCAO_DESCRITOR:.0%} dos documentos: descrevem o "
            "corpus, não distinguem temas).")
    if sem_ano:
        if referencias:
            motivo = f"a referência não traz um ano válido, entre 1400 e {teto_ref}" if sem_ano == 1 \
                else f"as referências não trazem um ano válido, entre 1400 e {teto_ref}"
        elif not anos_doc:
            motivo = "nenhum documento do projeto traz o ano de publicação"
        else:
            motivo = ("os documentos do item não trazem o ano" if sem_ano == 1
                      else "os documentos dos itens não trazem o ano")
        avisos.append(f"{sem_ano} {'item sem ano foi omitido' if sem_ano == 1 else 'itens sem ano foram omitidos'}"
                      f" ({motivo}).")
    if itens_de_fora > 0 or grupos_de_fora > 0:
        partes = [f"{itens_de_fora} {'item ficou' if itens_de_fora == 1 else 'itens ficaram'} de fora"]
        if grupos_de_fora:
            partes.append(f"{grupos_de_fora} {'agrupamento ficou' if grupos_de_fora == 1 else 'agrupamentos ficaram'}"
                          " sem nenhum nó")
        avisos.append(f"A figura mostra os {total} itens mais frequentes (no máximo {max_nos} "
                      f"no total e {por_faixa} por faixa); " + " e ".join(partes) + ".")
    if not faixas:
        if referencias:
            decisivo = (f"Nenhuma referência dos agrupamentos tem ano válido (entre 1400 e "
                        f"{teto_ref}); não há o que mostrar na linha do tempo.")
        elif not anos_doc:
            decisivo = ("Nenhum documento do projeto traz o ano de publicação (todos os itens "
                        "ficaram sem ano); não há o que mostrar na linha do tempo.")
        else:
            decisivo = "Nenhum item dos agrupamentos tem ano; não há o que mostrar na linha do tempo."
        avisos.insert(0, decisivo)      # a API devolve o primeiro aviso como erro
        return {"unidade": unidade, "faixas": [], "ligacoes": [], "anos": [],
                "atividade": atividade, "posicao": posicao, "avisos": avisos,
                "omitidos": {"itens": max(itens_de_fora, 0), "agrupamentos": grupos_de_fora,
                             "sem_ano": sem_ano, "descritores": omitidos_descritor}}

    todos_anos = [n["ano"] for f in faixas for n in f["nos"]]
    a0, a1 = min(todos_anos), max(todos_anos)
    if a0 == a1:
        avisos.append(f"Todos os itens mostrados caem no mesmo ano ({a0}): a linha do tempo "
                      "não mostra evolução. Use um corpus que cubra mais de um ano.")

    # Ligações: internas à faixa (3 mais fortes por nó) e as 6 cruzadas mais fortes.
    faixa_de = {n["id"]: i for i, f in enumerate(faixas) for n in f["nos"]}
    vizinhos: dict[int, list[tuple[float, int]]] = defaultdict(list)
    cruzadas = []
    for a, b, valor in resultado.rede.arestas():
        # NaN e infinito passam por `valor <= 0`; sem este filtro viram stroke-width="nan".
        if (a not in faixa_de or b not in faixa_de
                or not _finito(valor) or valor <= 0):
            continue
        if faixa_de[a] == faixa_de[b]:
            vizinhos[a].append((valor, b))
            vizinhos[b].append((valor, a))
        else:
            cruzadas.append((valor, a, b))
    internas: dict[tuple[int, int], float] = {}
    for no, lista in vizinhos.items():
        lista.sort(key=lambda t: (-t[0], t[1]))
        for valor, outro in lista[:LIGACOES_POR_NO]:
            internas[(min(no, outro), max(no, outro))] = valor
    cruzadas.sort(key=lambda t: (-t[0], t[1], t[2]))
    ligacoes = [{"origem": a, "destino": b, "valor": round(float(v), 6), "cruzada": False}
                for (a, b), v in sorted(internas.items(), key=lambda t: (-t[1], t[0]))]
    ligacoes += [{"origem": a, "destino": b, "valor": round(float(v), 6), "cruzada": True}
                 for v, a, b in cruzadas[:LIGACOES_CRUZADAS]]

    return {"unidade": unidade, "faixas": faixas, "ligacoes": ligacoes,
            "anos": [a0, a1], "atividade": atividade, "posicao": posicao,
            "avisos": avisos,
            "omitidos": {"itens": max(itens_de_fora, 0), "agrupamentos": grupos_de_fora,
                         "sem_ano": sem_ano, "descritores": omitidos_descritor},
            "total_itens": itens_total, "total_agrupamentos": len(resultado.grupos)}

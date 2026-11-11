"""Qualidade dos agrupamentos de um período.

Responde, em linguagem simples, se a divisão em grupos "se sustenta" na rede:

* ``q``: força da divisão (modularidade de Newman ponderada pela similaridade;
  o item sem grupo conta como um grupo de um item só). Vai de cerca de 0
  (equivale a dividir ao acaso) até perto de 1 (grupos bem separados);
* ``q_louvain``: o mesmo cálculo para a partição do Louvain na mesma rede,
  como régua de comparação, e ``razao = q / q_louvain``;
* silhueta: quão mais perto cada item está do seu grupo do que dos demais
  (distância = 1 − similaridade normalizada, como em ``dendrograma``).

Tudo é determinístico. A silhueta é O(n²) em memória e tempo (matriz n×n de
float64: 2000 itens ≈ 32 MB); acima de ``LIMITE_NOS`` itens agrupados ela é pulada.

Valores em porcentagem (``pct_*``) vão de 0 a 100.
"""
from __future__ import annotations

import numpy as np

from .clustering import louvain

NIVEIS = ("ok", "atencao", "ruim", "indefinido")
MINIMO_NOS = 15
MINIMO_NOS_SILHUETA = 3
LIMITE_NOS = 2000       # acima disto a silhueta (matriz n×n) é dispensada


# ------------------------------------------------------------------ base


def _num(x: float, casas: int = 2, limiares: tuple = ()) -> str:
    """Número em pt-BR, com vírgula e o sinal "−" (U+2212) nos negativos.

    Perto de um limiar do selo (a menos de meia unidade da última casa), mostra
    uma casa a mais (ao menos 3 com 2 casas) e, se ainda assim o texto igualar o
    limiar sem que o valor o iguale, continua aumentando as casas: assim o texto
    nunca contradiz o selo (0,1496 não vira "0,15"). "-0,00" vira "0,00".
    """
    meia = 0.5 * 10.0 ** -casas
    perto = [t for t in limiares if abs(x - t) < meia]
    extra = 0
    if perto:
        extra = 1
        while extra < 5 and any(x != t and round(x, casas + extra) == t for t in perto):
            extra += 1
    texto = f"{x:.{casas + extra}f}"
    if float(texto) == 0:
        texto = texto.lstrip("-")
    return texto.replace(".", ",").replace("-", "\u2212")


def _grupo_do_no(grupos) -> dict[int, int]:
    destino: dict[int, int] = {}
    for indice, grupo in enumerate(grupos):
        for no in grupo.nos:
            destino.setdefault(no, indice)
    return destino


def modularidade(rede, particao: dict[int, int]) -> float | None:
    """Q de Newman ponderado. Nó fora de `particao` é um grupo de um nó.

    Devolve None quando a rede não tem ligação com peso positivo.
    """
    grau: dict[int, float] = {no: 0.0 for no in rede.nos}
    dois_m = 0.0
    dentro: dict[object, float] = {}
    for a, b, w in rede.arestas():
        if not w > 0:
            continue
        grau[a] += w
        grau[b] += w
        dois_m += 2.0 * w
        ga, gb = particao.get(a, ("s", a)), particao.get(b, ("s", b))
        if ga == gb:
            dentro[ga] = dentro.get(ga, 0.0) + 2.0 * w
    if dois_m <= 0:
        return None
    total: dict[object, float] = {}
    for no, g in grau.items():
        chave = particao.get(no, ("s", no))
        total[chave] = total.get(chave, 0.0) + g
    return sum(dentro.get(c, 0.0) / dois_m - (t / dois_m) ** 2
               for c, t in total.items())


def componentes(rede) -> int:
    """Componentes conexas (item isolado conta como uma)."""
    visto: set[int] = set()
    quantidade = 0
    for inicio in rede.nos:
        if inicio in visto:
            continue
        quantidade += 1
        pilha = [inicio]
        visto.add(inicio)
        while pilha:
            no = pilha.pop()
            for viz, w in rede.adjacencia.get(no, {}).items():
                if w > 0 and viz not in visto:
                    visto.add(viz)
                    pilha.append(viz)
    return quantidade


def _silhuetas(rede, grupos):
    """Silhueta por nó agrupado: (nós, rótulos de grupo, valores) ou None.

    Item de grupo de um só nó recebe 0, como no scikit-learn.
    """
    particao = _grupo_do_no(grupos)
    nos = [no for no in rede.nos if no in particao]
    n = len(nos)
    if n < 2:
        return None
    ids = sorted({particao[no] for no in nos})
    if len(ids) < 2:
        return None
    coluna = {no: i for i, no in enumerate(nos)}
    maximo = max((v for _, _, v in rede.arestas()), default=0.0)
    escala = maximo if maximo > 1.0 else 1.0
    dist = np.ones((n, n))
    np.fill_diagonal(dist, 0.0)
    for a, b, w in rede.arestas():
        if a in coluna and b in coluna:
            s = min(1.0, max(0.0, w) / escala)
            dist[coluna[a], coluna[b]] = dist[coluna[b], coluna[a]] = 1.0 - s
    posicao_do_grupo = {g: i for i, g in enumerate(ids)}
    rotulo = np.array([posicao_do_grupo[particao[no]] for no in nos])
    k = len(ids)
    onehot = np.zeros((n, k))
    onehot[np.arange(n), rotulo] = 1.0
    tamanho = onehot.sum(axis=0)
    soma = dist @ onehot                      # soma das distâncias a cada grupo
    proprio = tamanho[rotulo]
    with np.errstate(divide="ignore", invalid="ignore"):
        a_ = soma[np.arange(n), rotulo] / (proprio - 1.0)
        medias = soma / tamanho
    medias[np.arange(n), rotulo] = np.inf
    b_ = medias.min(axis=1)
    m = np.maximum(a_, b_)
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.where((proprio > 1) & (m > 0), (b_ - a_) / m, 0.0)
    return nos, np.array([ids[r] for r in rotulo]), s


def _silhuetas_validas(rede, grupos, limite_nos):
    """Silhuetas, ou None se for grande demais / impossível."""
    agrupados = len({no for g in grupos for no in g.nos})
    if agrupados > limite_nos:
        return None
    return _silhuetas(rede, grupos)


# ------------------------------------------------------------------ avaliação


AVISO_COAUTORIA = (
    "Em redes de coautoria, um Q alto costuma ser artefato: a rede é feita de "
    "pequenos grupos de coautores, que a modularidade premia mesmo sem estrutura "
    "temática. Leia o Q junto com o número de itens por agrupamento.")


def avalia(resultado, limite_nos: int = LIMITE_NOS) -> dict:
    """Indicadores de qualidade dos agrupamentos de um `ResultadoPeriodo`."""
    rede = resultado.rede
    grupos = list(resultado.grupos)
    n_nos = len(rede.nos)
    particao = _grupo_do_no(grupos)
    n_agrupados = sum(1 for no in rede.nos if no in particao)
    n_grupos = len(grupos)
    comp = componentes(rede) if n_nos else 0
    out: dict = {
        "n_nos": n_nos,
        "n_grupos": n_grupos,
        "pct_agrupados": 100.0 * n_agrupados / n_nos if n_nos else 0.0,
        "q": None, "q_louvain": None, "razao": None,
        "silhueta_media": None,
        "silhueta_por_grupo": {i: None for i in range(n_grupos)},
        "pct_silhueta_negativa": None,
        "componentes": comp,
        "nivel": "indefinido",
        "avisos": [],
    }
    avisos: list[str] = out["avisos"]

    if n_nos < MINIMO_NOS:
        if n_nos == 0:
            avisos.append(
                "A rede não tem itens; não dá para avaliar a qualidade dos "
                f"agrupamentos (mínimo de {MINIMO_NOS} itens).")
        else:
            avisos.append(
                f"A rede tem só {n_nos} {'item' if n_nos == 1 else 'itens'}; com "
                "tão poucos itens não dá para avaliar a qualidade dos "
                f"agrupamentos (mínimo de {MINIMO_NOS}).")
        return out
    if n_grupos < 2:
        avisos.append(
            "Há menos de dois agrupamentos; não dá para avaliar se a divisão "
            "em grupos faz sentido.")
        return out

    q = modularidade(rede, {no: g for no, g in particao.items()})
    if q is None:
        avisos.append("A rede não tem ligações com valor positivo; não dá para "
                      "avaliar os agrupamentos.")
        return out
    out["q"] = q

    try:
        conj = louvain(rede, 1, n_nos + 1)
        ql = modularidade(rede, {no: i for i, g in enumerate(conj.agrupamentos)
                                 for no in g.nos})
    except Exception:       # a comparação nunca pode derrubar a avaliação
        ql = None
    out["q_louvain"] = ql
    if ql is not None and ql > 0:
        out["razao"] = q / ql

    # Silhueta
    sil = _silhuetas_validas(rede, grupos, limite_nos)
    if sil is None and n_agrupados > limite_nos:
        avisos.append(
            f"A rede é grande ({n_agrupados} itens agrupados); a medida de "
            "coesão por item foi dispensada para não deixar a análise lenta.")
    elif sil is not None:
        nos, rotulos, valores = sil
        tamanhos = {i: len(set(g.nos)) for i, g in enumerate(grupos)}
        for i in range(n_grupos):
            if tamanhos[i] >= MINIMO_NOS_SILHUETA:
                sel = rotulos == i
                if sel.any():
                    out["silhueta_por_grupo"][i] = float(valores[sel].mean())
        validos = np.array([tamanhos[int(r)] >= MINIMO_NOS_SILHUETA for r in rotulos])
        if validos.any():
            out["silhueta_media"] = float(valores[validos].mean())
            out["pct_silhueta_negativa"] = float(100.0 * (valores[validos] < 0).mean())

    # Níveis
    ordem = {"ok": 0, "atencao": 1, "ruim": 2}
    nivel = "ok"

    def sobe(novo: str) -> None:
        nonlocal nivel
        if ordem[novo] > ordem[nivel]:
            nivel = novo

    if q < 0.15:
        sobe("ruim")
        avisos.append(
            f"A divisão em grupos é muito fraca (força {_num(q, 2, (0.15, 0.30))}): os itens "
            "de um grupo quase não se ligam mais entre si do que com os "
            "outros grupos.")
    elif q < 0.30:
        sobe("atencao")
        avisos.append(
            f"A divisão em grupos é moderada (força {_num(q, 2, (0.15, 0.30))}); os limites "
            "entre alguns grupos podem ser pouco nítidos.")
    if out["razao"] is not None and out["razao"] < 0.6:
        sobe("atencao")
        avisos.append(
            "Outro método de agrupamento acha uma divisão bem mais nítida "
            f"nesta rede (a atual alcança só {_num(100 * out['razao'], 0, (60,))}% "
            "dela); vale comparar.")
    sm = out["silhueta_media"]
    if sm is not None:
        if sm < 0:
            sobe("ruim")
            avisos.append(
                f"Em média, os itens estão mais perto de outros grupos do que "
                f"do próprio (coesão {_num(sm, 2, (0.0, 0.10))}).")
        elif sm < 0.10:
            sobe("atencao")
            avisos.append(
                f"Os grupos são pouco coesos (coesão média {_num(sm, 2, (0.0, 0.10))}): os "
                "itens ficam quase tão perto de outros grupos quanto do seu.")
    pn = out["pct_silhueta_negativa"]
    if pn is not None and pn > 30:
        sobe("atencao")
        avisos.append(
            f"{_num(pn, 0, (30,))}% dos itens estão mais perto de outro grupo do que "
            "do seu; talvez estejam mal alocados.")
    if out["pct_agrupados"] < 60:
        sobe("atencao")
        avisos.append(
            f"Só {_num(out['pct_agrupados'], 0, (60,))}% dos itens entraram em "
            "agrupamentos; o restante ficou de fora.")
    if comp > n_nos / 2:
        avisos.append(
            "A rede é fragmentada (quase só pares e itens isolados); um valor "
            "de força alto não indica qualidade.")
        if nivel == "ok":
            nivel = "atencao"
    if getattr(getattr(resultado, "configuracao", None), "unidade", None) == "Authors":
        avisos.append(AVISO_COAUTORIA)
        if nivel == "ok":
            nivel = "atencao"
    out["nivel"] = nivel
    return out


# ------------------------------------------------------------------ tabela


def _quadrante(grupo) -> str:
    """Mesma regra de `report._quadrante`."""
    if grupo.centralidade_faixa >= 0.5 and grupo.densidade_faixa >= 0.5:
        return "Motor"
    if grupo.densidade_faixa >= 0.5:
        return "Nicho"
    if grupo.centralidade_faixa >= 0.5:
        return "Básico"
    return "Emergente"


def anos_dos_documentos(kb, ids=None) -> dict[int, int]:
    """Ano de publicação por documento (campo do documento ou da data de publicação)."""
    try:
        linhas = kb.conexao.execute(
            "SELECT d.idDocument, d.year, p.year FROM Document d "
            "LEFT JOIN PublishDate p ON p.idPublishDate = d.PublishDate_idPublishDate")
    except Exception:
        return {}
    anos: dict[int, int] = {}
    for doc, ano_doc, ano_data in linhas:
        if ids is not None and doc not in ids:
            continue
        for bruto in (ano_doc, ano_data):
            texto = str(bruto).strip() if bruto is not None else ""
            if texto.isdigit():
                anos[doc] = int(texto)
                break
    return anos


def _avaliavel(rede, grupos) -> bool:
    """Os mesmos portões de `avalia` antes de qualquer número (senão, "indefinido")."""
    if len(rede.nos) < MINIMO_NOS or len(grupos) < 2:
        return False
    return modularidade(rede, _grupo_do_no(grupos)) is not None


def tabela_grupos(resultado, rotulos: dict | None = None, *, kb=None,
                  anos: dict[int, int] | None = None,
                  limite_nos: int = LIMITE_NOS) -> list[dict]:
    """Uma linha por agrupamento, do maior para o menor.

    `rotulos` é a saída de `rotulos.rotula_grupos` (ou índice → texto).
    `ano_medio` só existe se vier `anos` (documento → ano) ou `kb`; senão None.
    A chave `indice` é a posição em `resultado.grupos`.
    A silhueta segue os portões de `avalia`: None quando a avaliação é
    "indefinida" (poucos itens, menos de 2 grupos, sem ligações) ou dispensada
    pelo limite de itens.
    """
    grupos = list(resultado.grupos)
    sil = (_silhuetas_validas(resultado.rede, grupos, limite_nos)
           if _avaliavel(resultado.rede, grupos) else None)
    por_grupo: dict[int, float] = {}
    if sil is not None:
        _, rot, valores = sil
        for i, g in enumerate(grupos):
            if len(set(g.nos)) >= MINIMO_NOS_SILHUETA:
                sel = rot == i
                if sel.any():
                    por_grupo[i] = float(valores[sel].mean())
    if anos is None and kb is not None:
        todos = set()
        for g in grupos:
            todos |= set(g.documentos_nucleo)
        anos = anos_dos_documentos(kb, todos)
    ordem = sorted(range(len(grupos)), key=lambda i: (-len(grupos[i].nos), i))
    linhas = []
    for posicao, i in enumerate(ordem, start=1):
        g = grupos[i]
        novo = None
        if rotulos and i in rotulos:
            r = rotulos[i]
            novo = r.get("rotulo") if isinstance(r, dict) else str(r)
        docs = g.documentos_nucleo
        ys = [anos[d] for d in docs if anos and d in anos]
        linhas.append({
            "posicao": posicao,
            "indice": i,
            "rotulo": g.rotulo,
            "rotulo_novo": novo,
            "itens": len(g.nos),
            "silhueta": por_grupo.get(i),
            "ano_medio": sum(ys) / len(ys) if ys else None,
            "documentos_nucleo": len(docs),
            "quadrante": _quadrante(g),
            "centralidade": g.centralidade,
            "densidade": g.densidade,
        })
    return linhas

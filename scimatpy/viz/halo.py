"""Rede completa em halos, no estilo do atlas RELIME.

Cada agrupamento vira um halo translúcido; as arestas internas saem na cor do
halo e as ligações entre agrupamentos em cinza. Nós fora de qualquer
agrupamento viram pontos brancos, como no Pajek do SciMAT.

O layout é calculado uma vez por `layout_halo` e reaproveitado por duas saídas:
`halo_svg`, a figura estática exportável, e o JSON que alimenta o renderizador
interativo da interface web (zoom, rótulos e filtro de nós no navegador).
"""

from __future__ import annotations

import collections
import html
import itertools
import math

import networkx as nx
import numpy as np

from ..texto import exibe_termo, rotulo_legivel, termo_legivel

PALETA = ["#2F2BFF", "#00A344", "#6A3BFF", "#B45309", "#0B1F66", "#0E7490",
          "#8B5CF6", "#4D7C0F", "#9D174D", "#0369A1", "#A16207", "#7C3AED",
          "#0F766E", "#BE185D", "#DC2626"]
CINZA = "#8A94A6"


def cor_do_grupo(posicao: int) -> str:
    """Cor do agrupamento: a paleta fixa primeiro e, depois, tons distintos.

    Passado o fim da paleta, o ângulo áureo espalha os matizes e alterna
    luminosidade e saturação, para que nenhum agrupamento fique cinza.
    """
    if posicao < len(PALETA):
        return PALETA[posicao]
    extra = posicao - len(PALETA)
    matiz = (extra * 137.508 + 20) % 360
    luz = (0.40, 0.50, 0.33)[extra % 3]
    sat = (0.62, 0.55, 0.70)[extra % 3]
    c = (1 - abs(2 * luz - 1)) * sat
    x = c * (1 - abs((matiz / 60) % 2 - 1))
    m = luz - c / 2
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(matiz // 60) % 6]
    return "#%02X%02X%02X" % tuple(round((v + m) * 255) for v in (r, g, b))


CINZA_LIGACAO = "#CBD5E1"
TINTA = "#14204A"
TINTA_FRACA = "#64748B"

FONTE = "Inter, Arial, sans-serif"

UNIDADE_TITULO = {"Words": "palavras-chave", "Authors": "autores",
                  "References": "referências",
                  "AuthorsReference": "autores de referência",
                  "ReferenceSources": "fontes de referência",
                  "Countries": "países",
                  "Institutions": "instituições (IES)"}

# Abaixo disto a legenda cabe em uma coluna; acima, ela é distribuída.
LARGURA_COLUNA_LEGENDA = 236
COLUNAS_MAX_LEGENDA = 4


def _rotulo_curto(texto: str, unidade: str, limite: int = 30) -> str:
    """Nome legível do agrupamento: termo, autor ou referência abreviada."""
    import re

    texto = (texto or "Sem grupo").strip()

    if unidade == "Words":
        texto = termo_legivel(texto)
    elif unidade == "References":
        achado = re.match(r"^(.{2,34}?),\s*(\d{4})", texto)
        texto = (achado.group(1) + ", " + achado.group(2)) if achado else texto[:36]
    elif unidade == "ReferenceSources":
        texto = texto[:40]

    if len(texto) > limite:
        texto = texto[:limite - 1] + "…"
    return texto


def texto_rotulo_novo(rotulo, termos: int = 2) -> str | None:
    """Texto curto (até `termos` termos) de um rótulo novo.

    Aceita a saída de ``rotulos.rotula_grupos`` (dict com "termos"/"rotulo") ou um
    texto simples; devolve None se não houver rótulo utilizável.
    """
    if rotulo is None:
        return None
    if isinstance(rotulo, dict):
        lista = [t for t in (rotulo.get("termos") or []) if t]
        texto = " · ".join(lista[:termos]) if lista else str(rotulo.get("rotulo") or "")
    else:
        texto = str(rotulo)
    texto = " ".join(texto.split())
    # Os termos do rótulo vêm em minúsculas: inicial maiúscula e siglas em cada um.
    return rotulo_legivel(texto) or None


def nomes_por_rotulo(resultado, rotulos: dict | None) -> dict[int, str]:
    """Índice do agrupamento em ``resultado.grupos`` → rótulo novo curto.

    Só os agrupamentos com rótulo novo. A chave é o índice (identidade do
    agrupamento), não o texto do rótulo atual, que pode se repetir entre
    agrupamentos (ou ser "Sem grupo" em vários).
    """
    nomes: dict[int, str] = {}
    if not rotulos:
        return nomes
    for indice in range(len(resultado.grupos)):
        texto = texto_rotulo_novo(rotulos.get(indice))
        if texto:
            nomes[indice] = texto
    return nomes


def _nome_do_halo(indices, nomes: dict[int, str] | None) -> str | None:
    """Rótulo novo de uma entrada do halo; só se ela for um agrupamento só.

    (Agrupamentos de mesmo rótulo atual são desenhados juntos num halo só; aí
    nenhum dos nomes novos vale pelo conjunto e a legenda fica com o atual.)
    """
    indices = list(indices or ())
    return (nomes or {}).get(indices[0]) if len(indices) == 1 else None


def _nome_curto(texto: str, unidade: str, novo: str | None,
                limite: int = 30) -> str:
    """Rótulo novo (`novo`, quando existe) ou o atual, abreviado para a legenda."""
    if novo:
        novo = novo[:1].upper() + novo[1:]
        return novo if len(novo) <= limite else novo[:limite - 1] + "…"
    return _rotulo_curto(texto, unidade, limite)


def _tamanhos_por_posto(valores: dict[int, int]) -> dict[int, float]:
    """Três classes de espessura (7, 11, 15 px) por posto de frequência."""
    if not valores:
        return {}
    ordenados = sorted(valores.values())
    if len(ordenados) == 1:
        return {ordenados[0]: 11}
    corte1 = ordenados[max(0, len(ordenados) // 3 - 1)]
    corte2 = ordenados[max(0, 2 * len(ordenados) // 3 - 1)]
    classes = {}
    for valor in set(valores.values()):
        classes[valor] = 7 if valor <= corte1 else (11 if valor <= corte2 else 15)
    return classes


def geometria_legenda(quantidade: int, altura: int, topo: int = 118,
                      base: int = 40, passo_max: int = 24,
                      passo_min: int = 16) -> dict:
    """Colunas e passo da legenda para que ela caiba na altura disponível.

    Devolve `visiveis`, que pode ser menor que `quantidade` (com `restantes`)
    quando nem quatro colunas cabem; a figura então avisa quantos agrupamentos
    ficaram de fora em vez de vazar para fora do SVG.
    """
    disponivel = max(80, altura - base - topo)
    if quantidade <= 0:
        return {"colunas": 0, "linhas": 0, "passo": passo_max,
                "largura": LARGURA_COLUNA_LEGENDA, "visiveis": 0, "restantes": 0}

    for colunas in range(1, COLUNAS_MAX_LEGENDA + 1):
        linhas = math.ceil(quantidade / colunas)
        passo = min(passo_max, max(passo_min, disponivel // max(1, linhas)))
        if linhas * passo <= disponivel:
            return {"colunas": colunas, "linhas": linhas, "passo": passo,
                    "largura": LARGURA_COLUNA_LEGENDA,
                    "visiveis": quantidade, "restantes": 0}

    linhas = max(1, disponivel // passo_min)
    visiveis = linhas * COLUNAS_MAX_LEGENDA
    return {"colunas": COLUNAS_MAX_LEGENDA, "linhas": linhas,
            "passo": passo_min, "largura": LARGURA_COLUNA_LEGENDA,
            "visiveis": min(quantidade, visiveis),
            "restantes": max(0, quantidade - visiveis)}


def _separar(pos: np.ndarray, raios: np.ndarray, largura: float, altura: float,
             iteracoes: int, folga: float = 8.0,
             topo: float = 96.0, base: float = 40.0) -> np.ndarray:
    """Empurra halos sobrepostos em paralelo (versão vetorizada).

    A troca do laço em Python por operações NumPy não altera o resultado
    final, mas evita dezenas de segundos com muitos agrupamentos. A soma dos
    raios não muda entre as iterações e é calculada uma vez; a ordem das somas
    foi mantida, porque o layout é sensível a diferenças de arredondamento.
    """
    if len(pos) < 2:
        return pos
    precisa = raios[:, None] + raios[None, :] + folga
    for _ in range(iteracoes):
        delta = pos[:, None, :] - pos[None, :, :]
        # mesma conta de np.linalg.norm(delta, axis=2), sem a sobrecarga da chamada
        dist = np.sqrt(np.add.reduce(delta * delta, axis=2)) + 1e-6
        falta = np.maximum(precisa - dist, 0.0) / dist
        np.fill_diagonal(falta, 0.0)
        anterior = pos
        pos = pos + 0.5 * np.einsum("ij,ijk->ik", falta, delta)
        pos[:, 0] = np.clip(pos[:, 0], raios + 8, largura - raios - 8)
        pos[:, 1] = np.clip(pos[:, 1], raios + topo, altura - raios - base)
        # Sem sobreposição e sem nada a recortar, as iterações seguintes
        # repetiriam exatamente este estado: pode parar sem mudar o resultado.
        if not falta.any() and np.array_equal(pos, anterior):
            break
    return pos


def _separados(pos: np.ndarray, raios: np.ndarray, folga: float) -> bool:
    """Todos os pares de halos mantêm a distância mínima (versão vetorizada)."""
    if len(pos) < 2:
        return True
    x = pos[:, 0]
    y = pos[:, 1]
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    dist = np.sqrt(dx * dx + dy * dy)
    minimo = raios[:, None] + raios[None, :] + folga
    ok = dist >= minimo
    np.fill_diagonal(ok, True)
    return bool(ok.all())


def _relaxa_soltos(nodepos: dict, soltos: list[int], centros: np.ndarray,
                   raios: np.ndarray, dentro, iteracoes: int = 300) -> None:
    """Afasta os nós sem agrupamento uns dos outros e dos halos.

    É o mesmo relaxamento sequencial de sempre (cada empurrão já vale para o
    teste seguinte), com a diferença de que a busca do próximo par ou halo em
    conflito é vetorizada: o laço Python só roda nos conflitos, o que reduz o
    custo de O(iterações × nós × agrupamentos) chamadas de `norm` para algumas
    operações NumPy por nó. O resultado é o mesmo.
    """
    m = len(soltos)
    k = len(centros)
    if not m:
        return
    pontos = np.array([nodepos[no] for no in soltos], dtype=float)
    extras = np.array([abs(hash(no)) % 12 for no in soltos], dtype=float)
    limites_base = raios + 8 if k else raios

    for _ in range(iteracoes):
        # Pares de nós soltos: (a, b) em ordem lexicográfica, a < b.
        for a in range(m - 1):
            b = a + 1
            while b < m:
                dv = pontos[a] - pontos[b:]
                dist = np.sqrt((dv * dv).sum(axis=1)) + 1e-6
                perto = np.nonzero(dist < 16)[0]
                if not len(perto):
                    break
                b += int(perto[0])
                dvp = pontos[a] - pontos[b]
                distancia = np.linalg.norm(dvp) + 1e-6
                if distancia < 16:
                    passo = (16 - distancia) / 2 * dvp / distancia
                    pontos[a] += passo
                    pontos[b] -= passo
                b += 1

        # Cada nó solto contra os centros dos halos, na ordem dos halos.
        for j in range(m):
            if k:
                limites = limites_base + extras[j]
                i = 0
                while i < k:
                    dv = pontos[j] - centros[i:]
                    dist = np.sqrt((dv * dv).sum(axis=1)) + 1e-6
                    perto = np.nonzero(dist < limites[i:])[0]
                    if not len(perto):
                        break
                    i += int(perto[0])
                    dvi = pontos[j] - centros[i]
                    distancia = np.linalg.norm(dvi) + 1e-6
                    if distancia < limites[i]:
                        pontos[j] += (limites[i] - distancia) * dvi / distancia
                    i += 1
            pontos[j] = dentro(pontos[j])

    for j, no in enumerate(soltos):
        nodepos[no] = pontos[j]


def layout_halo(resultado, largura: int = 1280, altura: int = 780,
                legenda_largura: int = 300, rotulos: dict | None = None) -> dict:
    """Calcula posições de nós, halos, selos e arestas de uma rede.

    `rotulos` (opcional): índice em ``resultado.grupos`` → rótulo novo; quando
    existe, vira o `rotulo_curto` do agrupamento. Não altera a posição de nada.
    """
    unidade = resultado.configuracao.unidade
    nomes_novos = nomes_por_rotulo(resultado, rotulos)
    rede = resultado.rede

    grupos: dict[str, list[int]] = collections.defaultdict(list)
    origem: dict[str, list[int]] = collections.defaultdict(list)
    soltos: list[int] = []
    for posicao, grupo in enumerate(resultado.grupos):
        grupos[grupo.rotulo or "Sem grupo"].extend(grupo.nos)
        origem[grupo.rotulo or "Sem grupo"].append(posicao)
    # `grupos` e `origem` ficam com o rótulo guardado (chave); a exibição é `_nome_curto`.
    for no in rede.nos:
        if no not in resultado.conjunto.grupo_do_no:
            soltos.append(no)

    ordem = sorted(grupos, key=lambda chave: (-len(grupos[chave]), chave))
    lista = [grupos[chave] for chave in ordem]
    indice = {no: i for i, membros in enumerate(lista) for no in membros}
    k = len(lista)
    cores = [cor_do_grupo(i) for i in range(k)]

    legenda = geometria_legenda(
        k + (1 if soltos else 0), altura, topo=118, base=48)
    largura_legenda = (26 + max(1, legenda["colunas"]) * LARGURA_COLUNA_LEGENDA
                       if k or soltos else 0)
    largura_legenda = max(legenda_largura, largura_legenda)
    largura = max(largura, 880 + int(largura_legenda))
    pw = largura - largura_legenda
    ph = altura

    meta = collections.Counter()
    for a, b, _ in rede.arestas():
        if a in indice and b in indice and indice[a] != indice[b]:
            meta[tuple(sorted((indice[a], indice[b])))] += 1

    grafo_grupos = nx.Graph()
    grafo_grupos.add_nodes_from(range(k))
    for (i, j), peso in meta.items():
        grafo_grupos.add_edge(i, j, weight=peso)

    circulo = np.array([[0.5 + 0.34 * math.cos(2 * math.pi * i / max(1, k)),
                         0.5 + 0.34 * math.sin(2 * math.pi * i / max(1, k))]
                        for i in range(k)])

    if 1 < k <= 400 and grafo_grupos.number_of_edges() >= k:
        mola = nx.spring_layout(grafo_grupos, seed=4, weight="weight", k=1.2,
                                iterations=300)
        mola = np.array([mola[i] for i in range(k)])
        mola = (mola - mola.min(0)) / (np.ptp(mola, 0) + 1e-9)
        base = 0.65 * circulo + 0.35 * mola
    else:
        base = circulo

    unit = 30.0
    info = {}
    pos = np.zeros((k, 2))

    # Muitos agrupamentos tornam a separação vetorizada cara: reduz o esforço
    # sem mudar o desenho de redes pequenas, que é o caso comum.
    tentativas = 14 if k <= 50 else (5 if k <= 150 else 1)
    iteracoes = 600 if k <= 50 else (350 if k <= 150 else 120)
    refinos = 8 if k <= 150 else 2

    # O desenho interno de cada agrupamento não depende da escala: só o
    # diâmetro muda entre as tentativas. Calcula uma vez e reaproveita.
    internos: dict[int, tuple] = {}
    # Com centenas de agrupamentos o desenho interno de cada um não é legível;
    # menos iterações da mola mantêm o aspecto e cortam a maior parte do tempo.
    # Até 300 agrupamentos o resultado é o de sempre.
    iter_mola = 300 if k <= 300 else 120

    def desenho_interno(i: int) -> tuple:
        if i not in internos:
            membros = lista[i]
            sub = rede.subgrafo(membros)
            n = len(sub)
            if n == 1:
                q = {membros[0]: np.zeros(2)}
            elif n == 2:
                q = {membros[0]: np.array([-1.0, 0.0]),
                     membros[1]: np.array([1.0, 0.0])}
            else:
                bruto = nx.spring_layout(sub, seed=5, iterations=iter_mola,
                                         k=1.3 / math.sqrt(n), weight="weight")
                q = {no: np.array(v) for no, v in bruto.items()}
            pontos = np.array([q[no] for no in q])
            centro = pontos.mean(0)
            escala = max(1e-6, np.abs(pontos - centro).max())
            internos[i] = (sub, n, q, centro, escala)
        return internos[i]

    if k:
        for _ in range(tentativas):
            info = {}
            for i in range(len(lista)):
                sub, n, q, centro, escala = desenho_interno(i)
                diametro = unit * math.sqrt(n) + unit * 0.7
                info[i] = (sub, {no: (np.array(v) - centro) / escala * diametro / 2
                                 for no, v in q.items()}, diametro / 2 + 10)

            pos = np.array([np.array([40 + base[i, 0] * (pw - 80),
                                      90 + base[i, 1] * (ph - 130)]) for i in range(k)])
            raios = np.array([info[i][2] for i in range(k)])
            pos = _separar(pos, raios, pw, ph, iteracoes=iteracoes)

            separados = _separados(pos, raios, 2.0)
            if k == 1 or separados:
                break
            unit *= 0.9

        # Refinamento: separação de correção inteira e, se ainda houver
        # sobreposição, encolhimento gradual dos halos (com os nós).
        for _ in range(refinos):
            raios = np.array([info[i][2] for i in range(k)])
            pos = _separar(pos, raios, pw, ph,
                           iteracoes=min(400, iteracoes))

            separados = _separados(pos, raios, 6.0)
            if separados or k < 2:
                break

            for i in range(k):
                sub, q, r = info[i]
                info[i] = (sub, {no: deslocamento * 0.94
                                 for no, deslocamento in q.items()}, r * 0.94)
            pos = pos * 0.94 + np.array([pw / 2, (90 + ph - 40) / 2]) * 0.06

        # Enquadramento: layouts esparsos deixavam metade da área vazia.
        xs = np.concatenate([pos[:, 0] - [info[i][2] for i in range(k)],
                             pos[:, 0] + [info[i][2] for i in range(k)]])
        ys = np.concatenate([pos[:, 1] - [info[i][2] for i in range(k)],
                             pos[:, 1] + [info[i][2] for i in range(k)]])
        largura_usada = xs.max() - xs.min()
        altura_usada = ys.max() - ys.min()
        fator = min((pw - 100) / max(1e-6, largura_usada),
                    (ph - 170) / max(1e-6, altura_usada), 2.2)
        if fator > 1.0:
            cx = (xs.min() + xs.max()) / 2
            cy = (ys.min() + ys.max()) / 2
            pos[:, 0] = pw / 2 + (pos[:, 0] - cx) * fator
            pos[:, 1] = (90 + ph - 40) / 2 + (pos[:, 1] - cy) * fator

    nodepos: dict[int, np.ndarray] = {}
    for i, membros in enumerate(lista):
        _, q, _ = info[i]
        for no, deslocamento in q.items():
            nodepos[no] = np.array([pos[i][0] + deslocamento[0],
                                    pos[i][1] + deslocamento[1]])

    def _dentro(ponto: np.ndarray) -> np.ndarray:
        """Reflete o ponto para dentro da área útil, sem empilhar na borda."""
        baixo = np.array([20.0, 104.0])
        alto = np.array([pw - 20.0, ph - 44.0])
        faixa = alto - baixo
        deslocado = np.abs((ponto - baixo) % (2 * faixa) - faixa)
        return baixo + deslocado

    if soltos:
        for j, no in enumerate(soltos):
            angulo = 2 * math.pi * j / max(1, len(soltos)) + 0.4
            nodepos[no] = np.array([pw / 2 + math.cos(angulo) * pw * 0.42,
                                    ph / 2 + math.sin(angulo) * ph * 0.40])
        fixos = list(indice)
        if len(nodepos) <= 400:
            try:
                nodepos = nx.spring_layout(rede.para_networkx(), pos=nodepos,
                                           fixed=fixos, iterations=200, seed=6)
            except Exception:  # noqa: BLE001 - layout é opcional
                pass

        _relaxa_soltos(nodepos, soltos, pos,
                       np.array([info[i][2] for i in range(k)]), _dentro)

    selos = []
    for i in range(k):
        vetor = pos[i] - np.array([pw / 2, ph / 2])
        norma = np.linalg.norm(vetor)
        vetor = vetor / norma if norma > 1e-6 else np.array([0, -1.0])
        ponto = pos[i] + vetor * info[i][2]
        selos.append({
            "x": float(min(max(ponto[0], 30), pw - 30)),
            "y": float(min(max(ponto[1], 96), ph - 42)),
        })

    tamanhos = _tamanhos_por_posto(
        {no: resultado.frequencia_nos.get(no, 1) for no in rede.nos})

    nos = []
    for no in rede.nos:
        x, y = nodepos[no]
        grupo = indice.get(no)
        nos.append({
            "id": int(no),
            "rotulo": resultado.rotulo(no),
            "grupo": -1 if grupo is None else int(grupo),
            "frequencia": int(resultado.frequencia_nos.get(no, 1)),
            "grau": round(float(resultado.centralidades.get("grau", {}).get(no, 0)), 3),
            "centralidade": round(float(resultado.centralidades.get("grau", {}).get(no, 0)), 3),
            "raio": round(tamanhos.get(resultado.frequencia_nos.get(no, 1), 7) / 2, 2),
            "x": round(float(x), 2),
            "y": round(float(y), 2),
        })

    grupos_dados = []
    for i, membros in enumerate(lista):
        grupos_dados.append({
            "indice": i + 1,
            "rotulo": resultado.exibe(ordem[i]),
            "rotulo_original": ordem[i],
            "indices": list(origem[ordem[i]]),
            "rotulo_curto": _nome_curto(
                ordem[i], unidade, _nome_do_halo(origem[ordem[i]], nomes_novos)),
            "cor": cores[i],
            "nos": len(membros),
            "x": round(float(pos[i][0]), 2),
            "y": round(float(pos[i][1]), 2),
            "raio": round(float(info[i][2]), 2),
            "selo_x": round(selos[i]["x"], 2),
            "selo_y": round(selos[i]["y"], 2),
        })

    internas = []
    for i, membros in enumerate(lista):
        for a, b in info[i][0].edges():
            internas.append({"a": int(a), "b": int(b), "g": i})

    entre = [{"gi": i, "gj": j, "peso": int(peso)}
             for (i, j), peso in meta.items()]

    soltas = [{"a": int(a), "b": int(b)} for a, b, _ in rede.arestas()
              if not (a in indice and b in indice)]

    cruzadas = [{"a": int(a), "b": int(b), "peso": float(peso)}
                for a, b, peso in rede.arestas()
                if a in indice and b in indice and indice[a] != indice[b]]
    if len(cruzadas) > 600:
        # Acima disso o desenho volta ao traço agregado; não vale carregar
        # centenas de milhares de ligações até a interface.
        cruzadas = []

    return {
        "largura": int(largura),
        "altura": int(altura),
        "area": {"largura": int(pw), "altura": int(ph)},
        "legenda": legenda,
        "cores": cores,
        "grupos": grupos_dados,
        "soltos": [int(no) for no in soltos],
        "nos": nos,
        "internas": internas,
        "entre": entre,
        "cruzadas": cruzadas,
        "soltas": soltas,
        "meta": {
            "grupos": k,
            "nos": rede.quantidade_nos(),
            "arestas": rede.quantidade_arestas(),
            "soltos": len(soltos),
            "unidade": unidade,
        },
    }


def halo_svg(resultado, titulo: str, subtitulo: str = "", largura: int = 1280,
             altura: int = 780, legenda_largura: int = 300,
             layout: dict | None = None, rotulos: dict | None = None,
             pivos=None) -> str:
    """Desenha a rede completa de um `ResultadoPeriodo` como SVG.

    `rotulos` (opcional): índice em ``resultado.grupos`` → rótulo novo (saída de
    ``rotulos.rotula_grupos``); a legenda usa o novo (2 termos) quando existe.
    `pivos` (opcional): pontos de virada, em ordem (ids de nó ou dicionários com
    ``no``, como em ``pivos.pontos_de_virada``); cada um ganha um anel escuro numerado
    e a legenda "ponto de virada". Sem pivôs (ou ``None``) a saída não muda.
    """
    dados = layout or layout_halo(resultado, largura, altura, legenda_largura)
    unidade = resultado.configuracao.unidade
    rede = resultado.rede
    nomes_novos = nomes_por_rotulo(resultado, rotulos)

    largura = dados["largura"]
    altura = dados["altura"]
    pw = dados["area"]["largura"]
    ph = dados["area"]["altura"]
    grupos = dados["grupos"]
    k = len(grupos)
    cores = dados["cores"]
    legenda = dados["legenda"]

    nodepos = {no["id"]: np.array([no["x"], no["y"]]) for no in dados["nos"]}
    soltos = dados["soltos"]

    halos = "".join(
        f'<circle cx="{grupo["x"]:.0f}" cy="{grupo["y"]:.0f}" '
        f'r="{grupo["raio"]:.0f}" fill="{grupo["cor"]}" fill-opacity="0.09"/>'
        for grupo in grupos)

    ligacoes = ""
    cruzadas = dados.get("cruzadas") or []
    if cruzadas and len(cruzadas) <= 600:
        # Uma linha por cooperação entre agrupamentos diferentes, para que a
        # relação país–país não desapareça dentro de um traço agregado.
        ligacoes = "".join(
            f'<path d="M{nodepos[ligacao["a"]][0]:.1f} '
            f'{nodepos[ligacao["a"]][1]:.1f}'
            f'L{nodepos[ligacao["b"]][0]:.1f} '
            f'{nodepos[ligacao["b"]][1]:.1f}" '
            f'stroke-width="{1.0 + 0.9 * min(ligacao["peso"], 1.0):.2f}"/>'
            for ligacao in cruzadas)
    else:
        for ligacao in sorted(dados["entre"], key=lambda item: -item["peso"])[:30]:
            if ligacao["peso"] < 2:
                continue
            a = grupos[ligacao["gi"]]
            b = grupos[ligacao["gj"]]
            ligacoes += (f'<path d="M{a["x"]:.0f} {a["y"]:.0f}'
                         f'L{b["x"]:.0f} {b["y"]:.0f}" '
                         f'stroke-width="{1.2 + 0.35 * min(ligacao["peso"], 10):.1f}"/>')

    ligacoes_soltas = "".join(
        f'<path d="M{nodepos[ligacao["a"]][0]:.1f} {nodepos[ligacao["a"]][1]:.1f}'
        f'L{nodepos[ligacao["b"]][0]:.1f} {nodepos[ligacao["b"]][1]:.1f}" '
        f'stroke-width="0.9"/>'
        for ligacao in dados["soltas"])

    por_no = {no["id"]: no for no in dados["nos"]}
    arestas_por_grupo = collections.Counter(
        ligacao["g"] for ligacao in dados["internas"])
    grupos_svg = ""
    for i, grupo in enumerate(grupos):
        arestas = "".join(
            f'M{nodepos[ligacao["a"]][0]:.1f} {nodepos[ligacao["a"]][1]:.1f}'
            f'L{nodepos[ligacao["b"]][0]:.1f} {nodepos[ligacao["b"]][1]:.1f}'
            for ligacao in dados["internas"] if ligacao["g"] == i)
        pontos = collections.defaultdict(str)
        quantidade = 0
        for no in dados["nos"]:
            if no["grupo"] != i:
                continue
            quantidade += 1
            pontos[no["raio"] * 2] += f'M{no["x"]:.1f} {no["y"]:.1f}h0'

        opacidade = max(0.18, min(0.55, 8.0 / math.sqrt(max(1, arestas_por_grupo[i]))))
        grupos_svg += (f'<g stroke="{grupo["cor"]}" fill="none" stroke-linecap="round">'
                       f'<path d="{arestas}" stroke-width="1.4" opacity="{opacidade:.2f}"/>')
        for espessura, caminho in pontos.items():
            grupos_svg += f'<path d="{caminho}" stroke-width="{espessura}"/>'
        grupos_svg += "</g>"

    soltos_svg = ""
    for no in soltos:
        x, y = nodepos[no]
        raio = por_no[no]["raio"]
        soltos_svg += (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{raio:.1f}" '
                       f'fill="#ffffff" stroke="{TINTA_FRACA}" stroke-width="1.5"/>')

    selos = "".join(
        f'<circle cx="{grupo["selo_x"]:.0f}" cy="{grupo["selo_y"]:.0f}" r="17" '
        f'fill="#ffffff" stroke="{grupo["cor"]}" stroke-width="3"/>'
        f'<text x="{grupo["selo_x"]:.0f}" y="{grupo["selo_y"] + 6:.0f}" '
        f'text-anchor="middle" font-size="19" font-weight="700" fill="{grupo["cor"]}" '
        f'font-family="{FONTE}">{grupo["indice"]}</text>'
        for grupo in grupos)

    aneis_svg = ""
    marcados = []
    for item in (pivos or []):
        no = item.get("no") if isinstance(item, dict) else item
        if no in nodepos and no in por_no and no not in marcados:
            marcados.append(no)
    for numero, no in enumerate(marcados, start=1):
        x, y = nodepos[no]
        raio = por_no[no]["raio"] + 3.5
        aneis_svg += (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{raio:.1f}" fill="none" '
            f'stroke="#ffffff" stroke-width="5.2"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{raio:.1f}" fill="none" '
            f'stroke="{TINTA}" stroke-width="2.2"/>'
            f'<text x="{x + raio + 3:.1f}" y="{y - raio + 2:.1f}" font-size="11" '
            f'font-weight="700" fill="{TINTA}" font-family="{FONTE}" stroke="#ffffff" '
            f'stroke-width="3" paint-order="stroke">{numero}</text>')
    legenda_pivos = ""
    if marcados:
        legenda_pivos = (
            f'<circle cx="46" cy="{altura - 40}" r="6.5" fill="none" stroke="{TINTA}" '
            f'stroke-width="2.2"/>'
            f'<text x="60" y="{altura - 36}" font-size="11" fill="{TINTA}" '
            f'font-family="{FONTE}">ponto de virada (liga agrupamentos diferentes; o número '
            f'é o Nº da tabela)</text>')

    entradas = [("grupo", i) for i in range(k)]
    if soltos:
        entradas.append(("soltos", 0))
    visiveis = entradas[:legenda["visiveis"]]
    restantes = legenda["restantes"]
    if restantes and visiveis:
        visiveis[-1] = ("restantes", restantes)

    legenda_svg = ""
    passo = legenda["passo"]
    linhas = max(1, legenda["linhas"])
    for ordem_item, (tipo, valor) in enumerate(visiveis):
        coluna, linha = divmod(ordem_item, linhas)
        x = pw + 26 + coluna * LARGURA_COLUNA_LEGENDA
        y = 118 + linha * passo

        if tipo == "grupo":
            grupo = grupos[valor]
            legenda_svg += (
                f'<circle cx="{x}" cy="{y - 4}" r="10" fill="#ffffff" '
                f'stroke="{grupo["cor"]}" stroke-width="2.5"/>'
                f'<text x="{x}" y="{y + 1}" text-anchor="middle" font-size="11" '
                f'font-weight="700" fill="{grupo["cor"]}" '
                f'font-family="{FONTE}">{grupo["indice"]}</text>'
                f'<text x="{x + 18}" y="{y + 1}" font-size="12" fill="{TINTA}" '
                f'font-family="{FONTE}">{html.escape(_nome_curto(grupo["rotulo_original"], unidade, _nome_do_halo(grupo.get("indices"), nomes_novos)))} '
                f'<tspan fill="{TINTA_FRACA}">({grupo["nos"]})</tspan></text>')
        elif tipo == "soltos":
            legenda_svg += (
                f'<circle cx="{x}" cy="{y - 4}" r="7" fill="#ffffff" '
                f'stroke="{TINTA_FRACA}" stroke-width="1.5"/>'
                f'<text x="{x + 18}" y="{y + 1}" font-size="12" fill="{TINTA}" '
                f'font-family="{FONTE}">Sem agrupamento '
                f'<tspan fill="{TINTA_FRACA}">({len(soltos)})</tspan></text>')
        else:
            legenda_svg += (
                f'<text x="{x}" y="{y + 1}" font-size="11.5" fill="{TINTA_FRACA}" '
                f'font-family="{FONTE}">+ {valor} agrupamentos (ver tabela)</text>')

    subtitulo_original = subtitulo
    subtitulo = subtitulo or (f"{k} agrupamentos · {rede.quantidade_nos()} nós · "
                              f"{rede.quantidade_arestas()} arestas")
    if (not subtitulo_original and
            resultado.configuracao.matriz != "CoOccurrence"):
        subtitulo += " · nós = documentos"
    titulo = titulo.replace("{unidade}", UNIDADE_TITULO.get(unidade, unidade))

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{html.escape(titulo, quote=True)}" '
        f'viewBox="0 0 {largura} {altura}" width="{largura}" height="{altura}">'
        f'<rect width="{largura}" height="{altura}" fill="#ffffff"/>'
        f'<text x="40" y="38" font-size="17" font-weight="600" fill="{TINTA}" '
        f'font-family="{FONTE}">{html.escape(titulo)}</text>'
        f'<text x="40" y="60" font-size="12" fill="{TINTA_FRACA}" '
        f'font-family="{FONTE}">{html.escape(subtitulo)}</text>'
        f'<text x="{pw + 16}" y="86" font-size="11" font-weight="700" '
        f'fill="{TINTA_FRACA}" font-family="{FONTE}">AGRUPAMENTOS</text>'
        f'<g fill="none" stroke="{CINZA_LIGACAO}" stroke-linecap="round" '
        f'opacity="0.62">{ligacoes}</g>'
        f'{halos}'
        f'<g fill="none" stroke="{CINZA_LIGACAO}" stroke-linecap="round" '
        f'opacity="0.6">{ligacoes_soltas}</g>'
        f'{grupos_svg}{soltos_svg}{aneis_svg}{selos}{legenda_svg}{legenda_pivos}'
        f'<text x="40" y="{altura - 16}" font-size="10" fill="{TINTA_FRACA}" '
        f'font-family="{FONTE}">Redes · '
        f'halo = agrupamento; ponto branco = nó sem agrupamento</text>'
        f'</svg>'
    )

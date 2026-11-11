"""Algoritmos de agrupamento do SciMAT.

Porta `CentersSimpleGroupingAlgorithm` e as quatro variantes de ligação
(média, completa, simples e soma). O critério de desempate é a ordem da lista
de pares, como no original.
"""

from __future__ import annotations

import heapq

from .network import Cancelado, Rede


def _verifica(cancelado) -> None:
    if cancelado is not None and cancelado():
        raise Cancelado()


class Agrupamento:
    """Conjunto de nós com um nó principal opcional."""

    def __init__(self, nos, principal: int | None = None) -> None:
        self.nos: list[int] = sorted(set(nos))
        self.principal = principal

    def __len__(self) -> int:
        return len(self.nos)

    def __repr__(self) -> str:
        return f"Agrupamento({len(self.nos)} nós, principal={self.principal})"


class ConjuntoDeAgrupamentos:
    """Resultado do agrupamento sobre uma rede, com o índice nó → grupo."""

    def __init__(self, rede: Rede) -> None:
        self.rede = rede
        self.agrupamentos: list[Agrupamento] = []
        self.grupo_do_no: dict[int, int] = {}

    def adiciona(self, nos, principal: int | None = None) -> bool:
        nos = list(nos)
        if any(no not in self.rede.adjacencia for no in nos):
            return False
        if any(no in self.grupo_do_no for no in nos):
            return False
        posicao = len(self.agrupamentos)
        self.agrupamentos.append(Agrupamento(nos, principal))
        for no in nos:
            self.grupo_do_no[no] = posicao
        return True

    def nos_sem_grupo(self) -> list[int]:
        return [no for no in self.rede.nos if no not in self.grupo_do_no]

    def tamanhos(self) -> list[int]:
        return [len(a) for a in self.agrupamentos]


# ------------------------------------------------------------------ centros simples


def centros_simples(rede: Rede, tamanho_minimo: int, tamanho_maximo: int,
                    corte: float = 0.0, cancelado=None) -> ConjuntoDeAgrupamentos:
    """Aglomeração por centros de similaridade, na formulação do SciMAT.

    Percorre os pares em ordem decrescente de valor; quando um nó acumula
    `tamanho_atual - 1` pares vira semente e leva consigo os vizinhos de maior
    peso. Os pares usados são retirados da lista e a varredura recomeça.

    A varredura é incremental: depois de uma extração, os pares que sobram antes
    da posição da semente nunca atingem o limite (a varredura anterior já os
    percorreu sem acerto), então a contagem é ajustada em vez de recomeçar do
    zero. O resultado é idêntico ao da formulação literal (reler a lista
    inteira a cada extração), mas o custo cai de O(grupos x pares) para O(pares).
    """
    resultado = ConjuntoDeAgrupamentos(rede)
    pares = [list(par) for par in rede.arestas()]
    pares.sort(key=lambda par: -par[2])

    total = len(pares)
    origem = [par[0] for par in pares]
    destino = [par[1] for par in pares]
    vivo = [True] * total
    pares_do_no: dict[int, list[int]] = {}
    for indice in range(total):
        pares_do_no.setdefault(origem[indice], []).append(indice)
        pares_do_no.setdefault(destino[indice], []).append(indice)

    contagem: dict[int, int] = {}
    # Nenhum nó acumula mais pares do que o seu grau: os tamanhos acima do maior
    # grau só produziriam varreduras vazias (o resultado é o mesmo sem elas).
    # Nunca desce abaixo de `tamanho_minimo - 1`, que é onde a busca para.
    grau_maximo = max((len(v) for v in pares_do_no.values()), default=0)
    tamanho_atual = min(tamanho_maximo - 1, max(grau_maximo, tamanho_minimo - 1))
    restantes = total
    i = 0

    while restantes > 0 and tamanho_atual >= 1:
        _verifica(cancelado)
        # Varredura a partir de i, sobre os pares ainda vivos.
        semente = -1
        posicao = -1
        while i < total:
            if not i & 0x3FFF:
                _verifica(cancelado)
            if vivo[i]:
                a = origem[i]
                b = destino[i]
                contagem[a] = contagem.get(a, 0) + 1
                contagem[b] = contagem.get(b, 0) + 1
                if contagem[a] == tamanho_atual:
                    semente, posicao = a, i
                    break
                if contagem[b] == tamanho_atual:
                    semente, posicao = b, i
                    break
            i += 1

        if semente < 0:
            # Chegou ao fim sem acerto: reduz o tamanho e recomeça do zero.
            if tamanho_atual > tamanho_minimo - 1:
                contagem.clear()
                i = 0
                tamanho_atual -= 1
                continue
            break

        tema = [semente]
        for indice in reversed(pares_do_no[semente]):
            if indice > posicao or not vivo[indice]:
                continue
            tema.append(destino[indice] if origem[indice] == semente
                        else origem[indice])
        resultado.adiciona(tema, semente)

        # Retira todo par que toca o tema e ajusta a contagem do trecho já lido.
        for no in tema:
            for indice in pares_do_no.get(no, ()):
                if not vivo[indice]:
                    continue
                vivo[indice] = False
                restantes -= 1
                if indice <= posicao:
                    contagem[origem[indice]] -= 1
                    contagem[destino[indice]] -= 1
        i = posicao + 1

    return resultado


# ---------------------------------------------------------------- ligação hierárquica


def _medida_ligacao(valores: list[float], criterio: str) -> float:
    if criterio == "soma":
        return sum(valores)
    if criterio == "media":
        return sum(valores) / len(valores)
    if criterio == "completa":
        return min(valores)
    return max(valores)


def _ligacao(rede: Rede, tamanho_minimo: int, tamanho_maximo: int,
             criterio: str, corte: float = 0.0,
             cancelado=None) -> ConjuntoDeAgrupamentos:
    """Hierárquico aglomerativo com corte por similaridade e limite de tamanho.

    A formulação literal (reler todos os pares de grupos a cada fusão) é
    cúbica. Aqui o valor de cada par de grupos fica guardado e, a cada fusão,
    só os pares do grupo novo são refeitos a partir da lista de adjacência; os
    pares ficam num monte ordenado por (valor decrescente, posição). Os valores
    são somados na mesma ordem da formulação literal (grupo anterior na lista
    por fora, grupo posterior por dentro), então o resultado é idêntico,
    inclusive nos desempates e nos arredondamentos.
    """
    resultado = ConjuntoDeAgrupamentos(rede)
    adjacencia = rede.adjacencia

    # Cada grupo é identificado pela posição inicial do seu primeiro nó; a
    # ordem dos identificadores é a ordem dos grupos na lista do original.
    grupo_de = {no: i for i, no in enumerate(rede.nos)}
    posicao = {no: 0 for no in rede.nos}
    membros = {i: [no] for i, no in enumerate(rede.nos)}
    vizinhos: dict[int, set[int]] = {i: set() for i in membros}
    pares: dict[tuple[int, int], float] = {}
    monte: list[tuple[float, int, int]] = []

    def refaz(g: int) -> None:
        """Recalcula os pares entre o grupo g e todos os grupos ligados a ele."""
        por_grupo: dict[int, list[tuple[int, int, float]]] = {}
        for pa, a in enumerate(membros[g]):
            for b, valor in adjacencia[a].items():
                k = grupo_de[b]
                if k != g:
                    por_grupo.setdefault(k, []).append((pa, posicao[b], valor))
        for k, lista in por_grupo.items():
            if g < k:
                lista.sort(key=lambda t: (t[0], t[1]))
                chave = (g, k)
            else:
                lista.sort(key=lambda t: (t[1], t[0]))
                chave = (k, g)
            valor = _medida_ligacao([t[2] for t in lista], criterio)
            vizinhos[g].add(k)
            vizinhos[k].add(g)
            if valor > -1.0:             # também descarta NaN, como o original
                pares[chave] = valor
                heapq.heappush(monte, (-valor, chave[0], chave[1]))

    for g in list(membros):
        refaz(g)

    while True:
        _verifica(cancelado)
        melhor = None
        while monte:
            negativo, i, j = monte[0]
            if pares.get((i, j)) == -negativo:
                melhor = (i, j, -negativo)
                break
            heapq.heappop(monte)         # entrada velha
        if melhor is None or melhor[2] < corte:
            break
        i, j, _ = melhor
        if len(membros[i]) + len(membros[j]) > tamanho_maximo:
            break

        for g in (i, j):
            for k in vizinhos.pop(g):
                if k in vizinhos:
                    vizinhos[k].discard(g)
                pares.pop((g, k) if g < k else (k, g), None)
        deslocamento = len(membros[i])
        for no in membros[j]:
            grupo_de[no] = i
            posicao[no] += deslocamento
        membros[i] = membros[i] + membros.pop(j)
        vizinhos[i] = set()
        refaz(i)

    for g in sorted(membros):
        grupo = membros[g]
        if len(grupo) >= tamanho_minimo:
            resultado.adiciona(grupo, _no_principal(rede, grupo))

    return resultado


def ligacao_media(rede: Rede, minimo: int, maximo: int,
                  corte: float = 0.0,
                  cancelado=None) -> ConjuntoDeAgrupamentos:
    return _ligacao(rede, minimo, maximo, "media", corte, cancelado)


def ligacao_completa(rede: Rede, minimo: int, maximo: int,
                     corte: float = 0.0,
                     cancelado=None) -> ConjuntoDeAgrupamentos:
    return _ligacao(rede, minimo, maximo, "completa", corte, cancelado)


def ligacao_simples(rede: Rede, minimo: int, maximo: int,
                    corte: float = 0.0,
                    cancelado=None) -> ConjuntoDeAgrupamentos:
    return _ligacao(rede, minimo, maximo, "simples", corte, cancelado)


def ligacao_soma(rede: Rede, minimo: int, maximo: int,
                 corte: float = 0.0,
                 cancelado=None) -> ConjuntoDeAgrupamentos:
    return _ligacao(rede, minimo, maximo, "soma", corte, cancelado)


def _no_principal(rede: Rede, nos) -> int:
    """Nó de maior similaridade média, com o critério peculiar do original.

    O SciMAT compara todas as médias com a do primeiro nó e fica com o último
    nó cuja média seja menor que a primeira — não com o máximo. O resultado é
    replicado aqui para manter a paridade dos rótulos.
    """
    similaridades = []
    for no in nos:
        vizinhos = rede.vizinhos(no)
        if not vizinhos:
            similaridades.append(float("nan"))
        else:
            similaridades.append(sum(rede.valor(no, v) for v in vizinhos) / len(vizinhos))

    principal = nos[0]
    primeira = similaridades[0]
    for posicao in range(1, len(nos)):
        if primeira > similaridades[posicao]:
            principal = nos[posicao]
    return principal




# ------------------------------------------------------------------------ Louvain


def louvain(rede: Rede, tamanho_minimo: int, tamanho_maximo: int,
            corte: float = 0.0, cancelado=None) -> ConjuntoDeAgrupamentos:
    """Louvain em duas fases, com ajuste de tamanho, como no Bibliomapa.

    Detecta comunidades por modularidade, absorve grupos menores que o mínimo
    no vizinho mais forte e corta grupos maiores que o máximo pelas arestas de
    menor peso.
    """
    grafo = {no: dict(rede.adjacencia[no]) for no in rede.nos}
    particao = _detecta_comunidades(grafo, cancelado)
    grupos = _agrupa(particao)

    _verifica(cancelado)
    grupos = _junta_grupos_pequenos(grupos, grafo, tamanho_minimo, cancelado)
    grupos = _divide_grupos_grandes(grupos, grafo, tamanho_maximo, cancelado)
    grupos.sort(key=lambda grupo: (-len(grupo), min(grupo)))

    resultado = ConjuntoDeAgrupamentos(rede)
    for grupo in grupos:
        if len(grupo) >= max(2, tamanho_minimo):
            resultado.adiciona(grupo, _principal_por_grau(grupo, grafo))
    return resultado


def _detecta_comunidades(original: dict[int, dict[int, float]],
                         cancelado=None) -> dict[int, int]:
    grafo = {no: dict(vizinhos) for no, vizinhos in original.items()}
    pertence = {no: no for no in original}

    while True:
        _verifica(cancelado)
        particao = _move_nos(grafo, cancelado)
        if len(set(particao.values())) == len(grafo):
            break
        for no in pertence:
            pertence[no] = particao[pertence[no]]
        grafo = _agrega(grafo, particao)

    return pertence


def _move_nos(grafo: dict[int, dict[int, float]], cancelado=None) -> dict[int, int]:
    comunidade = {}
    graus = _graus(grafo)
    total_por_comunidade = {}
    dois_m = 0.0

    for no in grafo:
        comunidade[no] = no
        total_por_comunidade[no] = graus[no]
        dois_m += graus[no]

    if dois_m <= 0:
        return comunidade

    passadas = 0
    mudou = True
    while mudou and passadas < 100:
        mudou = False
        passadas += 1
        _verifica(cancelado)

        for no in list(grafo):
            atual = comunidade[no]
            peso_para: dict[int, float] = {}
            for vizinho, peso in grafo[no].items():
                destino = comunidade[vizinho]
                peso_para[destino] = peso_para.get(destino, 0.0) + peso

            total_por_comunidade[atual] -= graus[no]

            melhor = atual
            melhor_ganho = (peso_para.get(atual, 0.0)
                            - graus[no] * total_por_comunidade.get(atual, 0.0) / dois_m)

            for destino in sorted(peso_para):
                if destino == atual:
                    continue
                ganho = (peso_para[destino]
                         - graus[no] * total_por_comunidade.get(destino, 0.0) / dois_m)
                if ganho > melhor_ganho + 1e-9 or (
                        abs(ganho - melhor_ganho) <= 1e-9 and destino < melhor):
                    melhor_ganho = ganho
                    melhor = destino

            total_por_comunidade[melhor] = total_por_comunidade.get(melhor, 0.0) + graus[no]
            comunidade[no] = melhor
            if melhor != atual:
                mudou = True

    return comunidade


def _agrega(grafo, particao):
    representante = {}
    for no, grupo in particao.items():
        if grupo not in representante or no < representante[grupo]:
            representante[grupo] = no

    agregado = {representante[grupo]: {} for grupo in set(particao.values())}
    for no, vizinhos in grafo.items():
        origem = representante[particao[no]]
        for destino_no, peso in vizinhos.items():
            destino = representante[particao[destino_no]]
            agregado[origem][destino] = agregado[origem].get(destino, 0.0) + peso
    return agregado


def _graus(grafo):
    graus = {}
    for no, vizinhos in grafo.items():
        grau = 0.0
        for destino, peso in vizinhos.items():
            grau += 2 * peso if destino == no else peso
        graus[no] = grau
    return graus


def _agrupa(particao):
    grupos: dict[int, list[int]] = {}
    for no in sorted(particao):
        grupos.setdefault(particao[no], []).append(no)
    return list(grupos.values())


def _junta_grupos_pequenos(grupos, grafo, minimo, cancelado=None):
    resultado = [list(grupo) for grupo in grupos]
    grupo_do_no = {no: i for i, grupo in enumerate(resultado) for no in grupo}

    juntou = True
    while juntou:
        _verifica(cancelado)
        juntou = False
        for i in range(len(resultado)):
            if len(resultado[i]) < minimo:
                vizinho = _vizinho_mais_forte(resultado, i, grupo_do_no, grafo)
                if vizinho >= 0:
                    resultado[vizinho].extend(resultado[i])
                    for no in resultado[i]:
                        grupo_do_no[no] = vizinho
                    resultado.pop(i)
                    juntou = True
                    break
    return resultado


def _vizinho_mais_forte(grupos, indice, grupo_do_no, grafo):
    pesos: dict[int, float] = {}
    for no in grupos[indice]:
        for vizinho, peso in grafo[no].items():
            destino = grupo_do_no.get(vizinho)
            if destino is not None and destino != indice:
                pesos[destino] = pesos.get(destino, 0.0) + peso

    melhor = -1
    melhor_peso = -1.0
    for destino, peso in pesos.items():
        if peso > melhor_peso or (peso == melhor_peso and destino < melhor):
            melhor_peso = peso
            melhor = destino
    return melhor


def _divide_grupos_grandes(grupos, grafo, maximo, cancelado=None):
    resultado = []
    for grupo in grupos:
        if len(grupo) <= maximo:
            resultado.append(grupo)
        else:
            _verifica(cancelado)
            resultado.extend(_divide(grupo, grafo, maximo, cancelado))
    return resultado


def _divide(grupo, grafo, maximo, cancelado=None):
    """Retira as arestas mais fracas, uma a uma, até o grupo se partir.

    A formulação literal refaz os componentes a cada aresta retirada
    (quadrática). Como estar conexo só depende de quais arestas restam, basta
    achar o menor `k` tal que, sem as `k` mais fracas, o grupo fica
    desconexo: devolvendo as arestas à união-separação, da mais forte para a
    mais fraca, o primeiro instante em que o grafo vira um só componente dá
    `k - 1`. O resultado é o mesmo da formulação literal.
    """
    _verifica(cancelado)
    if len(grupo) <= 1:
        return [[no] for no in grupo]
    arestas = _arestas_internas(grupo, grafo)

    pai = {no: no for no in grupo}

    def raiz(no):
        while pai[no] != no:
            pai[no] = pai[pai[no]]
            no = pai[no]
        return no

    comp = len(grupo)
    k = 0                      # sem alcançar um só componente: já nasce desconexo
    for indice in range(len(arestas) - 1, -1, -1):
        a, b, _ = arestas[indice]
        ra, rb = raiz(a), raiz(b)
        if ra != rb:
            pai[ra] = rb
            comp -= 1
            if comp == 1:
                k = indice + 1
                break

    resultado = []
    for componente in _componentes(grupo, arestas, k):
        if len(componente) > maximo:
            resultado.extend(_divide(componente, grafo, maximo, cancelado))
        else:
            resultado.append(componente)
    return resultado


def _arestas_internas(grupo, grafo):
    dentro = set(grupo)
    arestas = []
    for no in grupo:
        for vizinho, peso in grafo[no].items():
            if vizinho > no and vizinho in dentro:
                arestas.append((no, vizinho, round(peso * 1_000_000)))
    arestas.sort(key=lambda a: (a[2], a[0], a[1]))
    return arestas


def _componentes(grupo, arestas, retiradas: int = 0):
    """Componentes do grupo sem as `retiradas` primeiras arestas (as mais fracas)."""
    pai = {no: no for no in grupo}

    def raiz(no):
        while pai[no] != no:
            no = pai[no]
        return no

    for a, b, _ in arestas[retiradas:]:
        raiz_a, raiz_b = raiz(a), raiz(b)
        if raiz_a != raiz_b:
            pai[max(raiz_a, raiz_b)] = min(raiz_a, raiz_b)

    por_raiz: dict[int, list[int]] = {}
    for no in grupo:
        por_raiz.setdefault(raiz(no), []).append(no)
    return list(por_raiz.values())


def _principal_por_grau(grupo, grafo):
    principal = grupo[0]
    for no in grupo:
        if _grau_no(no, grupo, grafo) > _grau_no(principal, grupo, grafo):
            principal = no
    return principal


def _grau_no(no, grupo, grafo):
    dentro = set(grupo)
    return sum(peso for vizinho, peso in grafo[no].items() if vizinho in dentro)


ALGORITMOS = {
    "CentersSimples": centros_simples,
    "AverageLink": ligacao_media,
    "CompleteLink": ligacao_completa,
    "SingleLink": ligacao_simples,
    "SumLink": ligacao_soma,
    "Louvain": louvain,
}

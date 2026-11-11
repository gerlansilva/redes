"""Dendrograma: clusterização hierárquica aglomerativa sobre uma `Rede`.

Python puro (sem numpy/scipy; redes de até ~200 nós). A distância entre dois
nós é ``1 - s``, com ``s`` a similaridade da rede (equivalência por padrão)
normalizada para [0, 1]: se o maior valor da rede passa de 1, divide-se por
ele; senão os valores ficam como estão. Par sem aresta tem similaridade 0 e
distância 1.

Convenções do resultado (`Dendrograma`, um ``dict`` serializável em JSON):

- ``nos``: identificadores dos nós; as folhas são numeradas por posição nesta
  lista (0..n-1) e as fusões criam os rótulos n, n+1, ... como no ``linkage``
  do scipy.
- ``fusoes``: ``[(a, b, altura, tamanho), ...]`` em ordem de fusão.
- ``ordem``: identificadores dos nós na ordem de desenho do dendrograma.
- ``alturas``: alturas das fusões (mesma ordem de ``fusoes``).
- ``coph``: correlação cofenética (Pearson) entre a distância original e a
  altura em que cada par se junta; 0.0 se não houver variância.
"""

from __future__ import annotations

import math
from collections import Counter

LIGACOES = ("media", "completa", "simples")
LIMITE_COPH = 0.6
POUCOS_NOS = 6


class Dendrograma(dict):
    """Resultado de `constroi`, com `corte` e `comparacao` como métodos."""

    def corte(self, n_grupos: int | None = None,
              altura: float | None = None) -> dict[int, int]:
        return corte(self, n_grupos=n_grupos, altura=altura)

    def comparacao(self, particao: dict[int, int],
                   grupos_rede: dict[int, int] | None = None) -> dict:
        return comparacao(particao, grupos_rede if grupos_rede is not None
                          else self.get("grupos_rede") or {})


# --------------------------------------------------------------- construção


def _distancias(rede, nos: list[int]) -> list[list[float]]:
    maximo = max((v for _, _, v in rede.arestas()), default=0.0)
    escala = maximo if maximo > 1.0 else 1.0
    n = len(nos)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        linha = rede.adjacencia.get(nos[i], {})
        for j in range(i + 1, n):
            s = max(0.0, linha.get(nos[j], 0.0)) / escala
            d = 1.0 - min(1.0, s)
            dist[i][j] = dist[j][i] = d
    return dist


def _liga(ligacao: str, d_ik: float, d_jk: float, ni: int, nj: int) -> float:
    if ligacao == "simples":
        return min(d_ik, d_jk)
    if ligacao == "completa":
        return max(d_ik, d_jk)
    return (ni * d_ik + nj * d_jk) / (ni + nj)


def _aglomera(dist: list[list[float]], ligacao: str):
    n = len(dist)
    d = [linha[:] for linha in dist]
    rotulo = list(range(n))
    tamanho = [1] * n
    ativos = list(range(n))
    fusoes = []
    for passo in range(n - 1):
        melhor = None
        for x, i in enumerate(ativos):
            linha = d[i]
            for j in ativos[x + 1:]:
                if melhor is None or linha[j] < melhor[0]:
                    melhor = (linha[j], i, j)
        altura, i, j = melhor
        a, b = sorted((rotulo[i], rotulo[j]))
        novo_tam = tamanho[i] + tamanho[j]
        for k in ativos:
            if k in (i, j):
                continue
            v = _liga(ligacao, d[i][k], d[j][k], tamanho[i], tamanho[j])
            d[i][k] = d[k][i] = v
        ativos.remove(j)
        rotulo[i] = n + passo
        tamanho[i] = novo_tam
        fusoes.append((a, b, altura, novo_tam))
    return fusoes


def _ordem_folhas(fusoes, n: int) -> list[int]:
    """Ordem de desenho (posições das folhas); o ramo maior vem primeiro."""
    if n == 1:
        return [0]
    filhos = {n + k: (f[0], f[1]) for k, f in enumerate(fusoes)}
    tam = {i: 1 for i in range(n)}
    menor = {i: i for i in range(n)}
    for k, f in enumerate(fusoes):
        tam[n + k] = f[3]
        menor[n + k] = min(menor[f[0]], menor[f[1]])
    ordem, pilha = [], [n + len(fusoes) - 1]
    while pilha:
        no = pilha.pop()
        if no < n:
            ordem.append(no)
            continue
        a, b = filhos[no]
        if (-tam[a], menor[a]) > (-tam[b], menor[b]):
            a, b = b, a
        pilha.append(b)
        pilha.append(a)
    return ordem


def _cofenetica(fusoes, n: int, dist) -> float:
    membros = {i: [i] for i in range(n)}
    coph = {}
    for k, (a, b, h, _) in enumerate(fusoes):
        ma, mb = membros.pop(a), membros.pop(b)
        for x in ma:
            for y in mb:
                coph[(min(x, y), max(x, y))] = h
        membros[n + k] = ma + mb
    xs = [dist[i][j] for (i, j) in coph]
    ys = list(coph.values())
    return _pearson(xs, ys)


def _pearson(xs, ys) -> float:
    m = len(xs)
    if m < 2:
        return 0.0
    mx, my = sum(xs) / m, sum(ys) / m
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 1e-15 or syy <= 1e-15:
        return 0.0
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


def _sugere(alturas: list[float], n: int) -> int:
    """Número de grupos pelo maior salto entre fusões consecutivas."""
    if n < 3:
        return n
    melhor_k, melhor_salto = 2, -1.0
    for k in range(2, min(n, 11)):
        # cortar em k grupos separa a fusão (n-k) [índice n-k-1] da seguinte
        salto = alturas[n - k] - alturas[n - k - 1]
        if salto > melhor_salto + 1e-12:
            melhor_k, melhor_salto = k, salto
    return melhor_k


def constroi(rede, ligacao: str = "media", nomes: dict[int, str] | None = None,
             pesos: dict[int, float] | None = None,
             grupos_rede: dict[int, int] | None = None) -> Dendrograma:
    """Dendrograma aglomerativo da `rede` (ligação média, completa ou simples)."""
    if ligacao not in LIGACOES:
        raise ValueError(f"ligação inválida: {ligacao!r}; use {', '.join(LIGACOES)}")
    nos = list(rede.nos)
    n = len(nos)
    if n == 0:
        raise ValueError("a rede não tem nós")
    dist = _distancias(rede, nos)
    fusoes = _aglomera(dist, ligacao) if n > 1 else []
    ordem_pos = _ordem_folhas(fusoes, n)
    alturas = [f[2] for f in fusoes]
    nomes = {no: (nomes or {}).get(no, str(no)) for no in nos}
    return Dendrograma(
        ligacao=ligacao,
        nos=nos,
        nomes=nomes,
        pesos={no: float(pesos[no]) for no in nos if pesos and no in pesos} or None,
        grupos_rede=dict(grupos_rede) if grupos_rede else None,
        ordem=[nos[p] for p in ordem_pos],
        fusoes=[tuple(f) for f in fusoes],
        alturas=alturas,
        coph=_cofenetica(fusoes, n, dist) if n > 2 else 0.0,
        n_grupos_sugerido=_sugere(alturas, n) if n > 1 else 1,
    )


# -------------------------------------------------------------------- cortes


def corte(resultado, n_grupos: int | None = None,
          altura: float | None = None) -> dict[int, int]:
    """Partição ``{no: grupo}`` por número de grupos ou por altura.

    Os grupos são numerados de 0 na ordem em que aparecem em ``ordem``.
    """
    nos, fusoes = resultado["nos"], resultado["fusoes"]
    n = len(nos)
    if (n_grupos is None) == (altura is None):
        raise ValueError("informe n_grupos ou altura (apenas um)")
    if n_grupos is not None:
        if not 1 <= int(n_grupos) <= n:
            raise ValueError(f"n_grupos deve estar entre 1 e {n}")
        aplicar = n - int(n_grupos)
    else:
        aplicar = sum(1 for f in fusoes if f[2] <= altura + 1e-12)
    pai = list(range(n + len(fusoes)))

    def raiz(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x

    for k in range(aplicar):
        a, b = fusoes[k][0], fusoes[k][1]
        pai[raiz(a)] = n + k
        pai[raiz(b)] = n + k
    posicao = {no: i for i, no in enumerate(nos)}
    numero, particao = {}, {}
    for no in resultado["ordem"]:
        r = raiz(posicao[no])
        particao[no] = numero.setdefault(r, len(numero))
    return particao


def altura_do_corte(resultado, n_grupos: int) -> float:
    """Altura que separa exatamente ``n_grupos`` grupos (ponto médio do salto)."""
    alturas, n = resultado["alturas"], len(resultado["nos"])
    if n_grupos >= n:
        return 0.0 if not alturas else alturas[0] / 2
    if n_grupos <= 1:
        return alturas[-1] if alturas else 0.0
    inferior, superior = alturas[n - n_grupos - 1], alturas[n - n_grupos]
    return (inferior + superior) / 2


# ----------------------------------------------------------------- comparação


def _comb2(x: int) -> float:
    return x * (x - 1) / 2


def comparacao(particao: dict[int, int], grupos_rede: dict[int, int]) -> dict:
    """ARI e informação mútua normalizada (média aritmética das entropias).

    Só entram os nós presentes nas duas partições; ``n_comparados`` informa
    quantos foram. Partições triviais idênticas valem 1.0.
    """
    comuns = [no for no in particao if no in (grupos_rede or {})]
    n = len(comuns)
    base = {"n_comparados": n,
            "n_grupos_corte": len({particao[no] for no in comuns}),
            "n_grupos_rede": len({grupos_rede[no] for no in comuns})}
    if n == 0:
        return {"ari": None, "nmi": None, **base}
    ca = Counter(particao[no] for no in comuns)
    cb = Counter(grupos_rede[no] for no in comuns)
    cab = Counter((particao[no], grupos_rede[no]) for no in comuns)
    soma_ab = sum(_comb2(v) for v in cab.values())
    soma_a = sum(_comb2(v) for v in ca.values())
    soma_b = sum(_comb2(v) for v in cb.values())
    total = _comb2(n)
    esperado = soma_a * soma_b / total if total else 0.0
    maximo = (soma_a + soma_b) / 2
    if abs(maximo - esperado) < 1e-12:
        ari = 1.0
    else:
        ari = (soma_ab - esperado) / (maximo - esperado)
    ha = -sum(v / n * math.log(v / n) for v in ca.values())
    hb = -sum(v / n * math.log(v / n) for v in cb.values())
    info = sum(v / n * math.log(v * n / (ca[i] * cb[j]))
               for (i, j), v in cab.items())
    if ha + hb < 1e-12:
        nmi = 1.0
    else:
        nmi = max(0.0, min(1.0, 2 * info / (ha + hb)))
    return {"ari": round(ari, 6), "nmi": round(nmi, 6), **base}


# --------------------------------------------------------------- interpretação


def _alturas_primeira_fusao(resultado) -> dict[int, float]:
    n = len(resultado["nos"])
    primeira = {}
    for k, (a, b, h, _) in enumerate(resultado["fusoes"]):
        for x in (a, b):
            if x < n and x not in primeira:
                primeira[x] = h
    return {resultado["nos"][i]: h for i, h in primeira.items()}


def _pares_proximos(resultado, limite: int = 3):
    n = len(resultado["nos"])
    return [(resultado["nos"][a], resultado["nos"][b], h)
            for a, b, h, _ in resultado["fusoes"] if a < n and b < n][:limite]


def _fmt(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def interpreta(resultado, n_grupos: int | None = None) -> list[str]:
    """Frases em português sobre o que o dendrograma mostra no corte dado."""
    nos = resultado["nos"]
    n = len(nos)
    nomes = resultado.get("nomes") or {}
    nome = lambda no: nomes.get(no, str(no))  # noqa: E731
    frases = []
    if n < 2:
        return ["A rede tem um único nó; não há hierarquia a interpretar."]
    if n_grupos is None:
        n_grupos = resultado.get("n_grupos_sugerido") or 2
    n_grupos = max(1, min(int(n_grupos), n))
    particao = corte(resultado, n_grupos=n_grupos)
    h_corte = altura_do_corte(resultado, n_grupos)
    contagem = Counter(particao.values())

    frases.append(
        f"O corte em {n_grupos} grupo{'s' if n_grupos != 1 else ''} "
        f"(altura ≈ {_fmt(h_corte)}, distância = 1 − similaridade) divide "
        f"{n} nós; quanto mais baixo o corte, mais temas específicos, e quanto "
        "mais alto, menos temas e mais amplos.")
    sem_arestas = not resultado["alturas"] or max(resultado["alturas"]) - min(resultado["alturas"]) < 1e-9
    if sem_arestas:
        frases.append("Os itens quase não têm ligações entre si: todas as fusões ocorrem "
                      "na mesma distância e não há estrutura hierárquica a interpretar.")
    elif n_grupos == resultado.get("n_grupos_sugerido"):
        frases.append("Esse número coincide com o maior salto entre fusões, "
                      "indício de uma separação natural em temas.")
    elif resultado.get("n_grupos_sugerido"):
        frases.append(
            f"O maior salto entre fusões sugere {resultado['n_grupos_sugerido']} "
            "grupos como separação mais natural.")

    grande, tam = contagem.most_common(1)[0]
    membros = [no for no in resultado["ordem"] if particao[no] == grande]
    pesos = resultado.get("pesos")
    if pesos:
        membros.sort(key=lambda no: -pesos.get(no, 0))
    exemplo = ", ".join(nome(no) for no in membros[:4])
    frases.append(
        f"O maior ramo tem {tam} {'nó' if tam == 1 else 'nós'} ({tam * 100 // n}% da rede), por exemplo: "
        f"{exemplo}{'…' if tam > 4 else ''}.")

    pares = _pares_proximos(resultado)
    if pares:
        txt = "; ".join(f"{nome(a)} e {nome(b)} (distância {_fmt(h)})"
                        for a, b, h in pares)
        frases.append(f"Os pares mais próximos são {txt}.")

    primeira = _alturas_primeira_fusao(resultado)
    valores = sorted(primeira.values())
    if len(valores) >= 4:
        q1 = valores[len(valores) // 4]
        q3 = valores[(3 * len(valores)) // 4]
        limite = q3 + 1.5 * (q3 - q1)
        tardios = sorted((no for no, h in primeira.items() if h > limite + 1e-12),
                         key=lambda no: -primeira[no])
        isolados = [no for no in nos if contagem[particao[no]] == 1]
        if tardios or isolados:
            lista = list(dict.fromkeys(tardios + isolados))[:5]
            frases.append(
                "Nós que se juntam tarde ou ficam isolados no corte (possíveis "
                "outliers ou temas periféricos): "
                + ", ".join(nome(no) for no in lista) + ".")

    grupos_rede = resultado.get("grupos_rede")
    if grupos_rede:
        comp = comparacao(particao, grupos_rede)
        if comp["ari"] is not None and comp["n_grupos_rede"] >= 2:
            ari = comp["ari"]
            nivel = ("alta" if ari >= 0.7 else "moderada" if ari >= 0.4
                     else "baixa")
            frases.append(
                f"Concordância {nivel} com os agrupamentos da rede: índice de "
                f"Rand ajustado {_fmt(ari)} e informação mútua normalizada "
                f"{_fmt(comp['nmi'])} ({comp['n_grupos_rede']} grupos na rede "
                f"contra {comp['n_grupos_corte']} no corte).")
            if ari < 0.4:
                frases.append(
                    "Divergência grande indica partição pouco robusta: os "
                    "temas dependem do método de agrupamento.")

    coph = resultado.get("coph", 0.0)
    if n < POUCOS_NOS:
        frases.append(f"Aviso: apenas {n} nós; a hierarquia tem pouco poder "
                      "de interpretação.")
    if n > 2 and coph < LIMITE_COPH:
        frases.append(
            f"Aviso: correlação cofenética {_fmt(coph)} (abaixo de 0,6); o "
            "dendrograma distorce as distâncias originais e deve ser lido com "
            "cautela. Tente outra ligação.")
    elif n > 2:
        frases.append(f"Correlação cofenética {_fmt(coph)}: o dendrograma "
                      "representa bem as distâncias originais.")
    return frases

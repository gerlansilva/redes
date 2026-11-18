"""Rede de um único agrupamento, para a página de cada cluster do relatório.

Layout circular: os nós do agrupamento ficam na circunferência, na ordem em
que aparecem no conjunto (o que mantém o desenho estável entre execuções), e as
arestas internas recebem espessura proporcional à similaridade. O rótulo de
cada nó fica fora do círculo, ancorado à direita ou à esquerda, para não
sobrepor o desenho.
"""

from __future__ import annotations

import html
import math

TINTA = "#14204A"
TINTA_FRACA = "#64748B"


def _ligacoes_txt(n: int) -> str:
    return f"{n} ligação interna" if n == 1 else f"{n} ligações internas"


def _novo_do_grupo(resultado, grupo, rotulos, termos: int = 3) -> str | None:
    """Rótulo novo do `grupo` (índice em ``resultado.grupos``), ou None."""
    if not rotulos:
        return None
    from .halo import texto_rotulo_novo
    for indice, g in enumerate(resultado.grupos):
        if g is grupo:
            return texto_rotulo_novo(rotulos.get(indice), termos)
    return None


def rede_agrupamento_svg(resultado, grupo, titulo: str,
                         largura: int = 720, rotulos: dict | None = None) -> str:
    """Rede de um agrupamento.

    `rotulos` (opcional): índice em ``resultado.grupos`` → rótulo novo (saída de
    ``rotulos.rotula_grupos``). Quando o agrupamento tem rótulo novo, o título passa
    a ser "período — rótulo novo" e o rótulo atual vira o subtítulo. Sem ele, o
    desenho é o de sempre.
    """
    novo = _novo_do_grupo(resultado, grupo, rotulos)
    subtitulo = None
    if novo:
        subtitulo = (grupo.exibicao or "Sem grupo")
        titulo = f"{resultado.periodo} — {novo}"
    nos = list(grupo.nos)
    limite_titulo = max(20, int((largura - 24) / 7.4))
    titulo_curto = titulo if len(titulo) <= limite_titulo else titulo[:limite_titulo - 1].rstrip() + "…"
    if not nos:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="120" '
            f'viewBox="0 0 {largura} 120"><rect width="100%" height="100%" '
            'fill="#ffffff"/>'
            f'<text x="{largura/2}" y="60" text-anchor="middle" '
            'font-family="Inter, Arial, sans-serif" font-size="14" fill="#64748B">'
            f'{html.escape(titulo_curto)} — agrupamento vazio</text></svg>')

    altura = max(400, min(980, 36 * len(nos)))
    desloca = 18 if subtitulo else 0     # espaço do subtítulo
    altura += desloca
    cx, cy = largura / 2, altura / 2 - 6 + desloca / 2
    raio = min(largura * 0.30, altura * 0.36)
    # No acoplamento os nós são documentos: o rótulo vem de `resultado.rotulos`.
    nomes_nos = {no: resultado.item(no) for no in nos}
    # Os rótulos (até 28 caracteres) ficam fora do círculo: reserva espaço
    # para o mais longo caber na lateral sem ser cortado.
    maior_rotulo = max(min(len(r), 28) for r in nomes_nos.values())
    raio = max(40.0, min(raio, cx - (maior_rotulo * 6.0 + 14 + 10)))

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" role="img" '
        f'aria-label="{html.escape(titulo)}">',
        f'<title>{html.escape(titulo)}</title>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{largura/2}" y="24" text-anchor="middle" '
        'font-family="Inter, Arial, sans-serif" font-size="14" fill="#14204A">'
        f'{html.escape(titulo_curto)}</text>',
    ]
    if subtitulo:
        curto = subtitulo if len(subtitulo) <= limite_titulo else subtitulo[:limite_titulo - 1].rstrip() + "…"
        partes.append(
            f'<text x="{largura/2}" y="42" text-anchor="middle" '
            'font-family="Inter, Arial, sans-serif" font-size="11.5" '
            f'fill="{TINTA_FRACA}">{html.escape(curto)}</text>')

    posicoes = {}
    for indice, no in enumerate(nos):
        angulo = 2 * math.pi * indice / len(nos) - math.pi / 2
        posicoes[no] = (cx + raio * math.cos(angulo),
                        cy + raio * math.sin(angulo))

    valores = [resultado.rede.valor(a, b) for a in nos for b in nos
               if a < b and resultado.rede.contem_aresta(a, b)]
    maximo = max(valores) if valores else 1.0

    for a in nos:
        for b in nos:
            if a >= b or not resultado.rede.contem_aresta(a, b):
                continue
            valor = resultado.rede.valor(a, b)
            (x1, y1), (x2, y2) = posicoes[a], posicoes[b]
            espessura = 0.6 + 2.8 * (valor / maximo if maximo else 0)
            partes.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="#CBD5E1" stroke-width="{espessura:.2f}" opacity="0.75"/>')

    margem_texto = 14
    for no in nos:
        x, y = posicoes[no]
        partes.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#EDEBFF" '
            'stroke="#2F2BFF" stroke-width="1.3"/>')
        direita = x >= cx
        ancora = "start" if direita else "end"
        deslocamento = margem_texto if direita else -margem_texto
        rotulo = nomes_nos[no]
        if len(rotulo) > 28:
            rotulo = rotulo[:26] + "…"
        partes.append(
            f'<text x="{x + deslocamento:.1f}" y="{y + 4:.1f}" text-anchor="{ancora}" '
            'font-family="Helvetica, Arial, sans-serif" font-size="10.5" '
            f'fill="{TINTA}">{html.escape(rotulo)}</text>')

    partes.append(
        f'<text x="{largura/2}" y="{altura - 12}" text-anchor="middle" '
        'font-family="Helvetica, Arial, sans-serif" font-size="10" '
        f'fill="{TINTA_FRACA}">{len(nos)} itens · '
        f'{_ligacoes_txt(sum(1 for a in nos for b in nos if a < b and resultado.rede.contem_aresta(a, b)))}'
        '</text>')
    partes.append("</svg>")
    return "\n".join(partes)


def rede_de_agrupamentos_svg(resultado, titulo: str,
                             largura: int = 1000, altura: int = 700,
                             rotulos: dict | None = None) -> str:
    """Rede de agrupamentos: cada nó é um tema; a aresta é a associação entre eles.

    A posição usa um layout de mola sobre os agrupamentos; a espessura e a
    opacidade da aresta seguem o índice de equivalência entre os conjuntos de
    itens dos dois temas (c(A,B)² / c(A)·c(B), a mesma medida de Callon). A cor
    do nó é o quadrante do diagrama estratégico e o raio, o número de itens.

    `rotulos` (opcional): índice em ``resultado.grupos`` → rótulo novo; o texto
    sobre cada nó usa o novo (2 termos) quando existe e o atual nos demais.
    """
    import networkx as nx

    from .strategic import _curtos, _quadrante, _quadrantes

    grupos = resultado.grupos
    if not grupos:
        raise ValueError("não há agrupamentos para desenhar")

    unidade = resultado.configuracao.unidade
    cores = _quadrantes(unidade)
    curtos = _curtos(unidade)
    from .halo import nomes_por_rotulo
    novos = nomes_por_rotulo(resultado, rotulos)
    rede = resultado.rede

    ordem = sorted(range(len(grupos)),
                   key=lambda i: (-len(grupos[i].nos), grupos[i].rotulo or "Sem grupo"))
    k = len(ordem)

    internos = []
    for i in ordem:
        internos.append(sum(v for _, _, v in rede.pares_internos(grupos[i].nos)))

    # Soma das arestas entre cada par de agrupamentos, numa passada só pelas
    # arestas da rede (antes: um teste de aresta por par de nós de cada par de
    # agrupamentos, o que levava minutos com centenas de agrupamentos).
    posicao_do_no = {}
    for posicao, i in enumerate(ordem):
        for dentro, no in enumerate(grupos[i].nos):
            posicao_do_no[no] = (posicao, dentro)
    brutas: dict[tuple[int, int], list[tuple[int, int, float]]] = {}
    for a, vizinhos in rede.adjacencia.items():
        origem = posicao_do_no.get(a)
        if origem is None:
            continue
        for b, valor in vizinhos.items():
            destino = posicao_do_no.get(b)
            if destino is not None and origem[0] < destino[0]:
                brutas.setdefault((origem[0], destino[0]), []).append(
                    (origem[1], destino[1], valor))
    # A soma segue a ordem original (nó de A, depois nó de B): a ordem das
    # parcelas muda o último dígito e o layout de mola é sensível a isso.
    entre = {par: sum(valor for _, _, valor in sorted(itens))
             for par, itens in brutas.items()}

    pesos = {}
    for (a, b) in sorted(entre):
        ca, cb = internos[a], internos[b]
        if ca <= 0 or cb <= 0:
            continue
        c_ab = entre[(a, b)]
        if c_ab <= 0:
            continue
        equivalencia = c_ab * c_ab / (ca * cb)
        if equivalencia >= 0.015:
            pesos[(a, b)] = equivalencia

    grafo = nx.Graph()
    grafo.add_nodes_from(range(k))
    for (a, b), peso in pesos.items():
        grafo.add_edge(a, b, weight=peso)

    if grafo.number_of_edges():
        # Com mais de 300 agrupamentos o ganho de 400 iterações é invisível e
        # o custo passa de segundos; até 300 o layout é o de sempre.
        pos = nx.spring_layout(grafo, seed=4, weight="weight", k=1.7,
                               iterations=400 if k <= 300 else 150)
    else:
        pos = nx.circular_layout(grafo)

    xs = [pos[i][0] for i in range(k)]
    ys = [pos[i][1] for i in range(k)]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    margem = 90.0

    def px(i: int) -> float:
        return margem + (pos[i][0] - min_x) / span_x * (largura - 2 * margem)

    def py(i: int) -> float:
        return margem + (pos[i][1] - min_y) / span_y * (altura - 2 * margem)

    tamanhos = [len(grupos[i].nos) for i in ordem]
    raio_max = max(tamanhos) if tamanhos else 1
    raios = [12 + 26 * math.sqrt(t / raio_max) for t in tamanhos]

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" '
        f'height="{altura}" viewBox="0 0 {largura} {altura}" role="img" '
        f'aria-label="{html.escape(titulo)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{largura/2}" y="30" text-anchor="middle" '
        'font-family="Helvetica, Arial, sans-serif" font-size="15" '
        f'font-weight="600" fill="{TINTA}">{html.escape(titulo)}</text>',
    ]

    max_peso = max(pesos.values()) if pesos else 1.0
    for (a, b), peso in pesos.items():
        razao = peso / max_peso
        espessura = 0.5 + 3.5 * razao
        opacidade = 0.28 + 0.60 * razao
        partes.append(
            f'<line x1="{px(a):.1f}" y1="{py(a):.1f}" '
            f'x2="{px(b):.1f}" y2="{py(b):.1f}" stroke="#64748B" '
            f'stroke-width="{espessura:.2f}" opacity="{opacidade:.2f}"/>')

    quadrantes_presentes = sorted({
        _quadrante(grupos[ordem[i]].centralidade_faixa,
                   grupos[ordem[i]].densidade_faixa) for i in range(k)})

    for i in range(k):
        grupo = grupos[ordem[i]]
        quadrante = _quadrante(grupo.centralidade_faixa, grupo.densidade_faixa)
        cor, fundo = cores[quadrante][1], cores[quadrante][2]
        x, y, r = px(i), py(i), raios[i]
        partes.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fundo}" '
            f'stroke="{cor}" stroke-width="1.6"/>')
        partes.append(
            f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" '
            'font-family="Helvetica, Arial, sans-serif" '
            f'font-size="{min(11.0, r / 2 + 7):.1f}" font-weight="700" '
            f'fill="{cor}">{ordem[i] + 1}</text>')
        novo = novos.get(ordem[i])
        rotulo = (novo[:1].upper() + novo[1:]) if novo else (grupo.exibicao or "Sem grupo")
        if len(rotulo) > 26:
            rotulo = rotulo[:24] + "…"
        partes.append(
            f'<text x="{x:.1f}" y="{y - r - 5:.1f}" text-anchor="middle" '
            'font-family="Helvetica, Arial, sans-serif" font-size="10" '
            f'fill="{TINTA}">{html.escape(rotulo)}</text>')

    # Legenda de quadrantes no rodapé.
    legenda = "  ·  ".join(
        f'{curtos[q]} {cores[q][1]}' for q in quadrantes_presentes)
    partes.append(
        f'<text x="{largura/2}" y="{altura - 14}" text-anchor="middle" '
        'font-family="Helvetica, Arial, sans-serif" font-size="10.5" '
        f'fill="{TINTA_FRACA}">{k} agrupamentos · {len(pesos)} associações'
        '  —  esfera ∝ itens  ·  {}</text>'.format(html.escape(legenda)))
    partes.append("</svg>")
    return "\n".join(partes)

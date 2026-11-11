"""Duplo mapa simplificado em SVG próprio (sem JavaScript): áreas das revistas que
publicam o corpus (esquerda) e das revistas citadas (direita).

Cada coluna reúne as revistas por **área** (bloco com barra colorida e nome da área);
as faixas entre as colunas ligam uma área da esquerda a uma área da direita e a
largura é o número de citações. Recebe o dicionário de `scimatpy.duplo_mapa.calcula`;
é puro e devolve o mesmo texto para os mesmos dados.

A classificação das áreas é aproximada (palavras do nome da revista) e a própria
figura diz isso no rodapé. Tudo o que é desenhado cabe dentro do SVG: os rótulos são
medidos e cortados com reticências, e o texto inteiro fica na dica (``<title>``).
"""
from __future__ import annotations

import hashlib
import itertools
import textwrap

from ..duplo_mapa import porcentagem
from .linha_do_tempo import largura as _largura_texto
from .linha_do_tempo import limpa

LARGURA = 1100
MARGEM = 16
TOPO_TITULO = 46
TOPO_CABECALHO = 30          # faixa dos títulos das colunas
LARGURA_BARRA = 14
LINHA = 18                   # altura mínima de uma revista
CABECA_AREA = 20             # faixa do nome da área, acima da barra
ENTRE_BLOCOS = 12
ALTURA_FLUXO = 360           # altura das faixas somadas, em cada coluna
ESCALA_MAX = 40.0            # pixels por citação, no máximo
ROTULO_MAX = 235             # largura máxima de um rótulo, em pixels
FONTE = "Inter, Arial, sans-serif"
TINTA = "#14204A"
TINTA_FRACA = "#64748B"
QUEBRA_RODAPE = 160


def _esc(texto) -> str:
    import html
    return html.escape(limpa(texto), quote=True)


def _cabe(texto: str, px: float, tamanho: float = 12.0, negrito: bool = False) -> str:
    texto = limpa(texto)
    if _largura_texto(texto, tamanho, negrito) <= px:
        return texto
    while len(texto) > 1 and _largura_texto(texto.rstrip() + "…", tamanho, negrito) > px:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _citacoes(n: int) -> str:
    return f"{n} citaç" + ("ão" if n == 1 else "ões")


def _revistas(n: int) -> str:
    return f"{n} revista" + ("" if n == 1 else "s")


def _ordem_direita(esq: list[str], dir_: list[str], fluxo: dict) -> list[str]:
    """Ordem das áreas da direita com menos cruzamentos de faixas (exaustivo até 6 áreas)."""
    posicao_esq = {a: i for i, a in enumerate(esq)}

    def custo(ordem):
        pos = {a: i for i, a in enumerate(ordem)}
        itens = [(posicao_esq[a], pos[b], n) for (a, b), n in fluxo.items()
                 if a in posicao_esq and b in pos]
        total = 0
        for i, (a1, b1, n1) in enumerate(itens):
            for a2, b2, n2 in itens[i + 1:]:
                if (a1 - a2) * (b1 - b2) < 0:
                    total += n1 * n2
        return total

    base = list(dir_)
    if len(base) <= 6:
        melhor = min(itertools.permutations(base), key=lambda o: (custo(o), [base.index(a) for a in o]))
        return list(melhor)

    def baricentro(a):
        pesos = [(posicao_esq[o], n) for (o, d), n in fluxo.items() if d == a and o in posicao_esq]
        soma = sum(n for _, n in pesos)
        return sum(p * n for p, n in pesos) / soma if soma else base.index(a)
    return sorted(base, key=lambda a: (baricentro(a), base.index(a)))


def layout(dados: dict, largura: int = LARGURA, topo: float = 0.0) -> dict:
    """Posições dos blocos, revistas e faixas (coordenadas do SVG)."""
    esquerda, direita = dados["esquerda"], dados["direita"]
    fluxos = {(f["origem"], f["destino"]): f["valor"] for f in dados["fluxos"]}
    ordem_esq = [a["nome"] for a in dados["areas"] if any(i["area"] == a["nome"] for i in esquerda)]
    ordem_dir = [a["nome"] for a in dados["areas"] if any(i["area"] == a["nome"] for i in direita)]
    ordem_dir = _ordem_direita(ordem_esq, ordem_dir, fluxos)

    total = sum(fluxos.values()) or 1
    escala = min(ESCALA_MAX, ALTURA_FLUXO / total)
    saida = {a: sum(n for (o, _), n in fluxos.items() if o == a) for a in ordem_esq}
    entrada = {a: sum(n for (_, d), n in fluxos.items() if d == a) for a in ordem_dir}

    cabecalhos = [limpa(c) for c in dados["colunas"]]
    maior_e = max([_largura_texto(i["nome"]) for i in esquerda]
                  + [_largura_texto(a, 12, True) for a in ordem_esq], default=0)
    maior_d = max([_largura_texto(i["nome"]) for i in direita]
                  + [_largura_texto(a, 12, True) for a in ordem_dir], default=0)
    larg_e = min(ROTULO_MAX, max(maior_e, _largura_texto(cabecalhos[0], 12, True)))
    larg_d = min(ROTULO_MAX, max(maior_d, _largura_texto(cabecalhos[1], 12, True)))
    x_barra_e = MARGEM + larg_e + 14
    x_barra_d = largura - MARGEM - larg_d - 14 - LARGURA_BARRA

    def coluna(ordem, itens, peso_area):
        blocos, y = [], 0.0
        for area in ordem:
            membros = [i for i in itens if i["area"] == area]
            corpo = max(len(membros) * LINHA, peso_area[area] * escala, LINHA)
            blocos.append({"area": area, "membros": membros, "y": y + CABECA_AREA, "h": corpo})
            y += CABECA_AREA + corpo + ENTRE_BLOCOS
        return blocos, max(0.0, y - ENTRE_BLOCOS)

    blocos_e, altura_e = coluna(ordem_esq, esquerda, saida)
    blocos_d, altura_d = coluna(ordem_dir, direita, entrada)
    altura = max(altura_e, altura_d)
    for blocos, h in ((blocos_e, altura_e), (blocos_d, altura_d)):
        deslocamento = topo + (altura - h) / 2
        for b in blocos:
            b["y"] += deslocamento
            n = max(1, len(b["membros"]))
            for k, m in enumerate(b["membros"]):
                m["y_centro"] = b["y"] + (k + 0.5) * b["h"] / n
    por_e = {b["area"]: b for b in blocos_e}
    por_d = {b["area"]: b for b in blocos_d}

    # Faixas: cada bloco empilha as suas, centradas na barra, na ordem do outro lado.
    faixas = []
    cursor_e = {a: por_e[a]["y"] + (por_e[a]["h"] - saida[a] * escala) / 2 for a in ordem_esq}
    cursor_d = {a: por_d[a]["y"] + (por_d[a]["h"] - entrada[a] * escala) / 2 for a in ordem_dir}
    pares = sorted(fluxos.items(), key=lambda kv: (ordem_dir.index(kv[0][1]), ordem_esq.index(kv[0][0])))
    por_origem: dict[str, list] = {}
    for (o, d), n in pares:
        por_origem.setdefault(o, []).append((d, n))
    topo_e: dict[tuple, float] = {}
    for o in ordem_esq:
        for d, n in sorted(por_origem.get(o, []), key=lambda t: ordem_dir.index(t[0])):
            topo_e[(o, d)] = cursor_e[o]
            cursor_e[o] += n * escala
    topo_d: dict[tuple, float] = {}
    for d in ordem_dir:
        for (o, dd), n in sorted(((k, v) for k, v in fluxos.items() if k[1] == d),
                                 key=lambda kv: ordem_esq.index(kv[0][0])):
            topo_d[(o, d)] = cursor_d[d]
            cursor_d[d] += n * escala
    for (o, d), n in pares:
        espessura = max(1.0, n * escala)
        faixas.append({"origem": o, "destino": d, "valor": n, "espessura": espessura,
                       "y0": topo_e[(o, d)], "y1": topo_d[(o, d)]})
    return {"blocos_e": blocos_e, "blocos_d": blocos_d, "x_barra_e": x_barra_e,
            "x_barra_d": x_barra_d, "altura": altura, "faixas": faixas, "escala": escala,
            "larg_e": larg_e, "larg_d": larg_d, "ordem_e": ordem_esq, "ordem_d": ordem_dir}


def _prefixo(dados: dict, titulo: str) -> str:
    base = repr((titulo, [(i["original"], i["valor"], i["area"]) for i in dados["esquerda"]],
                 [(i["original"], i["valor"], i["area"]) for i in dados["direita"]]))
    return "dm" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:6]


def _linhas_rodape(dados: dict) -> list[str]:
    c = dados["cobertura"]
    texto = [
        "Classificação aproximada: a área de cada revista é inferida por palavras do NOME da "
        "revista (sem base de categorias) e pode errar ou faltar; confira a tabela revista → área.",
        f"Desenhadas {c['desenhadas']} de {c['referencias']} citações com periódico "
        f"({len(dados['esquerda'])} de {_revistas(dados['total_esquerda'])} que publicam o corpus; "
        f"{len(dados['direita'])} de {_revistas(dados['total_direita'])} citadas). "
        f"Largura da faixa = citações da área da esquerda para a da direita. "
        f"Sem área: {porcentagem(c['pct_citadas_nao_classificadas'])} das citações recebidas "
        f"e {porcentagem(c['pct_revistas_nao_classificadas'])} das revistas."]
    saida = []
    for t in texto:
        saida.extend(textwrap.wrap(t, QUEBRA_RODAPE))
    return saida


def svg(dados: dict, titulo: str = "", largura: int = LARGURA, prefixo_id: str | None = None) -> str:
    """SVG do duplo mapa, ou "" quando não há o que desenhar."""
    if not dados or not dados.get("aplicavel") or not dados.get("fluxos"):
        return ""
    topo_t = TOPO_TITULO if titulo else 12
    cabeca_y = topo_t + 14
    d = layout(dados, largura, topo_t + TOPO_CABECALHO)
    rodape = _linhas_rodape(dados)
    altura = int(topo_t + TOPO_CABECALHO + d["altura"] + 22 + 15 * len(rodape) + 8)
    p = prefixo_id or _prefixo(dados, titulo)
    cores = dados["cores"]
    x_e, x_d = d["x_barra_e"], d["x_barra_d"]
    maiores = sorted(dados["fluxos"], key=lambda f: -f["valor"])[:3]
    desc = ("Duplo mapa: áreas das revistas que publicam o corpus (esquerda) e das revistas citadas "
            "(direita), com classificação aproximada por palavras do nome. Maiores fluxos: "
            + "; ".join(f"{f['origem']} para {f['destino']}, {_citacoes(f['valor'])}" for f in maiores)
            + ".")
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura} {altura}" '
         f'width="{largura}" height="{altura}" font-family="{FONTE}" role="img" '
         f'aria-labelledby="{p}-t {p}-d">',
         f'<title id="{p}-t">{_esc(titulo or "Duplo mapa de áreas das revistas")}</title>'
         f'<desc id="{p}-d">{_esc(desc)}</desc>',
         "<style>.dm-fx{fill-opacity:.4;transition:fill-opacity .12s}"
         ".dm-fx:hover{fill-opacity:.75}</style>",
         f'<rect width="{largura}" height="{altura}" fill="#fff"/>']
    if titulo:
        o.append(f'<text x="{largura / 2:.0f}" y="28" text-anchor="middle" font-size="16" '
                 f'font-weight="700" fill="{TINTA}">{_esc(_cabe(titulo, largura - 2 * MARGEM, 16, True))}'
                 "</text>")
    o.append(f'<text x="{x_e + LARGURA_BARRA:.1f}" y="{cabeca_y + 4}" text-anchor="end" '
             f'font-size="12" font-weight="700" fill="{TINTA_FRACA}">{_esc(dados["colunas"][0])}</text>')
    o.append(f'<text x="{x_d:.1f}" y="{cabeca_y + 4}" text-anchor="start" font-size="12" '
             f'font-weight="700" fill="{TINTA_FRACA}">{_esc(dados["colunas"][1])}</text>')

    o.append('<g class="dm-faixas">')
    for k, f in enumerate(d["faixas"]):
        x0, x1 = x_e + LARGURA_BARRA, x_d
        xm = (x0 + x1) / 2
        a0, a1 = f["y0"], f["y0"] + f["espessura"]
        b0, b1 = f["y1"], f["y1"] + f["espessura"]
        pct = next(g["pct"] for g in dados["fluxos"]
                   if g["origem"] == f["origem"] and g["destino"] == f["destino"])
        o.append(f'<path id="{p}-f{k}" class="dm-fx" fill="{cores.get(f["origem"], "#8A94A6")}" '
                 f'd="M{x0:.1f},{a0:.1f} C{xm:.1f},{a0:.1f} {xm:.1f},{b0:.1f} {x1:.1f},{b0:.1f} '
                 f'L{x1:.1f},{b1:.1f} C{xm:.1f},{b1:.1f} {xm:.1f},{a1:.1f} {x0:.1f},{a1:.1f} Z">'
                 f'<title>{_esc(f["origem"])} → {_esc(f["destino"])}: {_citacoes(f["valor"])} '
                 f'({porcentagem(pct)} das desenhadas)</title></path>')
    o.append("</g>")

    areas = {a["nome"]: a for a in dados["areas"]}
    for lado, blocos, x_barra in (("e", d["blocos_e"], x_e), ("d", d["blocos_d"], x_d)):
        o.append(f'<g class="dm-col-{lado}">')
        esq = lado == "e"
        larg = d["larg_e"] if esq else d["larg_d"]
        x_texto = x_barra - 12 if esq else x_barra + LARGURA_BARRA + 12
        ancora = "end" if esq else "start"
        for b in blocos:
            cor = cores.get(b["area"], "#8A94A6")
            a = areas[b["area"]]
            n_rev = len(b["membros"])
            fluxo = a["saida"] if esq else a["entrada"]
            dica = (f'{b["area"]}: {n_rev} revista' + ("" if n_rev == 1 else "s")
                    + f' desenhada' + ("" if n_rev == 1 else "s")
                    + f" · {_citacoes(fluxo)} nas faixas · área inferida pelo nome")
            o.append(f'<rect x="{x_barra:.1f}" y="{b["y"]:.1f}" width="{LARGURA_BARRA}" '
                     f'height="{b["h"]:.1f}" rx="2" fill="{cor}"><title>{_esc(dica)}</title></rect>')
            x_cab = x_barra + LARGURA_BARRA if esq else x_barra
            o.append(f'<text x="{x_cab:.1f}" y="{b["y"] - 6:.1f}" text-anchor="{ancora}" '
                     f'font-size="12" font-weight="700" fill="{TINTA}">'
                     f'<title>{_esc(dica)}</title>'
                     f'{_esc(_cabe(b["area"], larg + 12 + LARGURA_BARRA, 12, True))}</text>')
            for m in b["membros"]:
                y = m["y_centro"]
                rot = _cabe(m["nome"], larg)
                if esq:
                    o.append(f'<line x1="{x_barra - 6:.1f}" x2="{x_barra:.1f}" y1="{y:.1f}" y2="{y:.1f}" '
                             f'stroke="{cor}" stroke-width="2"/>')
                else:
                    o.append(f'<line x1="{x_barra + LARGURA_BARRA:.1f}" x2="{x_barra + LARGURA_BARRA + 6:.1f}" '
                             f'y1="{y:.1f}" y2="{y:.1f}" stroke="{cor}" stroke-width="2"/>')
                extra = (f'{m["valor"]} citaç' + ("ão feita" if m["valor"] == 1 else "ões feitas")
                         if esq else
                         f'{_citacoes(m["valor"])} das revistas desenhadas à esquerda'
                         + (f' ({m["total"]} no corpus)' if m.get("total") != m["valor"] else ""))
                termo = f' · termo: {m["termo"]}' if m.get("termo") else " · sem termo que case"
                o.append(f'<text x="{x_texto:.1f}" y="{y + 4:.1f}" text-anchor="{ancora}" font-size="12" '
                         f'fill="{TINTA}"><title>{_esc(m["nome"])} — {_esc(m["area"])}{_esc(termo)}'
                         f' · {_esc(extra)}</title>{_esc(rot)}</text>')
        o.append("</g>")

    y_rod = topo_t + TOPO_CABECALHO + d["altura"] + 24
    for n, linha in enumerate(rodape):
        o.append(f'<text x="{MARGEM}" y="{y_rod + 15 * n:.0f}" font-size="11" '
                 f'fill="{TINTA_FRACA}">{_esc(linha)}</text>')
    o.append("</svg>")
    return "\n".join(o)

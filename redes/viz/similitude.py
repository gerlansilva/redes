"""Figura da análise de similitude: grafo em halos por bloco, no estilo do IRaMuTeQ.

Recebe o dicionário de `redes.similitude.analisa_documentos` e devolve um SVG:
cada palavra é um círculo (área ~ frequência) com o rótulo ao lado; a árvore máxima
é desenhada em linhas cheias e as arestas extras em tracejado cinza; cada bloco
(comunidade de Louvain) ganha cor e uma mancha translúcida.

**Layout em dois níveis.** Primeiro cada bloco é arrumado sozinho (layout de molas sobre
as arestas internas, depois separação de caixas), num bloco compacto; depois os blocos
são dispostos entre si pelo grafo de blocos, sem que suas manchas se toquem. Assim os
halos não se entrelaçam e nada fica sobreposto.

**Largura do texto.** Não depende de PIL, de fontes instaladas nem do navegador: usa a
tabela de larguras por caractere já embutida em `linha_do_tempo.largura` (Inter, 12 px)
multiplicada por 1,20: a tabela subestima o Inter 500 em até 2% no pior rótulo, de modo que a
folga fica em ~7% sobre o Inter e ainda cobre o DejaVu Sans (a fonte de reserva mais larga). O viewBox é
calculado a partir da geometria (círculos, rótulos, manchas, legenda, rodapé), então nada
sai da área da figura, e a caixa de cada rótulo inclui essa folga, então rótulos não se
sobrepõem. A conferência no navegador (getBBox) está em `tests/test_similitude.py`.
"""
from __future__ import annotations

import html
import math

import networkx as nx
import numpy as np

from .halo import TINTA, TINTA_FRACA, cor_do_grupo
from .linha_do_tempo import largura as _largura_base
from .linha_do_tempo import limpa

FONTE = "Inter, Arial, sans-serif"
FOLGA_TEXTO = 1.20
LARGURA_MINIMA = 680.0
MARGEM = 14.0
FOLGA_HALO = 20.0           # espessura da mancha ao redor do bloco
RAIO_MIN, RAIO_MAX = 4.5, 14.0
FONTE_MIN, FONTE_MAX = 11.5, 20.5
LARGURA_COLUNA_LEGENDA = 280.0
QUEBRA_RODAPE_PX = 1.0       # fração da largura útil
SEMENTE_LAYOUT = 3


def largura_texto(texto: str, px: float, negrito: bool = False) -> float:
    """Largura estimada (px) do texto na fonte ``px``, com folga para fontes substitutas."""
    return _largura_base(texto, px, negrito) * FOLGA_TEXTO


def _esc(texto) -> str:
    return html.escape(limpa(str(texto)), quote=True)


def _f(x: float) -> str:
    return f"{x:.1f}"


def _cabe(texto: str, px: float, tamanho: float, negrito: bool = False) -> str:
    texto = limpa(texto)
    if largura_texto(texto, tamanho, negrito) <= px:
        return texto
    while len(texto) > 1 and largura_texto(texto.rstrip(", ") + "…", tamanho, negrito) > px:
        texto = texto[:-1]
    return texto.rstrip(", ") + "…"


def _quebra(texto: str, px: float, tamanho: float) -> list[str]:
    """Quebra por palavras para que cada linha caiba em ``px``."""
    linhas: list[str] = []
    atual = ""
    for palavra in limpa(texto).split():
        teste = f"{atual} {palavra}".strip()
        if atual and largura_texto(teste, tamanho) > px:
            linhas.append(atual)
            atual = palavra
        else:
            atual = teste
    if atual:
        linhas.append(atual)
    return linhas


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


# ------------------------------------------------------------------ geometria

def tamanhos(res: dict) -> dict[str, dict]:
    """Raio, fonte e largura do rótulo de cada forma (posição ainda zerada)."""
    formas = res["formas"]
    fr = [f["frequencia"] for f in formas]
    fmin, fmax = min(fr), max(fr)
    nos = {}
    for f in formas:
        t = math.sqrt((f["frequencia"] - fmin) / max(fmax - fmin, 1))
        r = RAIO_MIN + (RAIO_MAX - RAIO_MIN) * t
        fs = FONTE_MIN + (FONTE_MAX - FONTE_MIN) * t
        txt = limpa(f["forma"])
        nos[f["id"]] = dict(r=r, fs=fs, tw=largura_texto(txt, fs), txt=txt, x=0.0, y=0.0,
                            com=f["comunidade"], freq=f["frequencia"], resumos=f["resumos"],
                            idioma=f["idioma"])
    return nos


def caixa(d: dict, folga: float = 3.0) -> tuple[float, float, float, float]:
    """Caixa (x0, y0, x1, y1) do círculo mais o rótulo à direita."""
    h = max(2 * d["r"], 1.25 * d["fs"]) + 2 * folga
    return (d["x"] - d["r"] - folga, d["y"] - h / 2, d["x"] + d["r"] + 4 + d["tw"] + folga, d["y"] + h / 2)


def _remove_sobreposicao(nos: dict, ids: list[str], iters: int = 400) -> None:
    for _ in range(iters):
        moveu = False
        for i, ia in enumerate(ids):
            a = nos[ia]
            ba = caixa(a)
            for ib in ids[i + 1:]:
                b = nos[ib]
                bb = caixa(b)
                dx = min(ba[2], bb[2]) - max(ba[0], bb[0])
                dy = min(ba[3], bb[3]) - max(ba[1], bb[1])
                if dx > 0 and dy > 0:
                    moveu = True
                    if dy * 1.6 < dx:                       # rótulos são largos: separa na vertical
                        s = 1 if a["y"] < b["y"] or (a["y"] == b["y"] and ia < ib) else -1
                        a["y"] -= s * (dy / 2 + 0.5)
                        b["y"] += s * (dy / 2 + 0.5)
                    else:
                        s = 1 if (ba[0] + ba[2]) <= (bb[0] + bb[2]) else -1
                        a["x"] -= s * (dx / 2 + 0.5)
                        b["x"] += s * (dx / 2 + 0.5)
                    ba = caixa(a)
        if not moveu:
            break


def layout(res: dict, usa_extras: bool = True, semente: int = SEMENTE_LAYOUT) -> dict[str, dict]:
    """Posição de cada forma: blocos compactos dispostos sem que as manchas se toquem."""
    nos = tamanhos(res)
    com = {i: d["com"] for i, d in nos.items()}
    cids = sorted(set(com.values()))
    arvore = [(a["origem"], a["destino"]) for a in res["arestas"] if a["tipo"] == "arvore"]
    extras = [(a["origem"], a["destino"]) for a in res["arestas"] if a["tipo"] == "extra"] if usa_extras else []
    blocos: dict[int, dict] = {}
    for c in cids:
        mem = sorted(i for i in nos if com[i] == c)
        H = nx.Graph()
        H.add_nodes_from(mem)
        for u, v in arvore:
            if com[u] == c and com[v] == c:
                H.add_edge(u, v, weight=1.0)
        for u, v in extras:
            if com[u] == c and com[v] == c and not H.has_edge(u, v):
                H.add_edge(u, v, weight=0.35)
        pedacos = [sorted(x) for x in nx.connected_components(H)]
        pedacos.sort(key=lambda p: p[0])
        for a, b in zip(pedacos, pedacos[1:]):
            H.add_edge(a[0], b[0], weight=0.1)
        if len(mem) == 1:
            pos = {mem[0]: np.array([0.0, 0.0])}
        else:
            pos = nx.spring_layout(H, weight="weight", k=1.5 / math.sqrt(len(mem)), iterations=300, seed=semente)
        area = sum((2 * nos[i]["r"] + 4 + nos[i]["tw"]) * max(2 * nos[i]["r"], 1.25 * nos[i]["fs"]) for i in mem)
        L = math.sqrt(area * 4.5)
        P = np.array([pos[i] for i in mem])
        P = (P - P.mean(0)) / (np.ptp(P, axis=0).max() / 2 + 1e-9) * (L / 2)
        for k, i in enumerate(mem):
            nos[i]["x"], nos[i]["y"] = float(P[k, 0]), float(P[k, 1])
        _remove_sobreposicao(nos, mem, 300)
        cx = (min(caixa(nos[i], 1.0)[0] for i in mem) + max(caixa(nos[i], 1.0)[2] for i in mem)) / 2
        cy = (min(caixa(nos[i], 1.0)[1] for i in mem) + max(caixa(nos[i], 1.0)[3] for i in mem)) / 2
        for i in mem:
            nos[i]["x"] -= cx
            nos[i]["y"] -= cy
        rad = max(math.hypot(x, y) for i in mem for x, y in [
            (caixa(nos[i], 1.0)[0], caixa(nos[i], 1.0)[1]), (caixa(nos[i], 1.0)[2], caixa(nos[i], 1.0)[1]),
            (caixa(nos[i], 1.0)[0], caixa(nos[i], 1.0)[3]), (caixa(nos[i], 1.0)[2], caixa(nos[i], 1.0)[3])])
        blocos[c] = dict(mem=mem, r=rad + FOLGA_HALO + 5.0)
    # grafo dos blocos
    S = nx.Graph()
    S.add_nodes_from(cids)
    for u, v in arvore + extras:
        a, b = com[u], com[v]
        if a != b:
            S.add_edge(a, b, weight=S.get_edge_data(a, b, {"weight": 0})["weight"] + 1.0)
    if len(cids) == 1:
        sp = {cids[0]: np.array([0.0, 0.0])}
    else:
        pedacos_s = [sorted(x) for x in nx.connected_components(S)]
        pedacos_s.sort(key=lambda p: p[0])
        S2 = S.copy()
        for a, b in zip(pedacos_s, pedacos_s[1:]):
            S2.add_edge(a[0], b[0], weight=0.2)
        sp = nx.spring_layout(S2, weight="weight", k=1.2, iterations=300, seed=semente)
    P = np.array([sp[c] for c in cids])
    P = P - P.mean(0)
    span = np.ptp(P, axis=0) + 1e-9
    P = P / span * 2
    area_tot = sum(math.pi * blocos[c]["r"] ** 2 for c in cids)
    P = P * (math.sqrt(area_tot / math.pi) * 0.85)
    cen = {c: P[k].copy() for k, c in enumerate(cids)}
    for it in range(3000):
        moveu = False
        for i, a in enumerate(cids):
            for b in cids[i + 1:]:
                d = cen[b] - cen[a]
                dist = float(np.hypot(*d)) + 1e-9
                if dist == 1e-9:                      # centros iguais: separa em direção fixa
                    d = np.array([1.0, 0.0])
                    dist = 1.0
                need = blocos[a]["r"] + blocos[b]["r"]
                if dist < need:
                    moveu = True
                    push = d / dist * (need - dist) / 2 * 1.02
                    cen[a] -= push
                    cen[b] += push
        for c in cids:
            cen[c] -= cen[c] * 0.01
        for a, b, dd in S.edges(data=True):
            d = cen[b] - cen[a]
            dist = float(np.hypot(*d)) + 1e-9
            need = blocos[a]["r"] + blocos[b]["r"]
            if dist > need:
                pull = d / dist * min(dist - need, 6.0) * 0.06 * min(dd["weight"], 6)
                cen[a] += pull
                cen[b] -= pull
        if not moveu and it > 400:
            break
    # garantia final: sem sobreposição de blocos (o puxão pode ter encostado alguns)
    for _ in range(500):
        moveu = False
        for i, a in enumerate(cids):
            for b in cids[i + 1:]:
                d = cen[b] - cen[a]
                dist = float(np.hypot(*d)) + 1e-9
                need = blocos[a]["r"] + blocos[b]["r"]
                if dist < need - 0.01:
                    moveu = True
                    push = (d / dist if dist > 1e-6 else np.array([1.0, 0.0])) * (need - dist) / 2 * 1.02
                    cen[a] -= push
                    cen[b] += push
        if not moveu:
            break
    for c in cids:
        for i in blocos[c]["mem"]:
            nos[i]["x"] += float(cen[c][0])
            nos[i]["y"] += float(cen[c][1])
    return nos


# ------------------------------------------------------------------------ SVG

def _titulo_bloco(info: dict, multi: bool) -> str:
    sufixo = f" [{'/'.join(i.upper() for i in info['idiomas'])}]" if multi else ""
    return f"{info['id']}. {info['nome']} ({info['n']}){sufixo}"


def svg(res: dict, titulo: str = "", prefixo_id: str | None = None, mostrar_extras: bool = True,
        rodape: str | None = None) -> str:
    """SVG da análise de similitude, ou "" quando não há o que desenhar."""
    if not res or len(res.get("formas") or []) < 2:
        return ""
    from ..similitude import texto_parametros
    nos = layout(res, mostrar_extras)
    com = {i: d["com"] for i, d in nos.items()}
    ids_com = sorted(set(com.values()))
    cor = {c: cor_do_grupo(k) for k, c in enumerate(ids_com)}
    arvore = [a for a in res["arestas"] if a["tipo"] == "arvore"]
    extras = [a for a in res["arestas"] if a["tipo"] == "extra"] if mostrar_extras else []
    wmax = max([a["peso"] for a in arvore + extras] + [1e-9])
    p = prefixo_id or "sim"

    halos = {}
    for c in ids_com:
        pts = []
        for i, d in nos.items():
            if com[i] == c:
                x0, y0, x1, y1 = caixa(d, 1.0)
                pts += [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        halos[c] = _hull(pts)
    xs, ys = [], []
    for h in halos.values():
        for x, y in h:
            xs += [x - FOLGA_HALO - 1, x + FOLGA_HALO + 1]
            ys += [y - FOLGA_HALO - 1, y + FOLGA_HALO + 1]
    gx0, gx1, gy0, gy1 = min(xs), max(xs), min(ys), max(ys)
    M = MARGEM
    cx_graf = (gx0 + gx1) / 2
    larg = max(gx1 - gx0 + 2 * M, LARGURA_MINIMA)
    vx0, vx1 = cx_graf - larg / 2, cx_graf + larg / 2
    util = larg - 2 * M

    multi = len(res.get("idiomas_nas_formas", [])) > 1
    linhas_titulo = _quebra(titulo, util, 15) if titulo else []
    topo = (len(linhas_titulo) * 20 + 14) if titulo else 4.0
    n_col = max(1, min(4, int(util // LARGURA_COLUNA_LEGENDA)))
    col_w = util / n_col
    infos = {c["id"]: c for c in res["comunidades"]}
    n_lin = math.ceil(len(ids_com) / n_col)
    alt_leg = n_lin * 20 + 12
    texto_rodape = rodape if rodape is not None else texto_parametros(res)
    linhas_rodape = _quebra(texto_rodape, util, 10.5)
    vy0 = gy0 - topo
    y_leg = gy1 + M + 14
    y_rod = gy1 + M + alt_leg + 12
    vy1 = y_rod + 14 * len(linhas_rodape) + 2
    Wv, Hv = vx1 - vx0, vy1 - vy0

    desc = (f"Grafo de similitude com {len(res['formas'])} palavras em {len(ids_com)} blocos, "
            f"calculado sobre {res['n_resumos']} resumos. Blocos: "
            + "; ".join(f"{i['nome']}" for i in res["comunidades"][:6]) + ".")
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{_f(vx0)} {_f(vy0)} {_f(Wv)} {_f(Hv)}" '
         f'width="{_f(Wv)}" height="{_f(Hv)}" font-family="{FONTE}" role="img" aria-labelledby="{p}-t {p}-d">',
         f'<title id="{p}-t">{_esc(titulo or "Análise de similitude dos resumos")}</title>'
         f'<desc id="{p}-d">{_esc(desc)}</desc>',
         f'<rect x="{_f(vx0)}" y="{_f(vy0)}" width="{_f(Wv)}" height="{_f(Hv)}" fill="#FFFFFF"/>']
    for k, linha in enumerate(linhas_titulo):
        o.append(f'<text x="{_f(vx0 + M)}" y="{_f(vy0 + 22 + 20 * k)}" font-size="15" font-weight="700" '
                 f'fill="{TINTA}">{_esc(linha)}</text>')
    o.append('<g class="sim-halos">')
    for c, h in halos.items():
        pts = " ".join(f"{_f(x)},{_f(y)}" for x, y in h)
        o.append(f'<g opacity="0.15"><polygon points="{pts}" fill="{cor[c]}" stroke="{cor[c]}" '
                 f'stroke-width="{2 * FOLGA_HALO:g}" stroke-linejoin="round"/></g>')
    o.append("</g>")
    if extras:
        o.append('<g class="sim-extras" stroke-linecap="round">')
        for a in extras:
            u, v = nos[a["origem"]], nos[a["destino"]]
            sw = 0.6 + 2.0 * (a["peso"] / wmax)
            o.append(f'<line x1="{_f(u["x"])}" y1="{_f(u["y"])}" x2="{_f(v["x"])}" y2="{_f(v["y"])}" '
                     f'stroke="#94A3B8" stroke-opacity="0.6" stroke-width="{sw:.2f}" stroke-dasharray="4 3"/>')
        o.append("</g>")
    o.append('<g class="sim-arvore" stroke-linecap="round">')
    for a in arvore:
        u, v = nos[a["origem"]], nos[a["destino"]]
        sw = 0.9 + 4.1 * (a["peso"] / wmax)
        col = cor[com[a["origem"]]] if com[a["origem"]] == com[a["destino"]] else "#64748B"
        o.append(f'<line x1="{_f(u["x"])}" y1="{_f(u["y"])}" x2="{_f(v["x"])}" y2="{_f(v["y"])}" '
                 f'stroke="{col}" stroke-opacity="0.8" stroke-width="{sw:.2f}"/>')
    o.append("</g>")
    o.append('<g class="sim-nos">')
    for i, d in nos.items():
        rs = d["resumos"]
        o.append(f'<circle cx="{_f(d["x"])}" cy="{_f(d["y"])}" r="{_f(d["r"])}" fill="{cor[d["com"]]}" '
                 f'stroke="#FFFFFF" stroke-width="1.5"><title>{_esc(d["txt"])}: {rs} resumo{"" if rs == 1 else "s"}'
                 f'{" · " + d["idioma"].upper() if multi else ""}</title></circle>')
    o.append('</g><g class="sim-rotulos">')
    for i, d in nos.items():
        o.append(f'<text class="rot" x="{_f(d["x"] + d["r"] + 4)}" y="{_f(d["y"] + d["fs"] * 0.35)}" '
                 f'font-size="{d["fs"]:.1f}" font-weight="500" fill="{TINTA}" stroke="#FFFFFF" stroke-width="3" '
                 f'paint-order="stroke" stroke-linejoin="round">{_esc(d["txt"])}</text>')
    o.append("</g>")
    o.append('<g class="sim-legenda">')
    for k, c in enumerate(ids_com):
        ci, li = k % n_col, k // n_col
        x = vx0 + M + ci * col_w
        y = y_leg + li * 20
        o.append(f'<circle cx="{_f(x + 5)}" cy="{_f(y - 4)}" r="5" fill="{cor[c]}"/>')
        txt = _cabe(_titulo_bloco(infos[c], multi), col_w - 24, 12)
        o.append(f'<text class="leg" x="{_f(x + 15)}" y="{_f(y)}" font-size="12" fill="{TINTA}">{_esc(txt)}</text>')
    o.append("</g>")
    for k, linha in enumerate(linhas_rodape):
        o.append(f'<text class="rod" x="{_f(vx0 + M)}" y="{_f(y_rod + 14 * k)}" font-size="10.5" '
                 f'fill="{TINTA_FRACA}">{_esc(linha)}</text>')
    o.append("</svg>")
    return "\n".join(o)

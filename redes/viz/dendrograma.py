"""Dendrograma horizontal em SVG autocontido (sem JS), até 900 px de largura.

A raiz fica à esquerda e as folhas à direita, com os rótulos. Os ramos abaixo
da linha de corte recebem a cor do seu grupo; os acima ficam em cinza.
"""

from __future__ import annotations

import hashlib
import html
import re

from .. import dendrograma as _dg

_CONTROLE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def _esc(texto) -> str:
    return html.escape(_CONTROLE.sub("", str(texto)))


LARGURA = 900
TINTA = "#14204A"
TINTA_FRACA = "#64748B"
CINZA = "#94A3B8"
# Paleta categórica distinguível (inclui daltonismo); cicla acima de 10 grupos.
PALETA = ("#1F77B4", "#D95F02", "#2CA02C", "#9467BD", "#C0392B",
          "#0F9D9A", "#B8860B", "#E7298A", "#555555", "#6B8E23")
FONTE = "Inter, Arial, sans-serif"


def _curto(texto: str, limite: int = 30) -> str:
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"


def _escala_ticks(maximo: float) -> list[float]:
    if maximo <= 0:
        return [0.0]
    for passo in (0.05, 0.1, 0.2, 0.25, 0.5, 1.0):
        if maximo / passo <= 6:
            break
    ticks, v = [], 0.0
    while v <= maximo + 1e-9:
        ticks.append(round(v, 4))
        v += passo
    return ticks


def svg(resultado, n_grupos: int | None = None, titulo: str = "") -> str:
    nos, fusoes = resultado["nos"], resultado["fusoes"]
    n = len(nos)
    nomes = resultado.get("nomes") or {}
    rotulos = {no: nomes.get(no, str(no)) for no in nos}
    assinatura = hashlib.sha1(
        repr((nos, fusoes, n_grupos, titulo)).encode("utf-8")).hexdigest()[:8]
    pref = f"dg{assinatura}"
    titulo_txt = titulo or "Dendrograma"

    if n < 2:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="120" '
            f'viewBox="0 0 {LARGURA} 120" role="img" aria-labelledby="{pref}-t">'
            f'<title id="{pref}-t">{_esc(titulo_txt)}</title>'
            '<rect width="100%" height="100%" fill="#ffffff"/>'
            f'<text x="{LARGURA/2}" y="64" text-anchor="middle" font-family="{FONTE}" '
            f'font-size="14" fill="{TINTA_FRACA}">Dendrograma indisponível: '
            'a rede tem menos de 2 nós.</text></svg>')

    if n_grupos is None:
        n_grupos = resultado.get("n_grupos_sugerido") or 2
    n_grupos = max(1, min(int(n_grupos), n))
    particao = _dg.corte(resultado, n_grupos=n_grupos)
    h_corte = _dg.altura_do_corte(resultado, n_grupos)
    h_max = max(resultado["alturas"]) or 1.0
    h_max = max(h_max, h_corte)

    # Geometria.
    linha = 20 if n > 40 else 22
    topo, base = 58, 52
    maior = max(len(_curto(r)) for r in rotulos.values())
    esq, dir_ = 24, 24 + maior * 7.8 + 16
    x0, x1 = esq, LARGURA - dir_            # raiz (altura máx.) .. folhas (0)
    altura_svg = int(topo + base + linha * n)
    fonte = 12 if linha >= 20 else 11

    def x_de(h: float) -> float:
        return x1 - (h / h_max) * (x1 - x0)

    y_folha = {}
    for i, no in enumerate(resultado["ordem"]):
        y_folha[no] = topo + linha * (i + 0.5)
    posicao = {no: i for i, no in enumerate(nos)}
    y = {posicao[no]: yy for no, yy in y_folha.items()}
    h_no = {i: 0.0 for i in range(n)}
    grupo_no = {i: particao[nos[i]] for i in range(n)}
    for k, (a, b, h, _) in enumerate(fusoes):
        y[n + k] = (y[a] + y[b]) / 2
        h_no[n + k] = h
        ga, gb = grupo_no[a], grupo_no[b]
        grupo_no[n + k] = ga if (ga == gb and ga is not None) else None
        # Um ramo só é "de grupo" se a fusão ocorre abaixo do corte.
        if h > h_corte:
            grupo_no[n + k] = None

    def cor(g):
        return CINZA if g is None else PALETA[g % len(PALETA)]

    contagem = {}
    for g in particao.values():
        contagem[g] = contagem.get(g, 0) + 1
    desc = (f"Dendrograma horizontal de {n} nós, ligação "
            f"{resultado.get('ligacao', '')}, cortado em {n_grupos} grupos "
            f"(tamanhos: {', '.join(str(contagem[g]) for g in sorted(contagem))}). "
            f"Correlação cofenética {resultado.get('coph', 0):.2f}.")

    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" '
        f'height="{altura_svg}" viewBox="0 0 {LARGURA} {altura_svg}" role="img" '
        f'aria-labelledby="{pref}-t {pref}-d">',
        f'<title id="{pref}-t">{_esc(titulo_txt)}</title>',
        f'<desc id="{pref}-d">{_esc(desc)}</desc>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{LARGURA/2}" y="22" text-anchor="middle" font-family="{FONTE}" '
        f'font-size="15" font-weight="600" fill="{TINTA}">'
        f'{_esc(_curto(titulo_txt, 110))}</text>',
        f'<text x="{LARGURA/2}" y="40" text-anchor="middle" font-family="{FONTE}" '
        f'font-size="12" fill="{TINTA_FRACA}">{n_grupos} '
        f'grupo{"s" if n_grupos != 1 else ""} · ligação '
        f'{_esc(str(resultado.get("ligacao", "")))} · cofenética '
        f'{resultado.get("coph", 0):.2f}</text>',
    ]

    # Grade e escala de altura (distância = 1 − similaridade).
    eixo_y = topo + linha * n + 6
    p.append(f'<g id="{pref}-escala" font-family="{FONTE}" font-size="11" fill="{TINTA_FRACA}">')
    for t in _escala_ticks(h_max):
        xt = x_de(t)
        p.append(f'<line x1="{xt:.1f}" y1="{topo}" x2="{xt:.1f}" y2="{eixo_y}" '
                 'stroke="#E2E8F0" stroke-width="1"/>')
        p.append(f'<text x="{xt:.1f}" y="{eixo_y + 14}" text-anchor="middle">'
                 f'{t:.2f}</text>')
    p.append(f'<text x="{(x0 + x1)/2:.1f}" y="{eixo_y + 32}" text-anchor="middle">'
             'altura de fusão (distância = 1 − similaridade)</text></g>')

    # Ramos.
    p.append(f'<g id="{pref}-ramos" fill="none" stroke-width="1.8" '
             'stroke-linecap="round" stroke-linejoin="round">')
    for k, (a, b, h, _) in enumerate(fusoes):
        xm = x_de(h)
        for filho in (a, b):
            g = grupo_no[filho] if h <= h_corte else None
            g_vis = g if g is not None else None
            xf = x_de(h_no[filho])
            p.append(f'<path d="M{xm:.1f} {y[n + k]:.1f}V{y[filho]:.1f}H{xf:.1f}" '
                     f'stroke="{cor(g_vis)}"/>')
    p.append('</g>')

    # Linha de corte.
    xc = x_de(h_corte)
    p.append(f'<g id="{pref}-corte"><line x1="{xc:.1f}" y1="{topo - 6}" '
             f'x2="{xc:.1f}" y2="{eixo_y}" stroke="{TINTA}" stroke-width="1.4" '
             'stroke-dasharray="6 4"/>'
             f'<text x="{xc:.1f}" y="{topo - 10}" text-anchor="{'start' if xc < 45 else 'middle'}" '
             f'font-family="{FONTE}" font-size="11" fill="{TINTA}">'
             f'corte {h_corte:.2f}</text></g>')

    # Folhas e rótulos.
    pesos = resultado.get("pesos") or {}
    pmax = max(pesos.values(), default=0.0)
    p.append(f'<g id="{pref}-folhas" font-family="{FONTE}" font-size="{fonte}" '
             f'fill="{TINTA}">')
    for no in resultado["ordem"]:
        yy = y_folha[no]
        g = particao[no]
        raio = 3.0 + (3.0 * pesos.get(no, 0.0) / pmax if pmax > 0 else 0.0)
        p.append(f'<circle cx="{x1:.1f}" cy="{yy:.1f}" r="{raio:.1f}" '
                 f'fill="{cor(g)}"/>')
        p.append(f'<text x="{x1 + 11:.1f}" y="{yy + 4:.1f}">'
                 f'<title>{_esc(rotulos[no])} (grupo {g + 1})</title>'
                 f'{_esc(_curto(rotulos[no]))}</text>')
    p.append('</g></svg>')
    return "".join(p)

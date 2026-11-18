"""Linha do tempo dos agrupamentos em SVG próprio (sem JavaScript).

Recebe o dicionário de ``redes.linha_do_tempo.constroi``: uma faixa por
agrupamento, eixo x em anos, nós no ano do item, tamanho = frequência, arcos de
ligação e o rótulo da faixa à esquerda. Tema claro, como os outros SVGs (as
variáveis CSS ``--sk-*`` valem na interface; fora dela valem as cores claras).

Largura de rótulo medida por classe de caractere (a 12 px); colisões resolvidas
deslocando o nó para outra linha da faixa; rótulo truncado só acima de 34
caracteres, com o texto completo em ``<title>``. Ids únicos por hash dos dados.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import re
import unicodedata

from ..texto import rotulo_legivel
from .sankey import FONTE, PALETA

LARGURA = 1100
COL_ESQ = 214
MARGEM_DIR = 44
TOPO = 88
LINHA = 26
FAIXA_MIN = 44
PAD = 9
LIMITE_ROTULO = 34
ROTULO_FAIXA_PX = COL_ESQ - 34
PAD_X = 16
MEDIDA_SEGURA = 1.05
CINZA_ARCO = "#9AA3B2"
VERMELHO = "#DC2626"

NOMES_UNIDADE = {"Words": "Palavras-chave", "Authors": "Autores", "References": "Referências",
                 "AuthorsReference": "Autores citados", "ReferenceSources": "Fontes citadas",
                 "Countries": "Países"}

ESTILO = (
    ".lt-fundo{fill:var(--sk-fundo,#fff)}"
    ".lt-tit{fill:var(--sk-texto,#14204A);font-size:16px;font-weight:700}"
    ".lt-sub{fill:var(--sk-fraco,#64748B);font-size:11.5px}"
    ".lt-rot{fill:var(--sk-texto,#14204A);font-size:11px;unicode-bidi:plaintext}"
    ".lt-faixa{fill:var(--sk-texto,#14204A);font-size:12px;font-weight:700;unicode-bidi:plaintext}"
    ".lt-meta{fill:var(--sk-fraco,#64748B);font-size:10.5px}"
    ".lt-eixo{fill:var(--sk-fraco,#64748B);font-size:11px}"
    ".lt-halo{stroke:var(--sk-fundo,#fff);stroke-width:3;paint-order:stroke;stroke-linejoin:round}"
    ".lt-aviso{fill:#9A3412;font-size:11.5px}")

_CONTROLES = re.compile(
    "[\x00-\x1f\x7f-\x9f‎‏‪-‮⁦-⁩﻿￾￿"
    "\ud800-\udfff]")

# ------------------------------------------------------------------ texto

_ESTREITOS = set("il.,;:'!|¡`")
_MEIOS = set("jtfrI()[]{}-–—/\\\"")
_ZERO = {0x200D, 0xFE0F, 0xFE0E}


def limpa(texto) -> str:
    """Texto de uma linha, sem controles nem marcas bidirecionais."""
    if texto is None:
        return ""
    return " ".join(_CONTROLES.sub(" ", str(texto)).split())


def _esc(texto) -> str:
    return html.escape(limpa(texto), quote=True)


def _largura_caractere(c: str) -> float:
    """Largura aproximada, em px, a 12 px de fonte."""
    cod = ord(c)
    if cod in _ZERO or unicodedata.combining(c):
        return 0.0
    if c == " ":
        return 3.6
    if (unicodedata.east_asian_width(c) in ("W", "F") or cod >= 0x1F000
            or 0x2600 <= cod <= 0x27BF):
        return 14.0
    if c.isalpha():
        base = unicodedata.normalize("NFD", c)[0]
        if base in _ESTREITOS:
            return 3.4
        if base in _MEIOS:
            return 4.8
        if base in "mw":
            return 9.6
        if base in "MW":
            return 11.0
        return 8.2 if base.isupper() else 6.6
    if c.isdigit():
        return 7.0
    if c in _ESTREITOS:
        return 3.4
    if c in _MEIOS:
        return 4.8
    return 7.0


def largura(texto: str, tamanho: float = 12.0, negrito: bool = False) -> float:
    total = sum(_largura_caractere(c) for c in texto)
    return total * tamanho / 12.0 * (1.07 if negrito else 1.0)


def _curto(texto: str, limite: int = LIMITE_ROTULO) -> str:
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"


def _cabe(texto: str, px: float, tamanho: float, negrito: bool) -> str:
    """Texto reduzido com … até caber em ``px``."""
    if largura(texto, tamanho, negrito) <= px:
        return texto
    while texto and largura(texto + "…", tamanho, negrito) > px:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _cabe_com(texto: str, px: float, medida) -> str:
    """Texto reduzido com … até que ``medida`` caiba em ``px``."""
    if medida(texto) <= px:
        return texto
    while len(texto) > 1 and medida(texto.rstrip() + "…") > px:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _quebra(texto: str, px: float, linhas: int, tamanho: float, negrito: bool) -> list[str]:
    """Quebra por palavras em até ``linhas`` linhas; a última recebe o … se sobrar."""
    palavras = texto.split()
    saida: list[str] = []
    atual = ""
    i = 0
    while i < len(palavras) and len(saida) < linhas:
        tentativa = (atual + " " + palavras[i]).strip()
        if largura(tentativa, tamanho, negrito) <= px or not atual:
            atual = tentativa
            i += 1
        else:
            saida.append(atual)
            atual = ""
    if atual and len(saida) < linhas:
        saida.append(atual)
    if i < len(palavras) and saida:
        saida[-1] = _cabe(saida[-1] + " " + " ".join(palavras[i:]), px, tamanho, negrito)
    return [_cabe(s, px, tamanho, negrito) for s in saida] or [""]


def _prefixo(dados: dict, titulo: str, rotulos) -> str:
    base = json.dumps([dados, titulo, sorted((str(k), str(v)) for k, v in (rotulos or {}).items())],
                      sort_keys=True, default=str, ensure_ascii=True)
    return "lt" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]


# ------------------------------------------------------------------ eixo


def _valor_finito(valor) -> bool:
    """NaN e infinito não desenham: viram stroke-width="nan" e quebram o SVG."""
    try:
        return math.isfinite(float(valor))
    except (TypeError, ValueError, OverflowError):
        return False


def _passo(span: int) -> int:
    for passo in (1, 2, 5, 10, 20, 25, 50, 100):
        if span / passo <= 14:
            return passo
    return 200


def _rotulos_novos(rotulos) -> dict[int, str]:
    saida: dict[int, str] = {}
    for chave, valor in (rotulos or {}).items():
        try:
            indice = int(chave)
        except (TypeError, ValueError):
            continue
        if isinstance(valor, dict):
            valor = valor.get("rotulo")
        # Os termos do rótulo vêm em minúsculas: inicial maiúscula e siglas em cada um.
        texto = rotulo_legivel(limpa(valor))
        if texto:
            saida[indice] = texto
    return saida


def _svg_simples(mensagem: str, titulo: str, p: str) -> str:
    mensagem = limpa(mensagem)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="110" '
            f'viewBox="0 0 {LARGURA} 110" font-family="{FONTE}" role="img" '
            f'aria-labelledby="{p}-t {p}-d"><title id="{p}-t">{_esc(titulo or "Linha do tempo")}</title>'
            f'<desc id="{p}-d">{_esc(mensagem)}</desc><style>{ESTILO}</style>'
            f'<rect class="lt-fundo" width="{LARGURA}" height="110"/>'
            f'<text class="lt-tit" x="16" y="30">{_esc(_cabe(limpa(titulo) or "Linha do tempo", LARGURA - 32, 16, True))}</text>'
            f'<text class="lt-aviso" x="16" y="64">{_esc(_cabe(mensagem, LARGURA - 32, 11.5, False))}</text>'
            "</svg>")


def svg(dados: dict, titulo: str = "", rotulos: dict | None = None) -> str:
    """SVG autônomo da linha do tempo; ``rotulos``: índice da faixa → rótulo novo."""
    p = _prefixo(dados, titulo, rotulos)
    faixas = [f for f in dados.get("faixas", []) if any(n.get("ano") is not None for n in f["nos"])]
    avisos = [limpa(a) for a in dados.get("avisos", []) if limpa(a)]
    if not faixas:
        return _svg_simples(avisos[0] if avisos else "Não há agrupamentos para desenhar.",
                            titulo, p)
    novos = _rotulos_novos(rotulos)
    atividade = bool(dados.get("atividade"))
    unidade = dados.get("unidade", "")

    anos_nos = [n["ano"] for f in faixas for n in f["nos"] if n.get("ano") is not None]
    n0, n1 = min(anos_nos), max(anos_nos)
    a0, a1 = n0 - 1, n1 + 1
    x0, x1 = COL_ESQ, LARGURA - MARGEM_DIR

    area_e, area_d = COL_ESQ - 10, LARGURA - MARGEM_DIR + 4
    xi, xf = x0 + PAD_X, x1 - PAD_X          # folga para o círculo e o anel nas pontas

    def X(ano: float) -> float:
        return xi + (ano - a0) / (a1 - a0) * (xf - xi)

    todos = [n for f in faixas for n in f["nos"] if n.get("ano") is not None]
    fmax = max(max(int(n.get("frequencia", 1)) for n in todos), 1)
    fmin = min(int(n.get("frequencia", 1)) for n in todos)

    def R(freq) -> float:
        return 3.5 + 7.0 * (max(int(freq), 0) / fmax) ** 0.5

    # ---------------------------------------------- layout das faixas
    layout = []          # (y0, altura, faixa, nos com _x/_y/_r/_lado/_texto)
    pos: dict[int, tuple[float, float, int]] = {}
    y = float(TOPO)
    for i, faixa in enumerate(faixas):
        nos = sorted((n for n in faixa["nos"] if n.get("ano") is not None),
                     key=lambda n: (n["ano"], -int(n.get("frequencia", 1)), str(n.get("rotulo")), n["id"]))
        linhas_ocupadas: list[list[tuple[float, float]]] = []
        itens = []
        for n in nos:
            r = R(n.get("frequencia", 1))
            rotulo = limpa(n.get("rotulo")) or f"Item {n['id']}"
            texto = _curto(rotulo)
            raj_n = bool(n.get("rajada"))
            cx = X(n["ano"])
            folga = 9 if raj_n else 5
            lim_e, lim_d = area_e + 5, area_d - 5
            sobra_d = lim_d - (cx + r + folga)
            sobra_e = (cx - r - folga) - lim_e
            medida = lambda t: largura(t, 11.0, raj_n) * MEDIDA_SEGURA
            w = medida(texto)
            if w <= sobra_d:
                lado = "d"
            elif w <= sobra_e:
                lado = "e"
            else:                              # não cabe em nenhum lado: trunca no maior
                lado = "d" if sobra_d >= sobra_e else "e"
                texto = _cabe_com(texto, max(sobra_d if lado == "d" else sobra_e, 20.0), medida)
                w = medida(texto)
            direita = (cx - r - 2, cx + r + folga + w)
            esquerda = (cx - r - folga - w, cx + r + 2)
            caixa = direita if lado == "d" else esquerda
            for k, ocupados in enumerate(linhas_ocupadas):
                if all(caixa[1] + 6 <= a or caixa[0] - 6 >= b for a, b in ocupados):
                    ocupados.append(caixa)
                    linha = k
                    break
            else:
                linhas_ocupadas.append([caixa])
                linha = len(linhas_ocupadas) - 1
            itens.append(dict(n=n, r=r, texto=texto, completo=rotulo, cx=cx, lado=lado, linha=linha))
        altura = max(FAIXA_MIN, 2 * PAD + max(len(linhas_ocupadas), 1) * LINHA)
        desloc = (altura - len(linhas_ocupadas) * LINHA) / 2
        for it in itens:
            it["cy"] = y + desloc + it["linha"] * LINHA + LINHA / 2
            pos[it["n"]["id"]] = (it["cx"], it["cy"], i)
        layout.append((y, altura, faixa, itens))
        y += altura + 3
    fim_faixas = y

    # ---------------------------------------------- legenda (abaixo do eixo inferior)
    teve_rajada = any(n.get("rajada") for n in todos)
    teve_linha = atividade and any(n.get("primeiro") is not None and n.get("ultimo") is not None
                                   and n["ultimo"] > n["primeiro"] for n in todos)
    teve_cruzada = any(l.get("cruzada") for l in dados.get("ligacoes", []))
    teve_interna = any(not l.get("cruzada") for l in dados.get("ligacoes", []))
    modo = dados.get("posicao") or ("media" if atividade else "documento")
    pos_texto = {"referencia": "posição = ano da própria referência",
                 "media": "posição = ano médio dos documentos do item"}.get(
                     modo, "posição = ano do documento")
    itens_leg = [("tam", f"tamanho = frequência em documentos ({fmin} a {fmax})"),
                 ("pos", pos_texto)]
    if teve_linha:
        itens_leg.append(("linha", "linha fina = do primeiro ao último ano em que o item aparece"))
    if teve_rajada:
        itens_leg.append(("anel", "anel vermelho = rajada de " + ("citação" if modo == "referencia" else "uso")
                                  + " (3 documentos ou mais, entre as 10 mais fortes do corpus)"
                                  + ("; traço vermelho = anos da rajada" if teve_linha else "")
                                  + ("; rajadas calculadas só sobre palavras-chave dos autores"
                                     if unidade == "Words" else "")))
    if teve_interna:
        itens_leg.append(("arco", "arco colorido = ligação dentro da faixa (as 3 mais fortes de cada item)"))
    if teve_cruzada:
        itens_leg.append(("cinza", "arco cinza = ligação entre faixas (as 6 mais fortes)"))
    linhas_texto = []
    for tipo, texto in itens_leg:
        for k, parte in enumerate(_quebra(texto, LARGURA - 72, 3, 11.5, False)):
            linhas_texto.append((tipo if k == 0 else "", parte, False))
    for aviso in avisos:
        for k, parte in enumerate(_quebra("Aviso: " + aviso, LARGURA - 72, 3, 11.5, False)):
            linhas_texto.append(("", parte, True))

    y_eixo_baixo = fim_faixas + 20
    y_leg = y_eixo_baixo + 30
    H = y_leg + 18 * len(linhas_texto) + 14

    cores = [PALETA[i % len(PALETA)] for i in range(len(faixas))]
    n_itens = len(todos)
    nome_unidade = NOMES_UNIDADE.get(unidade, unidade or "Itens")
    titulo_fig = limpa(titulo) or "Linha do tempo dos agrupamentos"
    sub = f"{nome_unidade} · {n_itens} itens em {len(faixas)} agrupamentos · {n0}–{n1}"
    descricao = (f"{titulo_fig}. {sub}. Cada faixa é um agrupamento; o eixo horizontal vai de {a0} a {a1}.")

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{H:.0f}" '
         f'viewBox="0 0 {LARGURA} {H:.0f}" font-family="{FONTE}" role="img" '
         f'aria-labelledby="{p}-t {p}-d">',
         f'<title id="{p}-t">{_esc(titulo_fig)}</title><desc id="{p}-d">{_esc(descricao)}</desc>',
         f"<style>{ESTILO}</style>",
         f'<defs><clipPath id="{p}-area"><rect x="{area_e}" y="{TOPO}" width="{area_d - area_e}" '
         f'height="{fim_faixas - TOPO:.1f}"/></clipPath></defs>',
         f'<rect class="lt-fundo" width="{LARGURA}" height="{H:.0f}"/>',
         f'<text class="lt-tit" x="16" y="28">{_esc(_cabe(titulo_fig, LARGURA - 32, 16, True))}</text>',
         f'<text class="lt-sub" x="16" y="47">{_esc(sub)}</text>']

    # faixas
    for i, (y0, h, faixa, itens) in enumerate(layout):
        c = cores[i]
        o.append(f'<rect x="{x0 - 10}" y="{y0:.1f}" width="{LARGURA - MARGEM_DIR + 4 - x0 + 10:.1f}" '
                 f'height="{h:.1f}" fill="{c}" fill-opacity="{0.07 if i % 2 else 0.13}"/>')
        o.append(f'<rect x="4" y="{y0:.1f}" width="4" height="{h:.1f}" fill="{c}"/>')
    # grade e eixos
    passo = _passo(a1 - a0)
    ticks = [a for a in range((a0 // passo) * passo, a1 + 1) if a >= a0 and a % passo == 0]
    for a in ticks:
        x = X(a)
        o.append(f'<line x1="{x:.1f}" y1="{TOPO - 6}" x2="{x:.1f}" y2="{fim_faixas:.1f}" '
                 'stroke="#94A3B8" stroke-opacity=".28"/>')
        for ty in (TOPO - 12, y_eixo_baixo):
            o.append(f'<text class="lt-eixo" x="{x:.1f}" y="{ty:.1f}" text-anchor="middle">{a}</text>')
    # rótulos das faixas
    for i, (y0, h, faixa, itens) in enumerate(layout):
        indice = faixa.get("indice", i)
        texto = novos.get(indice) if novos.get(indice) else limpa(faixa.get("rotulo")) or f"Agrupamento {i + 1}"
        prefixo = f"#{i + 1} "
        n_linhas = 2 if h >= 60 else 1
        disp = ROTULO_FAIXA_PX - largura(prefixo, 12, True)
        partes = _quebra(texto, disp, n_linhas, 12, True)
        total_itens = faixa.get("itens_total", len(faixa["nos"]))
        meta = f'{len(itens)} de {total_itens} itens'
        if faixa.get("frequencia_total") is not None:
            meta += f' · freq. {faixa["frequencia_total"]}'
        bloco = len(partes) * 14 + 13
        ty = y0 + (h - bloco) / 2 + 11
        o.append(f'<g><title>{_esc(prefixo + texto)}</title>')
        for k, parte in enumerate(partes):
            pre = html.escape(prefixo) if k == 0 else ""
            o.append(f'<text class="lt-faixa" x="14" y="{ty + k * 14:.1f}">{pre}{_esc(parte)}</text>')
        o.append(f'<text class="lt-meta" x="14" y="{ty + len(partes) * 14 + 1:.1f}">{_esc(_cabe(meta, ROTULO_FAIXA_PX, 10.5, False))}</text></g>')

    # arcos
    o.append(f'<g class="lt-plot" clip-path="url(#{p}-area)">')
    ligacoes = [l for l in dados.get("ligacoes", [])
                if l["origem"] in pos and l["destino"] in pos and _valor_finito(l.get("valor", 0))]
    vmax = max((float(l.get("valor", 0)) for l in ligacoes), default=0.0) or 1.0
    topo_faixa = {i: layout[i][0] for i in range(len(layout))}
    for l in sorted(ligacoes, key=lambda l: (bool(l.get("cruzada")), float(l.get("valor", 0)),
                                             l["origem"], l["destino"])):
        xa, ya, fa = pos[l["origem"]]
        xb, yb, fb = pos[l["destino"]]
        v = float(l.get("valor", 0))
        sw = 0.7 + 1.9 * v / vmax
        if fa == fb:
            dist = abs(xb - xa) + abs(yb - ya)
            bulge = min(18.0, 6 + 0.1 * dist)
            cx = min(max((xa + xb) / 2, area_e + 2), area_d - 2)
            cy = max((ya + yb) / 2 - bulge, topo_faixa[fa] + 2)
            d = f"M{xa:.1f},{ya:.1f} Q{cx:.1f},{cy:.1f} {xb:.1f},{yb:.1f}"
            o.append(f'<path d="{d}" fill="none" stroke="{cores[fa]}" stroke-opacity=".5" '
                     f'stroke-width="{sw:.2f}"/>')
        else:
            meio = (xa + xb) / 2
            desvio = 34.0 if meio + 34.0 <= area_d - 2 else -34.0
            cx = min(max(meio + desvio, area_e + 2), area_d - 2)
            d = f"M{xa:.1f},{ya:.1f} Q{cx:.1f},{(ya + yb) / 2:.1f} {xb:.1f},{yb:.1f}"
            o.append(f'<path d="{d}" fill="none" stroke="{CINZA_ARCO}" stroke-opacity=".38" '
                     f'stroke-width="{sw:.2f}"/>')

    # atividade, rajada, nós e rótulos
    def corta(a: float, b: float):
        e, d = max(a, a0), min(b, a1)
        return (e, d, a < a0, b > a1) if e < d else None

    for i, (y0, h, faixa, itens) in enumerate(layout):
        c = cores[i]
        if atividade:
            for it in itens:
                n = it["n"]
                pr, ul = n.get("primeiro"), n.get("ultimo")
                if pr is None or ul is None or ul <= pr:
                    continue
                seg = corta(pr, ul)
                if seg:
                    e, d, ce, cd = seg
                    o.append(f'<line x1="{X(e):.1f}" y1="{it["cy"]:.1f}" x2="{X(d):.1f}" y2="{it["cy"]:.1f}" '
                             f'stroke="{c}" stroke-opacity=".38" stroke-width="1.1"/>')
                    for flag, xx, sinal in ((ce, X(e), 1), (cd, X(d), -1)):
                        if flag:
                            o.append(f'<path d="M{xx + 4 * sinal:.1f},{it["cy"] - 3:.1f} L{xx:.1f},{it["cy"]:.1f} '
                                     f'L{xx + 4 * sinal:.1f},{it["cy"] + 3:.1f}" fill="none" stroke="{c}" '
                                     'stroke-opacity=".7" stroke-width="1.2"/>')
                if n.get("rajada") and n.get("rajada_inicio") is not None and n.get("rajada_fim") is not None:
                    rs = corta(n["rajada_inicio"], n["rajada_fim"])
                    if rs:
                        o.append(f'<line x1="{X(rs[0]):.1f}" y1="{it["cy"]:.1f}" x2="{X(rs[1]):.1f}" '
                                 f'y2="{it["cy"]:.1f}" stroke="{VERMELHO}" stroke-width="2.8" stroke-linecap="round"/>')
                        # Rajada que começa antes (ou termina depois) do eixo: setinha, como na atividade.
                        for flag, xx, sinal in ((rs[2], X(rs[0]), 1), (rs[3], X(rs[1]), -1)):
                            if flag:
                                o.append(f'<path class="lt-seta-rajada" d="M{xx + 4 * sinal:.1f},{it["cy"] - 3.5:.1f} '
                                         f'L{xx:.1f},{it["cy"]:.1f} L{xx + 4 * sinal:.1f},{it["cy"] + 3.5:.1f}" '
                                         f'fill="none" stroke="{VERMELHO}" stroke-width="1.6"/>')
    o.append('</g>')
    for i, (y0, h, faixa, itens) in enumerate(layout):
        c = cores[i]
        for it in itens:
            n, r, cx, cy = it["n"], it["r"], it["cx"], it["cy"]
            raj = bool(n.get("rajada"))
            freq = int(n.get("frequencia", 1))
            if atividade and n.get("primeiro") is not None:
                dica_ano = (f'Ano médio: {n["ano"]}\nAparece de {n["primeiro"]} a {n["ultimo"]}')
            elif atividade:
                dica_ano = f'Ano médio: {n["ano"]}'
            else:
                dica_ano = f'Ano: {n["ano"]}'
            dica = f'{it["completo"]}\nFrequência: {freq} documento{"" if freq == 1 else "s"}\n{dica_ano}'
            if raj:
                dica += "\nRajada"
                if n.get("rajada_inicio") is not None:
                    dica += f' de {n["rajada_inicio"]} a {n["rajada_fim"]}'
            if it["lado"] == "d":
                tx, ancora = cx + r + (8 if raj else 4), "start"
            else:
                tx, ancora = cx - r - (8 if raj else 4), "end"
            o.append(f'<g><title>{_esc(dica)}</title>')
            if raj:
                o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r + 3:.1f}" fill="none" '
                         f'stroke="{VERMELHO}" stroke-width="2"/>')
            o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{c}" fill-opacity=".88" '
                     'stroke="#fff" stroke-width="1"/>')
            negrito = ' font-weight="700"' if raj else ""
            o.append(f'<text class="lt-rot lt-halo" aria-hidden="true" x="{tx:.1f}" y="{cy + 3.8:.1f}" '
                     f'text-anchor="{ancora}"{negrito}>{_esc(it["texto"])}</text>')
            o.append(f'<text class="lt-rot" x="{tx:.1f}" y="{cy + 3.8:.1f}" text-anchor="{ancora}"{negrito}>{_esc(it["texto"])}</text></g>')

    # legenda
    yl = y_leg
    o.append(f'<line x1="16" y1="{y_leg - 14}" x2="{LARGURA - 16}" y2="{y_leg - 14}" stroke="#94A3B8" stroke-opacity=".35"/>')
    for tipo, texto, aviso in linhas_texto:
        cy = yl - 4
        if tipo == "tam":
            o.append(f'<circle cx="22" cy="{cy}" r="3.5" fill="#64748B" fill-opacity=".8"/>'
                     f'<circle cx="36" cy="{cy}" r="7" fill="#64748B" fill-opacity=".8"/>')
        elif tipo == "linha":
            o.append(f'<line x1="14" y1="{cy}" x2="44" y2="{cy}" stroke="#64748B" stroke-opacity=".7" stroke-width="1.3"/>')
        elif tipo == "anel":
            o.append(f'<circle cx="29" cy="{cy}" r="6.5" fill="none" stroke="{VERMELHO}" stroke-width="2"/>'
                     '<circle cx="29" cy="%s" r="3.5" fill="#64748B"/>' % cy)
        elif tipo == "arco":
            o.append(f'<path d="M14,{cy + 3} Q29,{cy - 8} 44,{cy + 3}" fill="none" stroke="{cores[0]}" '
                     'stroke-opacity=".6" stroke-width="1.6"/>')
        elif tipo == "cinza":
            o.append(f'<path d="M14,{cy + 3} Q29,{cy - 8} 44,{cy + 3}" fill="none" stroke="{CINZA_ARCO}" '
                     'stroke-opacity=".7" stroke-width="1.6"/>')
        elif tipo == "pos":
            o.append(f'<path d="M14,{cy} L44,{cy} M40,{cy - 3} L44,{cy} L40,{cy + 3}" fill="none" '
                     'stroke="#64748B" stroke-width="1.2"/>')
        o.append(f'<text class="{"lt-aviso" if aviso else "lt-sub"}" x="56" y="{yl}">{_esc(texto)}</text>')
        yl += 18
    o.append("</svg>")
    return "\n".join(o)

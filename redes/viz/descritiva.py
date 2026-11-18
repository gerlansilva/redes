"""Figuras da visão geral descritiva: rajadas, nuvem de palavras e produção anual.

São as mesmas figuras da tela e do relatório HTML. Tudo em SVG, sem dependências.
"""
from __future__ import annotations

import html
import math
import re

from .halo import cor_do_grupo

FONTE = "Inter, Helvetica, Arial, sans-serif"
TINTA, FRACA, AZUL, AMARELO = "#14204A", "#64748B", "#2F2BFF", "#FFC400"


def _esc(texto) -> str:
    return html.escape(str(texto if texto is not None else ""))


def _limpa_referencia(texto: str) -> str:
    texto = re.sub(r"(,\s*)?Sem fonte(,\s*)?", ", ", str(texto))
    texto = re.sub(r"(,\s*){2,}", ", ", texto)
    return texto.strip(" ,")


def _curto(texto: str, limite: int) -> str:
    texto = " ".join(_limpa_referencia(texto).split())
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"


# ---------------------------------------------------------------- rajadas

def _nome(linha: dict) -> str:
    """Termo para mostrar: a forma legível quando a análise a trouxe."""
    return linha.get("termo_exibicao") or linha["termo"]


def rajadas_svg(dados: dict, titulo: str, rotulo_termo: str = "Termo",
                limite_texto: int = 44) -> str:
    """Tabela de rajadas (Kleinberg, 2002), com a barra de anos."""
    linhas = dados["rajadas"]
    if not linhas:
        return ""
    primeiro, ultimo = dados["anos"]
    n_anos = ultimo - primeiro + 1
    larg_termo = min(520, max(220, 7.4 * max(len(_curto(_nome(r), limite_texto)) for r in linhas)))
    x_ano = 24 + larg_termo + 16
    colunas = {"ano": x_ano, "forca": x_ano + 100, "inicio": x_ano + 170, "fim": x_ano + 234}
    x_barra = x_ano + 284
    larg_barra = 380
    passo = 26
    topo = 70
    L = int(x_barra + larg_barra + 24)
    A = topo + passo * len(linhas) + 20
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {L} {A}" width="{L}" '
              f'height="{A}" font-family="{FONTE}"><rect width="{L}" height="{A}" fill="#fff"/>',
              f'<text x="{L / 2}" y="28" text-anchor="middle" font-size="18" font-weight="700" '
              f'fill="{TINTA}">{_esc(titulo)}</text>']
    cab = [(24, "start", rotulo_termo), (colunas["ano"], "start", "Primeiro ano"),
           (colunas["forca"], "start", "Força"), (colunas["inicio"], "start", "Início"),
           (colunas["fim"], "start", "Fim"), (x_barra + larg_barra / 2, "middle", f"{primeiro} – {ultimo}")]
    for x, ancora, texto in cab:
        partes.append(f'<text x="{x}" y="{topo - 14}" text-anchor="{ancora}" font-size="12.5" '
                      f'font-weight="700" fill="{TINTA}">{_esc(texto)}</text>')
    passo_ano = larg_barra / n_anos
    for i, r in enumerate(linhas):
        y = topo + i * passo
        meio = y + passo / 2
        partes.append(f'<text x="24" y="{meio + 4}" font-size="12.5" fill="{TINTA}">'
                      f'<title>{_esc(_nome(r))}</title>{_esc(_curto(_nome(r), limite_texto))}</text>')
        partes.append(f'<text x="{colunas["ano"]}" y="{meio + 4}" font-size="12.5" fill="{FRACA}">{r["primeiro_ano"]}</text>')
        forca = f'{r["forca"]:.2f}'.replace(".", ",")
        partes.append(f'<text x="{colunas["forca"]}" y="{meio + 4}" font-size="12.5" fill="{TINTA}">{forca}</text>')
        partes.append(f'<text x="{colunas["inicio"]}" y="{meio + 4}" font-size="12.5" font-weight="700" fill="{TINTA}">{r["inicio"]}</text>')
        partes.append(f'<text x="{colunas["fim"]}" y="{meio + 4}" font-size="12.5" fill="{TINTA}">{r["fim"]}</text>')
        # linha-base: anos antes do primeiro uso em azul claro, depois em verde-água
        x_primeiro = x_barra + (r["primeiro_ano"] - primeiro) * passo_ano
        partes.append(f'<rect x="{x_barra}" y="{meio - 2.5}" width="{larg_barra}" height="5" rx="2" fill="#CFEDEE"/>')
        partes.append(f'<rect x="{x_primeiro:.1f}" y="{meio - 2.5}" width="{x_barra + larg_barra - x_primeiro:.1f}" '
                      f'height="5" rx="2" fill="#3FBFC0"/>')
        x_i = x_barra + (r["inicio"] - primeiro) * passo_ano
        x_f = x_barra + (r["fim"] - primeiro + 1) * passo_ano
        partes.append(f'<rect x="{x_i:.1f}" y="{meio - 5}" width="{max(3.0, x_f - x_i):.1f}" height="10" rx="2" '
                      f'fill="#E5252A"><title>{_esc(_nome(r))}: {r["inicio"]}–{r["fim"]}</title></rect>')
    partes.append("</svg>")
    return "".join(partes)


# ------------------------------------------------------------- nuvem de palavras

def layout_nuvem(termos: list[tuple[str, int]], largura: int = 1000, altura: int = 520,
                 tamanho_max: float = 64, tamanho_min: float = 13) -> list[dict]:
    """Posiciona as palavras em espiral, sem sobreposição, do maior para o menor.

    Se alguma palavra não couber, reduz os tamanhos e tenta de novo, para que
    nenhum termo da lista fique de fora.
    """
    melhor: list[dict] = []
    for fator in (1.0, 0.86, 0.74, 0.64, 0.55):
        itens = _espiral(termos, largura, altura, tamanho_max * fator,
                         max(9.0, tamanho_min * fator))
        if len(itens) > len(melhor):
            melhor = itens
        if len(itens) == len(termos):
            break
    return melhor


def _espiral(termos, largura, altura, tamanho_max, tamanho_min) -> list[dict]:
    if not termos:
        return []
    maior = max(v for _, v in termos)
    menor = min(v for _, v in termos)

    def tamanho(valor: int) -> float:
        if maior == menor:
            return (tamanho_max + tamanho_min) / 2
        t = (math.sqrt(valor) - math.sqrt(menor)) / (math.sqrt(maior) - math.sqrt(menor))
        return tamanho_min + t * (tamanho_max - tamanho_min)

    colocadas: list[tuple[float, float, float, float]] = []
    saida = []
    cx, cy = largura / 2, altura / 2
    for posicao, (termo, valor) in enumerate(termos):
        tam = tamanho(valor)
        w, h = 0.56 * tam * len(termo) + 6, tam * 1.08
        achou = False
        for passo in range(0, 6000):
            ang = 0.35 * passo
            raio = 1.1 * ang
            x = cx + raio * math.cos(ang) * 1.55 - w / 2
            y = cy + raio * math.sin(ang) - h / 2
            if x < 4 or y < 4 or x + w > largura - 4 or y + h > altura - 4:
                if raio > max(largura, altura):
                    break
                continue
            caixa = (x, y, x + w, y + h)
            if all(caixa[2] < c[0] or caixa[0] > c[2] or caixa[3] < c[1] or caixa[1] > c[3]
                   for c in colocadas):
                colocadas.append(caixa)
                saida.append({"termo": termo, "valor": valor, "tamanho": round(tam, 1),
                              "x": round(x + w / 2, 1), "y": round(y + h * 0.78, 1),
                              "cor": cor_do_grupo(posicao % 15)})
                achou = True
                break
        if not achou:
            continue
    return saida


def nuvem_svg(termos: list[tuple[str, int]], titulo: str = "", largura: int = 1000,
              altura: int = 520) -> str:
    itens = layout_nuvem(termos, largura, altura)
    if not itens:
        return ""
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura} {altura}" '
              f'width="100%" font-family="{FONTE}" role="img" aria-label="{_esc(titulo)}">']
    for it in itens:
        partes.append(
            f'<text data-termo="{_esc(it["termo"])}" style="cursor:pointer" x="{it["x"]}" y="{it["y"]}" text-anchor="middle" font-size="{it["tamanho"]}" '
            f'font-weight="700" fill="{it["cor"]}"><title>{_esc(it["termo"])}: {it["valor"]} documentos</title>'
            f'{_esc(it["termo"])}</text>')
    partes.append("</svg>")
    return "".join(partes)


# -------------------------------------------------------------------- produção

def _escala(maximo: float, passos: int = 4) -> tuple[float, list[float]]:
    if maximo <= 0:
        return 1.0, [0, 1]
    bruto = maximo / passos
    potencia = 10 ** math.floor(math.log10(bruto))
    fracao = bruto / potencia
    passo = (1 if fracao <= 1 else 2 if fracao <= 2 else 5 if fracao <= 5 else 10) * potencia
    topo = math.ceil(maximo / passo) * passo
    ticks, v = [], 0.0
    while v <= topo + passo / 1000:
        ticks.append(round(v, 3))
        v += passo
    return topo, ticks


def producao_svg(producao: list[dict]) -> str:
    """Documentos por ano (barras) e citações por ano (linha), com dois eixos."""
    if not producao:
        return ""
    L, A = 1100, 312
    me, md, mt, mb = 54, 62, 28, 30
    w, h = L - me - md, A - mt - mb
    topo_d, ticks_d = _escala(max(p["documentos"] for p in producao))
    topo_c, ticks_c = _escala(max(p["citacoes"] for p in producao))
    passo = w / len(producao)

    def yd(v): return mt + h - v / topo_d * h
    def yc(v): return mt + h - v / topo_c * h
    def xc(i): return me + i * passo + passo / 2

    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {L} {A}" width="100%" '
              f'font-family="{FONTE}" role="img" aria-label="Produção e citações por ano">']
    for v in ticks_d:
        partes.append(f'<line x1="{me}" x2="{L - md}" y1="{yd(v):.1f}" y2="{yd(v):.1f}" stroke="#E9ECF2"/>'
                      f'<text x="{me - 8}" y="{yd(v) + 4:.1f}" text-anchor="end" font-size="11" fill="{AZUL}">{v:g}</text>')
    for v in ticks_c:
        partes.append(f'<text x="{L - md + 8}" y="{yc(v) + 4:.1f}" font-size="11" fill="#A16207">{v:g}</text>')
    for i, p in enumerate(producao):
        altura = p["documentos"] / topo_d * h
        partes.append(f'<rect x="{me + i * passo + passo * 0.16:.1f}" y="{mt + h - altura:.1f}" '
                      f'width="{passo * 0.68:.1f}" height="{altura:.1f}" rx="3" fill="{AZUL}" fill-opacity=".85">'
                      f'<title>{p["ano"]}: {p["documentos"]} documentos, {p["citacoes"]} citações</title></rect>')
    caminho = " ".join(f'{"M" if i == 0 else "L"}{xc(i):.1f},{yc(p["citacoes"]):.1f}' for i, p in enumerate(producao))
    partes.append(f'<path d="{caminho}" fill="none" stroke="{AMARELO}" stroke-width="2.5" stroke-linejoin="round"/>')
    cada = max(1, math.ceil(len(producao) / 14))
    for i, p in enumerate(producao):
        if i % cada == 0 or i == len(producao) - 1:
            partes.append(f'<text x="{xc(i):.1f}" y="{A - 10}" text-anchor="middle" font-size="11" fill="{FRACA}">{p["ano"]}</text>')
    partes.append(f'<text x="{me - 8}" y="12" text-anchor="end" font-size="10.5" font-weight="600" fill="{AZUL}">Docs</text>'
                  f'<text x="{L - md + 8}" y="12" font-size="10.5" font-weight="600" fill="#A16207">Citações</text>')
    partes.append("</svg>")
    return "".join(partes)

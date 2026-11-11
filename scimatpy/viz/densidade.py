"""Mapa de densidade (estilo VOSviewer) em SVG próprio, sem JavaScript.

Os itens mais frequentes da rede de co-ocorrência são posicionados por um layout de
atração e repulsão (energia do tipo VOS: ligações fortes aproximam, todos os pares se
repelem) e, sobre as posições, soma-se um núcleo gaussiano por item, ponderado pela
frequência. O resultado é normalizado pelo máximo (0 a 1) e pintado de branco a
amarelo; as áreas quentes são vizinhanças de itens frequentes e fortemente ligados.

`svg` é puro: recebe um resultado de período (``rede``, ``frequencia_nos`` e
``rotulo``), não toca em banco nem em relógio e devolve sempre o mesmo texto para os
mesmos dados. Tudo o que é desenhado cabe na área do gráfico: a imagem de densidade
preenche o quadro, os rótulos só entram se a caixa inteira couber nele e a legenda
fica numa faixa própria, abaixo.
"""
from __future__ import annotations

import base64
import hashlib
import html
import math
import struct
import zlib

import numpy as np

from .linha_do_tempo import largura as _largura_texto
from .linha_do_tempo import limpa

LARGURA = 1100
ALTURA_QUADRO = 600          # altura da área do gráfico
TOPO_TITULO = 46             # faixa do título (só quando há título)
RODAPE = 50                  # faixa da legenda
MARGEM_QUADRO = 16           # espaço lateral entre o SVG e o quadro
MARGEM_NOS = 44              # os itens ficam a esta distância da borda do quadro
FONTE = "Inter, Arial, sans-serif"
TINTA = "#14204A"
TINTA_FRACA = "#64748B"

TOPO_NOS = 150               # itens no mapa (os mais frequentes)
LIMITE_NOS = (20, 300)
SUAVIZACAO = 4               # passos do núcleo gaussiano (1 a 9)
LIMITE_SUAVIZACAO = (1, 9)
SIGMA_POR_PASSO = 0.008      # desvio-padrão do núcleo = passo × 0,8% da largura do quadro
COMPRESSAO_PERIFERIA = 0.25   # fração da distância além de R que se mantém nos itens soltos
GAMMA = 0.8                  # realce: densidade normalizada ** 0,8
MAX_ROTULOS = 40
LIMITE_ROTULO = 26           # caracteres; acima disso o rótulo é cortado (texto inteiro em <title>)
MINIMO_NOS = 5
RESOLUCAO = 4                # pixels da imagem de densidade por pixel do SVG (1/4)
ITERACOES = 600

NOMES_UNIDADE = {"Words": "palavras-chave", "Authors": "autores", "References": "referências",
                 "AuthorsReference": "autores citados", "ReferenceSources": "fontes citadas",
                 "Countries": "países"}

# Escala de cores: branco, azul claro, azul, verde-azulado, verde, amarelo.
PARADAS = [(0.0, (255, 255, 255)), (0.04, (236, 242, 250)), (0.15, (120, 150, 215)),
           (0.35, (40, 160, 150)), (0.60, (110, 200, 70)), (0.85, (235, 225, 40)),
           (1.0, (255, 235, 20))]


def _esc(texto) -> str:
    return html.escape(limpa(texto), quote=True)


# ------------------------------------------------------------------ layout

def layout_vos(similaridade: np.ndarray, iteracoes: int = ITERACOES, semente: int = 3) -> np.ndarray:
    """Posições 2D minimizando Σ s_ij d_ij² − c Σ ln d_ij (descida com momento).

    ``similaridade`` é simétrica, com diagonal nula e valores em [0, 1]. A semente fixa
    torna o resultado reprodutível; o passo é limitado pela maior soma de ligações de
    um nó, para que o método não divirja em redes pequenas e densas.
    """
    n = len(similaridade)
    rng = np.random.default_rng(semente)
    x = rng.normal(0, 1, (n, 2))
    soma = similaridade.sum()
    s = similaridade / (soma / (n * (n - 1)) if soma > 0 else 1.0)       # média 1 por par
    s = np.minimum(s, 25.0)
    c = 4.0
    lipschitz = 8.0 * max(float(s.sum(axis=1).max()), 1.0) / n
    passo = min(0.05, 1.0 / lipschitz)
    v = np.zeros_like(x)
    for _ in range(iteracoes):
        dif = x[:, None, :] - x[None, :, :]
        d2 = (dif ** 2).sum(axis=2) + 1e-6
        g = (4 * s[:, :, None] * dif - 2 * c * dif / d2[:, :, None]).sum(axis=1) / n
        v = 0.8 * v - passo * g
        norma = np.linalg.norm(v, axis=1, keepdims=True)
        v = np.where(norma > 0.5, v * 0.5 / np.maximum(norma, 1e-12), v)
        x = x + v
        x -= x.mean(axis=0)
    return x


# ------------------------------------------------------------------ densidade

def mapa_de_cores(t: np.ndarray) -> np.ndarray:
    """Valores em [0, 1] → imagem RGB (uint8) pela escala de `PARADAS`."""
    t = np.clip(t, 0.0, 1.0)
    saida = np.zeros(t.shape + (3,))
    for (a, ca), (b, cb) in zip(PARADAS, PARADAS[1:]):
        m = (t >= a) & (t <= b)
        f = ((t - a) / (b - a))[m][:, None]
        saida[m] = np.array(ca) * (1 - f) + np.array(cb) * f
    return np.rint(saida).astype(np.uint8)


def _png_rgb(img: np.ndarray) -> bytes:
    h, w, _ = img.shape
    bruto = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def bloco(tipo: bytes, dados: bytes) -> bytes:
        corpo = tipo + dados
        return struct.pack(">I", len(dados)) + corpo + struct.pack(">I", zlib.crc32(corpo) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + bloco(b"IDAT", zlib.compress(bruto, 9)) + bloco(b"IEND", b""))


def densidade_gaussiana(px: np.ndarray, py: np.ndarray, pesos: np.ndarray, largura: float,
                        altura: float, sigma: float, colunas: int, linhas: int) -> np.ndarray:
    """Soma de núcleos gaussianos ponderados numa grade (linhas × colunas), em [0, 1]."""
    gx = np.linspace(0, largura, colunas)
    gy = np.linspace(0, altura, linhas)
    kx = np.exp(-((gx[None, :] - px[:, None]) ** 2) / (2 * sigma ** 2))     # (n, colunas)
    ky = np.exp(-((gy[None, :] - py[:, None]) ** 2) / (2 * sigma ** 2))     # (n, linhas)
    dens = (ky * pesos[:, None]).T @ kx                                       # (linhas, colunas)
    maximo = dens.max()
    return dens / maximo if maximo > 0 else dens


# ------------------------------------------------------------------ dados

def calcula(res, topo: int = TOPO_NOS, suavizacao: int = SUAVIZACAO,
            largura: float = LARGURA - 2 * MARGEM_QUADRO,
            altura: float = ALTURA_QUADRO) -> dict:
    """Posições, pesos e grade de densidade (sem desenhar).

    Devolve ``{"nos": [...], ...}``; ``nos`` fica vazio, com ``aviso``, quando a rede
    tem poucos itens ou nenhuma ligação. As posições vão de 0 a ``largura``/``altura``.
    """
    topo = max(LIMITE_NOS[0], min(LIMITE_NOS[1], int(topo)))
    suavizacao = max(LIMITE_SUAVIZACAO[0], min(LIMITE_SUAVIZACAO[1], int(suavizacao)))
    rede = res.rede
    freq = res.frequencia_nos
    ordem = sorted(rede.nos, key=lambda no: (-freq.get(no, 0), limpa(res.rotulo(no)), str(no)))
    nos = ordem[:topo]
    n = len(nos)
    vazio = {"nos": [], "total": len(ordem), "suavizacao": suavizacao, "topo": topo}
    if n < MINIMO_NOS:
        return {**vazio, "aviso": f"Poucos itens na rede ({n}) para um mapa de densidade "
                                  f"(mínimo de {MINIMO_NOS})."}
    posicao = {no: i for i, no in enumerate(nos)}
    s = np.zeros((n, n))
    for a, b, valor in rede.arestas():
        if a in posicao and b in posicao and a != b and valor > 0:
            i, j = posicao[a], posicao[b]
            s[i, j] = s[j, i] = max(s[i, j], float(valor))
    maximo = s.max()
    if maximo <= 0:
        return {**vazio, "aviso": "Os itens mais frequentes não têm ligações entre si; "
                                  "não há como posicioná-los."}
    x = layout_vos(s / maximo)
    # Itens soltos (sem ligação forte com o resto) são empurrados para longe pela repulsão
    # e esticariam o mapa: acima de R (1,3 × o percentil 85 da distância ao centro), o
    # excesso de distância é comprimido a 25%, sem mudar a direção do item.
    centro = np.median(x, axis=0)
    dist = np.linalg.norm(x - centro, axis=1)
    raio = 1.3 * float(np.percentile(dist, 85))
    if raio > 0:
        nova = np.where(dist > raio, raio + (dist - raio) * COMPRESSAO_PERIFERIA, dist)
        x = centro + (x - centro) * (nova / np.maximum(dist, 1e-12))[:, None]
    amplitude = np.maximum(np.ptp(x, axis=0), 1e-9)
    util = np.array([largura - 2 * MARGEM_NOS, altura - 2 * MARGEM_NOS])
    esc = float(min(util / amplitude))
    x = (x - (x.max(axis=0) + x.min(axis=0)) / 2) * esc + np.array([largura, altura]) / 2
    pesos = np.array([max(freq.get(no, 1), 1) for no in nos], float)
    sigma = suavizacao * SIGMA_POR_PASSO * largura
    colunas, linhas = int(largura // RESOLUCAO), int(altura // RESOLUCAO)
    dens = densidade_gaussiana(x[:, 0], x[:, 1], pesos, largura, altura, sigma, colunas, linhas)
    return {"nos": nos, "x": x[:, 0], "y": x[:, 1], "pesos": pesos, "densidade": dens,
            "sigma": sigma, "total": len(ordem), "suavizacao": suavizacao, "topo": topo,
            "largura": largura, "altura": altura}


# ------------------------------------------------------------------ rótulos

def _fonte(peso: float, maximo: float) -> float:
    return 11.0 + 7.0 * math.sqrt(peso / maximo)


def escolhe_rotulos(textos: list[str], x, y, pesos, caixa: tuple[float, float, float, float],
                    maximo: int = MAX_ROTULOS) -> list[tuple[int, float, float, float]]:
    """Rótulos por ordem de frequência, sem sobreposição e inteiros dentro de ``caixa``.

    Devolve (índice, caixa-largura, caixa-altura, tamanho da fonte); a caixa é centrada
    no ponto do item.
    """
    x0, y0, x1, y1 = caixa
    pmax = float(max(pesos)) or 1.0
    ocupadas: list[tuple[float, float, float, float]] = []
    escolhidos = []
    for i in sorted(range(len(textos)), key=lambda k: (-pesos[k], k)):
        fs = _fonte(pesos[i], pmax)
        larg = _largura_texto(textos[i], fs) * 1.06 + 8
        alt = fs + 5
        b = (x[i] - larg / 2, y[i] - alt / 2, x[i] + larg / 2, y[i] + alt / 2)
        if b[0] < x0 + 4 or b[2] > x1 - 4 or b[1] < y0 + 4 or b[3] > y1 - 4:
            continue
        if any(not (b[2] < c[0] or b[0] > c[2] or b[3] < c[1] or b[1] > c[3]) for c in ocupadas):
            continue
        ocupadas.append(b)
        escolhidos.append((i, larg, alt, fs))
        if len(escolhidos) >= maximo:
            break
    return escolhidos


def _corta(texto: str, limite: int = LIMITE_ROTULO) -> str:
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"


# ------------------------------------------------------------------ SVG

def svg(res, titulo: str = "", topo: int = TOPO_NOS, suavizacao: int = SUAVIZACAO,
        rotulos_max: int = MAX_ROTULOS, unidade: str = "", dados: dict | None = None) -> str:
    """Mapa de densidade do resultado ``res`` ou "" quando não há o que desenhar.

    Com ``titulo`` vazio a figura não leva faixa de título (a interface já tem o seu).
    ``dados`` aceita o retorno de `calcula` já pronto, para não repetir o layout.
    """
    d = dados if dados is not None else calcula(res, topo, suavizacao)
    if not d["nos"]:
        return ""
    larg_q, alt_q = d["largura"], d["altura"]
    topo_q = TOPO_TITULO if titulo else 12
    altura_total = topo_q + alt_q + RODAPE
    qx, qy = MARGEM_QUADRO, topo_q                   # canto do quadro no SVG
    textos_cheios = [limpa(res.rotulo(no)) or str(no) for no in d["nos"]]
    textos = [_corta(t) for t in textos_cheios]
    escolhidos = escolhe_rotulos(textos, d["x"] + qx, d["y"] + qy, d["pesos"],
                                 (qx, qy, qx + larg_q, qy + alt_q), rotulos_max)

    img = mapa_de_cores(d["densidade"] ** GAMMA)
    uri = "data:image/png;base64," + base64.b64encode(_png_rgb(img)).decode("ascii")
    chave = hashlib.sha1((repr(textos) + f"{d['suavizacao']}|{len(d['nos'])}|{titulo}")
                         .encode("utf-8")).hexdigest()[:8]
    p = f"dn{chave}"
    nome = NOMES_UNIDADE.get(unidade, "itens")
    resumo = (f"Mapa de densidade de {nome}: {len(d['nos'])} itens mais frequentes; "
              "as áreas mais quentes concentram itens frequentes e fortemente ligados.")
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {LARGURA} {altura_total:g}" '
         f'width="{LARGURA}" height="{altura_total:g}" font-family="{FONTE}" role="img" '
         f'aria-labelledby="{p}-t {p}-d">'
         f'<title id="{p}-t">{_esc(titulo or "Mapa de densidade")}</title>'
         f'<desc id="{p}-d">{_esc(resumo)}</desc>',
         f'<rect width="{LARGURA}" height="{altura_total:g}" fill="#fff"/>']
    if titulo:
        o.append(f'<text x="{qx}" y="30" font-size="16" font-weight="700" fill="{TINTA}">'
                 f'{_esc(_corta(limpa(titulo), 110))}</text>')
    o.append(f'<image href="{uri}" x="{qx}" y="{qy}" width="{larg_q:g}" height="{alt_q:g}" '
             'preserveAspectRatio="none"/>')
    o.append(f'<rect x="{qx}" y="{qy}" width="{larg_q:g}" height="{alt_q:g}" fill="none" '
             'stroke="#CBD5E1" stroke-width="1"/>')
    for x, y in zip(d["x"], d["y"]):
        o.append(f'<circle cx="{x + qx:.1f}" cy="{y + qy:.1f}" r="1.8" fill="{TINTA}" '
                 'fill-opacity=".38"/>')
    for i, _larg, _alt, fs in escolhidos:
        x, y = d["x"][i] + qx, d["y"][i] + qy
        o.append(f'<text x="{x:.1f}" y="{y + fs * 0.35:.1f}" text-anchor="middle" '
                 f'font-size="{fs:.1f}" fill="{TINTA}" stroke="#fff" stroke-width="3" '
                 'paint-order="stroke" stroke-linejoin="round" stroke-opacity=".75">'
                 f'<title>{_esc(textos_cheios[i])} — {int(d["pesos"][i])} '
                 f'documentos</title>{_esc(textos[i])}</text>')
    # Legenda na faixa de baixo, toda dentro do SVG.
    ly = qy + alt_q + 20
    paradas = "".join(f'<stop offset="{a:g}" stop-color="rgb({c[0]},{c[1]},{c[2]})"/>'
                      for a, c in PARADAS)
    o.append(f'<defs><linearGradient id="{p}-g" x1="0" x2="1" y1="0" y2="0">{paradas}'
             "</linearGradient></defs>")
    o.append(f'<rect x="{qx}" y="{ly}" width="220" height="10" rx="2" fill="url(#{p}-g)" '
             'stroke="#CBD5E1" stroke-width=".8"/>')
    o.append(f'<text x="{qx}" y="{ly + 25}" font-size="11" fill="{TINTA_FRACA}">menor densidade</text>')
    o.append(f'<text x="{qx + 220}" y="{ly + 25}" font-size="11" text-anchor="end" '
             f'fill="{TINTA_FRACA}">maior densidade</text>')
    o.append(f'<text x="{qx + larg_q}" y="{ly + 9}" font-size="11" text-anchor="end" '
             f'fill="{TINTA_FRACA}">{len(d["nos"])} de {d["total"]} {_esc(nome)} · '
             f'{len(escolhidos)} rótulos · suavização {d["suavizacao"]}</text>')
    o.append("</svg>")
    return "\n".join(o)

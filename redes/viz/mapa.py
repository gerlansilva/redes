"""Mapa de colaboração entre países.

Desenha o mundo em projeção Natural Earth, uma esfera por país (área
proporcional ao número de documentos) e uma curva por cooperação entre dois
países (espessura proporcional ao número de documentos em comum). Os rótulos
saem em chamada, com linha-guia, para não se sobrepor na Europa.

O contorno dos países vem de ``assets/mundo.geo.json`` (Natural Earth, domínio
público), embutido no pacote para não depender de rede.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from itertools import combinations
from pathlib import Path

from ..paises import _PAISES

CAMINHO_MUNDO = Path(__file__).resolve().parent.parent / "assets" / "mundo.geo.json"

TINTA = "#0B1F66"
TINTA_FRACA = "#64748B"
AZUL = "#2F2BFF"
ROXO = "#6A3BFF"
AMBAR = "#FFC400"
FUNDO = "#F7F8FB"
TERRA = "#E9E7F4"
TERRA_ATIVA = "#DCD8F7"
COSTA = "#FFFFFF"
FONTE = "Helvetica, Arial, sans-serif"

# Nomes que a base de países e a geometria grafam de formas diferentes.
ALIASES = {
    "estados unidos": "united states of america",
    "reino unido": "united kingdom",
    "coreia do sul": "south korea",
    "coreia do norte": "north korea",
    "republica tcheca": "czech republic",
    "russia": "russia",
    "vietna": "vietnam",
    "costa do marfim": "ivory coast",
    "macedonia do norte": "macedonia",
}


def _chave(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = texto.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _indicadores(documentos: dict[str, int], pares: list[tuple[str, str, int]],
                 total: int, internacionais: int) -> dict:
    graus = {pais: 0 for pais in documentos}
    for a, b, _ in pares:
        graus[a] += 1
        graus[b] += 1
    n = max(1, len(documentos))
    return {
        "documentos": documentos,
        "ligacoes": pares,
        "total": total,
        "internacionais": internacionais,
        "densidade": 2 * len(pares) / (n * (n - 1)) if n > 1 else 0.0,
        "grau_medio": sum(graus.values()) / n,
        "maior": max(pares, key=lambda x: x[2]) if pares else ("", "", 0),
        "mais_conectado": max(graus, key=graus.get) if graus else "",
        "grau_maximo": max(graus.values()) if graus else 0,
    }


def colaboracao_do_periodo(kb, periodo_id: int, minimo_frequencia: int = 1) -> dict:
    """Mesmos indicadores, restritos aos documentos de um período."""
    conjunto = kb.dataset("Countries", periodo_id)
    conjunto.filtra_itens_por_frequencia(max(1, minimo_frequencia))
    documentos: dict[str, int] = {}
    ligacoes: dict[tuple[str, str], int] = {}
    internacionais = 0
    for doc in conjunto.lista_documentos():
        paises = sorted({conjunto.rotulo_item(item)
                         for item in conjunto.itens_do_documento(doc)
                         if item is not None})
        if len(paises) > 1:
            internacionais += 1
        for pais in paises:
            documentos[pais] = documentos.get(pais, 0) + 1
        for a, b in combinations(paises, 2):
            ligacoes[(a, b)] = ligacoes.get((a, b), 0) + 1
    pares = [(a, b, p) for (a, b), p in sorted(ligacoes.items())]
    return _indicadores(documentos, pares, len(conjunto.lista_documentos()), internacionais)


def colaboracao(banco) -> dict:
    """Documentos por país, cooperações e indicadores, lidos do projeto."""
    import sqlite3

    con = sqlite3.connect(banco)
    nomes = dict(con.execute("SELECT idCountry, countryName FROM Country"))
    por_documento: dict[int, list[str]] = {}
    for doc, pais in con.execute("SELECT Document_idDocument, Country_idCountry FROM Document_Country"):
        por_documento.setdefault(doc, []).append(nomes[pais])
    total = con.execute("SELECT COUNT(*) FROM Document").fetchone()[0]

    documentos: dict[str, int] = {}
    ligacoes: dict[tuple[str, str], int] = {}
    internacionais = 0
    for paises in por_documento.values():
        unicos = sorted(set(paises))
        if len(unicos) > 1:
            internacionais += 1
        for pais in unicos:
            documentos[pais] = documentos.get(pais, 0) + 1
        for a, b in combinations(unicos, 2):
            ligacoes[(a, b)] = ligacoes.get((a, b), 0) + 1

    pares = [(a, b, p) for (a, b), p in sorted(ligacoes.items())]
    return _indicadores(documentos, pares, total, internacionais)


def _nome_em_ingles(pais: str) -> str:
    chave = _chave(pais)
    if chave in ALIASES:
        return ALIASES[chave]
    for ingles, portugues in _PAISES.items():
        if _chave(portugues) == chave:
            return ALIASES.get(ingles, ingles)
    return chave


def _anilhas(geometria: dict) -> list[list[tuple[float, float]]]:
    """Anéis exteriores e interiores de um Polygon ou MultiPolygon."""
    tipo = geometria.get("type")
    coordenadas = geometria.get("coordinates") or []
    poligonos = [coordenadas] if tipo == "Polygon" else coordenadas
    aneis: list[list[tuple[float, float]]] = []
    for poligono in poligonos:
        for anel in poligono:
            aneis.append([(p[0], p[1]) for p in anel])
    return aneis


def _centroide(anel: list[tuple[float, float]]) -> tuple[float, float]:
    area = cx = cy = 0.0
    for i, (x0, y0) in enumerate(anel):
        x1, y1 = anel[(i + 1) % len(anel)]
        fator = x0 * y1 - x1 * y0
        area += fator
        cx += (x0 + x1) * fator
        cy += (y0 + y1) * fator
    if abs(area) < 1e-12:
        xs = [p[0] for p in anel]
        ys = [p[1] for p in anel]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    area *= 0.5
    return cx / (6 * area), cy / (6 * area)


def _natural_earth(lon: float, lat: float) -> tuple[float, float]:
    """Projeção Natural Earth, em radianos de saída."""
    lam = math.radians(lon)
    phi = math.radians(max(-89.9, min(89.9, lat)))
    p2 = phi * phi
    p4 = p2 * p2
    x = lam * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)))
    y = phi * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)))
    return x, y


class Mundo:
    """Geometria do mundo já projetada sobre a caixa de desenho."""

    def __init__(self, largura: int, altura: int, margem: float = 8, topo: float = 0) -> None:
        dados = json.loads(CAMINHO_MUNDO.read_text(encoding="utf-8"))
        self.paises: dict[str, list[list[tuple[float, float]]]] = {}
        self.centros: dict[str, tuple[float, float]] = {}
        for feicao in dados["features"]:
            nome = _chave(feicao["properties"]["name"])
            aneis = _anilhas(feicao["geometry"])
            if not aneis:
                continue
            self.paises[nome] = aneis
            maior = max(aneis, key=len)
            self.centros[nome] = _centroide(maior)

        # Escala pela caixa útil do mundo: evita a faixa vazia do extremo sul.
        pontos = [_natural_earth(lon, lat)
                  for lon in range(-180, 181, 4)
                  for lat in range(-58, 85, 4)]
        xs = [p[0] for p in pontos]
        ys = [p[1] for p in pontos]
        escala = min((largura - 2 * margem) / (max(xs) - min(xs)),
                     (altura - 2 * margem) / (max(ys) - min(ys)))
        self.escala = escala
        self.dx = margem - min(xs) * escala + (largura - 2 * margem - (max(xs) - min(xs)) * escala) / 2
        self.dy = margem + max(ys) * escala + (altura - 2 * margem - (max(ys) - min(ys)) * escala) / 2 + topo

    def ponto(self, lon: float, lat: float) -> tuple[float, float]:
        x, y = _natural_earth(lon, lat)
        return x * self.escala + self.dx, self.dy - y * self.escala

    def posicao(self, nome_ingles: str) -> tuple[float, float] | None:
        lon, lat = self.centros[nome_ingles]
        return self.ponto(lon, lat)

    def caminho(self, aneis: list[list[tuple[float, float]]]) -> str:
        partes: list[str] = []
        for anel in aneis:
            trecho: list[str] = []
            anterior: tuple[float, float] | None = None
            for lon, lat in anel:
                x, y = self.ponto(lon, lat)
                if anterior is None or abs(x - anterior[0]) > self.escala * 2.2:
                    if trecho:
                        partes.append("M " + " L ".join(f"{a:.1f},{b:.1f}" for a, b in trecho) + " Z")
                    trecho = [(x, y)]
                else:
                    trecho.append((x, y))
                anterior = (x, y)
            if trecho:
                partes.append("M " + " L ".join(f"{a:.1f},{b:.1f}" for a, b in trecho) + " Z")
        return " ".join(partes)


def _curva(a: tuple[float, float], b: tuple[float, float], peso: float) -> str:
    (x1, y1), (x2, y2) = a, b
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy) or 1.0
    curvatura = min(0.22, 0.1 + peso * 0.02)
    cx = mx - dy * curvatura
    cy = my + dx * curvatura
    return f"M {x1:.1f},{y1:.1f} Q {cx:.1f},{cy:.1f} {x2:.1f},{y2:.1f}"


def _caixa(x: float, y: float, texto: str, tamanho: float) -> tuple[float, float, float, float]:
    largura = len(texto) * tamanho * 0.53 + 8
    return x, y - tamanho * 0.85, largura, tamanho * 1.15


def _colide(a, b) -> bool:
    return not (a[0] + a[2] < b[0] or b[0] + b[2] < a[0]
                or a[1] + a[3] < b[1] or b[1] + b[3] < a[1])


def _metricas_svg(metricas: list[tuple[str, str]], largura: int, y: float,
                  altura: float = 78) -> list[str]:
    """Faixa de métricas em cartões, abaixo da figura."""
    if not metricas:
        return []
    partes = [f'<rect x="24" y="{y:.0f}" width="{largura - 48}" height="{altura:.0f}" rx="10" '
              f'fill="#FFFFFF" stroke="#E2E5EE" stroke-width="1"/>']
    coluna = (largura - 48) / len(metricas)
    for i, (valor, rotulo) in enumerate(metricas):
        x = 24 + coluna * i + coluna / 2
        if i:
            partes.append(f'<line x1="{24 + coluna * i:.0f}" y1="{y + 16:.0f}" '
                          f'x2="{24 + coluna * i:.0f}" y2="{y + altura - 16:.0f}" '
                          f'stroke="#EEF0F6" stroke-width="1"/>')
        partes.append(f'<text x="{x:.0f}" y="{y + 34:.0f}" text-anchor="middle" font-family="{FONTE}" '
                      f'font-size="19" font-weight="600" fill="{TINTA}">{_escapa(valor)}</text>')
        partes.append(f'<text x="{x:.0f}" y="{y + 54:.0f}" text-anchor="middle" font-family="{FONTE}" '
                      f'font-size="10.5" fill="{TINTA_FRACA}">{_escapa(rotulo)}</text>')
    return partes


def mapa_svg(documentos_por_pais: dict[str, int],
             ligacoes: list[tuple[str, str, int]],
             titulo: str = "Colaboração entre países",
             largura: int = 1120, altura: int = 720,
             destaque: str = "", legenda: str = "",
             subtitulo: str = "",
             metricas: list[tuple[str, str]] | None = None) -> str:
    """SVG do mapa. ``ligacoes`` traz pares de países e o peso."""
    if not documentos_por_pais:
        raise ValueError("não há países para desenhar")

    metricas = metricas or []
    altura_metricas = 96 if metricas else 0
    topo, base = 96, 54 + altura_metricas
    mundo = Mundo(largura, altura - topo - base, topo=topo)
    posicoes: dict[str, tuple[float, float]] = {}
    ausentes: list[str] = []
    for pais in documentos_por_pais:
        ingles = _nome_em_ingles(pais)
        ponto = mundo.posicao(ingles)
        if ponto is None:
            ausentes.append(pais)
        else:
            posicoes[pais] = ponto

    maximo = max(documentos_por_pais.values())
    max_peso = max((p for _, _, p in ligacoes), default=1)

    def raio(n: int) -> float:
        return 4.0 + 17.0 * math.sqrt(n / maximo)

    partes: list[str] = []
    partes.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
                  f'viewBox="0 0 {largura} {altura}" role="img" aria-label="{_escapa(titulo)}">')
    partes.append(f'<rect width="{largura}" height="{altura}" fill="{FUNDO}"/>')

    # Cabeçalho separado do mapa por uma linha fina.
    partes.append(f'<text x="28" y="38" font-family="{FONTE}" font-size="20" font-weight="600" '
                  f'fill="{TINTA}">{_escapa(titulo)}</text>')
    if subtitulo:
        partes.append(f'<text x="28" y="62" font-family="{FONTE}" font-size="13" '
                      f'fill="{TINTA_FRACA}">{_escapa(subtitulo)}</text>')
    partes.append(f'<line x1="24" y1="80" x2="{largura - 24}" y2="80" stroke="#E2E5EE" stroke-width="1"/>')

    ativos = {_nome_em_ingles(p) for p in documentos_por_pais}
    for nome, aneis in mundo.paises.items():
        cor = TERRA_ATIVA if nome in ativos else TERRA
        partes.append(f'<path d="{mundo.caminho(aneis)}" fill="{cor}" stroke="{COSTA}" '
                      f'stroke-width="0.6"/>')

    # Curvas de cooperação, das mais fracas para as mais fortes.
    for a, b, peso in sorted(ligacoes, key=lambda x: x[2]):
        if a not in posicoes or b not in posicoes:
            continue
        espessura = 0.8 + 4.6 * (peso / max_peso)
        opacidade = 0.22 + 0.5 * (peso / max_peso)
        partes.append(f'<path d="{_curva(posicoes[a], posicoes[b], peso)}" fill="none" '
                      f'stroke="{ROXO}" stroke-width="{espessura:.2f}" stroke-opacity="{opacidade:.2f}" '
                      f'stroke-linecap="round"/>')

    # Esferas.
    ordem = sorted(documentos_por_pais.items(), key=lambda kv: kv[1])
    for pais, n in ordem:
        if pais not in posicoes:
            continue
        x, y = posicoes[pais]
        r = raio(n)
        if pais == destaque:
            partes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{AZUL}" '
                          f'fill-opacity="0.92" stroke="{AMBAR}" stroke-width="2.4"/>')
        else:
            partes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#FFFFFF" '
                          f'fill-opacity="0.95" stroke="{AZUL}" stroke-width="2"/>')

    # Rótulos em duas linhas (país e frequência), com desvio e linha-guia.
    ocupados: list[tuple[float, float, float, float]] = []
    for pais, n in documentos_por_pais.items():
        if pais not in posicoes:
            continue
        x, y = posicoes[pais]
        r = raio(n)
        ocupados.append((x - r - 3, y - r - 3, 2 * r + 6, 2 * r + 6))

    def _caixa_rotulo(x: float, y: float, nome: str, n: int, tamanho: float):
        largura_texto = len(f"{nome} {n}") * tamanho * 0.55 + 12
        return (x - largura_texto / 2, y - tamanho * 0.95, largura_texto, tamanho * 1.4)

    # Direções preferidas: para fora do centro do mapa, para não empilhar na Europa.
    cx0, cy0 = largura / 2, topo + (altura - topo - base) / 2
    direcoes = [(math.cos(a), math.sin(a)) for a in
                [math.radians(g) for g in range(-90, 270, 30)]]
    pendentes: list[tuple[str, int, float, float, float, float]] = []
    for pais, n in sorted(documentos_por_pais.items(), key=lambda kv: -kv[1]):
        if pais not in posicoes:
            continue
        x, y = posicoes[pais]
        r = raio(n)
        tamanho = 13.5 if pais == destaque or n >= maximo * 0.3 else 12.0
        angulo = math.atan2(y - cy0, x - cx0)
        ordem_direcoes = sorted(
            direcoes,
            key=lambda d: abs(math.atan2(d[1], d[0]) - angulo) % (2 * math.pi))
        melhor = None
        for dx, dy in ordem_direcoes:
            for afastamento in (12, 22, 34, 48, 64, 84):
                lx = x + dx * (r + afastamento)
                ly = y + dy * (r + afastamento)
                caixa = _caixa_rotulo(lx, ly, pais, n, tamanho)
                if caixa[0] < 8 or caixa[0] + caixa[2] > largura - 8:
                    continue
                if caixa[1] < topo - 6 or caixa[1] + caixa[3] > altura - base + 6:
                    continue
                if any(_colide(caixa, outro) for outro in ocupados):
                    continue
                melhor = (lx, ly, caixa, dx, dy)
                break
            if melhor:
                break
        if melhor is None:
            pendentes.append((pais, n, x, y, r, tamanho))
            continue
        lx, ly, caixa, dx, dy = melhor
        ocupados.append(caixa)
        ancora_x = x + dx * r * 0.98
        ancora_y = y + dy * r * 0.98
        if abs(lx - x) > r + 16 or abs(ly - y) > r + 16:
            partes.append(f'<path d="M {ancora_x:.1f},{ancora_y:.1f} L {lx:.1f},{ly - tamanho * 0.55:.1f}" '
                          f'stroke="{TINTA_FRACA}" stroke-width="0.9" stroke-opacity="0.45" fill="none"/>')
        partes.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-family="{FONTE}" '
                      f'font-size="{tamanho}" fill="{TINTA}" stroke="{FUNDO}" stroke-width="3.2" '
                      f'paint-order="stroke" stroke-linejoin="round">'
                      f'<tspan font-weight="600">{_escapa(pais)}</tspan>'
                      f'<tspan dx="5" fill="{AZUL}">{n}</tspan></text>')

    # O que não coube sem sobreposição não recebe rótulo no mapa: vai para a nota.
    sem_rotulo = sorted(pendentes, key=lambda p: p[0])

    rodape = altura - altura_metricas
    marcas = [v for v in (1, 10, 100, 1000) if v <= maximo] or [1]
    largura_marcas = sum(2 * raio(v) + 22 for v in marcas)
    x_rotulo = largura - 36 - largura_marcas
    partes.append(f'<text x="{x_rotulo:.1f}" y="{rodape - 46}" text-anchor="end" font-family="{FONTE}" '
                  f'font-size="11" fill="{TINTA_FRACA}">documentos</text>')
    xm = largura - 36
    raio_maior = max(raio(v) for v in marcas)
    y_marca = rodape - 30 - raio_maior
    for valor in sorted(marcas, reverse=True):
        r = raio(valor)
        xm -= r
        partes.append(f'<circle cx="{xm:.1f}" cy="{y_marca:.1f}" r="{r:.1f}" fill="#FFFFFF" '
                      f'stroke="{AZUL}" stroke-width="1.6"/>')
        partes.append(f'<text x="{xm:.1f}" y="{y_marca + raio_maior + 14:.1f}" text-anchor="middle" '
                      f'font-family="{FONTE}" font-size="10.5" fill="{TINTA_FRACA}">{valor}</text>')
        xm -= r + 22

    texto_rodape = f"Redes · {legenda}" if legenda else "Redes"
    partes.append(f'<text x="28" y="{rodape - 34}" font-family="{FONTE}" font-size="12.5" '
                  f'fill="{TINTA_FRACA}">{_escapa(texto_rodape)}</text>')
    if sem_rotulo:
        lista = ", ".join(f"{pais} {n}" for pais, n, *_ in sem_rotulo)
        partes.append(f'<text x="28" y="{rodape - 12}" font-family="{FONTE}" font-size="11" '
                      f'fill="{TINTA_FRACA}">Sem rótulo no mapa, por falta de espaço: '
                      f'{_escapa(lista)}</text>')

    partes.extend(_metricas_svg(metricas, largura, rodape + 6))

    partes.append("</svg>")
    return "\n".join(partes)


def _escapa(texto: str) -> str:
    return (texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# --------------------------------------------------------------- versão web

_CONTORNO: dict[tuple[int, int], list[dict]] = {}


def contorno(largura: int = 1000, altura: int = 560) -> list[dict]:
    """Contorno do mundo projetado em caminhos SVG, pronto para o canvas."""
    chave = (int(largura), int(altura))
    if chave not in _CONTORNO:
        mundo = Mundo(largura, altura)
        _CONTORNO[chave] = [{"n": nome, "d": mundo.caminho(aneis)}
                            for nome, aneis in mundo.paises.items()]
    return _CONTORNO[chave]


def dados_mapa(documentos_por_pais: dict[str, int],
               ligacoes: list[tuple[str, str, int]],
               largura: int = 1000, altura: int = 560,
               destaque: str = "") -> dict:
    """Dados do mapa interativo: posições, contorno e ligações indexadas."""
    mundo = Mundo(largura, altura)
    paises: list[dict] = []
    indice: dict[str, int] = {}
    for nome, quantidade in documentos_por_pais.items():
        ponto = mundo.posicao(_nome_em_ingles(nome))
        if ponto is None:
            continue
        indice[nome] = len(paises)
        paises.append({"nome": nome, "geo": _nome_em_ingles(nome),
                       "x": round(ponto[0], 1), "y": round(ponto[1], 1),
                       "documentos": int(quantidade)})

    graus = [0] * len(paises)
    arestas: list[list[int]] = []
    for a, b, peso in ligacoes:
        if a in indice and b in indice:
            i, j = indice[a], indice[b]
            arestas.append([i, j, int(peso)])
            graus[i] += 1
            graus[j] += 1
    for pais, grau in zip(paises, graus):
        pais["parceiros"] = grau

    return {
        "largura": int(largura),
        "altura": int(altura),
        "contorno": contorno(largura, altura),
        "paises": paises,
        "ligacoes": arestas,
        "maximo": max((p["documentos"] for p in paises), default=1),
        "max_peso": max((a[2] for a in arestas), default=1),
        "destaque": destaque if destaque in indice else "",
    }

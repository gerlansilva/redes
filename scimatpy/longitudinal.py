"""Mapas longitudinais: evolução temática e sobreposição entre períodos.

O fork constrói dois artefatos, ambos reproduzidos aqui:

- **mapa de evolução** (`EvolutionMapBuilder`): para cada par de períodos
  consecutivos, liga um agrupamento do período anterior a um do seguinte
  quando eles compartilham itens. O peso é a medida de sobreposição escolhida,
  aplicada ao tamanho dos dois conjuntos e ao da interseção. O elo é destacado
  quando os dois agrupamentos compartilham o nó principal;
- **mapa de sobreposição** (`OverlappingMapBuilder`): matriz entre todos os
  períodos, com a mesma medida aplicada ao conjunto de itens de cada um.

As medidas são as mesmas do resto do pacote (equivalência, associação,
inclusão, Jaccard e Salton), calculadas sobre conjuntos de itens.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field

from .pipeline import Configuracao, executa_periodo
from .similarity import MEDIDAS

NOMES_MEDIDA = {
    "AssociationStrength": "força de associação",
    "EquivalenceIndex": "índice de equivalência",
    "InclusionIndex": "índice de inclusão",
    "JaccardIndex": "índice de Jaccard",
    "SaltonCosine": "cosseno de Salton",
}


def _nome_medida(nome: str) -> str:
    return NOMES_MEDIDA.get(nome, nome)

MEDIDAS_TEMPORAIS = tuple(MEDIDAS)


@dataclass
class No:
    periodo: int          # posição do período (0..n-1)
    selo: int            # posição do agrupamento no período
    rotulo: str
    itens: set[int]
    principal: int | None
    tamanho: int

    def contem_principal(self, outro: "No") -> bool:
        return (self.principal is not None and self.principal in outro.itens) or (
            outro.principal is not None and outro.principal in self.itens)


@dataclass
class Elo:
    origem: No
    destino: No
    peso: float
    principal_comum: bool


@dataclass
class Evolucao:
    periodos: list[str]
    nos: list[No] = field(default_factory=list)
    elos: list[Elo] = field(default_factory=list)
    sobreposicao: list[list[float]] = field(default_factory=list)
    medida: str = "EquivalenceIndex"

    def nos_do_periodo(self, indice: int) -> list[No]:
        return [no for no in self.nos if no.periodo == indice]


def mede_conjuntos(medida: str, origem: set[int], destino: set[int]) -> float:
    """Aplica a medida de similaridade a dois conjuntos de itens."""
    comum = len(origem & destino)
    if not comum:
        return 0.0
    funcao = MEDIDAS[medida]
    valor = funcao(len(origem), len(destino), comum)
    return valor if math.isfinite(valor) else 0.0


def constroi(kb, config: Configuracao, periodos, medida: str = "EquivalenceIndex",
             limite_elos: int = 3) -> Evolucao:
    """Executa a análise de cada período e monta evolução e sobreposição."""
    if medida not in MEDIDAS:
        raise ValueError(f"medida temporal inválida: {medida}")

    resultados = [executa_periodo(kb, p.id, p.nome, config) for p in periodos]
    mapa = Evolucao(periodos=[p.nome for p in periodos], medida=medida)

    for indice, resultado in enumerate(resultados):
        grupos = sorted(resultado.grupos,
                        key=lambda g: (-len(g.nos), g.rotulo or ""))
        for selo, grupo in enumerate(grupos, start=1):
            mapa.nos.append(No(
                periodo=indice, selo=selo, rotulo=grupo.rotulo,
                itens=set(grupo.nos), principal=grupo.principal,
                tamanho=len(grupo.nos)))

    # Evolução: só pares consecutivos, como no EvolutionMapBuilder.
    for indice in range(len(periodos) - 1):
        origem = mapa.nos_do_periodo(indice)
        destino = mapa.nos_do_periodo(indice + 1)
        candidatos: list[Elo] = []
        for a in origem:
            for b in destino:
                peso = mede_conjuntos(medida, a.itens, b.itens)
                if peso > 0.0:
                    candidatos.append(Elo(a, b, peso, a.contem_principal(b)))
        # Mantém os elos mais fortes de cada agrupamento de origem, para o
        # desenho não virar uma teia ilegível em períodos grandes.
        candidatos.sort(key=lambda elo: -elo.peso)
        usados: dict[int, int] = {}
        for elo in candidatos:
            chave = elo.origem.selo
            if usados.get(chave, 0) >= limite_elos:
                continue
            usados[chave] = usados.get(chave, 0) + 1
            mapa.elos.append(elo)

    # Sobreposição: todos os pares de períodos.
    conjuntos = [set().union(*(no.itens for no in mapa.nos_do_periodo(i)))
                 if mapa.nos_do_periodo(i) else set()
                 for i in range(len(periodos))]
    mapa.sobreposicao = [
        [mede_conjuntos(medida, conjuntos[i], conjuntos[j])
         for j in range(len(periodos))]
        for i in range(len(periodos))
    ]
    return mapa


# ------------------------------------------------------------------- desenho


def _cor(peso: float, forte: bool) -> str:
    if forte:
        return "#2F2BFF" if peso >= 0.5 else "#6A3BFF"
    return "#CBD5E1"


def evolucao_svg(mapa: Evolucao, titulo: str = "Mapa de evolução",
                 largura: int = 960) -> str:
    """Desenha o mapa de evolução em SVG, com uma coluna por período."""
    periodos = len(mapa.periodos)
    altura_faixa = 34
    margem_topo = 74
    margem_base = 44
    margem_lado = 34
    coluna = max(200, (largura - 2 * margem_lado) // max(1, periodos)
                 if periodos else largura)
    maior = max((len(mapa.nos_do_periodo(i)) for i in range(periodos)), default=1)
    altura = margem_topo + margem_base + altura_faixa * max(1, maior)

    def x(indice: int) -> float:
        return margem_lado + coluna * (indice + 0.5)

    def y(no: No) -> float:
        nos = mapa.nos_do_periodo(no.periodo)
        posicao = next((i for i, item in enumerate(nos) if item.selo == no.selo), 0)
        return margem_topo + altura_faixa * (posicao + 0.5)

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" role="img" '
        f'aria-label="{html.escape(titulo)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{largura/2}" y="30" text-anchor="middle" '
        'font-family="Inter, Arial, sans-serif" font-size="16" fill="#14204A">'
        f'{html.escape(titulo)}</text>',
        f'<text x="{largura/2}" y="50" text-anchor="middle" '
        'font-family="Helvetica, Arial, sans-serif" font-size="11" fill="#64748B">'
        f'medida de sobreposição: {html.escape(_nome_medida(mapa.medida))}</text>',
    ]

    for indice, nome in enumerate(mapa.periodos):
        partes.append(
            f'<text x="{x(indice)}" y="{margem_topo - 12}" text-anchor="middle" '
            'font-family="Helvetica, Arial, sans-serif" font-size="11" '
            f'font-weight="600" fill="#33405E">{html.escape(nome)}</text>')

    for elo in mapa.elos:
        x1, y1 = x(elo.origem.periodo), y(elo.origem)
        x2, y2 = x(elo.destino.periodo), y(elo.destino)
        espessura = 0.8 + 2.4 * min(1.0, elo.peso)
        partes.append(
            f'<path d="M {x1 + 6:.1f} {y1:.1f} C {(x1+x2)/2:.1f} {y1:.1f}, '
            f'{(x1+x2)/2:.1f} {y2:.1f}, {x2 - 6:.1f} {y2:.1f}" fill="none" '
            f'stroke="{_cor(elo.peso, elo.principal_comum)}" '
            f'stroke-width="{espessura:.2f}" opacity="0.55"/>')

    raio = 5.0
    for no in mapa.nos:
        cx, cy = x(no.periodo), y(no)
        partes.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{raio + min(5, no.tamanho/4):.1f}" '
            'fill="#EDEBFF" stroke="#2F2BFF" stroke-width="1.2"/>')
        rotulo = no.rotulo if len(no.rotulo) <= 22 else no.rotulo[:20] + "…"
        partes.append(
            f'<text x="{cx + 12:.1f}" y="{cy + 4:.1f}" '
            'font-family="Helvetica, Arial, sans-serif" font-size="10" '
            f'fill="#14204A">{html.escape(rotulo)}</text>')

    partes.append(
        f'<text x="{margem_lado}" y="{altura - 16}" '
        'font-family="Helvetica, Arial, sans-serif" font-size="10" fill="#64748B">'
        'elos coloridos: agrupamentos que compartilham o nó principal; '
        'cinza: demais sobreposições</text>')
    partes.append("</svg>")
    return "\n".join(partes)


def sobreposicao_svg(mapa: Evolucao, titulo: str = "Mapa de sobreposição",
                     largura: int = 660) -> str:
    """Matriz de sobreposição entre todos os períodos."""
    n = len(mapa.periodos)
    margem = 104
    # A célula tem tamanho fixo e confortável: a figura cresce com o número de
    # períodos em vez de esticar poucos períodos por toda a largura.
    celula = min(84, max(56, int((largura - margem - 24) / max(1, n))))
    altura = margem + celula * n + 42
    largura = margem + celula * n + 24

    def tom(valor: float) -> str:
        # Escala sequencial de branco ao azul principal da identidade.
        passo = max(0.0, min(1.0, valor))
        r = int(255 - 208 * passo)
        g = int(255 - 212 * passo)
        b = 255
        return f"#{r:02x}{g:02x}{b:02x}"

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" role="img" '
        f'aria-label="{html.escape(titulo)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{largura/2}" y="26" text-anchor="middle" '
        'font-family="Inter, Arial, sans-serif" font-size="15" fill="#14204A">'
        f'{html.escape(titulo)}</text>',
    ]
    for i, nome in enumerate(mapa.periodos):
        partes.append(
            f'<text x="{margem - 10}" y="{margem + celula * i + celula/2 + 4:.1f}" '
            'text-anchor="end" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="10.5" fill="#33405E">{html.escape(nome)}</text>')
        partes.append(
            f'<text x="{margem + celula * i + celula/2:.1f}" y="{margem - 8}" '
            'text-anchor="middle" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="10.5" fill="#33405E">{html.escape(nome)}</text>')

    for i in range(n):
        for j in range(n):
            valor = mapa.sobreposicao[i][j]
            cor = tom(valor)
            texto = "#ffffff" if valor >= 0.55 else "#14204A"
            partes.append(
                f'<rect x="{margem + celula*j}" y="{margem + celula*i}" '
                f'width="{celula-2}" height="{celula-2}" rx="4" fill="{cor}" '
                'stroke="#E9ECF2"/>')
            partes.append(
                f'<text x="{margem + celula*j + (celula-2)/2:.1f}" '
                f'y="{margem + celula*i + (celula-2)/2 + 4:.1f}" '
                'text-anchor="middle" font-family="Helvetica, Arial, sans-serif" '
                f'font-size="11" fill="{texto}">{valor:.3f}</text>')

    partes.append(
        f'<text x="{margem}" y="{altura - 14}" '
        'font-family="Helvetica, Arial, sans-serif" font-size="10" fill="#64748B">'
        f'medida: {html.escape(_nome_medida(mapa.medida))} — valores entre 0 e 1</text>')
    partes.append("</svg>")
    return "\n".join(partes)


# ------------------------------------------------------------------- Pajek


def evolucao_pajek(mapa: Evolucao) -> str:
    """Mapa de evolução em Pajek, no formato de `EvolutionMapPajek`."""
    linhas = [f"*Vertices {len(mapa.nos)}"]
    indice = {}
    for posicao, no in enumerate(mapa.nos, start=1):
        indice[id(no)] = posicao
        linhas.append(f'{posicao} "{no.rotulo.replace(chr(34), chr(39))}"')
    linhas.append("*Edges")
    for elo in mapa.elos:
        linhas.append(f"{indice[id(elo.origem)]} {indice[id(elo.destino)]} "
                      f"{elo.peso:.6g}")
    return "\n".join(linhas) + "\n"

"""Diagrama estratégico: centralidade × densidade, com quadrantes.

Cada esfera é um agrupamento; o eixo horizontal é a centralidade de Callon e o
vertical, a densidade, ambos na faixa normalizada (1..n)/n, com o cruzamento em
0,5 — o mesmo critério do SciMAT. O tamanho da esfera representa o número de
nós. Os rótulos ficam numerados, com a legenda ao lado, para que nada se
sobreponha.
"""

from __future__ import annotations

import html
import math

from .halo import (CINZA, FONTE, LARGURA_COLUNA_LEGENDA, PALETA, TINTA,
                   TINTA_FRACA, _rotulo_curto, geometria_legenda)

QUADRANTES = {
    "motor": ("Temas motores", "#2F2BFF", "#EDEBFF"),
    "nicho": ("Temas de nicho", "#067647", "#E6F8EE"),
    "emergente": ("Temas emergentes ou em declínio", "#A16207", "#FFF8D6"),
    "basico": ("Temas básicos e transversais", "#0B1F66", "#EEF2FF"),
}

# Países não são temas: o quadrante lê coesão interna × ligação ao resto.
QUADRANTES_PAISES = {
    "motor": ("Núcleos de cooperação", "#2F2BFF", "#EDEBFF"),
    "nicho": ("Grupos isolados", "#067647", "#E6F8EE"),
    "emergente": ("Periféricos", "#A16207", "#FFF8D6"),
    "basico": ("Cooperação dispersa", "#0B1F66", "#EEF2FF"),
}


CURTOS = {"motor": "Motores", "nicho": "Nicho",
          "emergente": "Emergentes", "basico": "Básicos"}
CURTOS_PAISES = {"motor": "Núcleos", "nicho": "Isolados",
                 "emergente": "Periféricos", "basico": "Dispersa"}

DESCRICOES = {
    "motor": "Alta centralidade e alta densidade: temas desenvolvidos e "
             "centrais no campo.",
    "nicho": "Baixa centralidade e alta densidade: temas coesos, porém "
             "periféricos e especializados.",
    "emergente": "Baixa centralidade e baixa densidade: temas em formação "
                 "ou em declínio.",
    "basico": "Alta centralidade e baixa densidade: temas básicos, "
              "transversais e pouco coesos.",
}
DESCRICOES_PAISES = {
    "motor": "Núcleos de cooperação: países centrais e com colaboração "
             "interna coesa.",
    "nicho": "Grupos isolados: colaboração coesa, mas pouco ligada ao "
             "restante.",
    "emergente": "Periféricos: participação fraca e pouco coesa.",
    "basico": "Cooperação dispersa: países centrais, com vínculos pouco "
              "coesos.",
}


def _curtos(unidade: str) -> dict:
    return CURTOS_PAISES if unidade == "Countries" else CURTOS


def _descricoes(unidade: str) -> dict:
    return DESCRICOES_PAISES if unidade == "Countries" else DESCRICOES


def _quadrantes(unidade: str) -> dict:
    return QUADRANTES_PAISES if unidade == "Countries" else QUADRANTES


def _quadrante(x: float, y: float) -> str:
    if x >= 0.5 and y >= 0.5:
        return "motor"
    if x < 0.5 and y >= 0.5:
        return "nicho"
    if x < 0.5:
        return "emergente"
    return "basico"


def diagrama_svg(resultado, titulo: str, largura: int = 1120, altura: int = 820,
                 legenda_largura: int = 330, metrica: str | None = None,
                 rotulo_metrica: str | None = None) -> str:
    grupos = resultado.grupos
    if not grupos:
        raise ValueError("não há agrupamentos para desenhar")

    unidade = resultado.configuracao.unidade
    rotulos = _quadrantes(unidade)
    ordem = sorted(range(len(grupos)),
                   key=lambda i: -len(grupos[i].nos))
    cores = {chave: valor[1] for chave, valor in rotulos.items()}
    fundos = {chave: valor[2] for chave, valor in rotulos.items()}

    pw = largura - legenda_largura
    legenda = geometria_legenda(len(grupos), altura, topo=118, base=206)
    legenda_largura = max(
        26 + legenda["colunas"] * LARGURA_COLUNA_LEGENDA, legenda_largura)
    largura = max(largura, 820 + legenda_largura)
    pw = largura - legenda_largura
    margem_esq, margem_dir = 70, 34
    margem_topo, margem_base = 84, 74
    x0, x1 = margem_esq, pw - margem_dir
    y0, y1 = margem_topo, altura - margem_base

    def px(valor: float) -> float:
        return x0 + valor * (x1 - x0)

    def py(valor: float) -> float:
        return y1 - valor * (y1 - y0)

    if metrica:
        _, _, nome_medida = metrica.partition(":")
        legenda_area = ("área da esfera = "
                        f"{rotulo_metrica or nome_medida or metrica}")
    else:
        legenda_area = "área da esfera = número de nós"

    raio_base = 30.0
    if metrica:
        prefixo = metrica if ":" in metrica else f"nucleo:{metrica}"
        tamanhos = [g.medidas.get(prefixo, 0.0) for g in grupos]
        maior = max(tamanhos) if tamanhos else 0.0
        if maior <= 0:
            tamanhos = [float(len(g.nos)) for g in grupos]
            maior = max(tamanhos)
            legenda_area = ("área da esfera = número de nós "
                            "(medida sem valor neste recorte)")
    else:
        tamanhos = [float(len(g.nos)) for g in grupos]
        maior = max(tamanhos)
    raios = {i: raio_base * math.sqrt(tamanhos[i] / max(1e-9, maior)) + 9
             for i in range(len(grupos))}

    quadrantes = ""
    metade_x, metade_y = px(0.5), py(0.5)
    quadrantes += (f'<rect x="{x0}" y="{y0}" width="{metade_x - x0:.0f}" '
                   f'height="{metade_y - y0:.0f}" fill="{fundos["nicho"]}"/>'
                   f'<rect x="{metade_x:.0f}" y="{y0}" width="{x1 - metade_x:.0f}" '
                   f'height="{metade_y - y0:.0f}" fill="{fundos["motor"]}"/>'
                   f'<rect x="{x0}" y="{metade_y:.0f}" width="{metade_x - x0:.0f}" '
                   f'height="{y1 - metade_y:.0f}" fill="{fundos["emergente"]}"/>'
                   f'<rect x="{metade_x:.0f}" y="{metade_y:.0f}" '
                   f'width="{x1 - metade_x:.0f}" height="{y1 - metade_y:.0f}" '
                   f'fill="{fundos["basico"]}"/>')

    # Os nomes dos quadrantes ficam na legenda: dentro do gráfico eles
    # disputavam espaço com os selos dos agrupamentos das extremidades.
    rodape = ("centralidade = ligações ao resto; densidade = coesão interna"
              if unidade == "Countries"
              else "cruzamento em 0,5 da faixa normalizada")
    blocos = ""
    y_quadrantes = altura - 190
    blocos += (f'<text x="{pw + 16}" y="{y_quadrantes}" font-size="11" '
               f'font-weight="700" fill="{TINTA_FRACA}" font-family="{FONTE}">'
               f'QUADRANTES</text>')
    for posicao, chave in enumerate(("motor", "nicho", "emergente", "basico")):
        linha_y = y_quadrantes + 22 + posicao * 22
        blocos += (f'<rect x="{pw + 18}" y="{linha_y - 9}" width="16" height="12" rx="2" '
                   f'fill="{fundos[chave]}" stroke="{cores[chave]}"/>'
                   f'<text x="{pw + 40}" y="{linha_y + 1}" font-size="11.5" '
                   f'fill="{TINTA}" font-family="{FONTE}">{rotulos[chave][0]}</text>')

    eixos = (
        f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" '
        f'fill="none" stroke="#D8D6CE"/>'
        f'<line x1="{x0}" y1="{metade_y:.0f}" x2="{x1}" y2="{metade_y:.0f}" '
        f'stroke="#9C998F" stroke-dasharray="5 4"/>'
        f'<line x1="{metade_x:.0f}" y1="{y0}" x2="{metade_x:.0f}" y2="{y1}" '
        f'stroke="#9C998F" stroke-dasharray="5 4"/>')

    marcas = ""
    for valor in (0.0, 0.5, 1.0):
        marcas += (f'<text x="{px(valor):.0f}" y="{y1 + 22}" text-anchor="middle" '
                   f'font-size="11" fill="{TINTA_FRACA}" font-family="{FONTE}">'
                   f'{valor:.1f}</text>'
                   f'<text x="{x0 - 12}" y="{py(valor) + 4:.0f}" text-anchor="end" '
                   f'font-size="11" fill="{TINTA_FRACA}" font-family="{FONTE}">'
                   f'{valor:.1f}</text>')

    titulos_eixos = (
        f'<text x="{(x0 + x1) / 2:.0f}" y="{altura - 26}" text-anchor="middle" '
        f'font-size="12" font-weight="600" fill="{TINTA}" font-family="{FONTE}">'
        f'Centralidade de Callon (faixa normalizada)</text>'
        f'<text x="22" y="{(y0 + y1) / 2:.0f}" text-anchor="middle" font-size="12" '
        f'font-weight="600" fill="{TINTA}" font-family="{FONTE}" '
        f'transform="rotate(-90 22 {(y0 + y1) / 2:.0f})">'
        f'Densidade de Callon (faixa normalizada)</text>')

    # Esferas e selos: o selo fica no topo da esfera, nunca sobre outra.
    esferas = ""
    meio = ((x0 + x1) / 2, (y0 + y1) / 2)
    for i in ordem:
        grupo = grupos[i]
        r = raios[i]
        # A esfera inteira precisa caber na área do diagrama; sem isto, o
        # agrupamento de valor máximo ficava cortado pela borda.
        cx = min(max(px(grupo.centralidade_faixa), x0 + r + 2), x1 - r - 2)
        cy = min(max(py(grupo.densidade_faixa), y0 + r + 2), y1 - r - 2)

        vetor_x, vetor_y = cx - meio[0], cy - meio[1]
        norma = math.hypot(vetor_x, vetor_y) or 1.0
        sx = min(max(cx + vetor_x / norma * (r + 14), x0 + 16), x1 - 16)
        sy = min(max(cy + vetor_y / norma * (r + 14), y0 + 16), y1 - 16)

        cor = cores[_quadrante(grupo.centralidade_faixa, grupo.densidade_faixa)]
        esferas += (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{cor}" '
                    f'fill-opacity="0.16" stroke="{cor}" stroke-width="1.4"/>'
                    f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="12" fill="#ffffff" '
                    f'stroke="{cor}" stroke-width="2.5"/>'
                    f'<text x="{sx:.1f}" y="{sy + 4:.1f}" text-anchor="middle" '
                    f'font-size="12" font-weight="700" fill="{cor}" '
                    f'font-family="{FONTE}">{ordem.index(i) + 1}</text>')

    legenda_svg = ""
    passo = legenda["passo"]
    linhas = max(1, legenda["linhas"])
    entradas = ordem[:legenda["visiveis"]]
    for posicao, i in enumerate(entradas):
        grupo = grupos[i]
        cor = cores[_quadrante(grupo.centralidade_faixa, grupo.densidade_faixa)]
        nome = _rotulo_curto(grupo.rotulo, unidade)
        coluna, linha = divmod(posicao, linhas)
        x = pw + 26 + coluna * LARGURA_COLUNA_LEGENDA
        y = 122 + linha * passo
        legenda_svg += (f'<circle cx="{x}" cy="{y - 4}" r="10" fill="#ffffff" '
                        f'stroke="{cor}" stroke-width="2.5"/>'
                        f'<text x="{x}" y="{y + 1}" text-anchor="middle" font-size="11" '
                        f'font-weight="700" fill="{cor}" font-family="{FONTE}">{posicao + 1}</text>'
                        f'<text x="{x + 20}" y="{y + 1}" font-size="12" fill="{TINTA}" '
                        f'font-family="{FONTE}">{html.escape(nome)} '
                        f'<tspan fill="{TINTA_FRACA}">({len(grupo.nos)})</tspan></text>')

    if legenda["restantes"]:
        legenda_svg += (
            f'<text x="{pw + 26}" y="{122 + legenda["linhas"] * passo + 4}" '
            f'font-size="11.5" fill="{TINTA_FRACA}" font-family="{FONTE}">'
            f'+ {legenda["restantes"]} agrupamentos (ver tabela)</text>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{html.escape(titulo, quote=True)}" '
        f'viewBox="0 0 {largura} {altura}" width="{largura}" height="{altura}">'
        f'<rect width="{largura}" height="{altura}" fill="#ffffff"/>'
        f'<text x="40" y="40" font-size="18" font-weight="600" fill="{TINTA}" '
        f'font-family="{FONTE}">{html.escape(titulo)}</text>'
        f'<text x="40" y="62" font-size="12" fill="{TINTA_FRACA}" '
        f'font-family="{FONTE}">{len(grupos)} agrupamentos · '
        f'{resultado.rede.quantidade_nos()} nós; {html.escape(legenda_area)}</text>'
        f'{quadrantes}{eixos}{marcas}{titulos_eixos}'
        f'{esferas}{legenda_svg}{blocos}'
        f'<text x="40" y="{altura - 8}" font-size="10" fill="{TINTA_FRACA}" '
        f'font-family="{FONTE}">Redes · {rodape}</text>'
        f'</svg>'
    )


def dados_diagrama(grupos: list[dict], unidade: str) -> dict:
    """Dados do diagrama interativo, a partir dos grupos já serializados.

    Recebe a mesma lista que a interface usa na tabela (selo, rótulo, faixas e
    medidas), para que o ponto clicado abra exatamente aquele agrupamento.
    """
    rotulos = _quadrantes(unidade)
    curtos = _curtos(unidade)
    descricoes = _descricoes(unidade)
    pontos = []
    for grupo in grupos:
        chave = grupo.get("quadrante") or _quadrante(
            grupo["centralidade_faixa"], grupo["densidade_faixa"])
        pontos.append({
            "selo": int(grupo["selo"]),
            "nome": grupo.get("rotulo") or f"Agrupamento {grupo['selo']}",
            "x": float(grupo["centralidade_faixa"]),
            "y": float(grupo["densidade_faixa"]),
            "nos": int(grupo["itens"]),
            "documentos": int(grupo.get("documentos") or 0),
            "centralidade": float(grupo["centralidade"]),
            "densidade": float(grupo["densidade"]),
            "quadrante": chave,
        })
    return {
        "unidade": unidade,
        "pontos": pontos,
        "quadrantes": [
            {"chave": chave, "rotulo": valor[0], "curto": curtos[chave],
             "descricao": descricoes[chave],
             "cor": valor[1], "fundo": valor[2]}
            for chave, valor in rotulos.items()
        ],
        "max_nos": max((ponto["nos"] for ponto in pontos), default=1),
        "eixos": {
            "x": "Centralidade de Callon (faixa normalizada)",
            "y": "Densidade de Callon (faixa normalizada)",
        },
    }

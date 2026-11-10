"""Gera a figura do fluxo do Redes (SVG e PNG)."""
from __future__ import annotations

import sys
from pathlib import Path

AZUL, ESCURO, ROXO, AMARELO = "#2F2BFF", "#0B1F66", "#6A3BFF", "#FFC400"
VERDE, TINTA, FRACA = "#00A344", "#14204A", "#64748B"
FUNDO_A, FUNDO_B, ETIQUETA = "#F4F2FF", "#E6F8EE", "#DDE4FF"
FONTE = "Inter, Helvetica, Arial, sans-serif"

L, A = 1700, 990
p: list[str] = []


def add(s: str) -> None:
    p.append(s)


def texto(x, y, t, tam=14, peso=400, cor=TINTA, ancora="middle"):
    add(f'<text x="{x}" y="{y}" font-size="{tam}" font-weight="{peso}" fill="{cor}" text-anchor="{ancora}">{t}</text>')


def linhas(x, y, itens, tam=13, cor=TINTA, ancora="middle", passo=19, peso=400):
    for i, t in enumerate(itens):
        texto(x, y + i * passo, t, tam, peso, cor, ancora)


def caixa(x, y, w, h, preench="#fff", traco=ESCURO, raio=14, largura=2.2):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{raio}" fill="{preench}" stroke="{traco}" stroke-width="{largura}"/>')


def pilula(cx, cy, linhas_t, w=140):
    h = 14 + 17 * len(linhas_t)
    add(f'<rect x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" rx="9" fill="{ETIQUETA}" stroke="{AZUL}" stroke-width="1.2"/>')
    for i, t in enumerate(linhas_t):
        texto(cx, cy - h / 2 + 22 + i * 17 - 3, t, 12.5, 600, ESCURO)


def seta(pontos, cor=ESCURO, largura=3, tracejada=False, ponta="ponta"):
    d = "M" + " L".join(f"{x},{y}" for x, y in pontos)
    dash = ' stroke-dasharray="8 6"' if tracejada else ""
    add(f'<path d="{d}" fill="none" stroke="{cor}" stroke-width="{largura}" stroke-linejoin="round"{dash} marker-end="url(#{ponta})"/>')


add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {L} {A}" width="{L}" height="{A}" font-family="{FONTE}">')
add('<defs>'
    f'<marker id="ponta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="{ESCURO}"/></marker>'
    f'<marker id="pontaA" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#A16207"/></marker>'
    f'<marker id="pontaR" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="{ROXO}"/></marker></defs>')
add(f'<rect width="{L}" height="{A}" fill="#fff"/>')
texto(850, 44, "Fluxo de análise do Redes", 24, 700, ESCURO)

CY = 470  # linha central do fluxo

# 1. Bases
texto(140, 290, "Bases bibliográficas", 18, 700, ESCURO)
fontes = [("Scopus", "CSV"), ("Zotero", "RIS · CSV · BibTeX"), ("OpenAlex", "CSV"),
          ("Web of Science", "texto ISI"), ("CSV genérico", "SciMAT e outros")]
for i, (nome, fmt) in enumerate(fontes):
    y = 306 + i * 62
    caixa(30, y, 220, 52, "#fff", AZUL, 12, 1.8)
    texto(140, y + 23, nome, 15, 700, ESCURO)
    texto(140, y + 41, fmt, 12, 400, FRACA)
linhas(140, 640, ["O formato é reconhecido", "pelo conteúdo do arquivo"], 12, FRACA, "middle", 17)

# 2. Projeto
for i in range(5):
    add(f'<line x1="250" y1="{332 + i * 62}" x2="266" y2="{332 + i * 62}" stroke="{ESCURO}" stroke-width="2.6"/>')
add(f'<line x1="266" y1="332" x2="266" y2="{332 + 4 * 62}" stroke="{ESCURO}" stroke-width="2.6"/>')
seta([(266, CY), (410, CY)])
pilula(338, CY, ["Importar,", "limpar e unir"], 120)
caixa(410, 335, 250, 270, FUNDO_A, ESCURO, 16, 2.5)
texto(535, 366, "Projeto .redes", 18, 700, ESCURO)
texto(535, 386, "banco SQLite local", 12, 400, FRACA)
linhas(535, 418, ["Duplicatas removidas", "(DOI ou título + ano)", "Singular/plural e acento", "(pt · es · en)",
                  "Grupos de palavras, autores", "e países · termos ignorados", "Períodos sugeridos", "pelos anos do corpus"],
       12.5, TINTA, "middle", 21)

# 3. Matriz documento x item
seta([(660, CY), (820, CY)])
pilula(740, CY, ["Matriz", "documento ×", "item"], 120)
caixa(820, 335, 220, 270, "#fff", ESCURO, 16, 2.5)
texto(930, 366, "Documento × item", 17, 700, ESCURO)
mx, my, c = 865, 388, 26
for r, linha in enumerate(["11010", "00110", "10100", "01011", "00101"]):
    for k, v in enumerate(linha):
        add(f'<rect x="{mx + k * c}" y="{my + r * c}" width="{c}" height="{c}" fill="{AZUL if v == "1" else "#fff"}" '
            f'fill-opacity="{0.85 if v == "1" else 1}" stroke="{ESCURO}" stroke-width="1"/>')
linhas(930, 548, ["palavras-chave · autores", "referências · países", "periódicos"], 12, FRACA, "middle", 17)

# Ramo 1: descritiva
seta([(930, 335), (930, 195), (1200, 195)])
pilula(1070, 195, ["Estatística", "descritiva"], 130)
caixa(1200, 90, 450, 210, FUNDO_B, VERDE, 16, 2.5)
texto(1425, 122, "Visão geral descritiva (na tela)", 18, 700, ESCURO)
linhas(1425, 152, ["Produção e citações por ano · acumulado", "Autores, fontes, países e palavras-chave",
                   "Documentos mais citados · fontes citadas", "Coautoria · índice h",
                   "Leis de Lotka, Bradford e Zipf"], 13, TINTA, "middle", 24)

# Ramo 2: mapeamento científico
seta([(930, 605), (930, 700), (1200, 700)])
pilula(1070, 700, ["Matriz de rede:", "co-ocorrência ou", "acoplamento"], 150)
caixa(1200, 380, 450, 480, "#FBFAFF", ROXO, 16, 2.5)
texto(1425, 410, "Mapeamento científico, por período", 17, 700, ROXO)
etapas = [
    ("1  Rede do período", "Similaridade: equivalência, associação,", "inclusão, Jaccard, Salton"),
    ("2  Agrupamento", "Centros simples, ligação simples, completa,", "média, soma · Louvain"),
    ("3  Medidas", "Callon (centralidade e densidade) · h, g, hg, q2", "documentos por mapeador: núcleo, união…"),
    ("4  Mapas", "Diagrama estratégico: motor, básico, nicho, emergente", "Rede em halos · evolução e sobreposição · países"),
]
for i, (t, l1, l2) in enumerate(etapas):
    y = 432 + i * 104
    caixa(1222, y, 406, 80, "#fff", ROXO, 12, 1.8)
    texto(1425, y + 26, t, 15, 700, ESCURO)
    texto(1425, y + 48, l1, 12, 400, FRACA)
    texto(1425, y + 65, l2, 12, 400, FRACA)
    if i < 3:
        seta([(1425, y + 80), (1425, y + 104)], ROXO, 2.6, ponta="pontaR")

# Saídas
caixa(30, 770, 1100, 190, "#fff", AZUL, 16, 2.5)
texto(580, 802, "Saídas", 18, 700, ESCURO)
colunas = [
    ("Relatório", ["somente HTML", "redes e quadro de métricas", "por período e por agrupamento"]),
    ("Redes e tabelas", ["Pajek · GraphML", "TSV de índices e documentos", "Grupos da base (XML)"]),
    ("Figuras", ["SVG e PNG", "diagrama estratégico", "rede em halos · mapas"]),
    ("Grade de análises", ["162 combinações", "unidade × matriz ×", "algoritmo × similaridade"]),
]
for i, (t, ls) in enumerate(colunas):
    x = 175 + i * 270
    texto(x, 836, t, 14, 700, AZUL)
    linhas(x, 859, ls, 12.5, TINTA, "middle", 21)
seta([(1200, 860), (1132, 860)], ROXO, 3, ponta="pontaR")

# Ciclo de edição da base
seta([(535, 770), (535, 608)], "#A16207", 3.2, True, "pontaA")
add(f'<rect x="395" y="672" width="280" height="44" rx="9" fill="#FFF8D6" stroke="#A16207" stroke-width="1.4"/>')
linhas(535, 691, ["Editar a base: juntar, ignorar,", "renomear e refazer a análise"], 12.5, "#7A4B00", "middle", 17, 700)

add("</svg>")
destino = Path(sys.argv[1] if len(sys.argv) > 1 else "fluxo-redes.svg")
destino.write_text("\n".join(p), encoding="utf-8")
print("gerado", destino)

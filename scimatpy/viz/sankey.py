"""Diagrama de Sankey em SVG próprio (sem bibliotecas), em colunas.

Recebe o dicionário de ``scimatpy.fluxos.calcula``: nós por coluna e ligações
com valor em documentos. A ordem dos nós em cada coluna é refinada por
baricentros, mantendo a melhor de várias varreduras (menos cruzamentos de
ligações). Os nós levam a cor do país que mais pesa neles.

O SVG usa variáveis CSS com valor de reserva (``--sk-texto``, ``--sk-fundo``,
``--sk-contorno``, ``--sk-fraco``): na interface valem as cores do tema da ferramenta (só claro); fora dela
(arquivo baixado, relatório) valem as mesmas cores claras. Os ids
levam um prefixo estável derivado dos dados, então duas figuras na mesma
página não colidem, e cada nó e cada ligação traz ``<title>`` como dica.
"""
from __future__ import annotations

import hashlib
import html
import re
import textwrap

from .halo import cor_do_grupo

FONTE = "Inter, Helvetica, Arial, sans-serif"
LARGURA_NO = 14
ENTRE_NOS = 4
ALTURA_MIN_ROTULO = 16
TOPO = 62
CINZA_PAIS = "#8A94A6"
PALETA = ["#4C6FFF", "#00A344", "#8B5CF6", "#D97706", "#0E7490", "#DB2777", "#65A30D",
          "#0284C7", "#DC2626", "#0F766E", "#A16207", "#7C3AED", "#BE185D", "#4D7C0F", "#0369A1"]
CARACTERES = {0: 28, 1: 26, 2: 42}
PX_CARACTERE = 6.7

ESTILO = (
    ".sk-fundo{fill:var(--sk-fundo,#fff)}"
    ".sk-rot{fill:var(--sk-texto,#14204A);font-size:12px}"
    ".sk-fraco{fill:var(--sk-fraco,#64748B);font-size:11.5px}"
    ".sk-tit{fill:var(--sk-texto,#14204A);font-size:16px;font-weight:700}"
    ".sk-cab{fill:var(--sk-fraco,#64748B);font-size:11.5px;font-weight:700;letter-spacing:.04em;"
    "text-transform:uppercase}"
    ".sk-halo{stroke:var(--sk-fundo,#fff);stroke-width:3;paint-order:stroke;stroke-linejoin:round}"
    ".sk-no rect{stroke:var(--sk-contorno,#fff);stroke-width:.8}"
    ".sk-lig{fill:none;stroke-opacity:.36;transition:stroke-opacity .12s}"
    ".sk-lig:hover{stroke-opacity:.72}.sk-no:hover rect{stroke:var(--sk-texto,#14204A)}")


_CONTROLE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def _esc(texto) -> str:
    texto = _CONTROLE.sub("", str(texto if texto is not None else ""))
    return html.escape(texto, quote=True)


def _curto(texto: str, limite: int) -> str:
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"


def _docs(n: int) -> str:
    return f"{n} documento" + ("" if n == 1 else "s")


# ------------------------------------------------------------------ layout


def _cruzamentos(ordem: list[list[str]], ligacoes: list[dict], coluna_de: dict) -> int:
    posicao = {i: p for lista in ordem for p, i in enumerate(lista)}
    total = 0
    por_par: dict[int, list[tuple[int, int]]] = {}
    for l in ligacoes:
        c = coluna_de[l["origem"]]
        por_par.setdefault(c, []).append((posicao[l["origem"]], posicao[l["destino"]]))
    for pares in por_par.values():
        for i, (a1, b1) in enumerate(pares):
            for a2, b2 in pares[i + 1:]:
                if (a1 - a2) * (b1 - b2) < 0:
                    total += 1
    return total


def ordena(nos: list[dict], ligacoes: list[dict], n_colunas: int, rodadas: int = 14) -> list[list[str]]:
    """Ordem dos ids em cada coluna, com poucos cruzamentos (baricentro, melhor de N varreduras)."""
    coluna_de = {n["id"]: n["coluna"] for n in nos}
    valor = {n["id"]: n["valor"] for n in nos}
    vizinhos: dict[str, list[tuple[str, int]]] = {n["id"]: [] for n in nos}
    for l in ligacoes:
        vizinhos[l["origem"]].append((l["destino"], l["valor"]))
        vizinhos[l["destino"]].append((l["origem"], l["valor"]))
    ordem = [sorted((n["id"] for n in nos if n["coluna"] == c),
                    key=lambda i: (-valor[i], i)) for c in range(n_colunas)]
    melhor = [list(o) for o in ordem]
    menor = _cruzamentos(ordem, ligacoes, coluna_de)
    for rodada in range(rodadas):
        colunas = list(range(n_colunas)) if rodada % 2 == 0 else list(range(n_colunas - 1, -1, -1))
        for c in colunas:
            posicao = {i: (p + 0.5) / max(1, len(lista))
                       for lista in ordem for p, i in enumerate(lista)}
            chave = {}
            for p, i in enumerate(ordem[c]):
                pesos = [(posicao[v], w) for v, w in vizinhos[i]]
                soma = sum(w for _, w in pesos)
                chave[i] = sum(x * w for x, w in pesos) / soma if soma else posicao[i]
            ordem[c] = sorted(ordem[c], key=lambda i: (chave[i], -valor[i], i))
        atual = _cruzamentos(ordem, ligacoes, coluna_de)
        if atual < menor:
            menor, melhor = atual, [list(o) for o in ordem]
        if menor == 0:
            break
    return melhor


def layout(dados: dict, largura: int = 1100) -> dict:
    """Posições dos nós e das ligações (coordenadas do SVG)."""
    nos = {n["id"]: dict(n) for n in dados["nos"]}
    ligacoes = [dict(l) for l in dados["ligacoes"]]
    n_colunas = len(dados["colunas"])
    entrada = {i: 0 for i in nos}
    saida = {i: 0 for i in nos}
    for l in ligacoes:
        saida[l["origem"]] += l["valor"]
        entrada[l["destino"]] += l["valor"]
    for i, no in nos.items():
        no["fluxo"] = max(entrada[i], saida[i], 1)

    ordem = ordena(list(nos.values()), ligacoes, n_colunas)
    maximo_rotulo = {c: max((len(_curto(nos[i]["nome"], CARACTERES.get(c if n_colunas == 3 else c + 1, 30)))
                             for i in ordem[c]), default=0) for c in range(n_colunas)}
    margem_e = int(min(220, 18 + PX_CARACTERE * maximo_rotulo[0]))
    margem_d = int(min(300, 18 + PX_CARACTERE * maximo_rotulo[n_colunas - 1]))
    x_ini, x_fim = margem_e, largura - margem_d - LARGURA_NO
    x_col = [x_ini + c * (x_fim - x_ini) / max(1, n_colunas - 1) for c in range(n_colunas)]

    maior_n = max(len(o) for o in ordem)
    altura_util = max(380, 24 * maior_n)
    soma_max = max(sum(nos[i]["fluxo"] for i in o) for o in ordem)
    escala = min(18.0, (altura_util - ENTRE_NOS * (maior_n - 1)) / soma_max)
    for no in nos.values():
        no["h"] = max(3.0, no["fluxo"] * escala)
        no["slot"] = max(no["h"], ALTURA_MIN_ROTULO)
    altura_util = max(altura_util, max(sum(nos[i]["slot"] for i in o) + ENTRE_NOS * (len(o) - 1)
                                       for o in ordem))
    for c, o in enumerate(ordem):
        total = sum(nos[i]["slot"] for i in o) + ENTRE_NOS * (len(o) - 1)
        y = TOPO + (altura_util - total) / 2
        for i in o:
            no = nos[i]
            no["x"], no["y"] = x_col[c], y + (no["slot"] - no["h"]) / 2
            y += no["slot"] + ENTRE_NOS

    centro = lambda i: nos[i]["y"] + nos[i]["h"] / 2  # noqa: E731
    deslocamento_saida = {i: 0.0 for i in nos}
    deslocamento_entrada = {i: 0.0 for i in nos}
    for l in sorted(ligacoes, key=lambda l: (centro(l["destino"]), centro(l["origem"]))):
        l["espessura"] = max(1.0, l["valor"] * escala)
        l["y0"] = nos[l["origem"]]["y"] + deslocamento_saida[l["origem"]] + l["espessura"] / 2
        deslocamento_saida[l["origem"]] += l["valor"] * escala
    for l in sorted(ligacoes, key=lambda l: (centro(l["origem"]), centro(l["destino"]))):
        l["y1"] = nos[l["destino"]]["y"] + deslocamento_entrada[l["destino"]] + l["espessura"] / 2
        deslocamento_entrada[l["destino"]] += l["valor"] * escala
    return {"nos": nos, "ligacoes": ligacoes, "ordem": ordem, "largura": largura,
            "altura_util": altura_util, "x_col": x_col, "escala": escala,
            "cruzamentos": _cruzamentos(ordem, ligacoes, {i: n["coluna"] for i, n in nos.items()})}


# --------------------------------------------------------------------- SVG


def _cores(dados: dict) -> dict[str, str]:
    paises = [n["nome"] for n in sorted(
        (n for n in dados["nos"] if n["id"].startswith("p:")), key=lambda n: (-n["valor"], n["nome"]))]
    cores = {}
    for posicao, nome in enumerate(paises):
        cores[nome] = CINZA_PAIS if nome.startswith("Sem país") else (
            PALETA[posicao] if posicao < len(PALETA) else cor_do_grupo(posicao))
    return cores


def _prefixo(dados: dict, titulo: str) -> str:
    base = repr((titulo, [(n["id"], n["valor"]) for n in dados["nos"]],
                 [(l["origem"], l["destino"], l["valor"]) for l in dados["ligacoes"]]))
    return "sk" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:6]


def svg(dados: dict, titulo: str = "", largura: int = 1100, prefixo_id: str | None = None) -> str:
    """SVG do Sankey. Devolve texto vazio quando não há nós ou ligações."""
    if not dados or not dados.get("nos") or not dados.get("ligacoes"):
        return ""
    disposicao = layout(dados, largura)
    nos, ligacoes = disposicao["nos"], disposicao["ligacoes"]
    cores = _cores(dados)
    p = prefixo_id or _prefixo(dados, titulo)
    colunas = dados["colunas"]
    n_colunas = len(colunas)
    cor_do_no = lambda no: cores.get(no.get("pais", ""), CINZA_PAIS)  # noqa: E731

    cabecalhos = {"Autor": "Autores", "País": "Países", "IES": "Instituições (IES)"}
    partes_rodape = []
    c = dados.get("cobertura", {})
    partes_rodape.append(f"Desenhado com {c.get('mostrados', 0)} de {c.get('documentos', 0)} documentos "
                         "(autores, países e instituições mais frequentes).")
    if dados.get("rotulo_qualidade") and dados.get("modo") != "pais_ies":
        partes_rodape.append(dados["rotulo_qualidade"][0].upper() + dados["rotulo_qualidade"][1:] + ".")
    linhas_rodape = textwrap.wrap(" ".join(partes_rodape), 150)
    altura = int(TOPO + disposicao["altura_util"] + 18 + 15 * len(linhas_rodape) + 8)

    nome_figura = titulo or "Fluxo " + " → ".join(colunas)
    maiores = sorted(ligacoes, key=lambda l: -l["valor"])[:3]
    descricao = (f"Diagrama de Sankey com {len(dados['nos'])} nós em {n_colunas} colunas ("
                 + ", ".join(colunas) + "). Maiores fluxos: "
                 + "; ".join(f"{nos[l['origem']]['nome']} para {nos[l['destino']]['nome']}, "
                             f"{_docs(l['valor'])}" for l in maiores) + ".")

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura} {altura}" width="{largura}" '
         f'height="{altura}" font-family="{FONTE}" role="img" aria-labelledby="{p}-t {p}-d">',
         f'<title id="{p}-t">{_esc(nome_figura)}</title><desc id="{p}-d">{_esc(descricao)}</desc>',
         f"<style>{ESTILO}</style>",
         f'<rect class="sk-fundo" width="{largura}" height="{altura}"/>']
    if titulo:
        s.append(f'<text class="sk-tit" x="{largura / 2:.0f}" y="26" text-anchor="middle">{_esc(titulo)}</text>')
    for c_i, nome in enumerate(colunas):
        x = disposicao["x_col"][c_i]
        ancora, xt = ("end", x + LARGURA_NO) if c_i == 0 else ("start", x)
        s.append(f'<text class="sk-cab" x="{xt:.1f}" y="{TOPO - 14}" text-anchor="{ancora}">'
                 f'{_esc(cabecalhos.get(nome, nome))}</text>')

    s.append('<g class="sk-ligacoes">')
    for k, l in enumerate(ligacoes):
        o, d = nos[l["origem"]], nos[l["destino"]]
        x0, x1 = o["x"] + LARGURA_NO, d["x"]
        xm = (x0 + x1) / 2
        cor = cores.get(l["pais"], CINZA_PAIS)
        s.append(f'<path id="{p}-l{k}" class="sk-lig" d="M{x0:.1f},{l["y0"]:.1f} C{xm:.1f},{l["y0"]:.1f} '
                 f'{xm:.1f},{l["y1"]:.1f} {x1:.1f},{l["y1"]:.1f}" stroke="{cor}" '
                 f'stroke-width="{l["espessura"]:.2f}"><title>{_esc(o["nome"])} → {_esc(d["nome"])}: '
                 f'{_docs(l["valor"])}</title></path>')
    s.append("</g>")

    s.append('<g class="sk-nos">')
    for k, i in enumerate(i for o in disposicao["ordem"] for i in o):
        no = nos[i]
        c_i = no["coluna"]
        ultimo = c_i == n_colunas - 1
        cor = cor_do_no(no)
        if c_i == 0 and n_colunas > 1:
            xt, ancora = no["x"] - 6, "end"
        else:
            xt, ancora = no["x"] + LARGURA_NO + 6, "start"
        limite = CARACTERES.get(c_i if n_colunas == 3 else c_i + 1, 30)
        rotulo = _curto(no["nome"], limite)
        dica = f'{no["nome"]}: {_docs(no["valor"])} no fluxo'
        if no.get("total") and no["total"] != no["valor"]:
            dica += f' ({no["total"]} no corpus)'
        centro_y = no["y"] + no["h"] / 2
        s.append(f'<g id="{p}-n{k}" class="sk-no"><rect x="{no["x"]:.1f}" y="{no["y"]:.1f}" '
                 f'width="{LARGURA_NO}" height="{no["h"]:.1f}" rx="2" fill="{cor}"/>'
                 f'<text class="sk-rot sk-halo" aria-hidden="true" x="{xt:.1f}" y="{centro_y + 4:.1f}" text-anchor="{ancora}">'
                 f'{_esc(rotulo)}</text><text class="sk-rot" x="{xt:.1f}" y="{centro_y + 4:.1f}" '
                 f'text-anchor="{ancora}">{_esc(rotulo)}</text><title>{_esc(dica)}</title></g>')
    s.append("</g>")

    y_rodape = TOPO + disposicao["altura_util"] + 24
    for n, linha in enumerate(linhas_rodape):
        s.append(f'<text class="sk-fraco" x="12" '
                 f'y="{y_rodape + 15 * n:.0f}">{_esc(linha)}</text>')
    s.append("</svg>")
    return "".join(s)


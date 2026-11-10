"""Relatórios do Redes em HTML e LaTeX, simples e estendido.

Reproduz a estrutura dos quatro geradores do fork Bibliomapa:

- índice com a configuração da análise, o resumo dos períodos e os mapas
  longitudinais;
- uma página por período com os diagramas estratégicos (um por medida de
  desempenho) e a lista de agrupamentos;
- uma página por agrupamento com a rede, as ligações internas e externas e,
  no relatório estendido, os documentos associados por mapeador e as
  referências em formato ABNT.

As figuras são SVG, vetoriais, sem dependência de rasterizador. O LaTeX usa os
mesmos dados em tabelas; as imagens entram quando há PNG disponível.
"""

from __future__ import annotations

import html
import re
import shutil
import unicodedata
from pathlib import Path

from . import longitudinal
from .pipeline import executa_periodo
from .viz.cluster import rede_agrupamento_svg
from .viz.strategic import diagrama_svg

ROTULOS_MAPEADOR = {
    "nucleo": "Documentos centrais",
    "interseccao": "Documentos de interseção",
    "secundarios": "Documentos secundários",
    "kcore": "Documentos k-core",
    "uniao": "Documentos da união",
    "acoplamento": "Documentos de acoplamento",
}

ROTULOS_MEDIDA = {
    "documentos": "Documentos",
    "h": "Índice h",
    "g": "Índice g",
    "hg": "Índice hg",
    "q2": "Índice Q2",
    "media": "Citações médias",
    "soma": "Citações totais",
    "minimo": "Citações mínimas",
    "maximo": "Citações máximas",
}

ROTULOS_UNIDADE = {
    "Words": "Palavras",
    "Authors": "Autores",
    "References": "Referências",
    "AuthorsReference": "Autores de referência",
    "ReferenceSources": "Fontes de referência",
    "Countries": "Países",
}

ROTULOS_MATRIZ = {
    "CoOccurrence": "Coocorrência",
    "BasicCoupling": "Acoplamento",
    "AggregatedCouplingBasedOnAuthor": "Acoplamento agregado por autor",
    "AggregatedCouplingBasedOnJournal": "Acoplamento agregado por periódico",
}

ROTULOS_ALGORITMO = {
    "CentersSimples": "Centros simples",
    "AverageLink": "Ligação média",
    "CompleteLink": "Ligação completa",
    "SingleLink": "Ligação simples",
    "SumLink": "Ligação por soma",
    "Louvain": "Louvain",
}

ROTULOS_SIMILARIDADE = {
    "AssociationStrength": "Força de associação",
    "EquivalenceIndex": "Índice de equivalência",
    "InclusionIndex": "Índice de inclusão",
    "JaccardIndex": "Índice de Jaccard",
    "SaltonCosine": "Cosseno de Salton",
}

ORDEM_MEDIDAS = ("documentos", "h", "g", "hg", "q2", "media", "soma",
                 "minimo", "maximo")

_ASSETS = Path(__file__).with_name("assets")

_CSS = """
body { font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
       color:#1F2A44; max-width: 980px; margin: 32px auto; padding: 0 24px;
       line-height:1.5; font-size:14px; }
a { color:#1D3E8F; }
h1 { font-size:24px; color:#0B1F66; border-bottom:1px solid #D7DBE6;
     padding-bottom:6px; }
h2 { font-size:18px; color:#0B1F66; margin-top:28px; }
h3 { font-size:15px; color:#1F2A44; }
table { border-collapse:collapse; margin:12px 0 4px; width:100%; }
caption { caption-side:top; text-align:left; font-weight:600;
          padding-bottom:6px; color:#1F2A44; }
th, td { border:1px solid #E3E6EC; padding:5px 8px; text-align:left;
         vertical-align:top; }
th { background:#F5F6F9; color:#0B1F66; font-weight:600; }
img, svg { max-width:100%; height:auto; }
img.mapa-sobreposicao { display:block; margin:10px auto; }
.cabecalho { display:flex; align-items:center; justify-content:space-between;
             gap:24px; border-bottom:1px solid #E3E6EC;
             padding-bottom:10px; margin-bottom:24px; }
.marca-relatorio { font-size:10px; font-weight:600; letter-spacing:.14em;
                   text-transform:uppercase; color:#64748B; margin:0; }
.logo-relatorio { display:block; height:32px; width:auto; flex:none; }
.fonte { color:#64748B; font-size:12px; margin:0 0 18px; }
.num { text-align:right; }
nav a { margin-right:14px; }
"""


def _esc(texto) -> str:
    return html.escape(str(texto if texto is not None else ""))


def _slug(texto: str) -> str:
    limpo = unicodedata.normalize("NFD", texto or "")
    limpo = "".join(c for c in limpo if unicodedata.category(c) != "Mn")
    limpo = re.sub(r"[^A-Za-z0-9]+", "-", limpo).strip("-")
    return limpo or "item"


def referencia_abnt(completa: str) -> str:
    """Converte a referência no formato do SciMAT para o padrão ABNT.

    O armazenamento guarda ``autor, ano, fonte, volume, páginas``. A ABNT pede
    ``AUTOR. Fonte, ano.``, com o volume e as páginas no fim.
    """
    campos = [campo.strip() for campo in (completa or "").split(",")]
    autor = campos[0] if campos else ""
    ano = campos[1] if len(campos) > 1 else ""
    fonte = campos[2] if len(campos) > 2 else ""
    volume = campos[3] if len(campos) > 3 else ""
    paginas = campos[4] if len(campos) > 4 else ""
    partes = []
    if autor:
        partes.append(autor.upper() + ".")
    if fonte:
        partes.append(fonte + ("," if ano else "."))
    if ano:
        partes.append(ano + ".")
    if volume:
        partes.append(f"v. {volume}.")
    if paginas:
        partes.append(f"p. {paginas}.")
    return " ".join(partes) or completa


def _numero(valor: float) -> str:
    if valor is None:
        return ""
    if abs(valor - round(valor)) < 1e-9:
        return str(int(round(valor)))
    return f"{valor:.2f}".rstrip("0").rstrip(".")


def _documentos(kb, ids) -> dict[int, dict]:
    if not ids:
        return {}
    marcadores = ",".join("?" for _ in ids)
    linhas = kb.conexao.execute(
        "SELECT d.idDocument, d.title, d.year, d.authors, d.citationsCount, "
        "j.source FROM Document d LEFT JOIN Journal j "
        "ON j.idJournal = d.Journal_idJournal "
        f"WHERE d.idDocument IN ({marcadores})", list(ids)).fetchall()
    return {
        linha["idDocument"]: {
            "id": linha["idDocument"],
            "titulo": linha["title"] or "",
            "ano": linha["year"] or "",
            "autores": linha["authors"] or "",
            "citacoes": linha["citationsCount"] or 0,
            "fonte": linha["source"] or "",
        }
        for linha in linhas
    }


def _referencias(kb, ids) -> dict[int, list[str]]:
    if not ids:
        return {}
    marcadores = ",".join("?" for _ in ids)
    linhas = kb.conexao.execute(
        "SELECT dr.Document_idDocument, r.fullReference "
        "FROM Document_Reference dr, Reference r "
        "WHERE dr.Reference_idReference = r.idReference "
        f"AND dr.Document_idDocument IN ({marcadores}) "
        "ORDER BY dr.Document_idDocument, r.fullReference", list(ids)).fetchall()
    resultado: dict[int, list[str]] = {}
    for linha in linhas:
        resultado.setdefault(linha[0], []).append(linha[1])
    return resultado


def _pagina(titulo: str, corpo: str, profundidade: int = 0) -> str:
    raiz = "../" * profundidade
    return (
        "<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        f"<title>{_esc(titulo)}</title>\n<style>{_CSS}</style>\n</head>\n<body>\n"
        '<header class="cabecalho">\n'
        '<p class="marca-relatorio">Redes · mapeamento e análise da '
        'produção científica</p>\n'
        '<img class="logo-relatorio" src="logo.svg" alt="Redes">\n'
        '</header>\n'
        f"{corpo}\n<footer class=\"fonte\">Gerado por Redes.</footer>\n"
        "</body>\n</html>\n"
    ).replace('src="images/', f'src="{raiz}images/').replace(
        'src="logo.svg"', f'src="{raiz}logo.svg"')


def _tabela(cabecalho: list[str], linhas: list[list[str]],
            legenda: str | None = None, numericas=(),
            larguras: list[str] | None = None) -> str:
    partes = ["<table>"]
    if larguras:
        partes.append("<colgroup>" + "".join(
            f'<col style="width:{largura}">' for largura in larguras) + "</colgroup>")
    if legenda:
        partes.append(f"<caption>{_esc(legenda)}</caption>")
    partes.append("<thead><tr>" + "".join(
        f"<th>{_esc(coluna)}</th>" for coluna in cabecalho) + "</tr></thead><tbody>")
    for linha in linhas:
        celulas = []
        for indice, celula in enumerate(linha):
            classe = ' class="num"' if indice in numericas else ""
            celulas.append(f"<td{classe}>{celula}</td>")
        partes.append("<tr>" + "".join(celulas) + "</tr>")
    partes.append("</tbody></table>")
    return "\n".join(partes)


def _configuracao_tabela(config) -> str:
    linhas = [
        ["Unidade de análise", ROTULOS_UNIDADE.get(config.unidade, config.unidade)],
        ["Tipo de rede", ROTULOS_MATRIZ.get(config.matriz, config.matriz)],
        ["Medida de normalização",
         ROTULOS_SIMILARIDADE.get(config.similaridade, config.similaridade)],
        ["Algoritmo de agrupamento",
         ROTULOS_ALGORITMO.get(config.algoritmo, config.algoritmo)],
        ["Frequência mínima", str(config.minimo_frequencia)],
        ["Coocorrência mínima", str(config.minimo_coocorrencia)],
        ["Tamanho mínimo da rede", str(config.tamanho_minimo)],
        ["Tamanho máximo da rede", str(config.tamanho_maximo)],
        ["Ponto de corte", _numero(config.corte)],
        ["Mapeadores",
         ", ".join(ROTULOS_MAPEADOR.get(m, m) for m in config.mapeadores)],
        ["Origens das palavras", ", ".join(config.palavras) or "todas"],
    ]
    return _tabela(["Parâmetro", "Valor"], linhas)


def _quadrante(grupo) -> str:
    if grupo.centralidade_faixa >= 0.5 and grupo.densidade_faixa >= 0.5:
        return "Motor"
    if grupo.densidade_faixa >= 0.5:
        return "Nicho"
    if grupo.centralidade_faixa >= 0.5:
        return "Básico"
    return "Emergente"


def _ligacoes(resultado, grupo) -> tuple[list, list]:
    nos = set(grupo.nos)
    internas, externas = [], []
    for a, b, valor in resultado.rede.arestas():
        if a in nos and b in nos:
            internas.append((a, b, valor))
        elif a in nos or b in nos:
            externas.append((a, b, valor))
    internas.sort(key=lambda item: -item[2])
    externas.sort(key=lambda item: -item[2])
    return internas, externas


# --------------------------------------------------------------------- HTML


def gera_html(destino: Path, kb, periodos, config, estendido: bool = False,
              medida_temporal: str = "EquivalenceIndex") -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "images").mkdir(exist_ok=True)
    (destino / "misc").mkdir(exist_ok=True)
    shutil.copyfile(_ASSETS / "logo.svg", destino / "logo.svg")

    resultados = [executa_periodo(kb, p.id, p.nome, config) for p in periodos]
    mapa = longitudinal.constroi(kb, config, periodos, medida_temporal)

    for indice, resultado in enumerate(resultados):
        # Um diagrama por mapeador e medida de desempenho, como nas páginas de
        # período do fork: o tamanho das esferas muda com a medida escolhida.
        for mapeador in resultado.configuracao.mapeadores:
            for medida in ORDEM_MEDIDAS:
                titulo = (f"Diagrama estratégico — {resultado.periodo} — "
                          f"{ROTULOS_MAPEADOR.get(mapeador, mapeador)} — "
                          f"{ROTULOS_MEDIDA[medida]}")
                diagrama = diagrama_svg(
                    resultado, titulo, metrica=f"{mapeador}:{medida}",
                    rotulo_metrica=ROTULOS_MEDIDA[medida])
                (destino / "images" /
                 f"strategicDiagram-period{indice}-{mapeador}-{medida}.svg"
                 ).write_text(diagrama, encoding="utf-8")

        grupos = sorted(resultado.grupos,
                        key=lambda g: (-len(g.nos), g.rotulo or ""))
        for posicao, grupo in enumerate(grupos, start=1):
            svg = rede_agrupamento_svg(
                resultado, grupo,
                f"{resultado.periodo} — {grupo.rotulo}")
            (destino / "images" /
             f"clusterNetwork-period{indice}-cluster{posicao - 1}.svg").write_text(
                svg, encoding="utf-8")
            _pagina_cluster(destino, kb, resultado, grupo, grupos, indice,
                            posicao, estendido)

        _pagina_periodo(destino, resultado, grupos, indice)

    evolucao = longitudinal.evolucao_svg(
        mapa, "Mapa de evolução dos temas", largura=980)
    sobreposicao = longitudinal.sobreposicao_svg(
        mapa, "Mapa de sobreposição", largura=680)
    (destino / "images" / "evolutionMap.svg").write_text(evolucao, encoding="utf-8")
    (destino / "images" / "overlappingMap.svg").write_text(
        sobreposicao, encoding="utf-8")
    (destino / "misc" / "evolutionMap.net").write_text(
        longitudinal.evolucao_pajek(mapa), encoding="utf-8")

    _pagina_indice(destino, resultados, mapa, config, estendido)
    return {"html": str(destino), "periodos": len(resultados),
            "agrupamentos": sum(len(r.grupos) for r in resultados)}


def _pagina_indice(destino, resultados, mapa, config, estendido) -> None:
    linhas = []
    for indice, resultado in enumerate(resultados):
        linhas.append([
            f'<a href="period{indice}.html">{_esc(resultado.periodo)}</a>',
            str(resultado.dataset_original.quantidade_documentos()),
            str(resultado.dataset_original.quantidade_itens()),
            str(len(resultado.grupos)),
            f"{resultado.rede.quantidade_nos()}/{resultado.rede.quantidade_arestas()}",
        ])

    corpo = [
        "<h1>Relatório — Redes</h1>",
        "<p>Relatório gerado automaticamente a partir do projeto analisado.</p>",
        "<h2>Configuração da análise</h2>",
        _configuracao_tabela(config),
        "<h2>Resultados dos períodos</h2>",
        _tabela(["Período", "Documentos", "Itens", "Agrupamentos", "Nós/arestas"],
                linhas, "Resumo por período", numericas=(1, 2, 3, 4)),
        "<h2>Resultados longitudinais</h2>",
        f'<p><img src="images/evolutionMap.svg" '
        f'alt="Mapa de evolução dos temas" width="980"></p>',
        '<p class="fonte">Mapa de evolução em Pajek: '
        '<a href="misc/evolutionMap.net">misc/evolutionMap.net</a>.</p>',
        f'<p><img class="mapa-sobreposicao" src="images/overlappingMap.svg" '
        f'alt="Mapa de sobreposição"></p>',
    ]
    if estendido:
        corpo.append("<p>Relatório estendido: cada agrupamento lista os "
                     "documentos por mapeador, com citações e referências.</p>")
    (destino / "index.html").write_text(
        _pagina("Relatório — Redes", "\n".join(corpo)), encoding="utf-8")


def _pagina_periodo(destino, resultado, grupos, indice) -> None:
    corpo = [
        f'<p><a href="index.html">Índice</a></p>',
        f"<h1>Relatório — Redes — {_esc(resultado.periodo)}</h1>",
        "<h2>Parâmetros do período</h2>",
        _tabela(["Parâmetro", "Valor"], [
            ["Frequência mínima", str(resultado.configuracao.minimo_frequencia)],
            ["Coocorrência mínima", str(resultado.configuracao.minimo_coocorrencia)],
            ["No período", str(resultado.dataset_original.quantidade_documentos())],
            ["Itens", str(resultado.dataset_original.quantidade_itens())],
            ["Agrupamentos", str(len(grupos))],
        ]),
        "<h2>Diagramas estratégicos</h2>",
    ]
    for mapeador in resultado.configuracao.mapeadores:
        rotulo_mapeador = ROTULOS_MAPEADOR.get(mapeador, mapeador)
        linhas_diagramas = []
        for medida in ORDEM_MEDIDAS:
            nome = f"strategicDiagram-period{indice}-{mapeador}-{medida}.svg"
            linhas_diagramas.append([
                _esc(f"{rotulo_mapeador} — {ROTULOS_MEDIDA[medida]}"),
                f'<img src="images/{nome}" alt="Diagrama estratégico — '
                f'{_esc(rotulo_mapeador)} — {_esc(ROTULOS_MEDIDA[medida])}" '
                'width="760">',
            ])
        corpo.append(_tabela(["Medida de desempenho", "Diagrama estratégico"],
                             linhas_diagramas,
                             f"Diagramas estratégicos — {rotulo_mapeador}",
                             larguras=["26%", "74%"]))

    corpo.append(
        '<p class="fonte">O tamanho das esferas segue a medida de desempenho '
        'indicada em cada diagrama; o quadrante usa a centralidade e a '
        'densidade de Callon.</p>')

    linhas = []
    for posicao, grupo in enumerate(grupos, start=1):
        medidas = grupo.medidas
        prefixo = f"{resultado.configuracao.mapeadores[0]}:"
        valores = [_numero(medidas.get(prefixo + nome, 0)) for nome in ORDEM_MEDIDAS]
        linhas.append([
            str(posicao),
            f'<a href="period{indice}-cluster{posicao - 1}.html">'
            f'{_esc(grupo.rotulo)}</a>',
            str(len(grupo.nos)),
            _numero(grupo.densidade),
            _numero(grupo.centralidade),
            _quadrante(grupo),
        ] + valores)
    corpo.append("<h2>Agrupamentos</h2>")
    corpo.append(_tabela(
        ["Selo", "Agrupamento", "Itens", "Densidade", "Centralidade", "Quadrante"]
        + [ROTULOS_MEDIDA[nome] for nome in ORDEM_MEDIDAS],
        linhas, "Agrupamentos do período", numericas=tuple(range(2, 15))))

    (destino / f"period{indice}.html").write_text(
        _pagina(f"Relatório — Redes — {resultado.periodo}", "\n".join(corpo)),
        encoding="utf-8")


def _pagina_cluster(destino, kb, resultado, grupo, grupos, indice,
                    posicao, estendido) -> None:
    internas, externas = _ligacoes(resultado, grupo)
    nomes = {no: resultado.dataset.itens.get(no, str(no)) for no in resultado.rede.nos}

    corpo = [
        f'<p><a href="index.html">Índice</a> · '
        f'<a href="period{indice}.html">{_esc(resultado.periodo)}</a></p>',
        f"<h1>{_esc(resultado.periodo)} — {_esc(grupo.rotulo)}</h1>",
        "<h2>Informações do agrupamento</h2>",
        _tabela(["Medida", "Valor"], [
            ["Nome", _esc(grupo.rotulo)],
            ["Itens", str(len(grupo.nos))],
            ["Densidade", _numero(grupo.densidade)],
            ["Faixa de densidade", _numero(grupo.densidade_faixa)],
            ["Centralidade", _numero(grupo.centralidade)],
            ["Faixa de centralidade", _numero(grupo.centralidade_faixa)],
            ["Quadrante", _quadrante(grupo)],
        ]),
        "<h2>Rede do agrupamento</h2>",
        f'<p><img src="images/clusterNetwork-period{indice}-cluster{posicao - 1}.svg" '
        f'alt="Rede do agrupamento {_esc(grupo.rotulo)}" width="720"></p>',
    ]

    linhas = [[_esc(nomes[a]), _esc(nomes[b]), _numero(valor)] for a, b, valor in internas]
    corpo.append("<h2>Ligações internas</h2>")
    corpo.append(_tabela(["Nó A", "Nó B", "Peso"], linhas,
                         "Ligações internas", numericas=(2,)))

    linhas = [[_esc(nomes[a]), _esc(nomes[b]), _numero(valor)]
              for a, b, valor in externas]
    corpo.append("<h2>Ligações externas</h2>")
    corpo.append(_tabela(["Nó A", "Nó B", "Peso"], linhas,
                         "Ligações externas", numericas=(2,)))

    if estendido:
        _blocos_documentos(corpo, kb, resultado, grupo)

    (destino / f"period{indice}-cluster{posicao - 1}.html").write_text(
        _pagina(f"{resultado.periodo} — {grupo.rotulo} · Redes",
                "\n".join(corpo)),
        encoding="utf-8")


def _blocos_documentos(corpo, kb, resultado, grupo) -> None:
    corpo.append("<h2>Documentos por mapeador</h2>")
    for mapeador, ids in grupo.documentos.items():
        titulo = ROTULOS_MAPEADOR.get(mapeador, mapeador)
        documentos = _documentos(kb, sorted(ids))
        referencias = _referencias(kb, sorted(ids))
        linhas = []
        for doc_id in sorted(documentos):
            doc = documentos[doc_id]
            refs = "<br>".join(_esc(referencia_abnt(r)) for r in referencias.get(doc_id, []))
            linhas.append([
                _esc(doc["titulo"]), _esc(doc["autores"]), _esc(doc["ano"]),
                _esc(doc["fonte"]), str(doc["citacoes"]), refs,
            ])
        corpo.append(_tabela(
            ["Título", "Autores", "Ano", "Fonte", "Citações", "Referências (ABNT)"],
            linhas, f"{titulo} ({len(linhas)})", numericas=(4,),
            larguras=["28%", "14%", "6%", "14%", "7%", "31%"]))

        prefixo = f"{mapeador}:"
        medidas = [[ROTULOS_MEDIDA[nome],
                    _numero(grupo.medidas.get(prefixo + nome, 0))]
                   for nome in ORDEM_MEDIDAS]
        corpo.append(_tabela(["Medida", "Valor"], medidas,
                             f"{titulo} — medidas de desempenho", numericas=(1,)))


# --------------------------------------------------------------------- LaTeX


def _tex(texto) -> str:
    trocas = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    return "".join(trocas.get(c, c) for c in str(texto or ""))


def gera_latex(destino: Path, kb, periodos, config, estendido: bool = False,
               medida_temporal: str = "EquivalenceIndex") -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_ASSETS / "logo.png", destino / "logo.png")
    resultados = [executa_periodo(kb, p.id, p.nome, config) for p in periodos]
    mapa = longitudinal.constroi(kb, config, periodos, medida_temporal)

    partes = [
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage[brazil]{babel}",
        r"\usepackage[margin=2.5cm,top=3.2cm]{geometry}",
        r"\usepackage{longtable}",
        r"\usepackage{array}",
        r"\usepackage{booktabs}",
        r"\usepackage{graphicx}",
        r"\usepackage{xcolor}",
        r"\usepackage{fancyhdr}",
        r"\usepackage[scaled=0.92]{helvet}",
        r"\renewcommand{\familydefault}{\sfdefault}",
        r"\usepackage{hyperref}",
        r"\definecolor{redescinza}{HTML}{64748B}",
        r"\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}",
        r"\pagestyle{fancy}",
        r"\fancyhf{}",
        r"\fancyhead[L]{\footnotesize\color{redescinza}Redes · mapeamento e "
        r"análise da produção científica}",
        r"\fancyhead[R]{\includegraphics[height=12mm]{logo.png}}",
        r"\fancyfoot[C]{\footnotesize\color{redescinza}Gerado por Redes.}",
        r"\setlength{\headheight}{38pt}",
        r"\setlength{\headsep}{12pt}",
        r"\renewcommand{\headrulewidth}{0.4pt}",
        r"\renewcommand{\footrulewidth}{0pt}",
        r"\fancypagestyle{plain}{\fancyhf{}"
        r"\fancyhead[L]{\footnotesize\color{redescinza}Redes · mapeamento e "
        r"análise da produção científica}"
        r"\fancyhead[R]{\includegraphics[height=12mm]{logo.png}}"
        r"\fancyfoot[C]{\footnotesize\color{redescinza}Gerado por Redes.}"
        r"\renewcommand{\headrulewidth}{0.4pt}}",
        r"\title{Relatório — Redes}",
        r"\author{Redes}",
        r"\date{}",
        r"\begin{document}",
        r"\maketitle",
        r"\section*{Configuração da análise}",
        r"\begin{tabular}{ll}",
        r"\toprule",
    ]
    for rotulo, valor in [
        ("Unidade de análise", ROTULOS_UNIDADE.get(config.unidade, config.unidade)),
        ("Tipo de rede", ROTULOS_MATRIZ.get(config.matriz, config.matriz)),
        ("Normalização", ROTULOS_SIMILARIDADE.get(config.similaridade, config.similaridade)),
        ("Algoritmo", ROTULOS_ALGORITMO.get(config.algoritmo, config.algoritmo)),
        ("Frequência mínima", config.minimo_frequencia),
        ("Coocorrência mínima", config.minimo_coocorrencia),
        ("Rede", f"{config.tamanho_minimo}–{config.tamanho_maximo}"),
        ("Corte", _numero(config.corte)),
        ("Mapeadores", ", ".join(ROTULOS_MAPEADOR.get(m, m) for m in config.mapeadores)),
    ]:
        partes.append(f"{_tex(rotulo)} & {_tex(valor)} \\\\")
    partes += [r"\bottomrule", r"\end{tabular}", ""]

    for indice, resultado in enumerate(resultados):
        grupos = sorted(resultado.grupos, key=lambda g: (-len(g.nos), g.rotulo or ""))
        partes.append(f"\\section{{{_tex(resultado.periodo)}}}")
        partes.append(f"Documentos: {resultado.dataset_original.quantidade_documentos()}; "
                      f"itens: {resultado.dataset_original.quantidade_itens()}; "
                      f"agrupamentos: {len(grupos)}.")
        partes += [
            r"\begin{longtable}{rlrrrr}",
            r"\toprule",
            r"Selo & Agrupamento & Itens & Densidade & Centralidade & Quadrante \\",
            r"\midrule",
        ]
        for posicao, grupo in enumerate(grupos, start=1):
            partes.append(
                f"{posicao} & {_tex(grupo.rotulo)} & {len(grupo.nos)} & "
                f"{_numero(grupo.densidade)} & {_numero(grupo.centralidade)} & "
                f"{_quadrante(grupo)} \\\\")
        partes += [r"\bottomrule", r"\end{longtable}"]

        for posicao, grupo in enumerate(grupos, start=1):
            partes.append(f"\\subsection{{{_tex(grupo.rotulo)}}}")
            partes += [
                r"\begin{tabular}{lr}",
                r"\toprule",
                f"Itens & {len(grupo.nos)} \\\\",
                f"Densidade & {_numero(grupo.densidade)} \\\\",
                f"Centralidade & {_numero(grupo.centralidade)} \\\\",
                f"Quadrante & {_quadrante(grupo)} \\\\",
                r"\bottomrule",
                r"\end{tabular}",
            ]

            for mapeador in resultado.configuracao.mapeadores:
                prefixo = f"{mapeador}:"
                partes += [
                    f"\\paragraph{{Medidas de desempenho — "
                    f"{_tex(ROTULOS_MAPEADOR.get(mapeador, mapeador))}}}",
                    r"\mbox{}\par",
                    r"\begin{tabular}{lr}",
                    r"\toprule",
                    r"Medida & Valor \\",
                    r"\midrule",
                ]
                for medida in ORDEM_MEDIDAS:
                    partes.append(
                        f"{_tex(ROTULOS_MEDIDA[medida])} & "
                        f"{_numero(grupo.medidas.get(prefixo + medida, 0))} \\\\")
                partes += [r"\bottomrule", r"\end{tabular}"]
            internas, externas = _ligacoes(resultado, grupo)
            nomes = {no: resultado.dataset.itens.get(no, str(no))
                     for no in resultado.rede.nos}
            if internas:
                partes += [
                    r"\paragraph{Ligações internas}",
                    r"\begin{longtable}{L{6.4cm}L{6.4cm}r}",
                    r"\toprule",
                    r"Nó A & Nó B & Peso \\",
                    r"\midrule",
                ]
                for a, b, valor in internas[:40]:
                    partes.append(
                        f"{_tex(nomes[a])} & {_tex(nomes[b])} & {_numero(valor)} \\\\")
                partes += [r"\bottomrule", r"\end{longtable}"]
            if estendido:
                _latex_documentos(partes, kb, grupo)

    partes.append(r"\end{document}")
    (destino / "relatorio.tex").write_text("\n".join(partes) + "\n", encoding="utf-8")
    return {"latex": str(destino), "periodos": len(resultados),
            "agrupamentos": sum(len(r.grupos) for r in resultados)}


def _latex_documentos(partes, kb, grupo) -> None:
    for mapeador, ids in grupo.documentos.items():
        documentos = _documentos(kb, sorted(ids))
        if not documentos:
            continue
        partes += [
            f"\\paragraph{{{_tex(ROTULOS_MAPEADOR.get(mapeador, mapeador))}}}",
            r"\mbox{}\par",
            r"\begin{longtable}{p{6cm}p{3.6cm}r}",
            r"\toprule",
            r"Título & Autores & Citações \\",
            r"\midrule",
        ]
        for doc_id in sorted(documentos):
            doc = documentos[doc_id]
            partes.append(
                f"{_tex(doc['titulo'])} & {_tex(doc['autores'])} & "
                f"{doc['citacoes']} \\\\")
        partes += [r"\bottomrule", r"\end{longtable}"]


def gera(destino: str | Path, kb, periodos, config, formato: str = "html",
         estendido: bool = False,
         medida_temporal: str = "EquivalenceIndex") -> dict:
    destino = Path(destino)
    if formato == "html":
        return gera_html(destino, kb, periodos, config, estendido, medida_temporal)
    if formato == "latex":
        return gera_latex(destino, kb, periodos, config, estendido, medida_temporal)
    raise ValueError(f"formato de relatório inválido: {formato}")

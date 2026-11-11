"""Relatório do Redes em HTML, simples e estendido.

Reproduz a estrutura dos geradores de HTML do fork Bibliomapa:

- índice com a configuração da análise, o resumo dos períodos e os mapas
  longitudinais;
- uma página por período com os diagramas estratégicos (um por medida de
  desempenho) e a lista de agrupamentos;
- uma página por agrupamento com a rede, as ligações internas e externas e,
  no relatório estendido, os documentos associados por mapeador e as
  referências em formato ABNT.

As figuras são SVG, vetoriais, sem dependência de rasterizador.
"""

from __future__ import annotations

import html
import re
import shutil
from contextvars import ContextVar
import unicodedata
from pathlib import Path

from . import linha_do_tempo, longitudinal, metodo, rotulos
from .pipeline import executa_periodo
from . import exports
from .viz.cluster import rede_agrupamento_svg, rede_de_agrupamentos_svg
from .viz.halo import halo_svg
from .viz import densidade as viz_densidade
from .viz import linha_do_tempo as viz_linha_do_tempo
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
.voltar { margin:0 0 10px; font-size:13px; }
.sumario { position:sticky; top:0; background:#fff; padding:8px 0; border-bottom:1px solid #E6E9F2; margin:0 0 18px;
  display:flex; flex-wrap:wrap; gap:6px 16px; font-size:13px; z-index:2; }
.miniaturas { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:14px; margin:8px 0 22px; }
.miniaturas figure { margin:0; border:1px solid #E6E9F2; border-radius:10px; padding:8px; background:#fff; }
.miniaturas img { width:100%; height:auto; display:block; }
.miniaturas figcaption { font-size:12px; color:#475569; margin-top:6px; }
.fonte { color:#64748B; font-size:12px; margin:0 0 18px; }
.aviso { background:#FFF9E0; border:1px solid #F0D98A; border-left:4px solid #FFC400; border-radius:8px; padding:8px 14px; margin:0 0 16px; font-size:13px; color:#5C4500; }
.aviso ul { margin:6px 0 0; padding-left:18px; }
.num { text-align:right; }
nav a { margin-right:14px; }
""" + metodo.CSS


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


_VOLTAR: ContextVar[str] = ContextVar("redes_voltar", default="")


def _pagina(titulo: str, corpo: str, profundidade: int = 0) -> str:
    raiz = "../" * profundidade
    voltar = _VOLTAR.get()
    if voltar:
        corpo = (f'<nav class="voltar"><a href="{voltar}">← Relatório completo</a></nav>\n'
                 + corpo)
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


def _configuracao_tabela(config, legenda: str | None = None) -> str:
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
    ]
    if config.unidade == "Words":
        linhas.append(["Origens das palavras", ", ".join(config.palavras) or "todas"])
    return _tabela(["Parâmetro", "Valor"], linhas, legenda)


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


# ------------------------------------------------------- linha do tempo (corpus)

NOTA_LINHA_DO_TEMPO = (
    "Como ler: cada faixa é um agrupamento da rede do corpus completo (todos os documentos, "
    "sem dividir em períodos). A posição horizontal de um item é o ano médio dos documentos "
    "em que ele aparece; nas referências, o ano da própria obra. A linha fina atrás do nó vai "
    "do primeiro ao último ano do item. O tamanho do nó segue a frequência e o anel vermelho "
    "marca uma rajada (aumento súbito de uso ou de citação).")

NOTA_RAJADA_PALAVRAS = (
    " As rajadas de palavras-chave são calculadas só sobre as palavras-chave dos autores, "
    "embora a rede de palavras possa incluir também as de fonte.")


def linha_do_tempo_aplicavel(config) -> bool:
    """A figura só tem sentido para palavras, autores ou referências em co-ocorrência."""
    return (config.matriz == "CoOccurrence"
            and config.unidade in metodo.UNIDADES_LINHA_DO_TEMPO)


def rotulos_linha_do_tempo(kb, config, dados: dict) -> dict:
    """Rótulos novos (índice da faixa → rótulo) para a linha do tempo do corpus completo.

    Refaz o agrupamento do corpus completo (determinístico) e só aceita o rótulo de um
    agrupamento cujo nome atual coincide com o da faixa; qualquer falha devolve {}.
    """
    try:
        resultado = executa_periodo(linha_do_tempo._TodosOsDocumentos(kb), 0, "Corpus", config)
        novos = rotulos.rotula_grupos(kb, resultado) or {}
        saida = {}
        for faixa in dados.get("faixas", []):
            i = faixa["indice"]
            if i in novos and i < len(resultado.grupos):
                atual = (linha_do_tempo.limpa(resultado.grupos[i].rotulo)
                         or f"Agrupamento {i + 1}")
                if atual != faixa["rotulo"]:
                    continue
                saida[i] = novos[i]
        return saida
    except Exception:
        return {}


def linha_do_tempo_do_corpus(kb, config, max_nos: int = linha_do_tempo.MAX_NOS):
    """(dados, rótulos novos) da linha do tempo do corpus completo."""
    dados = linha_do_tempo.constroi(kb, config, max_nos=max_nos)
    rot = rotulos_linha_do_tempo(kb, config, dados) if dados.get("faixas") else {}
    return dados, rot


def titulo_linha_do_tempo(config) -> str:
    unidade = viz_linha_do_tempo.NOMES_UNIDADE.get(config.unidade, config.unidade)
    return f"Linha do tempo — {unidade} (corpus completo)"


def linha_do_tempo_html(kb, config, figura, classe_nota: str = "nota"):
    """Partes HTML da seção "Linha do tempo (corpus completo)", ou None.

    None quando a análise não é palavras, autores ou referências em co-ocorrência, ou
    quando o cálculo falha: quem chama omite a seção. `figura(svg, legenda, dados)` monta
    a figura numerada (e pode gravar o arquivo). Sem agrupamentos com ano, a seção traz só
    os avisos, sem figura vazia.
    """
    if kb is None or not linha_do_tempo_aplicavel(config):
        return None
    try:
        dados, rot = linha_do_tempo_do_corpus(kb, config)
        titulo = titulo_linha_do_tempo(config)
        partes = []
        if dados.get("faixas"):
            svg = viz_linha_do_tempo.svg(dados, titulo, rotulos=rot)
            partes.append(figura(svg, titulo + "."))
            nota = NOTA_LINHA_DO_TEMPO + (NOTA_RAJADA_PALAVRAS if config.unidade == "Words" else "")
            partes.append(f'<p class="{classe_nota}">{_esc(nota)}</p>')
        else:
            partes.append(f'<p class="{classe_nota}">Não foi possível desenhar a linha do '
                          "tempo com estes parâmetros.</p>")
        avisos = [linha_do_tempo.limpa(a) for a in dados.get("avisos", [])]
        if avisos:
            partes.append("<ul>" + "".join(f"<li>{_esc(a)}</li>" for a in avisos if a) + "</ul>")
        return partes
    except Exception:
        return None


def _bloco_linha_do_tempo_pasta(destino: Path, kb, config) -> str:
    """HTML da seção para o relatório em pasta (figura em images/); "" se não se aplica."""
    def figura(svg, legenda):
        (destino / "images" / "linhaDoTempo.svg").write_text(svg, encoding="utf-8")
        return (f'<p><img src="images/linhaDoTempo.svg" alt="{_esc(legenda)}" '
                'width="100%"></p>')
    partes = linha_do_tempo_html(kb, config, figura, classe_nota="fonte")
    if not partes:
        return ""
    return "\n".join(['<h2 id="linha-do-tempo">Linha do tempo (corpus completo)</h2>'] + partes)


# ------------------------------------------------------- mapa de densidade (corpus)

NOTA_DENSIDADE = (
    "Como ler: os itens mais frequentes da rede do corpus completo (todos os documentos, "
    "sem dividir em períodos) ficam mais perto quanto mais forte é a ligação entre eles. "
    "A cor mostra a densidade: do branco (pouca) ao amarelo (muita), somando a frequência "
    "dos itens vizinhos. Uma área quente é um conjunto de itens frequentes e fortemente "
    "ligados; áreas azuis e vazias são temas periféricos. Só os rótulos que cabem sem "
    "sobreposição são escritos (os maiores são os mais frequentes), e a posição absoluta "
    "não tem unidade: vale a distância relativa entre os itens.")


def densidade_aplicavel(config) -> bool:
    """O mapa precisa de itens ligados por co-ocorrência (não de documentos)."""
    return config.matriz == "CoOccurrence"


def densidade_do_corpus(kb, config):
    """Resultado de período do corpus completo, base do mapa de densidade."""
    return executa_periodo(linha_do_tempo._TodosOsDocumentos(kb), 0, "Corpus", config)


def titulo_densidade(config) -> str:
    unidade = viz_linha_do_tempo.NOMES_UNIDADE.get(config.unidade, config.unidade)
    return f"Mapa de densidade — {unidade} (corpus completo)"


def densidade_html(kb, config, figura, classe_nota: str = "nota"):
    """Partes HTML da seção "Mapa de densidade (corpus completo)", ou None.

    None quando a análise não é de co-ocorrência ou quando o cálculo falha: quem chama
    omite a seção. `figura(svg, legenda)` monta a figura numerada.
    """
    if kb is None or not densidade_aplicavel(config):
        return None
    try:
        resultado = densidade_do_corpus(kb, config)
        dados = viz_densidade.calcula(resultado)
        if not dados["nos"]:
            return [f'<p class="{classe_nota}">{_esc(dados.get("aviso") or "Sem dados para o mapa de densidade.")}</p>']
        titulo = titulo_densidade(config)
        svg = viz_densidade.svg(resultado, titulo, unidade=config.unidade, dados=dados)
        return [figura(svg, titulo + "."), f'<p class="{classe_nota}">{_esc(NOTA_DENSIDADE)}</p>']
    except Exception:
        return None


def _bloco_densidade_pasta(destino: Path, kb, config) -> str:
    """HTML da seção para o relatório em pasta (figura em images/); "" se não se aplica."""
    def figura(svg, legenda):
        (destino / "images" / "densidade.svg").write_text(svg, encoding="utf-8")
        return (f'<p><img src="images/densidade.svg" alt="{_esc(legenda)}" '
                'width="100%"></p>')
    partes = densidade_html(kb, config, figura, classe_nota="fonte")
    if not partes:
        return ""
    return "\n".join(['<h2 id="densidade">Mapa de densidade (corpus completo)</h2>'] + partes)


def gera_html(destino: Path, kb, periodos, config, estendido: bool = False,
              medida_temporal: str = "EquivalenceIndex",
              com_bibliometria: bool = True, devolve_resultados: bool = False) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "images").mkdir(exist_ok=True)
    (destino / "misc").mkdir(exist_ok=True)
    shutil.copyfile(_ASSETS / "logo.svg", destino / "logo.svg")

    resultados = [executa_periodo(kb, p.id, p.nome, config) for p in periodos]
    mapa = longitudinal.constroi(kb, config, periodos, medida_temporal)

    for indice, resultado in enumerate(resultados):
        rotulos_novos = metodo.rotulos_do_resultado(kb, resultado)
        # Um diagrama por mapeador e medida de desempenho, como nas páginas de
        # período do fork: o tamanho das esferas muda com a medida escolhida.
        for mapeador in (resultado.configuracao.mapeadores if resultado.grupos else ()):
            for medida in ORDEM_MEDIDAS:
                titulo = (f"Diagrama estratégico — {resultado.periodo} — "
                          f"{ROTULOS_MAPEADOR.get(mapeador, mapeador)} — "
                          f"{ROTULOS_MEDIDA[medida]}")
                diagrama = diagrama_svg(
                    resultado, titulo, metrica=f"{mapeador}:{medida}",
                    rotulo_metrica=ROTULOS_MEDIDA[medida],
                    rotulos=rotulos_novos)
                (destino / "images" /
                 f"strategicDiagram-period{indice}-{mapeador}-{medida}.svg"
                 ).write_text(diagrama, encoding="utf-8")

        # Rede completa do período (halo) e rede entre os agrupamentos, como a
        # seção "Whole network" do SciMAT, mais o arquivo Pajek correspondente.
        try:
            (destino / "images" / f"wholeNetwork-period{indice}.svg").write_text(
                halo_svg(resultado, f"Rede completa — {resultado.periodo}",
                         rotulos=rotulos_novos,
                         pivos=metodo.pivos_para_halo(kb, resultado)),
                encoding="utf-8")
        except Exception:
            pass
        try:
            (destino / "images" / f"clusterGraph-period{indice}.svg").write_text(
                rede_de_agrupamentos_svg(
                    resultado, f"Rede de agrupamentos — {resultado.periodo}",
                    rotulos=rotulos_novos),
                encoding="utf-8")
        except Exception:
            pass
        rotulos_rede = resultado.dataset.itens
        try:
            (destino / "misc" / f"wholeNetwork-period{indice}.net").write_text(
                exports.pajek(resultado.rede, rotulos_rede), encoding="utf-8")
        except Exception:
            pass

        grupos = sorted(resultado.grupos,
                        key=lambda g: (-len(g.nos), g.rotulo or ""))
        for posicao, grupo in enumerate(grupos, start=1):
            svg = rede_agrupamento_svg(
                resultado, grupo,
                f"{resultado.periodo} — {grupo.rotulo}", rotulos=rotulos_novos)
            (destino / "images" /
             f"clusterNetwork-period{indice}-cluster{posicao - 1}.svg").write_text(
                svg, encoding="utf-8")
            _pagina_cluster(destino, kb, resultado, grupo, grupos, indice,
                            posicao, estendido)

        _pagina_periodo(destino, resultado, grupos, indice, kb)

    evolucao = longitudinal.evolucao_svg(
        mapa, "Mapa de evolução dos temas", largura=980)
    sobreposicao = longitudinal.sobreposicao_svg(
        mapa, "Mapa de sobreposição", largura=680)
    (destino / "images" / "evolutionMap.svg").write_text(evolucao, encoding="utf-8")
    (destino / "images" / "overlappingMap.svg").write_text(
        sobreposicao, encoding="utf-8")
    (destino / "misc" / "evolutionMap.net").write_text(
        longitudinal.evolucao_pajek(mapa), encoding="utf-8")

    if com_bibliometria:
        _pagina_bibliometria(destino, kb)
    try:
        bloco_lt = _bloco_linha_do_tempo_pasta(destino, kb, config)
    except Exception:
        bloco_lt = ""
    try:
        bloco_dens = _bloco_densidade_pasta(destino, kb, config)
    except Exception:
        bloco_dens = ""
    if bloco_dens:
        bloco_lt = (bloco_lt + "\n" + bloco_dens) if bloco_lt else bloco_dens
    _pagina_indice(destino, resultados, mapa, config, estendido, com_bibliometria,
                   kb=kb, periodos=periodos, medida_temporal=medida_temporal,
                   linha_do_tempo_bloco=bloco_lt)
    resumo = {"html": str(destino), "periodos": len(resultados),
              "agrupamentos": sum(len(r.grupos) for r in resultados)}
    if devolve_resultados:
        resumo["resultados"] = resultados
    return resumo


def _numerador():
    """Tabelas com legenda "Tabela N — …", numeradas na ordem em que são pedidas."""
    contador = [0]

    def tabela(cabecalho, linhas, legenda=None, numericas=(), larguras=None):
        contador[0] += 1
        titulo = f"Tabela {contador[0]}" + (f" — {legenda}" if legenda else "")
        return _tabela(cabecalho, linhas, titulo, numericas=numericas, larguras=larguras)

    return tabela


def _pagina_indice(destino, resultados, mapa, config, estendido,
                   com_bibliometria: bool = True, kb=None, periodos=None,
                   medida_temporal: str = "EquivalenceIndex",
                   linha_do_tempo_bloco: str = "") -> None:
    linhas = []
    for indice, resultado in enumerate(resultados):
        linhas.append([
            f'<a href="period{indice}.html">{_esc(resultado.periodo)}</a>',
            str(resultado.dataset_original.quantidade_documentos()),
            str(resultado.dataset_original.quantidade_itens()),
            str(len(resultado.grupos)),
            f"{resultado.rede.quantidade_nos()}/{resultado.rede.quantidade_arestas()}",
        ])

    tabela = _numerador()
    bloco_metodo = metodo.metodo_html(
        config, periodos, resultados, None, medida_temporal, kb, tabela,
        titulo=lambda texto: f"<h3>{_esc(texto)}</h3>")
    corpo = [
        "<h1>Relatório — Redes</h1>",
        "<p>Relatório gerado automaticamente a partir do projeto analisado.</p>",
        ('<p><a href="bibliometria.html">Visão geral descritiva do corpus</a> '
         "(produção, rankings, rajadas e nuvens de palavras)</p>")
        if com_bibliometria else "",
        "<h2>Parâmetros e método</h2>",
        bloco_metodo,
        "<h2>Resultados dos períodos</h2>",
        tabela(["Período", "Documentos", "Itens", "Agrupamentos", "Nós/arestas"],
               linhas, "Resumo por período", numericas=(1, 2, 3, 4)),
        "<h2>Resultados longitudinais</h2>",
        f'<p><img src="images/evolutionMap.svg" '
        f'alt="Mapa de evolução dos temas" width="980"></p>',
        '<p class="fonte">Mapa de evolução em Pajek: '
        '<a href="misc/evolutionMap.net">misc/evolutionMap.net</a>.</p>',
        f'<p><img class="mapa-sobreposicao" src="images/overlappingMap.svg" '
        f'alt="Mapa de sobreposição"></p>',
    ]
    if linha_do_tempo_bloco:
        corpo.append(linha_do_tempo_bloco)
    if estendido:
        corpo.append("<p>Relatório estendido: cada agrupamento lista os "
                     "documentos por mapeador, com citações e referências.</p>")
    (destino / "index.html").write_text(
        _pagina("Relatório — Redes", "\n".join(corpo)), encoding="utf-8")


class _EstiloPasta:
    """Apresentação da visão geral nos relatórios em pasta (h1/h2, imagens em arquivo)."""

    def __init__(self, imagens: Path | None = None):
        self.imagens = imagens

    def titulo(self, nivel: int, texto: str) -> str:
        return f"<h{nivel + 1}>{_esc(texto)}</h{nivel + 1}>"

    def tabela(self, cabecalho, linhas, legenda=None, numericas=()) -> str:
        return _tabela(cabecalho, linhas, legenda, numericas=numericas)

    def figura(self, svg: str, legenda: str, arquivo: str | None = None) -> str:
        if arquivo and self.imagens is not None:
            (self.imagens / arquivo).write_text(svg, encoding="utf-8")
            return (f'<p><img src="images/{arquivo}" alt="{_esc(legenda)}" '
                    'style="max-width:100%"></p>')
        return svg


def corpo_bibliometria(kb, estilo=None) -> str | None:
    """Corpo HTML da visão geral descritiva do corpus, com os SVG embutidos.

    Devolve None quando o corpus está vazio. O `estilo` define cabeçalhos
    (`titulo(nivel, texto)`: 0 = título da visão geral, 1 = seções, 2 =
    subseções), tabelas (`tabela`) e figuras (`figura(svg, legenda, arquivo)`);
    o padrão reproduz a página dos relatórios em pasta.
    """
    from . import bibliometria, rajadas, termos
    from .viz import descritiva

    estilo = estilo or _EstiloPasta()
    conexao = kb.conexao
    dados = bibliometria.calcula(conexao)
    if dados.get("vazio"):
        return None
    p = dados["principal"]

    def num(valor, casas=0):
        if valor is None:
            return "—"
        texto = f"{valor:,.{casas}f}"
        return texto.replace(",", "X").replace(".", ",").replace("X", ".")

    cartoes = [
        ["Documentos", num(p["documentos"]), f'{p["primeiro_ano"]}–{p["ultimo_ano"]}'],
        ["Autores", num(p["autores"]), f'{num(p["autores_por_documento"], 2)} por documento'],
        ["Fontes", num(p["fontes"]), "periódicos do corpus"],
        ["Palavras-chave", num(p["palavras_chave"]), "dos autores"],
        ["Instituições", num(p.get("instituicoes", 0)), "distintas, pelas afiliações"],
        ["Países", num(p["paises"]), "com afiliação"],
        ["Referências", num(p["referencias"]), "distintas"],
        ["Citações", num(p["citacoes"]), f'{num(p["citacoes_por_documento"], 2)} por documento'],
        ["Crescimento anual", f'{num(p["crescimento_anual"], 1)}%'
         if p["crescimento_anual"] is not None else "—", "taxa composta"],
        ["Documentos de autor único", num(p["documentos_autor_unico"]), ""],
        ["Índice de colaboração", num(p["indice_colaboracao"], 2), "autores por documento em coautoria"],
    ]

    def ranking(titulo, linhas, colunas):
        cab = [c[0] for c in colunas]
        corpo = [[_esc(l.get(c[1], "")) if not c[2] else num(l.get(c[1], 0)) for c in colunas]
                 for l in linhas]
        numericas = tuple(i for i, c in enumerate(colunas) if c[2])
        return estilo.tabela(cab, corpo, titulo, numericas=numericas)

    corpo = [
        estilo.titulo(0, "Visão geral descritiva"),
        ('<div class="aviso"><b>O que falta neste corpus</b><ul>'
         + "".join(f"<li>{_esc(t)}</li>" for t in dados["lacunas"]) + "</ul></div>")
        if dados.get("lacunas") else "",
        estilo.tabela(["Indicador", "Valor", "Observação"], cartoes, "Informações principais",
                      numericas=(1,)),
        estilo.titulo(1, "Produção e citações por ano"),
        estilo.figura(descritiva.producao_svg(dados["producao"]),
                      "Produção e citações por ano"),
        '<p class="fonte">Barras: documentos por ano (eixo esquerdo). Linha: citações '
        "recebidas pelos documentos publicados em cada ano (eixo direito).</p>",
        estilo.titulo(1, "Autores, fontes e países"),
        ranking("Autores mais produtivos", dados["autores"],
                [("Autor", "nome", 0), ("Documentos", "documentos", 1),
                 ("Citações", "citacoes", 1), ("h", "h", 1)]),
        ranking("Fontes mais produtivas", dados["fontes"],
                [("Fonte", "nome", 0), ("Documentos", "documentos", 1), ("Citações", "citacoes", 1)]),
        ranking("Instituições (IES)", dados.get("instituicoes", []),
                [("Instituição", "nome", 0), ("Documentos", "documentos", 1), ("Citações", "citacoes", 1)]),
        ranking("Países", dados["paises"],
                [("País", "nome", 0), ("Documentos", "documentos", 1), ("Citações", "citacoes", 1)]),
        ranking("Fontes mais citadas nas referências", dados["fontes_citadas"],
                [("Fonte citada", "nome", 0), ("Documentos que citam", "documentos", 1)]),
        ranking("Documentos mais citados", dados["mais_citados"],
                [("Documento", "titulo", 0), ("Ano", "ano", 0), ("Citações", "citacoes", 1)]),
        estilo.titulo(1, "Leis bibliométricas"),
        estilo.tabela(["Lei", "Resultado"], [
            ["Lotka", f'expoente estimado β = {num(dados["lotka"]["beta"], 2)} '
                      f'(clássico: 2), {num(dados["lotka"]["autores"])} autores'],
            ["Bradford", f'{num(dados["bradford"]["fontes"])} '
                         f'{"fonte" if dados["bradford"]["fontes"] == 1 else "fontes"} em '
                         f'{len(dados["bradford"]["zonas"])} '
                         f'{"zona" if len(dados["bradford"]["zonas"]) == 1 else "zonas"}'],
            ["Zipf", f'inclinação estimada {num(dados["zipf"]["expoente"], 2)} (clássico: 1), '
                     f'{num(dados["zipf"]["palavras"])} palavras-chave'],
        ], "Leis de Lotka, Bradford e Zipf"),
    ]

    # Fluxo Autor - País - IES
    from . import fluxos
    sankey = fluxos.corpo_sankey_html(conexao)
    if sankey:
        corpo.append(estilo.titulo(1, "Fluxo Autor – País – IES"))
        corpo.append(sankey)

    # Nuvens de palavras
    corpo.append(estilo.titulo(1, "Nuvens de palavras"))
    for fonte, titulo in (("palavras", "Palavras-chave dos autores"), ("titulos", "Títulos dos documentos")):
        nuvem = termos.nuvem_dados(conexao, fonte, limite=70)
        svg = descritiva.nuvem_svg([(t["termo"], t["documentos"]) for t in nuvem["termos"]], titulo)
        if svg:
            corpo.append(estilo.titulo(2, titulo))
            corpo.append(estilo.figura(svg, f"Nuvem de palavras — {titulo.lower()}"))
        if nuvem["expressoes"]:
            corpo.append('<p class="fonte">Expressões frequentes: ' + " · ".join(
                f'{_esc(e["termo"])} ({e["documentos"]})' for e in nuvem["expressoes"]) + ".</p>")
    corpo.append('<p class="fonte">Nos títulos foram retiradas palavras vazias do português, '
                 "inglês e espanhol e termos genéricos da escrita acadêmica; singular, plural e "
                 "acento foram unidos.</p>")

    # Rajadas
    corpo.append(estilo.titulo(1, "Rajadas (bursts)"))
    for tipo, titulo, rotulo in (("palavras", "Palavras-chave com as rajadas mais fortes", "Palavras-chave"),
                                 ("referencias", "Referências com as rajadas mais fortes", "Referência")):
        resultado = rajadas.calcula(conexao, tipo)
        svg = descritiva.rajadas_svg(resultado, titulo, rotulo)
        corpo.extend(f'<p class="fonte">{_esc(a)}</p>' for a in resultado["avisos"])
        if svg:
            corpo.append(estilo.figura(svg, titulo, f"bursts-{tipo}.svg"))
    corpo.append('<p class="fonte">Rajadas pelo algoritmo de Kleinberg (s = 2, γ = 1). A contagem é de '
                 "documentos do corpus que usam o termo ou citam a referência, não de citações recebidas.</p>")

    corpo.append(estilo.titulo(1, "Método e parâmetros"))
    corpo.append(metodo.metodo_bibliometria_html(estilo.tabela))
    return "\n".join(c for c in corpo if c)


def _pagina_bibliometria(destino: Path, kb) -> None:
    """Página da visão geral descritiva: o que a tela mostra, em HTML estático."""
    (destino / "images").mkdir(parents=True, exist_ok=True)
    corpo = corpo_bibliometria(kb, _EstiloPasta(destino / "images"))
    if corpo is None:
        return
    (destino / "bibliometria.html").write_text(
        _pagina("Visão geral descritiva — Redes",
                '<p><a href="index.html">Índice</a></p>\n' + corpo),
        encoding="utf-8")


def _pagina_periodo(destino, resultado, grupos, indice, kb=None) -> None:
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
    ]
    diagramas = ["<h2>Diagramas estratégicos</h2>"]
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
        diagramas.append(_tabela(["Medida de desempenho", "Diagrama estratégico"],
                             linhas_diagramas,
                             f"Diagramas estratégicos — {rotulo_mapeador}",
                             larguras=["26%", "74%"]))

    diagramas.append(
        '<p class="fonte">O tamanho das esferas segue a medida de desempenho '
        'indicada em cada diagrama; o quadrante usa a centralidade e a '
        'densidade de Callon.</p>')

    # Rede completa e rede de agrupamentos, antes do quadro de métricas.
    imagens = destino / "images"
    if (imagens / f"wholeNetwork-period{indice}.svg").exists():
        corpo.append("<h2>Rede completa</h2>")
        corpo.append(
            f'<p><img src="images/wholeNetwork-period{indice}.svg" '
            f'alt="Rede completa — {_esc(resultado.periodo)}" width="100%"></p>')
        corpo.append(
            f'<p class="fonte"><a href="misc/wholeNetwork-period{indice}.net">'
            "Rede completa — arquivo Pajek</a></p>")
        tabela_pivos = metodo.pivos_html(
            kb, resultado,
            lambda cab, lin, leg, num=(): _tabela(cab, lin, leg, numericas=num),
            f"Pontos de virada — {resultado.periodo}", classe_nota="fonte")
        if tabela_pivos:
            corpo.append("<h2>Pontos de virada</h2>")
            corpo.append(tabela_pivos)
    if (imagens / f"clusterGraph-period{indice}.svg").exists():
        corpo.append("<h2>Rede de agrupamentos</h2>")
        corpo.append(
            f'<p><img src="images/clusterGraph-period{indice}.svg" '
            f'alt="Rede de agrupamentos — {_esc(resultado.periodo)}" width="100%"></p>')

    # Quadro único: métricas de cada agrupamento ao lado da sua rede.
    cartoes = []
    for posicao, grupo in enumerate(grupos, start=1):
        medidas = grupo.medidas
        prefixo = f"{resultado.configuracao.mapeadores[0]}:"
        metricas = "<br>".join([
            f"Itens: {len(grupo.nos)}",
            f"Centralidade: {_numero(grupo.centralidade)}",
            f"Densidade: {_numero(grupo.densidade)}",
            f"Quadrante: {_quadrante(grupo)}",
        ] + [f"{ROTULOS_MEDIDA[nome]}: {_numero(medidas.get(prefixo + nome, 0))}"
             for nome in ("documentos", "h", "g", "hg")])
        principal, sub, _ind = metodo.nome_do_grupo(kb, resultado, grupo)
        nome = (f'<a href="period{indice}-cluster{posicao - 1}.html">'
                f'{_esc(principal)}</a>')
        if sub:
            nome += f'<br><span class="rot-atual">{_esc(sub)}</span>'
        cartoes.append([
            nome,
            metricas,
            f'<img src="images/clusterNetwork-period{indice}-cluster{posicao - 1}.svg" '
            f'alt="Rede de {_esc(principal)}" width="320">',
        ])
    corpo.append("<h2>Métricas e rede de cada agrupamento</h2>")
    corpo.append(_tabela(["Agrupamento", "Métricas", "Rede do agrupamento"],
                         cartoes, "Quadro de métricas com a rede de cada agrupamento",
                         larguras=["24%", "26%", "50%"]))

    prefixo = f"{resultado.configuracao.mapeadores[0]}:"
    cabecalho, linhas, numericas = metodo.tabela_agrupamentos(
        kb, resultado, grupos,
        [(prefixo + nome, ROTULOS_MEDIDA[nome]) for nome in ORDEM_MEDIDAS],
        _numero,
        ligar=lambda posicao, texto: (
            f'<a href="period{indice}-cluster{posicao - 1}.html">{texto}</a>'))
    corpo.append("<h2>Agrupamentos</h2>")
    corpo.append(_tabela(cabecalho, linhas, "Agrupamentos do período",
                         numericas=numericas))
    corpo.append(
        '<p class="fonte">Silhueta: coesão média dos itens do agrupamento (de −1 a 1; “—” '
        "quando o agrupamento tem poucos itens). Ano médio: dos documentos do núcleo. "
        "Rótulo em destaque: termos distintivos do período; abaixo, o nome do item central.</p>")

    if resultado.configuracao.unidade == "Institutions":
        corpo.append("<h2>Variantes unidas</h2>")
        corpo.append(metodo.ies_html(
            resultado, lambda cab, lin, leg, numericas=(): _tabela(cab, lin, leg, numericas=numericas)))

    corpo.extend(diagramas)
    (destino / f"period{indice}.html").write_text(
        _pagina(f"Relatório — Redes — {resultado.periodo}", "\n".join(corpo)),
        encoding="utf-8")


def _pagina_cluster(destino, kb, resultado, grupo, grupos, indice,
                    posicao, estendido) -> None:
    internas, externas = _ligacoes(resultado, grupo)
    nomes = {no: resultado.dataset.itens.get(no, str(no)) for no in resultado.rede.nos}
    principal, sub, indicativo = metodo.nome_do_grupo(kb, resultado, grupo)
    nome_html = _esc(principal) + (' <span class="rot-ind">(indicativo)</span>'
                                   if indicativo else "")

    corpo = [
        f'<p><a href="index.html">Índice</a> · '
        f'<a href="period{indice}.html">{_esc(resultado.periodo)}</a></p>',
        f"<h1>{_esc(resultado.periodo)} — {_esc(principal)}</h1>",
    ]
    if sub:
        corpo.append(f'<p class="rot-atual">Rótulo atual (item central): {_esc(sub)}</p>')
    corpo += [
        "<h2>Informações do agrupamento</h2>",
        _tabela(["Medida", "Valor"], [
            ["Nome", nome_html],
            ["Itens", str(len(grupo.nos))],
            ["Densidade", _numero(grupo.densidade)],
            ["Faixa de densidade", _numero(grupo.densidade_faixa)],
            ["Centralidade", _numero(grupo.centralidade)],
            ["Faixa de centralidade", _numero(grupo.centralidade_faixa)],
            ["Quadrante", _quadrante(grupo)],
        ] + ([["Nome atual (item central)", _esc(sub)]] if sub else [])),
        "<h2>Rede do agrupamento</h2>",
        f'<p><img src="images/clusterNetwork-period{indice}-cluster{posicao - 1}.svg" '
        f'alt="Rede do agrupamento {_esc(principal)}" width="720"></p>',
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
        _pagina(f"{resultado.periodo} — {principal} · Redes",
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


def gera(destino: str | Path, kb, periodos, config, formato: str = "html",
         estendido: bool = False,
         medida_temporal: str = "EquivalenceIndex") -> dict:
    """Gera o relatório. O único formato é HTML."""
    if formato != "html":
        raise ValueError("o relatório é gerado somente em HTML")
    return gera_html(Path(destino), kb, periodos, config, estendido, medida_temporal)


def gera_pagina_completa(destino: Path, kb, secoes: list[dict], ignoradas: list[dict],
                         medida_temporal: str = "EquivalenceIndex") -> None:
    """Índice do relatório completo: seções numeradas, resumo por período e figuras.

    Cada seção é uma análise já gerada em `destino/<pasta>`; `secoes` traz o
    rótulo, a descrição, a pasta, a configuração e os resultados por período.
    """
    numero_figura = 0
    tabela = _numerador()
    try:
        periodos = kb.periodos()
    except Exception:
        periodos = None
    sumario = ['<a href="bibliometria.html">1 Visão geral descritiva</a>']
    corpo = ["<h1>Relatório completo — Redes</h1>",
             "<p>Cada seção traz o quadro por período, o diagrama estratégico e a rede de cada período; "
             "os links levam às páginas de período e de cada agrupamento.</p>"]
    blocos = ['<h2 id="visao">1 Visão geral descritiva</h2>'
              '<p><a href="bibliometria.html">Produção e citações, rankings, leis bibliométricas, '
              "nuvens de palavras e rajadas</a></p>"]
    for posicao, secao in enumerate(secoes, start=2):
        ancora = f"s{posicao}"
        sumario.append(f'<a href="#{ancora}">{posicao} {_esc(secao["rotulo"])}</a>')
        pasta = secao["pasta"]
        resultados = secao["resultados"]
        linhas = []
        for indice, r in enumerate(resultados):
            maior = max((len(g.nos) for g in r.grupos), default=0)
            linhas.append([
                f'<a href="{pasta}/period{indice}.html">{_esc(r.periodo)}</a>',
                str(r.dataset_original.quantidade_itens()),
                str(len(r.grupos)),
                f"{maior} nós",
            ])
        bloco = [f'<h2 id="{ancora}">{posicao} {_esc(secao["rotulo"])}</h2>',
                 f'<p>{_esc(secao["descricao"])}</p>',
                 _tabela(["Período", "Itens", "Grupos", "Maior grupo"], linhas,
                         f"{posicao}.1 Por período", numericas=(1, 2)),
                 f'<p><a href="{pasta}/index.html">Configuração, mapa de evolução e sobreposição</a></p>']
        if (destino / pasta / "images" / "linhaDoTempo.svg").exists():
            bloco.append(f'<p><a href="{pasta}/index.html#linha-do-tempo">Linha do tempo do '
                         "corpus completo</a></p>")
        if (destino / pasta / "images" / "densidade.svg").exists():
            bloco.append(f'<p><a href="{pasta}/index.html#densidade">Mapa de densidade do '
                         "corpus completo</a></p>")
        figuras = []
        mapeador = secao["config"].mapeadores[0] if secao["config"].mapeadores else "nucleo"
        for indice, r in enumerate(resultados):
            if not r.grupos:
                continue
            for arquivo, legenda in (
                    (f"strategicDiagram-period{indice}-{mapeador}-{ORDEM_MEDIDAS[0]}.svg",
                     "Diagrama estratégico"),
                    (f"wholeNetwork-period{indice}.svg", "Rede do período")):
                if not (destino / pasta / "images" / arquivo).exists():
                    continue
                numero_figura += 1
                figuras.append(
                    f'<figure><a href="{pasta}/period{indice}.html">'
                    f'<img src="{pasta}/images/{arquivo}" alt="{_esc(legenda)} {_esc(r.periodo)}" loading="lazy"></a>'
                    f'<figcaption>Figura {numero_figura} — {legenda.lower()} de '
                    f'{_esc(secao["rotulo"].lower())}, {_esc(r.periodo)}.</figcaption></figure>')
        if figuras:
            bloco.append('<div class="miniaturas">' + "".join(figuras) + "</div>")
        bloco.append(f'<h3 id="{ancora}-metodo">{posicao}.2 Parâmetros e método</h3>')
        bloco.append(metodo.metodo_html(
            secao["config"], periodos, resultados, None,
            secao.get("medida_temporal", medida_temporal), kb, tabela,
            rotulo=secao["rotulo"].lower(),
            titulo=lambda texto: f"<h4>{_esc(texto)}</h4>"))
        blocos.append("\n".join(bloco))
    if ignoradas:
        sumario.append('<a href="#nao-gerados">Não gerados</a>')
        blocos.append('<h2 id="nao-gerados">Análises não geradas</h2><ul>' + "".join(
            f'<li><b>{_esc(i["rotulo"])}</b>: {_esc(i["motivo"])}</li>' for i in ignoradas) + "</ul>")
    corpo.insert(1, '<nav class="sumario">' + " ".join(sumario) + "</nav>")
    corpo.extend(blocos)
    shutil.copyfile(_ASSETS / "logo.svg", destino / "logo.svg")
    (destino / "index.html").write_text(
        _pagina("Relatório completo — Redes", "\n".join(corpo)), encoding="utf-8")

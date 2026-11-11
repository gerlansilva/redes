"""Relatório completo em arquivo único.

Gera um .html autocontido (CSS e SVG embutidos, sem JavaScript e sem arquivos
externos), pensado para ler, citar e imprimir ou salvar em PDF pelo navegador.
A numeração é contínua, no estilo de artigo: seções "4", subseções "4.2",
"Figura 6 — …" e "Tabela 3 — …".
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

from . import cache_figuras, dendro_helper, longitudinal, metodo, report
from . import areas as _areas_revistas
from . import duplo_mapa as _duplo_mapa
from . import similitude as _similitude
from .report import (ORDEM_MEDIDAS, ROTULOS_MAPEADOR, ROTULOS_MEDIDA, _esc,
                     _quadrante, _tabela)
from .viz.cluster import rede_agrupamento_svg
from .viz.halo import halo_svg
from .viz.strategic import diagrama_svg

PARTES_DO_CORPO = ("linha-do-tempo", "densidade")

# Acima disso, as redes de agrupamento ficam só nos maiores grupos de cada período.
LIMITE_BYTES = 15 * 1024 * 1024
_LIMITES_REDES = (None, 12, 6, 3)

_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro")

_CSS_EXTRA = """
.sumario { position:static; display:block; border:1px solid #E3E6EC; border-radius:8px;
           padding:10px 18px; margin:0 0 24px; background:#FAFBFD; }
.sumario h2 { margin:6px 0 8px; font-size:16px; }
.sumario ol { list-style:none; margin:0; padding:0; }
.sumario li { margin:2px 0; }
.sumario li.n2 { font-weight:600; margin-top:8px; }
.sumario li.n3 { padding-left:20px; }
.sumario li.n4 { padding-left:40px; font-size:12.5px; }
.sumario small { color:#64748B; }
.capa { text-align:center; padding:28px 0 18px; border-bottom:1px solid #D7DBE6; margin-bottom:24px; }
.capa img.logo-capa, .capa svg.logo-capa { width:220px; height:auto; margin:0 auto 10px; display:block; }
.capa h1 { border:0; font-size:30px; margin:6px 0 4px; }
.capa .projeto { font-size:16px; color:#1F2A44; margin:0 0 14px; }
.capa dl { display:inline-grid; grid-template-columns:auto auto; gap:4px 18px; text-align:left;
           margin:6px 0 0; font-size:14px; }
.capa dt { color:#64748B; }
.capa dd { margin:0; font-weight:600; }
h2 { border-bottom:1px solid #D7DBE6; padding-bottom:4px; }
h3 { color:#0B1F66; margin-top:22px; }
h4 { color:#1F2A44; margin:20px 0 6px; font-size:14px; }
h5 { color:#1F2A44; margin:16px 0 6px; font-size:13.5px; }
figure { margin:14px 0 18px; text-align:center; }
figure svg { display:block; margin:0 auto; max-width:100%; height:auto; }
figcaption { font-size:12.5px; color:#475569; margin-top:6px; text-align:left; }
table { font-size:13px; }
table.larga { font-size:11.5px; }
.rolagem { overflow-x:auto; max-width:100%; }
@media print { .rolagem { overflow:visible; } }
table.larga th, table.larga td { padding:4px 5px; }
.redes-grupos figure { max-width:720px; margin:12px auto; border:1px solid #E6E9F2;
                       border-radius:8px; padding:6px; }
.nota { color:#475569; font-size:13px; font-style:italic; }
@media print {
  @page { size: A4; margin: 16mm 14mm; }
  html, body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { max-width:none; margin:0; padding:0; font-size:11pt; }
  .sumario { position:static; background:none; }
  h2 { break-before: page; page-break-before: always; }
  h2, h3, h4, caption, h4 + p, h3 + p { break-after: avoid; page-break-after: avoid; }
  figure, .aviso, .capa { break-inside: avoid; page-break-inside: avoid; }
  tr { break-inside: avoid; page-break-inside: avoid; }
  thead { display: table-header-group; }
  table { break-inside: auto; }
  a { color: inherit; text-decoration: none; }
  .sumario a { color:#1D3E8F; }
}
"""


def _n(valor) -> str:
    return report._numero(valor).replace(".", ",")


def _inteiro(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def _data_extenso(data: datetime.date) -> str:
    return f"{data.day} de {_MESES[data.month - 1]} de {data.year}"


def _prefixa_ids(svg: str, prefixo: str) -> str:
    """Prefixa os ids do SVG (e suas referências) para evitar colisões no documento.

    Cobre ``id``, ``url(#id)``, ``href="#id"`` e as listas de ids separados por espaço
    de ``aria-labelledby`` e ``aria-describedby``.
    """
    ids = set(re.findall(r'\sid="([^"]+)"', svg))
    if not ids:
        return svg
    for ident in sorted(ids, key=len, reverse=True):
        novo = f"{prefixo}-{ident}"
        svg = svg.replace(f'id="{ident}"', f'id="{novo}"')
        svg = svg.replace(f'url(#{ident})', f'url(#{novo})')
        svg = svg.replace(f'href="#{ident}"', f'href="#{novo}"')

    def lista(m: re.Match) -> str:
        nomes = " ".join(f"{prefixo}-{i}" if i in ids else i for i in m.group(2).split())
        return f'{m.group(1)}="{nomes}"'

    return re.sub(r'(aria-labelledby|aria-describedby)="([^"]*)"', lista, svg)


class _Documento:
    """Numeração contínua e sumário do documento em construção."""

    def __init__(self) -> None:
        self.figuras = 0
        self.tabelas = 0
        self.sumario: list[tuple[int, str, str]] = []  # (nível, âncora, texto)
        self._ancoras: set[str] = set()

    def ancora(self, base: str) -> str:
        nome, i = base, 2
        while nome in self._ancoras:
            nome, i = f"{base}-{i}", i + 1
        self._ancoras.add(nome)
        return nome

    def cabecalho(self, nivel: int, numero: str, texto: str, base: str,
                  no_sumario: bool = True) -> str:
        ident = self.ancora(base)
        titulo = f"{numero} {texto}" if numero else texto
        if no_sumario:
            self.sumario.append((nivel, ident, titulo))
        return f'<h{nivel} id="{ident}">{_esc(titulo)}</h{nivel}>'

    def tabela(self, cabecalho, linhas, legenda, numericas=(), classe="") -> str:
        self.tabelas += 1
        ident = self.ancora(f"tab-{self.tabelas}")
        html = _tabela(cabecalho, linhas, f"Tabela {self.tabelas} — {legenda}",
                       numericas=numericas)
        marca = f' id="{ident}"' + (f' class="{classe}"' if classe else "")
        html = html.replace("<table>", f"<table{marca}>", 1)
        # Tabelas largas rolam dentro do próprio quadro (celular) e quebram no papel.
        return f'<div class="rolagem">{html}</div>' if classe == "larga" else html

    def figura(self, svg: str, legenda: str) -> str:
        self.figuras += 1
        ident = self.ancora(f"fig-{self.figuras}")
        svg = _prefixa_ids(svg, ident)
        return (f'<figure id="{ident}">{svg}'
                f"<figcaption>Figura {self.figuras} — {_esc(legenda)}</figcaption></figure>")


class _EstiloUnico:
    """Estilo da visão geral descritiva dentro do documento único (seção 1)."""

    def __init__(self, doc: _Documento) -> None:
        self.doc = doc
        self.k = 0
        self.j = 0

    def titulo(self, nivel: int, texto: str) -> str:
        if nivel == 0:
            return ""
        if nivel == 1:
            self.k += 1
            self.j = 0
            return self.doc.cabecalho(3, f"1.{self.k}", texto, f"vg-{self.k}")
        self.j += 1
        return self.doc.cabecalho(4, f"1.{self.k}.{self.j}", texto,
                                  f"vg-{self.k}-{self.j}", no_sumario=False)

    def tabela(self, cabecalho, linhas, legenda=None, numericas=()) -> str:
        return self.doc.tabela(cabecalho, linhas, legenda or "Dados", numericas)

    def figura(self, svg: str, legenda: str, arquivo: str | None = None) -> str:
        return self.doc.figura(svg, legenda)


def _logo() -> str:
    svg = (report._ASSETS / "logo.svg").read_text(encoding="utf-8")
    svg = svg[svg.index("<svg"):]
    return svg.replace("<svg ", '<svg class="logo-capa" ', 1)


def _contagem_documentos(kb) -> int:
    try:
        return int(kb.conexao.execute("SELECT COUNT(*) FROM Document").fetchone()[0])
    except Exception:
        return 0


class _Cache:
    """Guarda os SVG já desenhados, para refazer o documento com menos redes."""

    def __init__(self, pular: frozenset = frozenset()) -> None:
        self.dados: dict[tuple, str | None] = {}
        # Partes (nomes no fim da chave) que este uso não precisa calcular: um
        # trabalhador da geração paralela pode cuidar só das figuras por período.
        self.pular = pular

    def obtem(self, chave, construtor, compartilhado: bool = True) -> str | None:
        """Valor do cache do documento; `compartilhado` o liga ao cache de figuras.

        A chave começa pelo conteúdo da análise (`chave_da_secao`), então o mesmo
        desenho pedido em outro relatório, ou por um processo trabalhador, vale aqui.
        """
        if self.pular and any(parte in self.pular for parte in chave):
            return None
        if chave not in self.dados:
            try:
                self.dados[chave] = (cache_figuras.obtem(("unico",) + tuple(chave), construtor)
                                     if compartilhado else construtor())
            except Exception:
                self.dados[chave] = None
        return self.dados[chave]


def _linha_do_tempo_partes(kb, config):
    """(HTML com marcadores de figura, figuras) da linha do tempo, ou None se não se aplica.

    O desenho vai para o cache sem número; a numeração das figuras é feita em cada
    montagem do documento.
    """
    figuras: list[tuple[str, str]] = []

    def figura(svg, legenda):
        figuras.append((svg, legenda))
        return f"\x00FIG{len(figuras) - 1}\x00"

    partes = report.linha_do_tempo_html(kb, config, figura, classe_nota="nota")
    return ("\n".join(partes), figuras) if partes else None


def _densidade_partes(kb, config):
    """(HTML com marcadores de figura, figuras) do mapa de densidade, ou None."""
    figuras: list[tuple[str, str]] = []

    def figura(svg, legenda):
        figuras.append((svg, legenda))
        return f"\x00FIG{len(figuras) - 1}\x00"

    partes = report.densidade_html(kb, config, figura, classe_nota="nota")
    return ("\n".join(partes), figuras) if partes else None


def _duplo_partes(kb):
    """(HTML com marcadores, figuras, tabelas) do duplo mapa de áreas das revistas, ou None."""
    figuras: list[tuple[str, str]] = []
    tabelas: list[tuple] = []

    def figura(svg, legenda):
        figuras.append((svg, legenda))
        return f"\x00FIG{len(figuras) - 1}\x00"

    def tabela(cabecalho, linhas, legenda, numericas=()):
        tabelas.append((cabecalho, linhas, legenda, numericas))
        return f"\x00TAB{len(tabelas) - 1}\x00"

    partes = report.duplo_mapa_html(kb, figura, tabela, classe_nota="nota")
    return ("\n".join(partes), figuras, tabelas) if partes else None


def _similitude_partes(kb):
    """(HTML com marcadores, figuras, tabelas) da similitude dos resumos, ou None."""
    figuras: list[tuple[str, str]] = []
    tabelas: list[tuple] = []

    def figura(svg, legenda):
        figuras.append((svg, legenda))
        return f"\x00FIG{len(figuras) - 1}\x00"

    def tabela(cabecalho, linhas, legenda, numericas=()):
        tabelas.append((cabecalho, linhas, legenda, numericas))
        return f"\x00TAB{len(tabelas) - 1}\x00"

    partes = report.similitude_html(kb, figura, tabela, classe_nota="nota")
    return ("\n".join(partes), figuras, tabelas) if partes else None


def _bloco_analise(doc: _Documento, cache: _Cache, kb, periodos, secao: dict,
                   numero: int, medida_temporal: str, limite) -> tuple[str, int]:
    """HTML de uma análise. Devolve também quantas redes de agrupamento foram omitidas."""
    omitidas = 0
    rotulo = secao["rotulo"]
    resultados = secao["resultados"]
    config = secao["config"]
    chave = cache_figuras.chave_da_secao(kb, config, resultados, medida_temporal)
    partes = [doc.cabecalho(2, str(numero), rotulo, f"s{numero}"),
              f'<p>{_esc(secao.get("descricao", ""))}</p>']

    # X.1 Parâmetros e método
    partes.append(doc.cabecalho(3, f"{numero}.1", "Parâmetros e método",
                                f"s{numero}-parametros"))
    contador = [0]

    def titulo(texto: str) -> str:
        contador[0] += 1
        return doc.cabecalho(4, f"{numero}.1.{contador[0]}", texto,
                             f"s{numero}-metodo-{contador[0]}", no_sumario=False)

    partes.append(metodo.metodo_html(
        config, periodos, resultados, None, secao.get("medida_temporal", medida_temporal),
        kb, doc.tabela, rotulo=rotulo.lower(), titulo=titulo,
        com_duplo=None if numero == 2 else False,
        com_similitude=None if numero == 2 else False))

    # X.2 Por período
    partes.append(doc.cabecalho(3, f"{numero}.2", "Por período", f"s{numero}-periodos"))
    linhas = []
    for r in resultados:
        maior = max(r.grupos, key=lambda g: (len(g.nos), g.rotulo or ""), default=None)
        if maior is not None:
            principal, sub, _ind = metodo.nome_do_grupo(kb, r, maior)
            celula_maior = f"{_esc(principal)} ({len(maior.nos)} itens)"
            if sub:
                celula_maior += f'<br><span class="rot-atual">{_esc(sub)}</span>'
        else:
            celula_maior = "—"
        linhas.append([
            _esc(r.periodo),
            _inteiro(r.dataset_original.quantidade_itens()),
            str(len(r.grupos)),
            celula_maior,
        ])
    partes.append(doc.tabela(["Período", "Itens", "Grupos", "Maior grupo"], linhas,
                             f"Resumo por período — {rotulo}.", numericas=(1, 2)))

    if config.unidade == "Institutions" and resultados and resultados[0].ies:
        partes.append(metodo.ies_html(resultados[0], doc.tabela, rotulo.lower()))
    elif config.unidade in ("Authors", "Countries") and resultados:
        partes.append(metodo.filtro_agrupamento_html(resultados[0], rotulo.lower()))

    # X.3 Períodos
    partes.append(doc.cabecalho(3, f"{numero}.3", "Resultados de cada período",
                                f"s{numero}-resultados"))
    mapeador = (resultados[0].configuracao.mapeadores[0]
                if resultados and resultados[0].configuracao.mapeadores else "nucleo")
    for indice, r in enumerate(resultados):
        partes.append(doc.cabecalho(4, f"{numero}.3.{indice + 1}", r.periodo,
                                    f"s{numero}-p{indice}"))
        grupos = sorted(r.grupos, key=lambda g: (-len(g.nos), g.rotulo or ""))
        if not grupos:
            partes.append(
                '<p class="nota">Nenhum agrupamento se formou neste período com os '
                "parâmetros usados; por isso não há diagrama estratégico, rede nem "
                "tabela de agrupamentos para ele.</p>")
            continue
        partes.append(
            f"<p>{_inteiro(r.dataset_original.quantidade_documentos())} documentos, "
            f"{_inteiro(r.dataset_original.quantidade_itens())} itens e "
            f"{len(grupos)} {'agrupamento' if len(grupos) == 1 else 'agrupamentos'}.</p>")

        medida = ORDEM_MEDIDAS[0]
        rotulos_novos = metodo.rotulos_do_resultado(kb, r)
        svg = cache.obtem((chave, indice, "diagrama"), lambda: diagrama_svg(
            r, f"Diagrama estratégico — {r.periodo}", metrica=f"{mapeador}:{medida}",
            rotulo_metrica=ROTULOS_MEDIDA[medida], rotulos=rotulos_novos))
        if svg:
            partes.append(doc.figura(
                svg, f"Diagrama estratégico — {rotulo.lower()}, {r.periodo}. O tamanho "
                     f"das esferas segue o número de documentos; o quadrante usa a "
                     f"centralidade e a densidade de Callon."))
        else:
            partes.append('<p class="nota">O diagrama estratégico não pôde ser desenhado '
                          "para este período.</p>")
        svg = cache.obtem((chave, indice, "halo"),
                          lambda: report.halo_cacheado(kb, r, rotulos_novos))
        if svg:
            legenda_halo = f"Rede do período — {rotulo.lower()}, {r.periodo}."
            if "ponto de virada" in svg:
                legenda_halo += (" Os anéis numerados são os pontos de virada da tabela "
                                 "seguinte.")
            partes.append(doc.figura(svg, legenda_halo))
        # Pontos de virada: depois da rede em halos
        tabela_pivos = metodo.pivos_html(
            kb, r, lambda cab, lin, leg, num=(): doc.tabela(cab, lin, leg, num),
            f"Pontos de virada de {rotulo.lower()}, {r.periodo}.")
        if tabela_pivos:
            partes.append(doc.cabecalho(5, f"{numero}.3.{indice + 1}.1", "Pontos de virada",
                                        f"s{numero}-p{indice}-pivos", no_sumario=False))
            partes.append(tabela_pivos)

        prefixo = f"{mapeador}:"
        cabecalho, linhas, numericas = metodo.tabela_agrupamentos(
            kb, r, grupos, [(prefixo + nome, ROTULOS_MEDIDA[nome]) for nome in ORDEM_MEDIDAS],
            _n)
        partes.append(doc.tabela(
            cabecalho, linhas, f"Agrupamentos de {rotulo.lower()}, {r.periodo}.",
            numericas=numericas, classe="larga"))
        partes.append(
            '<p class="nota">Silhueta: coesão média dos itens do agrupamento (de −1 a 1; “—” '
            "quando há poucos itens). Ano médio: dos documentos do núcleo. Rótulo em "
            "destaque: termos distintivos do período; abaixo, o nome do item central.</p>")

        mostrados = grupos if limite is None else grupos[:limite]
        if len(mostrados) < len(grupos):
            omitidas += len(grupos) - len(mostrados)
            partes.append(
                f'<p class="nota">Para manter o arquivo leve, as redes foram incluídas '
                f"apenas para os {len(mostrados)} maiores agrupamentos (de {len(grupos)}); "
                "as métricas de todos estão na tabela acima.</p>")
        figuras = []
        for posicao, g in enumerate(mostrados, start=1):
            principal, sub, _ind = metodo.nome_do_grupo(kb, r, g)
            svg = cache.obtem((chave, indice, "rede", posicao), lambda: rede_agrupamento_svg(
                r, g, f"{r.periodo} — {g.exibicao}", largura=720, rotulos=rotulos_novos))
            if svg:
                nome = f"“{principal}”" + (f" (atual: “{sub}”)" if sub else "")
                figuras.append(doc.figura(
                    svg, f"Rede do agrupamento {posicao}, {nome}, {r.periodo}."))
        if figuras:
            partes.append('<div class="redes-grupos">' + "".join(figuras) + "</div>")

    # X.4 Evolução e sobreposição; as subseções seguintes seguem um contador único,
    # para que a numeração não pule quando não há evolução.
    subsecao = 4
    if len(resultados) >= 2 and config.matriz == "CoOccurrence":
        partes.append(doc.cabecalho(3, f"{numero}.{subsecao}", "Evolução e sobreposição temática",
                                    f"s{numero}-evolucao"))
        subsecao += 1
        mapa = cache.obtem((chave, "mapa"), lambda: longitudinal.constroi(
            kb, config, periodos, medida_temporal, resultados=resultados), False)
        if mapa is not None:
            ev = cache.obtem((chave, "evolucao"), lambda: longitudinal.evolucao_svg(
                mapa, "Mapa de evolução dos temas", largura=980), False)
            so = cache.obtem((chave, "sobreposicao"), lambda: longitudinal.sobreposicao_svg(
                mapa, "Mapa de sobreposição", largura=680), False)
            if ev:
                partes.append(doc.figura(ev, f"Mapa de evolução dos temas — {rotulo.lower()}."))
            if so:
                partes.append(doc.figura(so, f"Mapa de sobreposição entre períodos — {rotulo.lower()}."))
        else:
            partes.append('<p class="nota">Os mapas de evolução e sobreposição não '
                          "puderam ser construídos.</p>")
    # X.n Linha do tempo (só palavras, autores e referências em co-ocorrência)
    bloco_lt = cache.obtem((chave, "linha-do-tempo"),
                           lambda: _linha_do_tempo_partes(kb, config))
    if bloco_lt:
        partes.append(doc.cabecalho(3, f"{numero}.{subsecao}", "Linha do tempo (corpus completo)",
                                    f"s{numero}-linha-do-tempo"))
        texto_lt, figuras_lt = bloco_lt
        for i, (svg, legenda) in enumerate(figuras_lt):
            texto_lt = texto_lt.replace(f"\x00FIG{i}\x00", doc.figura(svg, legenda))
        partes.append(texto_lt)
        subsecao += 1
    # X.n Mapa de densidade (co-ocorrência)
    bloco_dens = cache.obtem((chave, "densidade"), lambda: _densidade_partes(kb, config))
    if bloco_dens:
        partes.append(doc.cabecalho(3, f"{numero}.{subsecao}", "Mapa de densidade (corpus completo)",
                                    f"s{numero}-densidade"))
        texto_d, figuras_d = bloco_dens
        for i, (svg, legenda) in enumerate(figuras_d):
            texto_d = texto_d.replace(f"\x00FIG{i}\x00", doc.figura(svg, legenda))
        partes.append(texto_d)
        subsecao += 1
    # X.n Duplo mapa (corpus completo; igual em todas as análises, então só na primeira)
    bloco_duplo = None
    if numero == 2:
        bloco_duplo = cache.obtem(
            (chave, "duplo-mapa", _areas_revistas.assinatura(), _duplo_mapa.MAX_ESQ,
             _duplo_mapa.MAX_DIR), lambda: _duplo_partes(kb))
    if bloco_duplo:
        partes.append(doc.cabecalho(3, f"{numero}.{subsecao}", report.TITULO_SECAO_DUPLO,
                                    f"s{numero}-duplo-mapa"))
        texto_m, figuras_m, tabelas_m = bloco_duplo
        for i, (svg, legenda) in enumerate(figuras_m):
            texto_m = texto_m.replace(f"\x00FIG{i}\x00", doc.figura(svg, legenda))
        for i, (cabecalho, linhas, legenda, numericas) in enumerate(tabelas_m):
            texto_m = texto_m.replace(f"\x00TAB{i}\x00",
                                      doc.tabela(cabecalho, linhas, legenda, numericas))
        partes.append(texto_m)
        subsecao += 1
    # X.n Similitude dos resumos (corpus completo; igual em todas as análises, só na primeira)
    bloco_sim = None
    if numero == 2:
        bloco_sim = cache.obtem((chave, "similitude", _similitude.N_FORMAS, _similitude.EXTRAS_PADRAO),
                                lambda: _similitude_partes(kb))
    if bloco_sim:
        partes.append(doc.cabecalho(3, f"{numero}.{subsecao}", report.TITULO_SECAO_SIMILITUDE,
                                    f"s{numero}-similitude"))
        texto_s, figuras_s, tabelas_s = bloco_sim
        for i, (svg, legenda) in enumerate(figuras_s):
            texto_s = texto_s.replace(f"\x00FIG{i}\x00", doc.figura(svg, legenda))
        for i, (cabecalho, linhas, legenda, numericas) in enumerate(tabelas_s):
            texto_s = texto_s.replace(f"\x00TAB{i}\x00",
                                      doc.tabela(cabecalho, linhas, legenda, numericas))
        partes.append(texto_s)
        subsecao += 1
    # X.n Dendrograma
    partes.append(doc.cabecalho(3, f"{numero}.{subsecao}", "Dendrograma (agrupamento hierárquico)",
                                f"s{numero}-dendrograma"))
    partes.append(
        "<p>Complementa os agrupamentos da rede: junta, passo a passo, os itens mais "
        "parecidos (distância = 1 − similaridade; ligação média). Cortar a árvore mais "
        "alto dá poucos temas amplos; mais baixo, muitos temas finos. A linha tracejada "
        "marca o corte sugerido (maior salto entre fusões); a concordância com os "
        "agrupamentos da rede é medida por ARI e NMI (1 = idêntico).</p>")
    for r in resultados:
        partes.append(dendro_helper.bloco(
            r, f"Dendrograma — {rotulo.lower()}, {r.periodo}", doc.figura))
    return "\n".join(partes), omitidas


def _monta(caminho_kb_nome: str, kb, periodos, secoes, ignoradas, medida_temporal,
           cache: _Cache, limite) -> tuple[str, int]:
    doc = _Documento()
    omitidas = 0
    blocos = []

    # 1 Visão geral
    blocos.append(doc.cabecalho(2, "1", "Visão geral descritiva", "s1"))
    visao = report.corpo_bibliometria(kb, _EstiloUnico(doc))
    blocos.append(visao if visao else '<p class="nota">O corpus não tem documentos.</p>')

    for numero, secao in enumerate(secoes, start=2):
        texto, n = _bloco_analise(doc, cache, kb, periodos, secao, numero,
                                  medida_temporal, limite)
        blocos.append(texto)
        omitidas += n

    if ignoradas:
        numero = len(secoes) + 2
        blocos.append(doc.cabecalho(2, str(numero), "Análises não geradas", "nao-geradas"))
        blocos.append("<p>Estas análises não entraram no relatório, pelos motivos abaixo.</p><ul>"
                      + "".join(f'<li><b>{_esc(i["rotulo"])}</b>: {_esc(i["motivo"])}</li>'
                                for i in ignoradas) + "</ul>")

    # Sumário: lista plana, recuada por nível (seção > subseção > período)
    sumario = ['<nav class="sumario" aria-label="Sumário"><h2 id="sumario">Sumário</h2><ol>']
    for nivel, ident, texto in doc.sumario:
        sumario.append(f'<li class="n{nivel}"><a href="#{ident}">{_esc(texto)}</a></li>')
    sumario.append("</ol>")
    sumario.append(f"<p><small>{doc.figuras} figuras e {doc.tabelas} tabelas.</small></p></nav>")

    hoje = datetime.date.today()
    nomes = [p.nome for p in periodos]
    capa = [
        '<header class="capa">', _logo(),
        "<h1>Relatório completo — Redes</h1>",
    ]
    if caminho_kb_nome:
        capa.append(f'<p class="projeto">{_esc(caminho_kb_nome)}</p>')
    capa.append("<dl>")
    capa.append(f"<dt>Data</dt><dd>{_data_extenso(hoje)}</dd>")
    capa.append(f"<dt>Documentos</dt><dd>{_inteiro(_contagem_documentos(kb))}</dd>")
    capa.append(f"<dt>Períodos</dt><dd>{len(nomes)}: {_esc(', '.join(nomes))}</dd>")
    capa.append(f"<dt>Análises</dt><dd>{len(secoes)}</dd>")
    capa.append("</dl></header>")

    corpo = "\n".join(capa) + "\n" + "".join(sumario) + "\n" + "\n".join(blocos)
    pagina = (
        '<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Relatório completo — Redes</title>\n"
        f"<style>{report._CSS}{_CSS_EXTRA}</style>\n</head>\n<body>\n"
        f"{corpo}\n"
        '<footer class="fonte">Gerado por Redes.</footer>\n</body>\n</html>\n')
    return pagina, omitidas


def gera_arquivo_unico(caminho_saida: Path, kb, periodos, secoes: list[dict],
                       ignoradas: list[dict],
                       medida_temporal: str = "EquivalenceIndex") -> Path:
    """Grava o relatório completo num único .html autocontido e devolve o caminho.

    Cada item de `secoes` traz ``rotulo``, ``descricao``, ``pasta``, ``config`` e
    ``resultados`` (um por período). Se o arquivo passar de ~15 MB, as redes de
    agrupamento ficam só nos maiores grupos de cada período (com aviso no texto).
    """
    caminho_saida = Path(caminho_saida)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    nome_projeto = Path(getattr(kb, "caminho", "") or "").name
    cache = _Cache()
    pagina = ""
    for limite in _LIMITES_REDES:
        pagina, omitidas = _monta(nome_projeto, kb, periodos, secoes, ignoradas,
                                  medida_temporal, cache, limite)
        if len(pagina.encode("utf-8")) <= LIMITE_BYTES or limite == _LIMITES_REDES[-1]:
            break
    caminho_saida.write_text(pagina, encoding="utf-8")
    return caminho_saida


def aquece_secao(kb, periodos, secao: dict, medida_temporal: str = "EquivalenceIndex",
                 parte: str = "tudo") -> None:
    """Desenha e calcula, no cache compartilhado, o que o bloco de uma análise pede.

    Serve aos processos trabalhadores da geração paralela: o documento é montado
    de verdade (numeração descartável), de modo que o processo principal, ao montar
    o arquivo final, só encontra figuras e cálculos prontos. O texto é descartado.

    `parte`: "periodos" (tudo, menos as figuras do corpus completo), "corpo" (só a
    linha do tempo e o mapa de densidade do corpus completo) ou "tudo".
    """
    config = secao["config"]
    if parte in ("tudo", "periodos"):
        pular = frozenset(PARTES_DO_CORPO) if parte == "periodos" else frozenset()
        _bloco_analise(_Documento(), _Cache(pular), kb, periodos, secao, 2, medida_temporal, None)
    if parte == "corpo":
        chave = cache_figuras.chave_da_secao(kb, config, secao["resultados"], medida_temporal)
        cache = _Cache()
        cache.obtem((chave, "linha-do-tempo"), lambda: _linha_do_tempo_partes(kb, config))
        cache.obtem((chave, "densidade"), lambda: _densidade_partes(kb, config))

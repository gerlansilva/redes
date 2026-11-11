"""Parâmetros, método e indicadores de cada análise do relatório.

Todo relatório (único ou em pastas) traz, para cada análise, o bloco
"Parâmetros e método": os parâmetros efetivamente adotados, uma descrição em
linguagem simples do que o código faz e uma tabela de indicadores no estilo do
SciMAT (grafias distintas, itens após a redução, agrupamentos, maior
agrupamento, rede), calculada dos resultados reais.

As funções são puras: recebem a configuração e os resultados e devolvem HTML
(ou dados). As tabelas passam por um `tabela(cabecalho, linhas, legenda,
numericas)`, para que cada relatório aplique a sua numeração. Nada aqui lê
parâmetros de memória: limites e constantes vêm dos módulos que fazem o
cálculo (`rajadas`, `termos`, `bibliometria`, `similarity`, `clustering`).
"""

from __future__ import annotations

import html

from . import bibliometria, linha_do_tempo, pivos, qualidade, rajadas, rotulos, termos
from .viz import densidade as viz_densidade
from .clustering import ALGORITMOS
from .similarity import MEDIDAS
from .texto import rotulo_legivel

_ROTULOS_UNIDADE = {
    "Words": "Palavras-chave",
    "Authors": "Autores",
    "References": "Referências",
    "AuthorsReference": "Autores de referência",
    "ReferenceSources": "Fontes de referência",
    "Countries": "Países",
    "Institutions": "Instituições (IES)",
}

_ITEM_UNIDADE = {
    "Words": "palavras",
    "Authors": "autores",
    "References": "referências",
    "AuthorsReference": "autores de referência",
    "ReferenceSources": "fontes de referência",
    "Countries": "países",
    "Institutions": "instituições",
}

_ROTULOS_MATRIZ = {
    "CoOccurrence": "Co-ocorrência",
    "BasicCoupling": "Acoplamento básico",
    "AggregatedCouplingBasedOnAuthor": "Acoplamento agregado por autor",
    "AggregatedCouplingBasedOnJournal": "Acoplamento agregado por periódico",
}

_ROTULOS_ALGORITMO = {
    "CentersSimples": "Centros simples",
    "AverageLink": "Ligação média",
    "CompleteLink": "Ligação completa",
    "SingleLink": "Ligação simples",
    "SumLink": "Ligação por soma",
    "Louvain": "Louvain",
}

_ROTULOS_SIMILARIDADE = {
    "AssociationStrength": "Força de associação",
    "EquivalenceIndex": "Índice de equivalência",
    "InclusionIndex": "Índice de inclusão",
    "JaccardIndex": "Índice de Jaccard",
    "SaltonCosine": "Cosseno de Salton",
}

_FORMULAS = {
    "EquivalenceIndex": "c<sub>ij</sub>² ÷ (f<sub>i</sub> · f<sub>j</sub>)",
    "AssociationStrength": "c<sub>ij</sub> ÷ (f<sub>i</sub> · f<sub>j</sub>)",
    "InclusionIndex": "c<sub>ij</sub> ÷ mín(f<sub>i</sub>, f<sub>j</sub>)",
    "JaccardIndex": "c<sub>ij</sub> ÷ (f<sub>i</sub> + f<sub>j</sub> − c<sub>ij</sub>)",
    "SaltonCosine": "c<sub>ij</sub>² ÷ √(f<sub>i</sub> · f<sub>j</sub>)",
}

_EXPLICACAO_SIMILARIDADE = {
    "EquivalenceIndex": "vale 1 quando os dois itens sempre aparecem juntos e cai "
                        "rápido quando um deles aparece muito sem o outro",
    "AssociationStrength": "compara a ligação observada com a esperada se os itens "
                           "fossem independentes; favorece pares de itens raros",
    "InclusionIndex": "vale 1 quando o item menos frequente só aparece junto do "
                      "outro; favorece itens raros contidos em itens comuns",
    "JaccardIndex": "documentos com os dois itens divididos pelos documentos com "
                    "pelo menos um deles",
    "SaltonCosine": "como no SciMAT, o numerador é elevado ao quadrado; por isso o "
                    "valor não fica limitado a 1, ao contrário do cosseno clássico",
}

_ROTULOS_MAPEADOR = {
    "nucleo": "núcleo",
    "interseccao": "interseção",
    "secundarios": "secundários",
    "kcore": "k-core",
    "uniao": "união",
    "acoplamento": "acoplamento",
}

_ROTULOS_INDICE = {
    "h": "h", "g": "g", "hg": "hg", "q2": "q2", "media": "média de citações",
    "soma": "soma de citações", "minimo": "mínimo de citações",
    "maximo": "máximo de citações",
}

_ORIGEM_PALAVRAS = {
    "autor": "palavras-chave dos autores",
    "fonte": "palavras-chave atribuídas pela fonte",
    "adicionada": "palavras adicionadas na edição",
}

_ROTULOS_TEMPORAL = {
    "AssociationStrength": "força de associação",
    "EquivalenceIndex": "índice de equivalência",
    "InclusionIndex": "índice de inclusão",
    "JaccardIndex": "índice de Jaccard",
    "SaltonCosine": "cosseno de Salton",
}

CSS = """
.metodo p { margin:6px 0; }
.metodo ul, .metodo ol { margin:4px 0 8px; padding-left:22px; }
.metodo li { margin:2px 0; }
.metodo code.formula { background:#F5F6F9; border:1px solid #E3E6EC; border-radius:4px;
                       padding:1px 6px; font-family:inherit; white-space:nowrap; }
.rolagem { overflow-x:auto; max-width:100%; }
@media print { .rolagem { overflow:visible; } }
.metodo .nota-metodo { color:#475569; font-size:12.5px; }
@media print { .metodo { break-inside:auto; } .metodo p, .metodo li { orphans:3; widows:3; } }
.selo-q { display:inline-block; padding:1px 9px; border-radius:999px; border:1px solid;
          font-size:12px; font-weight:600; white-space:nowrap; line-height:1.5; }
.selo-q-ok { color:#067647; background:#E6F8EE; border-color:#9ED8BA; }
.selo-q-atencao { color:#7A4E00; background:#FFF3C4; border-color:#E8CB6A; }
.selo-q-ruim { color:#B42318; background:#FEF3F2; border-color:#F4A9A1; }
.selo-q-indefinido { color:#475569; background:#F1F3F8; border-color:#C5CCDB; }
.avisos-qualidade { margin:4px 0 14px; font-size:12.5px; color:#334155; }
.avisos-qualidade ul { margin:2px 0 6px; padding-left:20px; }
.avisos-qualidade li { margin:1px 0; }
.cel-agrupamento { min-width:170px; }
.rot-novo { color:#0B1F66; }
.rot-ind { color:#7A4E00; font-size:11px; font-weight:600; white-space:nowrap; }
.rot-atual { color:#64748B; font-size:11px; }
@media print { .selo-q { -webkit-print-color-adjust:exact; print-color-adjust:exact; } }
"""


def _esc(texto) -> str:
    return html.escape(str(texto if texto is not None else ""))


def _inteiro(valor) -> str:
    return f"{int(valor):,}".replace(",", ".")


def _decimal(valor: float) -> str:
    if abs(valor - round(valor)) < 1e-9:
        return str(int(round(valor)))
    return f"{valor:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _plural(n: int, singular: str, plural: str) -> str:
    return singular if n == 1 else plural


# Limiares do selo de qualidade. Os valores moram em `qualidade.avalia` (literais
# no código); aqui só se repetem para o texto, e tests/test_qualidade_integracao.py
# confere que continuam iguais aos do código.
LIMIARES_QUALIDADE = {
    "q_ruim": 0.15, "q_atencao": 0.30, "razao": 0.6,
    "silhueta_ruim": 0.0, "silhueta_atencao": 0.10,
    "pct_negativos": 30, "pct_agrupados": 60,
}

NIVEIS_ROTULO = {"ok": "OK", "atencao": "Atenção", "ruim": "Ruim",
                 "indefinido": "Indefinido"}
_NIVEIS_ICONE = {"ok": "✓", "atencao": "!", "ruim": "✕", "indefinido": "?"}


def _n2(valor, casas: int = 2) -> str:
    """Número com vírgula; '—' quando não há valor (nunca mostra 0 no lugar)."""
    return "—" if valor is None else f"{valor:.{casas}f}".replace(".", ",")


def selo_qualidade(nivel: str | None) -> str:
    """Selo textual do nível de qualidade (texto E cor; o texto basta sozinho)."""
    nivel = nivel if nivel in NIVEIS_ROTULO else "indefinido"
    return (f'<span class="selo-q selo-q-{nivel}">'
            f'<span aria-hidden="true">{_NIVEIS_ICONE[nivel]}</span> '
            f'{NIVEIS_ROTULO[nivel]}</span>')


def _guarda(resultado, chave: str, calcula):
    """Guarda no próprio resultado o que já foi calculado (os relatórios pedem várias vezes)."""
    cache = resultado.__dict__.setdefault("_cache_qualidade", {})
    if chave not in cache:
        try:
            cache[chave] = calcula()
        except Exception:        # qualidade e rótulos nunca derrubam um relatório
            cache[chave] = None
    return cache[chave]


def qualidade_do_resultado(resultado) -> dict | None:
    """`qualidade.avalia` do período (calculada uma vez), ou None se falhar."""
    return _guarda(resultado, "qualidade", lambda: qualidade.avalia(resultado))


def rotulos_do_resultado(kb, resultado) -> dict:
    """`rotulos.rotula_grupos` do período (calculado uma vez); {} se falhar ou sem `kb`."""
    if kb is None:
        return resultado.__dict__.get("_cache_qualidade", {}).get("rotulos") or {}
    return _guarda(resultado, "rotulos", lambda: rotulos.rotula_grupos(kb, resultado)) or {}


TOPO_PIVOS = 10      # pontos de virada listados por período


def pivos_do_resultado(kb, resultado) -> dict | None:
    """`pivos.pontos_de_virada` do período (calculado uma vez); None se falhar."""
    return _guarda(resultado, "pivos",
                   lambda: pivos.pontos_de_virada(resultado, kb, topo=TOPO_PIVOS))


def pivos_para_halo(kb, resultado) -> list | None:
    """Pivôs para o parâmetro `pivos=` do halo; None quando não há (a figura não muda)."""
    dados = pivos_do_resultado(kb, resultado)
    return list(dados["pivos"]) if dados and dados.get("pivos") else None


def _n4(valor) -> str:
    return "—" if valor is None else f"{valor:.4f}".replace(".", ",")


def _lista_nomes(itens: list[str], limite: int = 8) -> str:
    texto = ", ".join(itens[:limite])
    return texto + (f" e mais {len(itens) - limite}" if len(itens) > limite else "")


def pivos_html(kb, resultado, tabela, legenda: str, classe_nota: str = "nota") -> str:
    """Tabela "Pontos de virada" de um período, com as notas de leitura.

    `tabela(cabecalho, linhas, legenda, numericas)` aplica a numeração do relatório.
    A coluna sigma só aparece quando algum pivô tem rajada. Devolve "" se o cálculo
    falhar; nunca levanta.
    """
    dados = pivos_do_resultado(kb, resultado)
    if not dados:
        return ""
    partes: list[str] = []
    itens = dados.get("pivos") or []
    if dados.get("nao_calculado"):
        # Cálculo pulado (rede grande): dizer isso, e não "nenhum ponto de virada".
        return f'<p class="{classe_nota}">{_esc(dados["nao_calculado"])}</p>'
    if itens:
        com_sigma = any(i.get("sigma") is not None for i in itens)
        cabecalho = ["Nº", "Item", "Intermediação", "Agrupamentos vizinhos", "Grupo",
                     "Frequência"] + (["Sigma"] if com_sigma else [])
        grupos = list(getattr(resultado, "grupos", []) or [])
        linhas = []
        for posicao, i in enumerate(itens, start=1):
            indice = i.get("grupo")
            if indice is not None and 0 <= indice < len(grupos):
                principal = nome_do_grupo(kb, resultado, grupos[indice])[0]
            else:
                principal = "—"
            linha = [str(posicao), _esc(i["rotulo"]), _n4(i["intermediacao"]),
                     str(i["grupos_vizinhos"]), _esc(principal),
                     str(i.get("frequencia", 0))]
            if com_sigma:
                linha.append(_n2(i.get("sigma"), 3))
            linhas.append(linha)
        numericas = (0, 2, 3, 5) + ((6,) if com_sigma else ())
        partes.append(tabela(cabecalho, linhas, legenda, numericas))
        partes.append(
            f'<p class="{classe_nota}">Pontos de virada: itens de intermediação alta (decil '
            "superior da rede) cujos vizinhos estão em dois ou mais agrupamentos; ligam "
            "temas que, sem eles, ficariam mais separados. Intermediação normalizada, de 0 a "
            "1." + (" Sigma = (intermediação + 1) elevado à força da rajada do termo; entre "
                    "os pontos de virada, o ranking por sigma acompanha sobretudo a "
                    "intermediação, não a força da rajada. A rajada de palavras-chave é "
                    "calculada só sobre as palavras-chave dos autores." if com_sigma else "")
            + "</p>")
    else:
        motivos = [a for a in dados.get("avisos", [])
                   if not a.startswith("Poucos dados") and "fora do ranking" not in a]
        partes.append(f'<p class="{classe_nota}">Nenhum ponto de virada identificado neste '
                      "período." + (" " + " ".join(motivos) if motivos else "") + "</p>")
    termos_fora = dados.get("termos_descritores") or []
    if termos_fora:
        nomes = [f"{_esc(t['rotulo'])} ({t['proporcao_documentos']:.0%})" for t in termos_fora]
        partes.append(
            f'<p class="{classe_nota}">Termos-descritor excluídos do ranking: '
            f"{_lista_nomes(nomes)}. Aparecem em mais de {pivos.PROPORCAO_DESCRITOR:.0%} dos "
            "documentos do período; descrevem o corpus em vez de distinguir temas e ligam "
            "quase tudo, então não são lidos como pontos de virada.</p>")
    if not dados.get("suficiente"):
        partes.append(
            f'<p class="{classe_nota}"><strong>Poucos dados:</strong> a rede tem '
            f"{pivos._nos(dados.get('n_nos', 0))} (o mínimo confiável é {pivos.MINIMO_NOS}); leia os "
            "pontos de virada como indício.</p>")
    return "\n".join(partes)


def linhas_do_periodo(kb, resultado) -> dict[int, dict]:
    """`qualidade.tabela_grupos` do período, por índice em `resultado.grupos`."""
    def calcula():
        rot = rotulos_do_resultado(kb, resultado)
        linhas = qualidade.tabela_grupos(resultado, rot, kb=kb)
        for linha in linhas:
            r = rot.get(linha["indice"]) or {}
            linha["indicativo"] = bool(r.get("indicativo")) if linha["rotulo_novo"] else False
        return {linha["indice"]: linha for linha in linhas}
    return _guarda(resultado, "linhas", calcula) or {}


def nome_do_grupo(kb, resultado, grupo) -> tuple[str, str | None, bool]:
    """(principal, subtítulo, indicativo) de um agrupamento.

    O rótulo novo (quando existe) é o principal e o atual, o subtítulo; sem rótulo
    novo, o principal é o atual e o subtítulo é None.
    """
    atual = grupo.exibicao or "Sem grupo"
    try:
        indice = next(i for i, g in enumerate(resultado.grupos) if g is grupo)
        r = rotulos_do_resultado(kb, resultado).get(indice) or {}
    except Exception:
        r = {}
    novo = rotulo_legivel(" ".join(str(r.get("rotulo") or "").split()))
    if not novo:
        return atual, None, False
    return novo, atual, bool(r.get("indicativo"))


def tabela_agrupamentos(kb, resultado, grupos, medidas, formato, ligar=None):
    """Cabeçalho, linhas (HTML) e colunas numéricas da tabela de agrupamentos de um período.

    `grupos`: os grupos na ordem em que o relatório os numera. `medidas`: lista de
    (chave no grupo, rótulo da coluna). `formato(valor)`: número como texto.
    `ligar(posição, html)`: envolve o nome num link (padrão: sem link).

    A coluna Agrupamento mostra o rótulo novo em destaque (com "(indicativo)" quando
    há poucos documentos) e o atual como subtítulo; sem rótulo novo, só o atual.
    """
    por_indice = linhas_do_periodo(kb, resultado)
    posicao_no_resultado = {id(g): i for i, g in enumerate(resultado.grupos)}
    linhas = []
    for posicao, g in enumerate(grupos, start=1):
        extra = por_indice.get(posicao_no_resultado.get(id(g)), {})
        novo = extra.get("rotulo_novo")
        if novo:
            principal = f'<strong class="rot-novo">{_esc(novo)}</strong>'
            if extra.get("indicativo"):
                principal += ' <span class="rot-ind">(indicativo)</span>'
            nome = ((ligar(posicao, principal) if ligar else principal)
                    + f'<br><span class="rot-atual">{_esc(g.exibicao)}</span>')
        else:
            atual = _esc(g.exibicao)
            nome = ligar(posicao, atual) if ligar else atual
        nome = f'<div class="cel-agrupamento">{nome}</div>'
        sil = extra.get("silhueta")
        ano = extra.get("ano_medio")
        linhas.append([
            str(posicao), nome, str(len(g.nos)),
            _n2(sil), "—" if ano is None else _n2(ano, 1),
            str(extra.get("documentos_nucleo", len(g.documentos_nucleo))),
            _quadrante_rotulo(g),
            formato(g.centralidade), formato(g.densidade),
        ] + [formato(g.medidas.get(chave, 0)) for chave, _ in medidas])
    cabecalho = (["Nº", "Agrupamento", "Itens", "Silhueta", "Ano médio",
                  "Documentos (núcleo)", "Quadrante", "Centralidade", "Densidade"]
                 + [rotulo for _, rotulo in medidas])
    numericas = (0, 2, 3, 4, 5, 7, 8) + tuple(range(9, 9 + len(medidas)))
    return cabecalho, linhas, numericas


def _quadrante_rotulo(grupo) -> str:
    return {"motor": "Motor", "nicho": "Nicho", "basico": "Básico",
            "emergente": "Emergente"}[_quadrante(grupo)]


def _tabela_padrao(cabecalho, linhas, legenda=None, numericas=()):
    from .report import _tabela
    return _tabela(cabecalho, linhas, legenda, numericas=numericas)


def _quadrante(grupo) -> str:
    if grupo.centralidade_faixa >= 0.5 and grupo.densidade_faixa >= 0.5:
        return "motor"
    if grupo.densidade_faixa >= 0.5:
        return "nicho"
    if grupo.centralidade_faixa >= 0.5:
        return "basico"
    return "emergente"


def _frequencia_efetiva(config, frequencia) -> int:
    return int(frequencia) if frequencia is not None else int(config.minimo_frequencia)


def _no_e_peso(config) -> tuple[str, str, str]:
    """Nó, peso da aresta e frequência de normalização, conforme a matriz."""
    if config.matriz == "CoOccurrence":
        return ("os itens", "o número de documentos que contêm os dois itens",
                "o número de documentos que contêm o item")
    if config.matriz == "BasicCoupling":
        return ("os documentos", "o número de itens que os dois documentos têm em comum",
                "o número de itens do documento")
    autor = config.matriz == "AggregatedCouplingBasedOnAuthor"
    quem = "autor" if autor else "periódico"
    return ("os autores" if autor else "os periódicos",
            f"o número de itens em comum entre os documentos de cada {quem}",
            f"o número de documentos do {quem}")


# --------------------------------------------------------------------- períodos


def _periodos_info(periodos, resultados) -> list[dict]:
    info = []
    for posicao, r in enumerate(resultados):
        original = r.dataset_original
        nome = r.periodo
        if periodos and posicao < len(periodos):
            nome = getattr(periodos[posicao], "nome", None) or nome
        info.append({
            "periodo": nome,
            "documentos": original.quantidade_documentos(),
            "com_itens": sum(1 for d in original.documentos.values() if d.itens),
            "itens": original.quantidade_itens(),
        })
    return info


# -------------------------------------------------------------------- parâmetros


def parametros_linhas(config, periodos=None, resultados=(), frequencia=None,
                      medida_temporal: str | None = "EquivalenceIndex") -> list[list[str]]:
    """Linhas (parâmetro, valor) já escapadas, com os parâmetros efetivamente usados."""
    frequencia = _frequencia_efetiva(config, frequencia)
    coocorrencia = config.matriz == "CoOccurrence"
    minimo_aresta = "Co-ocorrência mínima" if coocorrencia else "Acoplamento mínimo"
    nos, _, _ = _no_e_peso(config)

    if config.corte and config.algoritmo not in ("CentersSimples", "Louvain"):
        corte = _decimal(config.corte)
    elif config.algoritmo in ("CentersSimples", "Louvain"):
        corte = (f"{_decimal(config.corte)} (não se aplica a "
                 f"{_ROTULOS_ALGORITMO[config.algoritmo].lower()})")
    else:
        corte = "0 (sem corte)"

    mapeadores = []
    for m in config.mapeadores:
        rotulo = _ROTULOS_MAPEADOR.get(m, m)
        mapeadores.append(f"{rotulo} (k = {config.k_core})" if m == "kcore" else rotulo)

    linhas = [
        ["Unidade de análise", _ROTULOS_UNIDADE.get(config.unidade, config.unidade)],
        ["Matriz", f"{_ROTULOS_MATRIZ.get(config.matriz, config.matriz)} "
                   f"(nós: {nos})"],
        ["Similaridade", f"{_ROTULOS_SIMILARIDADE.get(config.similaridade, config.similaridade)}: "
                         f"<code class=\"formula\">{_FORMULAS.get(config.similaridade, '')}</code>"],
        ["Algoritmo de agrupamento", _ROTULOS_ALGORITMO.get(config.algoritmo, config.algoritmo)],
        ["Frequência mínima", f"{frequencia} (itens em menos de {frequencia} "
                              f"{_plural(frequencia, 'documento', 'documentos')} saem antes da rede)"],
        [minimo_aresta, f"{config.minimo_coocorrencia} (ligações com valor menor saem "
                        "antes da normalização)"],
        ["Tamanho dos agrupamentos",
         f"mínimo {config.tamanho_minimo}, máximo {config.tamanho_maximo} nós"],
        ["Ponto de corte", corte],
        ["Mapeador de documentos", ", ".join(mapeadores) or "nenhum"],
        ["Medidas de desempenho", "documentos, " + ", ".join(
            _ROTULOS_INDICE.get(i, i) for i in config.indices)],
    ]
    if config.unidade == "Words":
        origens = [_ORIGEM_PALAVRAS.get(o, o) for o in config.palavras]
        linhas.append(["Origem das palavras",
                       ", ".join(origens) if origens else "todas (nenhuma origem marcada)"])
    if config.unidade == "Institutions":
        minimo_comp = config.componente_minimo
        linhas.append(["Tamanho mínimo do componente (IES)",
                       f"{minimo_comp} (componentes conexos da rede com menos de {minimo_comp} "
                       "instituições não viram agrupamento e ficam sem agrupamento, fora dos halos)"
                       if minimo_comp > 1 else "1 (todo componente pode virar agrupamento)"])
        linhas.append(["União de variantes de nome",
                       "automática e conservadora; cada união está na tabela \"variantes unidas\""])
    linhas.append(["Termos ignorados",
                   _Seguro(_esc(", ".join(config.ignorar)) if config.ignorar else "nenhum")])
    if resultados:
        info = _periodos_info(periodos, resultados)
        linhas.append(["Períodos", _Seguro(f"{len(info)}: " + "; ".join(
            f"{_esc(i['periodo'])} ({_inteiro(i['documentos'])} "
            f"{_plural(i['documentos'], 'documento', 'documentos')})" for i in info))])
    if medida_temporal and config.matriz == "CoOccurrence" and (periodos is None or len(periodos) >= 2):
        linhas.append(["Medida temporal (evolução e sobreposição)",
                       _ROTULOS_SIMILARIDADE.get(medida_temporal, medida_temporal)])
    return [[_esc_param(a), _esc_param(b)] for a, b in linhas]


class _Seguro(str):
    """Texto já escapado (vindo do usuário); não passa de novo por `_esc_param`."""


def _esc_param(texto: str) -> str:
    """Escapa o texto, preservando só as marcas de fórmula que este módulo escreve."""
    if isinstance(texto, _Seguro):
        return str(texto)
    protegido = {"<code class=\"formula\">": "\x00a", "</code>": "\x00b",
                 "<sub>": "\x00c", "</sub>": "\x00d"}
    for marca, ponto in protegido.items():
        texto = texto.replace(marca, ponto)
    texto = _esc(texto)
    for marca, ponto in protegido.items():
        texto = texto.replace(ponto, marca)
    return texto


def parametros_html(config, periodos=None, resultados=(), frequencia=None,
                    medida_temporal: str | None = "EquivalenceIndex", tabela=None,
                    rotulo: str = "") -> str:
    """Tabela de parâmetros da análise e tabela dos períodos com o número de documentos."""
    tabela = tabela or _tabela_padrao
    sufixo = f" — {rotulo}" if rotulo else ""
    partes = [tabela(["Parâmetro", "Valor"],
                     parametros_linhas(config, periodos, resultados, frequencia,
                                       medida_temporal),
                     f"Parâmetros adotados na análise{sufixo}.")]
    if resultados:
        info = _periodos_info(periodos, resultados)
        linhas = [[_esc(i["periodo"]), _inteiro(i["documentos"]), _inteiro(i["com_itens"]),
                   _inteiro(i["itens"])] for i in info]
        partes.append(tabela(
            ["Período", "Documentos", "Documentos com itens",
             f"Grupos de {_ITEM_UNIDADE.get(config.unidade, 'itens')}"],
            linhas, f"Períodos e documentos analisados{sufixo}.", numericas=(1, 2, 3)))
    return "\n".join(partes)


# -------------------------------------------------------------------- algoritmo


def algoritmo_html(config, medida_temporal: str | None = None,
                   n_periodos: int | None = None) -> str:
    """Como o código chega aos agrupamentos, em linguagem simples, para esta configuração."""
    frequencia = config.minimo_frequencia
    unidade = _ITEM_UNIDADE.get(config.unidade, "itens")
    p = ['<div class="metodo">']

    # 1. Rede
    if config.matriz == "CoOccurrence":
        p.append(
            f"<p><strong>1. Rede.</strong> Cada item (um grupo de {unidade}, unificado "
            "pela edição da base) é um nó. Dois itens ficam ligados quando aparecem no "
            "mesmo documento, e o peso da ligação é o número de documentos do período que "
            "contêm os dois (co-ocorrência, c<sub>ij</sub>). A frequência f<sub>i</sub> de "
            "um item é o número de documentos que o contêm.</p>")
    elif config.matriz == "BasicCoupling":
        p.append(
            f"<p><strong>1. Rede.</strong> Cada documento do período é um nó. Dois documentos "
            f"ficam ligados quando têm {unidade} em comum, e o peso é o número de itens "
            "compartilhados (acoplamento, c<sub>ij</sub>). A frequência f<sub>i</sub> de "
            "um documento é o seu número de itens. Com referências como itens, é o "
            "acoplamento bibliográfico.</p>")
    else:
        quem = ("autor" if config.matriz == "AggregatedCouplingBasedOnAuthor"
                else "periódico")
        p.append(
            f"<p><strong>1. Rede.</strong> Cada {quem} é um nó. Para cada um, reúne-se o "
            f"conjunto de {unidade} de todos os seus documentos; dois nós ficam ligados "
            "quando esses conjuntos têm itens em comum, e o peso é o tamanho da interseção "
            "(acoplamento agregado, c<sub>ij</sub>). A frequência f<sub>i</sub> é o número "
            f"de documentos do {quem}. Como no SciMAT, quem aparece em muitos documentos "
            "tende a se ligar a quase todos os demais.</p>")

    if config.unidade == "Institutions":
        p.append(_texto_ies_nomes())

    # 2. Redução
    p.append(
        f"<p><strong>2. Redução.</strong> Antes de montar a rede, saem os termos ignorados "
        f"e os itens que aparecem em menos de {frequencia} "
        f"{_plural(frequencia, 'documento', 'documentos')} (frequência mínima). Depois de "
        f"montada, saem as ligações com peso menor que {config.minimo_coocorrencia}. "
        "Itens que ficam sem nenhuma ligação continuam na rede, mas não entram em "
        "agrupamento.</p>")

    # 3. Similaridade
    adotada = config.similaridade
    itens = []
    for nome in MEDIDAS:
        marca = " <em>(adotada)</em>" if nome == adotada else ""
        itens.append(
            f"<li>{_ROTULOS_SIMILARIDADE[nome]}{marca}: "
            f"<code class=\"formula\">{_FORMULAS[nome]}</code> — "
            f"{_EXPLICACAO_SIMILARIDADE[nome]}.</li>")
    p.append(
        "<p><strong>3. Normalização.</strong> O peso bruto de cada ligação é trocado por uma "
        "medida de similaridade que desconta a frequência dos dois nós (c<sub>ij</sub> é o "
        "peso bruto; f<sub>i</sub> e f<sub>j</sub> são as frequências). As medidas "
        "disponíveis são:</p><ul>" + "".join(itens) + "</ul>")

    # 4. Agrupamento
    p.append("<p><strong>4. Agrupamento.</strong> " + _texto_algoritmo(config)
             + (_texto_ies_componentes(config) if config.unidade == "Institutions" else "")
             + "</p>")

    # 5. Diagrama estratégico
    p.append(
        "<p><strong>5. Centralidade, densidade e quadrantes.</strong> Para cada agrupamento, "
        "a centralidade de Callon é 10 × a soma dos pesos das ligações entre o agrupamento "
        "e nós de fora dele (quanto ele se liga ao resto da rede); a densidade de Callon é "
        "100 × a soma dos pesos das ligações internas ÷ o número de nós (quão coeso ele é). "
        "No diagrama estratégico, cada medida vira uma faixa: a posição do agrupamento "
        "na ordenação do período dividida pelo número de agrupamentos (de 1/n a 1). O "
        "plano é cortado em 0,5 nos dois eixos: <em>motor</em> (centralidade e densidade "
        "altas), <em>nicho</em> (só densidade alta), <em>básico ou transversal</em> (só "
        "centralidade alta) e <em>emergente ou em declínio</em> (as duas baixas). Como as "
        "faixas são posições, e não valores, o quadrante diz como o agrupamento se "
        "compara aos outros do mesmo período.</p>")

    # 6. Documentos e desempenho
    p.append("<p><strong>6. Documentos e desempenho.</strong> " + _texto_mapeadores(config)
             + "</p>")

    # 7. Evolução (só faz sentido com itens que se repetem entre períodos)
    evolui = (medida_temporal and config.matriz == "CoOccurrence"
              and (n_periodos is None or n_periodos >= 2))
    if evolui:
        nome = _ROTULOS_TEMPORAL.get(medida_temporal, medida_temporal)
        formula = _FORMULAS.get(medida_temporal, "")
        medida = (f"o {nome} (<code class=\"formula\">{formula}</code>)" if formula
                  else f"o {nome}")
        sentenca_medida = (
            f"A medida temporal é {medida}, aplicada aos conjuntos de itens: "
            "f<sub>i</sub> e f<sub>j</sub> são os tamanhos dos dois conjuntos e c<sub>ij</sub> "
            "o número de itens que têm em comum. ")
    else:
        sentenca_medida = ("A medida temporal é uma das mesmas medidas de similaridade, "
                           "aplicada aos conjuntos de itens. ")
    p.append(
        "<p><strong>7. Evolução e sobreposição entre períodos.</strong> No mapa de evolução, "
        "um agrupamento de um período se liga a um agrupamento do período seguinte quando "
        "os dois compartilham itens; cada agrupamento de origem mantém, no máximo, os três "
        "elos mais fortes, e o elo é destacado quando um nó principal está no outro "
        "agrupamento. O mapa de sobreposição compara todos os pares de períodos usando o "
        "conjunto de itens que ficou em agrupamentos em cada um. " + sentenca_medida
        + "</p>")
    p.append(
        "<p><strong>8. Dendrograma.</strong> Análise complementar sobre a mesma rede de cada "
        "período (até os 60 itens mais frequentes). Cada item começa sozinho; a cada passo "
        "juntam-se os dois grupos mais próximos, com distância 1 − similaridade (a "
        "similaridade da rede, dividida pelo maior valor se passar de 1; par sem ligação "
        "tem distância 1) e ligação média (média das distâncias entre os membros). A altura "
        "da fusão é a distância em que os grupos se juntam. O corte sugerido fica no maior "
        "salto entre fusões consecutivas; a correlação cofenética mede o quanto a árvore "
        "preserva as distâncias originais, e ARI e NMI comparam o corte com os "
        "agrupamentos da rede (1 = idêntico).</p>")
    proximo = 9
    if config.matriz == "CoOccurrence" and config.unidade in UNIDADES_LINHA_DO_TEMPO:
        p.append(_texto_linha_do_tempo(config, proximo))
        proximo += 1
    if config.matriz == "CoOccurrence":
        p.append(_texto_densidade(proximo))
        proximo += 1
    p.append(_texto_pivos(config, proximo))
    proximo += 1
    p.append(_texto_qualidade(config, proximo))
    p.append("</div>")
    return "\n".join(p)


UNIDADES_LINHA_DO_TEMPO = ("Words", "Authors", "References")


def _texto_linha_do_tempo(config, numero: int) -> str:
    """Método da linha do tempo, com os limites lidos de `linha_do_tempo`/`rajadas`."""
    lt = linha_do_tempo
    referencias = config.unidade == "References"
    return (
        f"<p><strong>{numero}. Linha do tempo.</strong> Figura complementar sobre o corpus "
        "completo (todos os documentos do projeto, sem dividir em períodos), com os mesmos "
        "parâmetros e o mesmo algoritmo desta análise. Cada agrupamento vira uma faixa; só "
        f"aparecem os {lt.MAX_NOS} itens mais frequentes no total e, no máximo, "
        f"{lt.POR_FAIXA} por faixa. "
        + ("Cada referência fica no ano da própria obra. " if referencias else
           "Cada item fica no seu ano médio, a média dos anos dos documentos em que "
           "aparece, arredondada; a linha fina atrás do nó vai do primeiro ao último ano "
           "do item e, quando o item tem rajada, um traço vermelho sobre essa linha marca "
           "os anos da rajada. ")
        + "O tamanho do nó segue a frequência. Os arcos mostram as "
        f"{lt.LIGACOES_POR_NO} ligações mais fortes de cada nó dentro da faixa e as "
        f"{lt.LIGACOES_CRUZADAS} mais fortes entre faixas. O anel vermelho marca rajadas "
        f"(Kleinberg): as {lt.RAJADAS_MAXIMAS} mais fortes do corpus, com pelo menos "
        f"{lt.RAJADA_MIN_DOCUMENTOS} documentos"
        + (", calculadas sobre as referências citadas" if referencias else
           ", calculadas só sobre as palavras-chave dos autores (a rede de palavras pode "
           "incluir também as de fonte)" if config.unidade == "Words"
           else " (não há rajada para autores)")
        + ". Itens sem ano ficam de fora, com aviso; os termos-descritor (presentes em mais "
        f"de {pivos.PROPORCAO_DESCRITOR:.0%} dos documentos) também, como nos pontos de "
        "virada.</p>")


def _texto_densidade(numero: int) -> str:
    """Método do mapa de densidade, com as constantes lidas de `viz.densidade`."""
    d = viz_densidade
    return (
        f"<p><strong>{numero}. Mapa de densidade.</strong> Figura complementar sobre o corpus "
        "completo, com os mesmos parâmetros e o mesmo algoritmo desta análise. Entram os "
        f"{d.TOPO_NOS} itens mais frequentes da rede (padrão; a tela aceita de "
        f"{d.LIMITE_NOS[0]} a {d.LIMITE_NOS[1]}). A similaridade entre dois itens é a força "
        "da ligação na rede, dividida pela maior ligação entre os itens do mapa. As "
        "posições vêm de um layout de atração e repulsão no plano (energia do tipo VOS): "
        "minimiza-se a soma de s<sub>ij</sub>·d<sub>ij</sub>² − c·Σ ln d<sub>ij</sub> por "
        f"descida de gradiente com momento ({d.ITERACOES} iterações, semente fixa, c = 4), de "
        "modo que o resultado se repete; itens soltos, muito afastados do conjunto (além de "
        f"1,3 vez o percentil 85 da distância ao centro), têm o excesso de distância reduzido a "
        f"{d.COMPRESSAO_PERIFERIA:.0%} antes de escalar o mapa. A densidade em "
        "cada ponto da imagem é a soma de núcleos gaussianos centrados nos itens, cada um "
        "com peso igual à frequência do item (número de documentos); o desvio-padrão do "
        f"núcleo (largura de banda) é a suavização × {d.SIGMA_POR_PASSO * 100:g}% da largura "
        f"do quadro, com suavização padrão {d.SUAVIZACAO} (de {d.LIMITE_SUAVIZACAO[0]} a "
        f"{d.LIMITE_SUAVIZACAO[1]}). A soma é normalizada pelo máximo, para ficar entre 0 e 1, "
        f"e elevada a {str(d.GAMMA).replace('.', ',')} para realçar as áreas médias; a cor vai do "
        "branco (0) ao amarelo (1). Os rótulos aparecem por ordem de frequência, sem "
        f"sobreposição e inteiros dentro do quadro, até o máximo de {d.MAX_ROTULOS}; nomes com "
        f"mais de {d.LIMITE_ROTULO} caracteres são cortados e o texto inteiro fica na dica "
        "do item. O mapa não é calculado para acoplamento nem cocitação, cujos nós são "
        "documentos.</p>")


def _texto_pivos(config, numero: int) -> str:
    """Método dos pontos de virada e do sigma, com as constantes lidas de `pivos`."""
    return (
        f"<p><strong>{numero}. Pontos de virada e sigma.</strong> Em cada período, a "
        "intermediação de cada nó (quantos caminhos mínimos entre outros pares passam por "
        "ele) é normalizada pelo número de pares possíveis, (n − 1)(n − 2)/2, e vai de 0 a 1. "
        f"É ponto de virada o nó com intermediação no decil superior (percentil "
        f"{pivos.PERCENTIL:g} entre os nós com intermediação positiva) <em>e</em> com "
        "vizinhos em pelo menos dois agrupamentos. Termos presentes em mais de "
        f"{pivos.PROPORCAO_DESCRITOR:.0%} dos documentos do período (termo-descritor) "
        "saem do ranking, porque descrevem o corpus em vez de distinguir temas. Com menos "
        f"de {pivos.MINIMO_NOS} nós, a lista é só indício e o relatório avisa. O sigma, "
        "como no CiteSpace, é (intermediação + 1) elevado à força da rajada do termo; só "
        "existe para quem tem rajada (palavras-chave e referências em co-ocorrência) e a "
        "coluna só aparece quando algum ponto de virada tem rajada. Como o sigma é um "
        "produto (o logaritmo do sigma é a força da rajada vezes ln(intermediação + 1)), entre "
        "os pontos de virada, que já têm intermediação alta, quem ordena o ranking por sigma "
        "é sobretudo a intermediação: nas redes testadas a correlação de Spearman do sigma "
        "com a intermediação ficou entre 0,89 e 0,97, e com a força da rajada, entre 0,21 e "
        "0,60. A rajada das palavras-chave é calculada só sobre as palavras-chave dos autores "
        "(a rede de palavras pode incluir também as de fonte), e a das referências, sobre as "
        "referências citadas. "
        f"A tabela lista no máximo {TOPO_PIVOS} pontos de virada.</p>")


def _texto_qualidade(config, numero: int = 9) -> str:
    """Qualidade do mapa e rótulos, em linguagem simples, com os limiares do código.

    `numero` é o número da seção "Qualidade do mapa"; "Rótulos" vem logo depois.
    """
    lim = LIMIARES_QUALIDADE
    minimo_nos = qualidade.MINIMO_NOS
    minimo_sil = qualidade.MINIMO_NOS_SILHUETA
    limite_nos = qualidade.LIMITE_NOS
    min_docs = rotulos.MINIMO_DOCUMENTOS
    indicativo_ate = rotulos.LIMITE_INDICATIVO - 1
    cobertura = int(round(rotulos.COBERTURA_MAXIMA * 100))
    minimo_grupo = rotulos.MINIMO_NO_GRUPO
    p = []
    p.append(
        f"<p><strong>{numero}. Qualidade do mapa.</strong> Duas medidas dizem se a divisão em "
        "agrupamentos se sustenta na rede.</p>")
    p.append(
        "<ul>"
        "<li><em>Modularidade Q</em> (força da divisão): compara as ligações que ficam "
        "dentro dos agrupamentos com as que se esperariam se a rede fosse sorteada, "
        "ponderando pela similaridade; vai de cerca de 0 (como dividir ao acaso) a perto "
        "de 1 (grupos bem separados). O item sem agrupamento conta como um grupo de um "
        "item só. Compara-se com o <em>Q do Louvain</em> porque o Louvain procura "
        "justamente o maior Q possível: se o Q desta divisão é bem menor, existe outra "
        f"divisão mais nítida (razão Q/Q<sub>Louvain</sub> abaixo de {_n2(lim['razao'])}).</li>"
        "<li><em>Silhueta</em>: para cada item, quanto mais perto ele está do próprio "
        "agrupamento do que do agrupamento vizinho mais próximo (distância = 1 − "
        "similaridade normalizada, como no dendrograma), de −1 a 1; valor negativo "
        f"indica item possivelmente mal alocado. Agrupamentos com menos de {minimo_sil} "
        "itens ficam fora (a silhueta de um grupo tão pequeno não informa nada) e "
        f"aparecem com “—”. Em redes com mais de {limite_nos} itens agrupados a silhueta "
        "é dispensada, para a análise não ficar lenta.</li></ul>")
    p.append(
        "<p><strong>Selo de qualidade.</strong> <em>Ruim</em>: Q abaixo de "
        f"{_n2(lim['q_ruim'])} ou silhueta média abaixo de {_n2(lim['silhueta_ruim'])}. "
        f"<em>Atenção</em>: Q abaixo de {_n2(lim['q_atencao'])}; razão Q/Q<sub>Louvain</sub> "
        f"abaixo de {_n2(lim['razao'])}; silhueta média abaixo de "
        f"{_n2(lim['silhueta_atencao'])}; mais de {lim['pct_negativos']}% dos itens com "
        f"silhueta negativa; menos de {lim['pct_agrupados']}% dos itens em agrupamentos; "
        "ou rede fragmentada (há mais componentes do que a metade dos itens, isto é, "
        "o componente médio tem menos de 2 itens, quase só itens isolados e pares; "
        "nesse caso um Q alto não indica qualidade). <em>Indefinido</em>: menos de "
        f"{minimo_nos} itens, menos de 2 agrupamentos ou rede sem ligações com valor "
        "positivo; nesses casos nenhum número é mostrado como 0, porque não houve "
        "avaliação. <em>OK</em>: nenhum dos alertas acima.</p>")
    p.append(
        "<p><strong>Aviso.</strong> A maioria das redes reais fica em “atenção”, e isso "
        "<em>não invalida o mapa</em>: o selo serve de leitura prudente (quais limites "
        "entre temas merecem desconfiança), não de aprovação ou reprovação.</p>")
    if config.unidade == "Authors":
        p.append(
            "<p><strong>Atenção com autores.</strong> Em redes de coautoria, um Q alto é "
            "em geral um artefato: cada documento liga todos os seus autores entre si e a "
            "rede se parte em muitos grupos pequenos e isolados, que a modularidade "
            "premia sem que haja estrutura temática. Leia o Q junto com o aviso de rede "
            "fragmentada e com o número de itens por agrupamento. Por isso, com autores, o "
            "selo nunca é <em>OK</em>: no máximo <em>Atenção</em>.</p>")
    p.append(
        f"<p><strong>{numero + 1}. Rótulos dos agrupamentos.</strong> O <em>rótulo novo</em> traz "
        "os termos que mais distinguem o agrupamento dos demais documentos do mesmo "
        "período, pela razão de verossimilhança de Dunning (G²): comparam-se os "
        "documentos do núcleo do agrupamento com todos os outros documentos do período, "
        "e sobem os termos bem mais frequentes no agrupamento. Os termos vêm das palavras "
        "do título, das palavras-chave dos autores (expressão inteira) e, do resumo, "
        "apenas de pares de palavras (bigramas), porque palavra solta de resumo é "
        f"genérica demais; um termo precisa aparecer em pelo menos {minimo_grupo} "
        "documentos do agrupamento, e singular, plural e acento são unidos. É preciso ao "
        f"menos {min_docs} documentos no núcleo; com {min_docs} a {indicativo_ate} o "
        "rótulo sai marcado como <em>(indicativo)</em>, e com "
        f"{rotulos.LIMITE_INDICATIVO} ou mais é firme. Agrupamento que cobre mais de "
        f"{cobertura}% dos documentos do período não recebe rótulo (não distingue "
        "nada). O rótulo atual, tirado do item central, continua como subtítulo, e "
        "onde não há rótulo novo vale só ele. Nas tabelas, <em>Ano médio</em> é a média "
        "do ano de publicação dos documentos do núcleo.</p>")
    return "\n".join(p)


def _texto_ies_nomes() -> str:
    """Como as variantes do nome de uma instituição são unidas (rede de IES)."""
    return (
        "<p><em>Nomes das instituições.</em> A instituição de cada afiliação é o trecho que "
        "a nomeia (por exemplo, o segmento com \"Universidade\" ou \"University\"). Antes "
        "de montar a rede, as variantes do mesmo nome são unidas, e só quando a "
        "normalização é inequívoca: caixa, acentos, pontuação e espaços não contam; "
        "ligações (de, of, the) são desprezadas; Univ., University, Universidade e "
        "Universidad valem o mesmo (e também instituto/institute e faculdade/faculty); "
        "sigla entre parênteses e país depois de hífen ou barra são ignorados. Não se "
        "une quando a ordem das palavras muda, quando falta ou sobra uma palavra, nem por "
        "semelhança de grafia. O mesmo nome com países diferentes não é unido entre países. "
        "A grafia adotada é a mais frequente. Cada união fica registrada na tabela "
        "\"variantes unidas\", com a grafia adotada, as variantes, o número de documentos "
        "e o motivo.</p>")


def _texto_ies_componentes(config) -> str:
    """Regra do tamanho mínimo do componente na rede de IES."""
    minimo = config.componente_minimo
    if minimo <= 1:
        return ""
    return (
        f" Na rede de instituições, antes de aceitar um agrupamento calculam-se os "
        f"componentes conexos da rede (conjuntos de instituições ligadas entre si, direta ou "
        f"indiretamente, por coautoria institucional). Componentes com menos de {minimo} "
        "instituições não viram agrupamento e não entram nos halos: seus nós ficam como "
        f"\"sem agrupamento\". O parâmetro é o tamanho mínimo do componente (padrão 3, "
        f"aqui {minimo}).")


def ies_html(resultado, tabela=None, rotulo: str = "") -> str:
    """Tabela auditável "variantes unidas" e nota dos componentes sem agrupamento (rede de IES)."""
    info = getattr(resultado, "ies", None)
    if not info:
        return ""
    tabela = tabela or _tabela_padrao
    sufixo = f" — {rotulo}" if rotulo else ""
    partes = []
    linhas = []
    for uniao in info["unioes"]:
        for variante in uniao["variantes"]:
            linhas.append([_esc(uniao["adotado"]), _esc(variante["nome"]),
                           _inteiro(variante["documentos"]), _esc(variante["motivo"])])
    if linhas:
        partes.append(tabela(
            ["Nome adotado", "Variante", "Documentos", "Motivo da união"], linhas,
            f"Variantes unidas{sufixo}: {len(info['unioes'])} "
            f"{_plural(len(info['unioes']), 'instituição teve', 'instituições tiveram')} "
            "variantes do nome unidas.", numericas=(2,)))
    else:
        partes.append('<p class="nota">Variantes unidas: nenhuma. Nenhum nome de instituição '
                      "tinha variante inequívoca nesta base.</p>")
    pequenos = info["componentes_pequenos"]
    minimo = info["componente_minimo"]
    nota = (f"Componentes com menos de {minimo} instituições não viram agrupamento e ficam "
            f"sem agrupamento: {len(pequenos)} {_plural(len(pequenos), 'componente', 'componentes')} "
            f"de 2 a {minimo - 1} instituições e {info['isolados']} "
            f"{_plural(info['isolados'], 'instituição isolada', 'instituições isoladas')}."
            if minimo > 1 else "Todos os componentes podem virar agrupamento.")
    partes.append(f'<p class="nota">{nota}</p>')
    return "\n".join(partes)


def _texto_algoritmo(config) -> str:
    tmin, tmax = config.tamanho_minimo, config.tamanho_maximo
    nome = _ROTULOS_ALGORITMO.get(config.algoritmo, config.algoritmo)
    if config.algoritmo == "CentersSimples":
        return (
            f"<em>{nome}</em> (algoritmo do SciMAT). As ligações são ordenadas da mais forte "
            "para a mais fraca e percorridas em sequência, contando quantas vezes cada nó "
            f"aparece. Quando um nó chega a {tmax - 1} ligações, ele vira o centro de um "
            f"agrupamento e leva consigo os vizinhos dessas ligações (até {tmax} nós). "
            "Todas as ligações que tocam o agrupamento saem da lista e a varredura "
            f"continua. Se a lista termina sem formar agrupamento, o limite cai uma unidade "
            f"e a varredura recomeça, até o mínimo de {tmin} nós. O centro dá o nome ao "
            "agrupamento; nós que não chegam a nenhum ficam de fora. O ponto de corte "
            "não é usado.")
    if config.algoritmo in ("AverageLink", "CompleteLink", "SingleLink", "SumLink"):
        criterio = {
            "AverageLink": "a média dos pesos das ligações que existem entre os dois grupos",
            "CompleteLink": "o menor peso entre as ligações que existem entre os dois grupos",
            "SingleLink": "o maior peso entre as ligações que existem entre os dois grupos",
            "SumLink": "a soma dos pesos das ligações entre os dois grupos",
        }[config.algoritmo]
        return (
            f"<em>{nome}</em> (aglomeração hierárquica). Cada nó começa sozinho. A cada passo, "
            f"juntam-se os dois grupos ligados com o maior valor, que aqui é {criterio}; "
            "pares sem nenhuma ligação nunca se juntam. Só entram na disputa pares com valor "
            f"maior ou igual ao ponto de corte ({_decimal(config.corte)}). O processo "
            f"para quando não há mais par elegível ou quando a melhor junção passaria de "
            f"{tmax} nós. Grupos com pelo menos {tmin} nós viram agrupamentos; os demais "
            "ficam de fora. O nó principal segue a regra do SciMAT.")
    return (
        f"<em>{nome}</em> (detecção de comunidades por modularidade). Cada nó começa numa "
        "comunidade própria e é movido para a comunidade vizinha que mais aumenta a "
        "modularidade, usando os pesos normalizados; depois as comunidades viram nós de uma "
        "rede menor e o processo se repete até nada mais mudar. Em seguida, o tamanho é "
        f"ajustado: comunidades com menos de {tmin} nós são absorvidas pela vizinha de "
        f"ligação total mais forte, e as com mais de {tmax} nós são partidas, retirando "
        "as ligações mais fracas até que o grupo se separe. O nó principal é o de maior "
        "soma de ligações dentro do grupo. O ponto de corte não é usado.")


def _texto_mapeadores(config) -> str:
    descricoes = {
        "nucleo": "<em>núcleo</em>: documentos que contêm os dois itens de pelo menos uma "
                  "ligação interna do agrupamento",
        "interseccao": "<em>interseção</em>: documentos que contêm todos os itens do "
                       "agrupamento",
        "secundarios": "<em>secundários</em>: documentos presentes em um número ímpar de "
                       "itens do agrupamento (diferença simétrica acumulada, como no SciMAT)",
        "kcore": f"<em>k-core</em>: documentos com pelo menos {config.k_core} itens do "
                 "agrupamento",
        "uniao": "<em>união</em>: documentos que contêm algum item do agrupamento",
        "acoplamento": "<em>acoplamento</em>: os próprios nós, que já são documentos",
    }
    usados = [descricoes[m] for m in config.mapeadores if m in descricoes]
    texto = ("Cada agrupamento recebe os documentos do mapeador adotado — "
             + "; ".join(usados) + ". " if usados else "")
    if config.matriz == "BasicCoupling" and "acoplamento" not in config.mapeadores:
        texto += ("Atenção: no acoplamento básico os nós já são documentos, e os mapeadores "
                  "por itens não os encontram; o adequado é o mapeador de acoplamento, e "
                  "com os adotados as medidas de desempenho saem zeradas ou quase. ")
    texto += (
        "Sobre esses documentos calculam-se, a partir das citações registradas na base "
        "(sem recontar citações): o <em>índice h</em>, o maior h tal que h documentos têm "
        "pelo menos h citações; o <em>índice g</em>, o maior g tal que os g documentos mais "
        "citados somam pelo menos g² citações; o <em>hg</em>, raiz de h × g; e o "
        "<em>q2</em>, raiz de h × a mediana das citações dos h documentos do núcleo h "
        "(a mediana superior, o maior dos dois valores centrais, quando h é par). Documentos sem citação não entram em h, g e "
        "q2. Também são calculados a soma, a média, o mínimo e o máximo de citações e o "
        "número de documentos.")
    return texto


# ------------------------------------------------------------------- indicadores

_GRAFIAS_SQL = {
    "Words": ("Document_Word", "Document_idDocument", "Word_idWord", None),
    "Authors": ("Document_Author", "Document_idDocument", "Author_idAuthor", None),
    "References": ("Document_Reference", "Document_idDocument", "Reference_idReference", None),
    "Countries": ("Document_Country", "Document_idDocument", "Country_idCountry", None),
}


def grafias_distintas(kb, config, periodos_ids) -> int | None:
    """Grafias (registros brutos, antes da unificação em grupos) usadas nos períodos."""
    if kb is None or not periodos_ids:
        return None
    marcas = ",".join("?" * len(periodos_ids))
    docs = ("SELECT d.idDocument FROM Document d JOIN PublishDate_Period pdp "
            "ON pdp.PublishDate_idPublishDate = d.PublishDate_idPublishDate "
            f"WHERE pdp.Period_idPeriod IN ({marcas})")
    try:
        if config.unidade == "Words":
            colunas = {"autor": "isAuthorWord", "fonte": "isSourceWord",
                       "adicionada": "isAddedWord"}
            ativas = [colunas[o] for o in config.palavras if o in colunas]
            filtro = (" AND (" + " OR ".join(f"dw.{c} = 1" for c in ativas) + ")"
                      if ativas else "")
            sql = ("SELECT COUNT(DISTINCT dw.Word_idWord) FROM Document_Word dw "
                   f"WHERE dw.Document_idDocument IN ({docs}){filtro}")
        elif config.unidade == "AuthorsReference":
            sql = ("SELECT COUNT(DISTINCT arr.AuthorReference_idAuthorReference) "
                   "FROM Document_Reference dr JOIN AuthorReference_Reference arr "
                   "ON arr.Reference_idReference = dr.Reference_idReference "
                   f"WHERE dr.Document_idDocument IN ({docs})")
        elif config.unidade == "ReferenceSources":
            sql = ("SELECT COUNT(DISTINCT r.ReferenceSource_idReferenceSource) "
                   "FROM Document_Reference dr JOIN Reference r "
                   "ON r.idReference = dr.Reference_idReference "
                   f"WHERE dr.Document_idDocument IN ({docs}) "
                   "AND r.ReferenceSource_idReferenceSource IS NOT NULL")
        else:
            tabela, doc_col, item_col, _ = _GRAFIAS_SQL[config.unidade]
            sql = (f"SELECT COUNT(DISTINCT t.{item_col}) FROM {tabela} t "
                   f"WHERE t.{doc_col} IN ({docs})")
        return int(kb.conexao.execute(sql, list(periodos_ids)).fetchone()[0])
    except Exception:
        return None


def _indicadores_periodo(resultado, nome: str, frequencia: int) -> dict:
    rede = resultado.rede
    grupos = resultado.grupos
    maior = max((len(g.nos) for g in grupos), default=0)
    agrupados = sum(len(g.nos) for g in grupos)
    quadrantes = {"motor": 0, "nicho": 0, "basico": 0, "emergente": 0}
    for g in grupos:
        quadrantes[_quadrante(g)] += 1
    original = resultado.dataset_original
    return {
        "escopo": nome,
        "documentos": original.quantidade_documentos(),
        "documentos_com_itens": sum(1 for d in original.documentos.values() if d.itens),
        "grafias": None,
        "grupos": original.quantidade_itens(),
        "itens_reduzidos": resultado.dataset.quantidade_itens(),
        "frequencia_minima": frequencia,
        "rede_nos": rede.quantidade_nos(),
        "rede_arestas": rede.quantidade_arestas(),
        "agrupamentos": len(grupos),
        "maior_agrupamento": maior,
        "itens_agrupados": agrupados,
        "itens_sem_agrupamento": len(resultado.conjunto.nos_sem_grupo()),
        "quadrantes": quadrantes,
        "qualidade": qualidade_do_resultado(resultado),
    }


def indicadores(resultados, periodos=None, kb=None, config=None, frequencia=None,
                completo: str = "Todos os períodos") -> list[dict]:
    """Indicadores por análise: primeiro o corpus completo, depois cada período.

    O corpus completo reúne os períodos: documentos e itens são a união (sem
    contar duas vezes), os agrupamentos são somados e o maior agrupamento é o
    maior dos períodos. Rede e arestas não se somam entre períodos e ficam em
    branco. Com um só período, devolve só a linha desse período. Com `kb` e
    `periodos`, inclui as grafias distintas na base.
    """
    resultados = list(resultados)
    if not resultados:
        return []
    config = config or resultados[0].configuracao
    frequencia = _frequencia_efetiva(config, frequencia)
    lista = [_indicadores_periodo(r, r.periodo, frequencia) for r in resultados]

    documentos: set[int] = set()
    com_itens: set[int] = set()
    grupos: set[int] = set()
    reduzidos: set[int] = set()
    agrupados: set[int] = set()
    quadrantes = {"motor": 0, "nicho": 0, "basico": 0, "emergente": 0}
    for r, linha in zip(resultados, lista):
        documentos |= set(r.dataset_original.documentos)
        com_itens |= {i for i, d in r.dataset_original.documentos.items() if d.itens}
        grupos |= set(r.dataset_original.itens)
        reduzidos |= set(r.dataset.itens)
        for g in r.grupos:
            agrupados |= set(g.nos)
        for chave, n in linha["quadrantes"].items():
            quadrantes[chave] += n
    total = {
        "escopo": completo,
        "documentos": len(documentos),
        "documentos_com_itens": len(com_itens),
        "grafias": None,
        "grupos": len(grupos),
        "itens_reduzidos": len(reduzidos),
        "frequencia_minima": frequencia,
        "rede_nos": None,
        "rede_arestas": None,
        "agrupamentos": sum(x["agrupamentos"] for x in lista),
        "maior_agrupamento": max(x["maior_agrupamento"] for x in lista),
        "itens_agrupados": len(agrupados),
        "itens_sem_agrupamento": None,
        "quadrantes": quadrantes,
        "qualidade": None,           # não se soma entre períodos
    }
    if kb is not None and periodos:
        ids = [p.id for p in periodos]
        total["grafias"] = grafias_distintas(kb, config, ids)
        for p, linha in zip(periodos, lista):
            linha["grafias"] = grafias_distintas(kb, config, [p.id])
    return lista if len(lista) == 1 else [total] + lista


def _nome_quadrantes(unidade: str) -> dict:
    from .viz.strategic import _curtos
    curtos = _curtos(unidade)
    return {"motor": curtos["motor"].lower(), "nicho": curtos["nicho"].lower(),
            "basico": curtos["basico"].lower(), "emergente": curtos["emergente"].lower()}


def indicadores_linhas(dados: list[dict], config, frequencia=None) -> tuple[list[str], list[list[str]]]:
    """Cabeçalho e linhas (já formatadas) da tabela de indicadores."""
    frequencia = _frequencia_efetiva(config, frequencia)
    unidade = _ITEM_UNIDADE.get(config.unidade, "itens")
    nomes = _nome_quadrantes(config.unidade)

    def numero(valor):
        return "—" if valor is None else _inteiro(valor)

    def rede(x):
        if x["rede_nos"] is None:
            return "—"
        return (f"{_inteiro(x['rede_nos'])} {_plural(x['rede_nos'], 'nó', 'nós')} · "
                f"{_inteiro(x['rede_arestas'])} "
                f"{_plural(x['rede_arestas'], 'aresta', 'arestas')}")

    def quadrantes(x):
        q = x["quadrantes"]
        if not x["agrupamentos"]:
            return "—"
        return " · ".join(f"{nomes[k]} {q[k]}" for k in ("motor", "nicho", "basico", "emergente"))

    def maior(x):
        n = x["maior_agrupamento"]
        return f"{_inteiro(n)} {_plural(n, 'nó', 'nós')}" if n else "—"

    cabecalho = ["Indicador"] + [_esc(x["escopo"]) for x in dados]
    linhas = [
        ["Documentos"] + [numero(x["documentos"]) for x in dados],
        ["Documentos com pelo menos um item"] + [numero(x["documentos_com_itens"]) for x in dados],
    ]
    if any(x["grafias"] is not None for x in dados):
        linhas.append(["Grafias distintas na base"] + [numero(x["grafias"]) for x in dados])
    linhas += [
        [f"Grupos de {unidade} (itens)"] + [numero(x["grupos"]) for x in dados],
        [f"Itens após redução (freq. ≥ {frequencia})"]
        + [numero(x["itens_reduzidos"]) for x in dados],
        ["Rede"] + [rede(x) for x in dados],
        [f"Agrupamentos (freq. ≥ {frequencia})"] + [numero(x["agrupamentos"]) for x in dados],
        ["Maior agrupamento"] + [maior(x) for x in dados],
        ["Nós em agrupamentos"] + [numero(x["itens_agrupados"]) for x in dados],
        ["Nós da rede sem agrupamento"] + [numero(x["itens_sem_agrupamento"]) for x in dados],
        ["Quadrantes"] + [quadrantes(x) for x in dados],
    ]
    if any(x.get("qualidade") for x in dados):
        def q(x, chave, casas=2, pct=False):
            ql = x.get("qualidade")
            if not ql or ql.get("nivel") == "indefinido" or ql.get(chave) is None:
                return "—"
            return _n2(ql[chave], 0 if pct else casas) + ("%" if pct else "")

        def pct_agrupados(x):
            ql = x.get("qualidade")
            if not ql or not ql.get("n_nos"):
                return "—"
            if ql.get("nivel") == "indefinido" and not ql["pct_agrupados"]:
                return "—"          # indefinido nunca mostra 0
            return _n2(ql["pct_agrupados"], 0) + "%"

        def nivel(x):
            ql = x.get("qualidade")
            return selo_qualidade(ql["nivel"]) if ql else "—"

        linhas += [
            ["Modularidade Q"] + [q(x, "q") for x in dados],
            ["Q do Louvain (referência)"] + [q(x, "q_louvain") for x in dados],
            ["Silhueta média"] + [q(x, "silhueta_media") for x in dados],
            ["% dos itens em agrupamentos"] + [pct_agrupados(x) for x in dados],
            ["Qualidade do mapa"] + [nivel(x) for x in dados],
        ]
    return cabecalho, [[_esc(l[0])] + l[1:] for l in linhas]


def indicadores_html(resultados, periodos=None, kb=None, config=None, frequencia=None,
                     tabela=None, rotulo: str = "") -> str:
    """Tabela de indicadores no estilo do relatório de referência, mais a nota de leitura."""
    resultados = list(resultados)
    if not resultados:
        return ""
    tabela = tabela or _tabela_padrao
    config = config or resultados[0].configuracao
    dados = indicadores(resultados, periodos, kb, config, frequencia)
    cabecalho, linhas = indicadores_linhas(dados, config, frequencia)
    sufixo = f" — {rotulo}" if rotulo else ""
    legenda = (f"Indicadores da análise{sufixo}." if len(dados) == 1 else
               f"Indicadores da análise, para todos os períodos e por período{sufixo}.")
    nota = ("Rede: nós e arestas depois da redução e do corte de ligações. Quadrantes: "
            "regra descrita em “Como funciona”.")
    if len(dados) > 1:
        nota = ("Todos os períodos: documentos e itens são a união dos períodos; "
                "agrupamentos e quadrantes são somados; o maior agrupamento é o maior dos "
                "períodos; a rede não se soma entre períodos. " + nota)
    return ('<div class="rolagem">'
            + tabela(cabecalho, linhas, legenda, numericas=tuple(range(1, len(cabecalho))))
            + f'</div><p class="fonte">{_esc(nota)}</p>' + _avisos_html(dados))


def _avisos_html(dados: list[dict]) -> str:
    """Avisos de qualidade de cada período, em lista abaixo da tabela de indicadores."""
    blocos = []
    por_periodo = [x for x in dados if x.get("qualidade")]
    multiplos = len(por_periodo) > 1
    for x in por_periodo:
        avisos = x["qualidade"].get("avisos") or []
        if not avisos:
            continue
        itens = "".join(f"<li>{_esc(a)}</li>" for a in avisos)
        titulo = (f"Avisos de qualidade — {_esc(x['escopo'])}" if multiplos
                  else "Avisos de qualidade")
        blocos.append(f"<p><strong>{titulo}</strong></p><ul>{itens}</ul>")
    if not blocos:
        return ""
    return ('<div class="avisos-qualidade">' + "".join(blocos)
            + '<p class="fonte">Como ler o selo: veja “Qualidade do mapa e rótulos” em '
              "“Como funciona”. A maioria das redes reais fica em atenção, e isso não "
              "invalida o mapa.</p></div>")


def metodo_html(config, periodos=None, resultados=(), frequencia=None,
                medida_temporal: str | None = "EquivalenceIndex", kb=None, tabela=None,
                rotulo: str = "", titulo=None) -> str:
    """Bloco completo: parâmetros, indicadores e método.

    `titulo(texto)` devolve o cabeçalho de cada parte; sem ele, usa `<h4>` sem
    número. Em relatórios numerados, quem chama passa o seu próprio gerador.
    """
    titulo = titulo or (lambda texto: f"<h4>{_esc(texto)}</h4>")
    partes = [titulo("Parâmetros adotados"),
              parametros_html(config, periodos, resultados, frequencia, medida_temporal,
                              tabela, rotulo)]
    if resultados:
        partes += [titulo("Indicadores"),
                   indicadores_html(resultados, periodos, kb, config, frequencia, tabela,
                                    rotulo)]
    partes += [titulo("Como funciona"), algoritmo_html(config, medida_temporal,
                                                          len(periodos) if periodos else None)]
    return "\n".join(partes)


# ------------------------------------------------------------------ bibliometria


def metodo_bibliometria_html(tabela=None) -> str:
    """Método da visão geral descritiva, com os parâmetros lidos do código que calcula."""
    tabela = tabela or _tabela_padrao
    s, gama = rajadas.S_PADRAO, rajadas.GAMA_PADRAO
    minimo = rajadas.MINIMO_DOCUMENTOS
    n_vazias = len(termos.PALAVRAS_VAZIAS)
    n_academicas = len(termos.PALAVRAS_ACADEMICAS)
    limite = bibliometria.LIMITE
    parametros = [
        ["Rajadas: razão entre a taxa de rajada e a taxa de base (s)", _decimal(s)],
        ["Rajadas: custo de entrar no estado de rajada (γ)",
         f"{_decimal(gama)} × ln(número de anos)"],
        ["Rajadas: mínimo de documentos do termo", str(minimo)],
        ["Rankings: itens mostrados", str(limite)],
        ["Nuvem de palavras: termos desenhados", "70"],
        ["Nuvem de títulos: palavras vazias (português, espanhol e inglês)", _inteiro(n_vazias)],
        ["Nuvem de títulos: termos acadêmicos genéricos", _inteiro(n_academicas)],
        ["Nuvem de títulos: mínimo para uma expressão de duas palavras", "2 títulos"],
        ["Zipf: posições usadas no ajuste", "até 200"],
        ["Bradford: zonas", "3, com cerca de um terço dos documentos cada"],
    ]
    p = ['<div class="metodo">',
         "<p><strong>Contagens.</strong> Autores, palavras-chave, fontes, instituições e "
         "países contam documentos: cada documento vale 1 para cada nome, por mais que o "
         "nome se repita nele. Quando a base foi editada, vale o nome do grupo; grupos "
         "marcados como parada ficam de fora. As citações são as registradas na base de "
         "origem na data da exportação, somadas por documento.</p>",
         "<p><strong>Produção anual.</strong> O ano é o da data de publicação (ou o ano do "
         "registro, se faltar). A figura mostra os documentos por ano, com os anos vazios "
         "entre o primeiro e o último, e as citações somadas dos documentos publicados em "
         "cada ano, não as citações recebidas naquele ano. O crescimento anual é a taxa "
         "composta entre a produção do primeiro e a do último ano, "
         "(n<sub>último</sub> ÷ n<sub>primeiro</sub>)<sup>1/anos</sup> − 1, e por isso "
         "oscila com um único ano atípico.</p>",
         "<p><strong>Autores, fontes, instituições (IES) e países.</strong> Cada ranking "
         f"mostra os {limite} primeiros por número de documentos, com desempate alfabético, "
         "e as citações somadas desses documentos. As instituições vêm do nome da "
         "organização na afiliação, unificado pelos apelidos cadastrados; os países vêm do "
         "país da afiliação. O <em>índice h</em> de cada autor usa só os documentos do "
         "corpus: é o maior h tal que h de seus documentos têm pelo menos h citações.</p>",
         "<p><strong>Lei de Lotka.</strong> Conta quantos autores publicaram 1, 2, 3… "
         "documentos e compara a proporção observada com a esperada, "
         "(6 ÷ π²) ÷ n². O expoente β é o oposto da inclinação da reta de mínimos quadrados "
         "entre log n e log da proporção de autores, exigindo pelo menos três valores "
         "distintos de n; o valor clássico é 2.</p>",
         "<p><strong>Lei de Bradford.</strong> Ordena as fontes pelo número de documentos e "
         "as divide em três zonas que reúnem cerca de um terço dos documentos cada. A fonte "
         "que cruza o limite fica na zona em que começa. O multiplicador de cada zona é o "
         "número de fontes dela dividido pelo da primeira.</p>",
         "<p><strong>Lei de Zipf.</strong> Ordena as palavras-chave dos autores pela "
         "frequência em documentos e ajusta uma reta, por mínimos quadrados, entre log da "
         "posição e log da frequência, nas primeiras 200 posições. O expoente é o oposto da "
         "inclinação; o valor clássico é 1.</p>",
         "<p><strong>Fluxo Autor – País – IES (Sankey).</strong> Cada faixa liga um nome da "
         "coluna da esquerda a um da coluna seguinte e sua largura é o número de documentos "
         "em que o par aparece. O vínculo autor–instituição é exato quando a base traz a "
         "afiliação de cada autor (Scopus); é inferido quando o documento tem uma só "
         "instituição ou um só país; documentos ambíguos ficam de fora e o relatório diz "
         "quantos. Entram os autores, países e instituições mais frequentes.</p>",
         "<p><strong>Nuvem de palavras-chave.</strong> Mostra as palavras-chave dos autores, "
         "contadas por documento. Os termos que o SciMAT guarda em maiúsculas e com hífen "
         "(STATISTICAL-REASONING) aparecem em forma legível (Statistical reasoning); "
         "as siglas conhecidas (SPSS, PISA) ficam em maiúsculas. O tamanho "
         "da letra cresce com a raiz quadrada da frequência, e as palavras são colocadas em "
         "espiral, do termo mais frequente ao menos frequente, sem sobreposição.</p>",
         "<p><strong>Nuvem de títulos.</strong> Os títulos são quebrados em palavras. Saem as "
         f"palavras com menos de três letras, as {_inteiro(n_vazias)} palavras vazias de "
         f"português, espanhol e inglês (artigos, preposições, conjunções) e os "
         f"{_inteiro(n_academicas)} termos genéricos da escrita acadêmica (como estudo, "
         "análise, research e approach). Singular, plural e acento são unificados, mantendo "
         "a grafia mais frequente, e cada termo vale 1 por título. Expressões de duas "
         "palavras seguidas, sem palavra descartada no meio, aparecem à parte quando se "
         f"repetem em pelo menos 2 títulos.</p>",
         "<p><strong>Rajadas (Kleinberg).</strong> Para cada palavra-chave ou referência, a "
         "série é, ano a ano, o número de documentos que a contêm entre os documentos do ano "
         "que têm algum termo do mesmo tipo. Um autômato de dois estados compara a taxa de "
         f"base do termo, p<sub>0</sub> (total de documentos com o termo ÷ total na base), "
         f"com uma taxa de rajada p<sub>1</sub> = s × p<sub>0</sub>, com s = {_decimal(s)} "
         "(limitada a 0,95). Em cada ano, o custo é o oposto do logaritmo da verossimilhança "
         f"binomial. Subir ao estado de rajada custa γ × ln(n), com γ = {_decimal(gama)} e "
         "n igual ao número de anos; descer é grátis. O caminho de menor custo total, "
         "encontrado por programação dinâmica (Viterbi), define os anos em rajada. A força "
         "é a soma, nesses anos, da diferença entre o custo na taxa de base e na taxa de "
         f"rajada. Só entram termos com pelo menos {minimo} documentos, e cada termo "
         "aparece uma vez, com a rajada mais forte. A contagem é de documentos do corpus "
         "que usam o termo ou citam a referência, e não de citações recebidas, o que difere "
         "do CiteSpace. Séries curtas (menos de 8 anos) ou bases pequenas (menos de 100 "
         "documentos) geram aviso, pois as rajadas ficam instáveis.</p>",
         "</div>",
         tabela(["Parâmetro", "Valor"], [[_esc(a), _esc(b)] for a, b in parametros],
                "Parâmetros da visão geral descritiva.")]
    return "\n".join(p)

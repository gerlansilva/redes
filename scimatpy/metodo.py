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

from . import bibliometria, rajadas, termos
from .clustering import ALGORITMOS
from .similarity import MEDIDAS

_ROTULOS_UNIDADE = {
    "Words": "Palavras-chave",
    "Authors": "Autores",
    "References": "Referências",
    "AuthorsReference": "Autores de referência",
    "ReferenceSources": "Fontes de referência",
    "Countries": "Países",
}

_ITEM_UNIDADE = {
    "Words": "palavras",
    "Authors": "autores",
    "References": "referências",
    "AuthorsReference": "autores de referência",
    "ReferenceSources": "fontes de referência",
    "Countries": "países",
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
    p.append("<p><strong>4. Agrupamento.</strong> " + _texto_algoritmo(config) + "</p>")

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
    p.append("</div>")
    return "\n".join(p)


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
            + f'</div><p class="fonte">{_esc(nota)}</p>')


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
         "com hífen trocado por espaço e em minúsculas, contadas por documento. O tamanho "
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

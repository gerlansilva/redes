"""Fluxo de análise do SciMAT: do banco ao conjunto de agrupamentos medido.

A ordem das etapas é a de `DoAnalysisWorker.doPeriod`:

1. conjunto documental do período (e cópia de trabalho)
2. conjunto agregado, quando a matriz é de acoplamento agregado
3. redução por frequência mínima
4. construção da rede
5. redução por valor mínimo de aresta
6. normalização por medida de similaridade
7. agrupamento
8. centralidade e densidade de Callon, com faixas normalizadas
9. rótulos de agrupamentos e nós
10. mapeamento de documentos
11. índices de desempenho
12. frequência e centralidade dos nós
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import measures
from .aggregate import Agregado
from .clustering import ALGORITMOS, ConjuntoDeAgrupamentos, _verifica
from .dataset import Dataset
from .kb import ProjetoScimat
from .mappers import MAPEADORES, k_core
from .texto import exibe_termo, termo_legivel
from .network import (Rede, rede_acoplamento, rede_acoplamento_agregado,
                      rede_coocorrencia)
from .similarity import normaliza_acoplamento, normaliza_coocorrencia

MATRIZES = ("CoOccurrence", "BasicCoupling", "AggregatedCouplingBasedOnAuthor",
            "AggregatedCouplingBasedOnJournal")


MENSAGEM_MAPEADOR_ACOPLAMENTO = (
    "O mapeador \"acoplamento\" só vale com a matriz de acoplamento básico "
    "(BasicCoupling), em que os nós são documentos; com a matriz {matriz} os "
    "nós são itens. Escolha outro mapeador (núcleo, interseção, união, "
    "secundários ou k-core).")


@dataclass
class Configuracao:
    """Parâmetros de uma análise, equivalentes a `AnalysisConfiguration`."""

    unidade: str = "Words"
    matriz: str = "CoOccurrence"
    similaridade: str = "EquivalenceIndex"
    algoritmo: str = "CentersSimples"
    minimo_frequencia: int = 1
    minimo_coocorrencia: int = 1
    tamanho_minimo: int = 2
    tamanho_maximo: int = 15
    corte: float = 0.0
    mapeadores: tuple[str, ...] = ("nucleo",)
    k_core: int = 2
    palavras: tuple[str, ...] = ("autor", "fonte")
    indices: tuple[str, ...] = ("h", "g", "hg", "q2", "media", "soma", "minimo", "maximo")
    # Itens a descartar antes da rede (termos genéricos como "ESTATISTICA").
    ignorar: tuple[str, ...] = ()
    # Só na unidade Institutions: componente conexo da rede com menos
    # instituições que isto não vira agrupamento (os nós ficam sem agrupamento).
    componente_minimo: int = 3

    def valida(self) -> None:
        if self.unidade not in ("Words", "Authors", "References",
                                "AuthorsReference", "ReferenceSources",
                                "Countries", "Institutions"):
            raise ValueError(f"unidade inválida: {self.unidade}")
        if self.matriz not in MATRIZES:
            raise ValueError(f"matriz inválida: {self.matriz}")
        if self.algoritmo not in ALGORITMOS:
            raise ValueError(f"algoritmo inválido: {self.algoritmo}")
        for mapeador in self.mapeadores:
            if mapeador not in MAPEADORES:
                raise ValueError(f"mapeador inválido: {mapeador}")
        if "acoplamento" in self.mapeadores and self.matriz != "BasicCoupling":
            raise ValueError(MENSAGEM_MAPEADOR_ACOPLAMENTO.format(matriz=self.matriz))
        for origem in self.palavras:
            if origem not in ("autor", "fonte", "adicionada"):
                raise ValueError(f"origem de palavra inválida: {origem}")
        if not math.isfinite(self.corte) or self.corte < 0:
            raise ValueError(f"corte inválido: {self.corte}")
        if self.k_core < 1:
            raise ValueError(f"k-core inválido: {self.k_core}")
        if self.componente_minimo < 1:
            raise ValueError(f"tamanho mínimo do componente inválido: {self.componente_minimo}")


@dataclass
class Grupo:
    """Agrupamento com rótulo, medidas e documentos."""

    nos: list[int]
    principal: int | None
    rotulo: str
    centralidade: float = 0.0
    densidade: float = 0.0
    centralidade_faixa: float = 0.0
    densidade_faixa: float = 0.0
    documentos: dict[str, set[int]] = field(default_factory=dict)
    medidas: dict[str, float] = field(default_factory=dict)
    # Só palavras-chave em co-ocorrência: o rótulo é um termo do SciMAT, que se
    # exibe em forma legível (o `rotulo` guardado não muda).
    legivel: bool = False

    @property
    def exibicao(self) -> str:
        """Rótulo para mostrar: `termo_legivel` nas palavras-chave, o texto como veio nas demais."""
        return termo_legivel(self.rotulo) if self.legivel else self.rotulo

    @property
    def documentos_nucleo(self) -> set[int]:
        return self.documentos.get("nucleo", set())


@dataclass
class ResultadoPeriodo:
    configuracao: Configuracao
    periodo: str
    dataset_original: Dataset
    dataset: Dataset
    rede: Rede
    conjunto: ConjuntoDeAgrupamentos
    grupos: list[Grupo]
    frequencia_nos: dict[int, int]
    centralidades: dict[str, dict[int, float]]
    agregado: Agregado | None = None
    rotulos: dict[int, str] = field(default_factory=dict)
    # Rede de IES: uniões de variantes feitas e componentes deixados sem agrupamento.
    ies: dict | None = None

    def rotulo(self, no: int) -> str:
        """Rótulo de um nó para exibição: título do documento ou nome do item.

        O nome do item (palavra-chave do SciMAT em caixa alta) sai em forma
        legível; o dado guardado em `dataset.itens` não muda.
        """
        titulo = self.rotulos.get(no)
        if titulo:
            return titulo
        return exibe_termo(self.configuracao.unidade, self.dataset.itens.get(no, str(no)))

    def exibe(self, texto) -> str:
        """Forma de exibição de um termo desta análise (só palavras-chave em co-ocorrência)."""
        cfg = self.configuracao
        if cfg.matriz != "CoOccurrence":
            return "" if texto is None else str(texto)
        return exibe_termo(cfg.unidade, texto)

    def item(self, no: int) -> str:
        """Como `rotulo`, mas com o nome do item na frente do título (nós que são itens)."""
        nome = self.dataset.itens.get(no)
        if nome:
            return exibe_termo(self.configuracao.unidade, nome)
        return self.rotulos.get(no) or str(no)


def executa_periodo(projeto: ProjetoScimat, periodo_id: int, periodo_nome: str,
                    config: Configuracao, cancelado=None) -> ResultadoPeriodo:
    """Executa a análise de um período inteiro.

    `cancelado` é um callback sem argumentos; quando devolve verdadeiro a
    análise para na próxima verificação (entre as etapas e dentro do
    agrupamento) levantando `clustering.Cancelado`.
    """
    config.valida()

    original = projeto.dataset(config.unidade, periodo_id, config.palavras)
    dataset = original.clone()
    agregado = None

    if config.matriz == "AggregatedCouplingBasedOnAuthor":
        agregado = Agregado.por_autor(projeto.conexao, dataset)
    elif config.matriz == "AggregatedCouplingBasedOnJournal":
        agregado = Agregado.por_periodico(projeto.conexao, dataset)

    if config.ignorar:
        _remove_ignorados(dataset, config.ignorar)
    dataset.filtra_itens_por_frequencia(config.minimo_frequencia)

    if config.matriz == "CoOccurrence":
        rede = rede_coocorrencia(dataset)
    elif config.matriz == "BasicCoupling":
        rede = rede_acoplamento(dataset, cancelado)
    else:
        rede = rede_acoplamento_agregado(agregado, dataset, cancelado)

    _verifica(cancelado)
    rede.filtra_por_valor(config.minimo_coocorrencia)

    if config.matriz == "CoOccurrence":
        normaliza_coocorrencia(dataset, rede, config.similaridade)
    else:
        normaliza_acoplamento(dataset if agregado is None else agregado,
                              rede, config.similaridade)

    _verifica(cancelado)
    conjunto = ALGORITMOS[config.algoritmo](rede, config.tamanho_minimo,
                                            config.tamanho_maximo, config.corte,
                                            cancelado=cancelado)
    info_ies = None
    if config.unidade == "Institutions":
        conjunto, pequenos = _descarta_componentes_pequenos(
            rede, conjunto, config.componente_minimo)
        indice = projeto.indice_ies()
        info_ies = {
            "componente_minimo": config.componente_minimo,
            "unioes": indice.unioes,
            "variantes_unidas": indice.quantidade_variantes_unidas(),
            "componentes": sorted((len(c) for c in rede.componentes()), reverse=True),
            "componentes_pequenos": [
                [dataset.itens.get(no, str(no)) for no in comp] for comp in pequenos],
            "isolados": sum(1 for c in rede.componentes() if len(c) == 1),
        }

    # No acoplamento os nós são documentos; o rótulo vem do título.
    rotulos = (projeto.titulos(rede.nos)
               if config.matriz != "CoOccurrence" else {})

    grupos = []
    for agrupamento in conjunto.agrupamentos:
        grupos.append(Grupo(
            nos=list(agrupamento.nos),
            principal=agrupamento.principal,
            rotulo=_rotulo(dataset, agrupamento.principal, rotulos),
            legivel=(config.unidade == "Words" and config.matriz == "CoOccurrence"),
        ))

    for grupo in grupos:
        _verifica(cancelado)
        grupo.centralidade = measures.centralidade_callon(rede, grupo.nos)
        grupo.densidade = measures.densidade_callon(rede, grupo.nos)

    for medida, campo in (("centralidade", "centralidade_faixa"),
                          ("densidade", "densidade_faixa")):
        faixas = measures.faixa_normalizada([getattr(g, medida) for g in grupos])
        for grupo, faixa in zip(grupos, faixas):
            setattr(grupo, campo, faixa)

    for grupo in grupos:
        _verifica(cancelado)
        _mapeia_documentos(rede, dataset, agregado, grupo, config)
        _calcula_indices(dataset, grupo, config)

    if agregado is not None:
        frequencia = {no: agregado.frequencia_documento_item(no) for no in rede.nos}
    elif config.matriz != "CoOccurrence":      # acoplamento: os nós são documentos
        frequencia = {no: dataset.frequencia_documento_item(no) for no in rede.nos}
    else:
        frequencia = {no: dataset.frequencia_item(no) for no in rede.nos}
    centralidades = measures.Centralidades(rede)

    return ResultadoPeriodo(
        configuracao=config,
        periodo=periodo_nome,
        dataset_original=original,
        dataset=dataset,
        rede=rede,
        conjunto=conjunto,
        grupos=grupos,
        frequencia_nos=frequencia,
        centralidades=centralidades,
        agregado=agregado,
        rotulos=rotulos,
        ies=info_ies,
    )


def _descarta_componentes_pequenos(rede: Rede, conjunto: ConjuntoDeAgrupamentos,
                                   minimo: int):
    """Tira dos agrupamentos os componentes conexos com menos de `minimo` nós.

    Um agrupamento nunca atravessa componentes, então basta olhar o componente
    de qualquer nó dele. Os nós dos componentes pequenos ficam sem agrupamento
    (e, portanto, fora dos halos). Devolve (conjunto, componentes pequenos).
    """
    if minimo <= 1:
        return conjunto, []
    pequenos = [c for c in rede.componentes() if len(c) < minimo]
    if not pequenos:
        return conjunto, []
    fora = {no for comp in pequenos for no in comp}
    novo = ConjuntoDeAgrupamentos(rede)
    for agrupamento in conjunto.agrupamentos:
        if not any(no in fora for no in agrupamento.nos):
            novo.adiciona(agrupamento.nos, agrupamento.principal)
    # Só os componentes com mais de um nó: o isolado não é "componente" para o leitor.
    return novo, [c for c in pequenos if len(c) > 1]


def _remove_ignorados(dataset: Dataset, ignorar) -> None:
    """Remove os itens cujo rótulo está na lista (sem caixa nem acento)."""
    from .text_utils import chave

    alvos = {chave(nome) for nome in ignorar if chave(nome)}
    for item_id in dataset.lista_itens():
        if chave(dataset.itens[item_id]) in alvos:
            dataset.remove_item(item_id)


def _rotulo(dataset: Dataset, principal: int | None,
            rotulos: dict[int, str] | None = None) -> str:
    if principal is None:
        return ""
    if rotulos and principal in rotulos:
        return rotulos[principal]
    return dataset.itens.get(principal, str(principal))


def _mapeia_documentos(rede: Rede, dataset: Dataset, agregado: Agregado | None,
                       grupo: Grupo, config: Configuracao) -> None:
    fonte = agregado if agregado is not None else dataset
    for nome in config.mapeadores:
        if nome == "kcore":
            grupo.documentos[nome] = k_core(fonte, grupo.nos, config.k_core)
        else:
            grupo.documentos[nome] = MAPEADORES[nome](rede, fonte, grupo.nos)


def _calcula_indices(dataset: Dataset, grupo: Grupo, config: Configuracao) -> None:
    """Índices de desempenho para cada conjunto de documentos mapeado."""
    for nome, documentos in grupo.documentos.items():
        ordenados = sorted(documentos)
        citacoes = [dataset.citacoes(doc) for doc in ordenados]

        prefixo = f"{nome}:"
        grupo.medidas[prefixo + "documentos"] = float(len(ordenados))
        if "h" in config.indices:
            grupo.medidas[prefixo + "h"] = float(measures.indice_h(citacoes))
        if "g" in config.indices:
            grupo.medidas[prefixo + "g"] = float(measures.indice_g(citacoes))
        if "hg" in config.indices:
            grupo.medidas[prefixo + "hg"] = float(measures.indice_hg(citacoes))
        if "q2" in config.indices:
            grupo.medidas[prefixo + "q2"] = float(measures.indice_q2(citacoes))
        if "media" in config.indices:
            grupo.medidas[prefixo + "media"] = measures.media_citacoes(dataset, ordenados)
        if "soma" in config.indices:
            grupo.medidas[prefixo + "soma"] = float(measures.soma_citacoes(dataset, ordenados))
        if "minimo" in config.indices:
            grupo.medidas[prefixo + "minimo"] = float(measures.minimo_citacoes(dataset, ordenados))
        if "maximo" in config.indices:
            grupo.medidas[prefixo + "maximo"] = float(measures.maximo_citacoes(dataset, ordenados))

"""Servidor local da interface web do scimatpy.

Sem dependências além da biblioteca padrão: o navegador só envia parâmetros e
recebe JSON; toda a análise roda no processo Python, com o mesmo núcleo do CLI.
O servidor escuta apenas em 127.0.0.1 e não expõe nada fora da máquina.
"""

from __future__ import annotations

import csv
import json
import re
import secrets
import sqlite3
import tempfile
import threading
import traceback
import webbrowser
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import build
from .grade import grade as combinacoes_grade
from .kb import ProjetoScimat
from .mappers import MAPEADORES
from .pipeline import Configuracao, executa_periodo
from .projeto import EXTENSAO, NOME_PADRAO, e_projeto, nome_de_projeto
from .viz.halo import UNIDADE_TITULO, halo_svg, layout_halo
from .viz.mapa import (colaboracao_do_periodo, dados_mapa as mapa_interativo,
                       mapa_svg)
from .viz.strategic import dados_diagrama, diagrama_svg
from .viz.cluster import rede_de_agrupamentos_svg

FORMATOS = ("csv", "bibtex", "ris", "openalex", "wos", "scopus", "zotero")
UNIDADES = ("Words", "Authors", "References", "AuthorsReference",
            "ReferenceSources", "Countries")
MATRIZES = ("CoOccurrence", "BasicCoupling", "AggregatedCouplingBasedOnAuthor",
            "AggregatedCouplingBasedOnJournal")
SIMILARIDADES = ("EquivalenceIndex", "AssociationStrength", "InclusionIndex",
                 "JaccardIndex", "SaltonCosine")
ALGORITMOS = ("CentersSimples", "AverageLink", "CompleteLink", "SingleLink",
              "SumLink", "Louvain")

QUADRANTES = {
    "motor": "Temas motores",
    "nicho": "Temas de nicho",
    "emergente": "Temas emergentes ou em declínio",
    "basico": "Temas básicos e transversais",
}

CACHE = Path(tempfile.mkdtemp(prefix="scimatpy-web-"))
ANALISES: "OrderedDict[str, dict]" = OrderedDict()
FIGURAS: dict[str, Path] = {}
ARQUIVOS: dict[str, Path] = {}
RELATORIOS: "OrderedDict[str, Path]" = OrderedDict()
TRAVA_REGISTRO = threading.Lock()
TRABALHOS: dict[str, "Trabalho"] = {}
TRAVA_TRABALHOS = threading.Lock()


class ErroApi(Exception):
    """Erro previsto, devolvido ao cliente com mensagem legível."""


class ErroExpirado(ErroApi):
    """A análise pedida não está mais na memória do servidor (HTTP 410)."""


MENSAGEM_EXPIRADA = (
    "Esta análise não está mais na memória do servidor (ele foi reiniciado ou "
    "ela foi substituída por análises mais recentes). Clique em "
    "Pré-visualizar para gerar de novo.")
MENSAGEM_SEM_TOKEN = (
    "Falta o identificador da análise. Clique em Pré-visualizar para gerar a "
    "análise antes de abrir este recurso.")
# Quantas análises mantêm a rede e o resultado completos em memória; as demais
# são recalculadas sob demanda a partir dos parâmetros guardados.
ANALISES_PESADAS = 3
MAXIMO_ANALISES = 40
TRAVA_RECALCULO = threading.RLock()


def _token(valor) -> str:
    """Normaliza o token vindo da URL; ``null``/``undefined`` contam como vazio."""
    texto = str(valor or "").strip()
    return "" if texto.lower() in ("null", "undefined", "none") else texto


def _param(parametros: dict, nome: str) -> str:
    """Primeiro valor de um parâmetro da URL ou texto vazio."""
    return (parametros.get(nome) or [""])[0]


def _analise(token) -> dict:
    """Registro da análise pelo token, com mensagem clara se não existir."""
    token = _token(token)
    if not token:
        raise ErroApi(MENSAGEM_SEM_TOKEN)
    with TRAVA_REGISTRO:
        analise = ANALISES.get(token)
        if analise is not None:
            ANALISES.move_to_end(token)
    if analise is None:
        raise ErroExpirado(MENSAGEM_EXPIRADA)
    return analise


def _poda_pesados() -> None:
    """Libera rede e resultado de tudo, menos das análises mais recentes."""
    with TRAVA_REGISTRO:
        recentes = list(ANALISES.values())[-ANALISES_PESADAS:]
        for analise in ANALISES.values():
            if not any(analise is r for r in recentes):
                analise["rede"] = None
                analise["resultado"] = None


def _recalcula(analise: dict) -> None:
    """Refaz resultado e rede de uma análise cujos dados pesados foram liberados."""
    with TRAVA_RECALCULO:
        if analise.get("resultado") is None:
            caminho = Path(analise["projeto"])
            if not caminho.exists():
                raise ErroExpirado(
                    f"O projeto desta análise não existe mais: {caminho}")
            with ProjetoScimat(caminho) as kb:
                analise["resultado"] = executa_periodo(
                    kb, analise["periodo_id"], analise["periodo"],
                    analise["config"])
            analise["rede"] = None
        if analise.get("rede") is None:
            # O layout é a etapa mais cara: só roda quando a tela pede a rede
            # ou a figura, não na própria prévia.
            analise["rede"] = layout_halo(analise["resultado"])
    _poda_pesados()


PREGUICOSAS: dict[str, object] = {}


def _registra(destino: Path, registro: dict[str, Path], gerador=None) -> str:
    """Registra um arquivo servido por token; ``gerador`` o cria sob demanda."""
    token = secrets.token_urlsafe(12)
    with TRAVA_REGISTRO:
        registro[token] = destino
        if gerador is not None:
            PREGUICOSAS[token] = gerador
    return token


def _materializa(token: str, arquivo: Path) -> None:
    """Gera a figura preguiçosa na primeira requisição."""
    with TRAVA_RECALCULO:
        gerador = PREGUICOSAS.get(token)
        if gerador is not None and not arquivo.exists():
            gerador()
        PREGUICOSAS.pop(token, None)


def _medidas(grupo) -> dict:
    """Agrupa `mapeador:índice` em `{mapeador: {índice: valor}}`."""
    resultado: dict[str, dict[str, float]] = {}
    for chave, valor in grupo.medidas.items():
        mapeador, _, indice = chave.partition(":")
        resultado.setdefault(mapeador, {})[indice] = round(valor, 2)
    return resultado


def _metricas_paises(paises: dict) -> list[tuple[str, str]]:
    total = paises["total"] or 1
    return [
        (f"{paises['total']}", "documentos"),
        (f"{len(paises['documentos'])}", "países"),
        (f"{len(paises['ligacoes'])}", "cooperações"),
        (f"{paises['densidade']:.1%}".replace(".", ","), "densidade da rede"),
        (f"{paises['grau_medio']:.1f}".replace(".", ","), "cooperações por país"),
        (f"{paises['internacionais'] / total:.1%}".replace(".", ","),
         "coautoria internacional"),
    ]


def _quadrante(centralidade: float, densidade: float) -> str:
    if centralidade >= 0.5 and densidade >= 0.5:
        return "motor"
    if centralidade < 0.5 and densidade >= 0.5:
        return "nicho"
    if centralidade >= 0.5:
        return "basico"
    return "emergente"


def _config(dados: dict) -> Configuracao:
    unidade = dados.get("unidade", "Words")
    matriz = dados.get("matriz", "CoOccurrence")
    similaridade = dados.get("similaridade", "EquivalenceIndex")
    algoritmo = dados.get("algoritmo", "CentersSimples")

    if unidade not in UNIDADES:
        raise ErroApi(f"Unidade de análise inválida: {unidade!r}. "
                      f"Use uma destas: {', '.join(UNIDADES)}.")
    if matriz not in MATRIZES:
        raise ErroApi(f"Matriz inválida: {matriz!r}. "
                      f"Use uma destas: {', '.join(MATRIZES)}.")
    if similaridade not in SIMILARIDADES:
        raise ErroApi(f"Medida de similaridade inválida: {similaridade!r}. "
                      f"Use uma destas: {', '.join(SIMILARIDADES)}.")
    if algoritmo not in ALGORITMOS:
        raise ErroApi(f"Algoritmo de agrupamento inválido: {algoritmo!r}. "
                      f"Use um destes: {', '.join(ALGORITMOS)}.")

    def inteiro(nome: str, padrao: int, minimo: int = 0) -> int:
        bruto = dados.get(nome)
        # Campo vazio na tela chega como "" ou null: vale o padrão.
        if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
            return padrao
        try:
            numero = float(str(bruto).replace(",", ".")) if isinstance(
                bruto, str) else float(bruto)
            if numero != int(numero):
                raise ValueError
            valor = int(numero)
        except (TypeError, ValueError, OverflowError):
            raise ErroApi(
                f"\"{nome}\" precisa ser um número inteiro (recebido: "
                f"{bruto!r})") from None
        if valor < minimo:
            raise ErroApi(f"\"{nome}\" precisa ser pelo menos {minimo} "
                          f"(recebido: {valor})")
        return valor

    minimo = inteiro("minimo_frequencia", 1, 1)
    tamanho_minimo = inteiro("tamanho_minimo", 2, 1)
    maximo = inteiro("tamanho_maximo", 15, 1)
    if tamanho_minimo > maximo:
        raise ErroApi("o tamanho mínimo da rede não pode passar do máximo")

    mapeadores = dados["mapeadores"] if dados.get("mapeadores") is not None else [
        "nucleo", "interseccao"]
    if isinstance(mapeadores, str):
        mapeadores = [mapeadores]
    desconhecidos = [m for m in mapeadores if m not in MAPEADORES]
    if desconhecidos:
        raise ErroApi(f"mapeador inválido: {desconhecidos[0]}")

    palavras = dados["palavras"] if dados.get("palavras") is not None else [
        "autor", "fonte"]
    if isinstance(palavras, str):
        palavras = [palavras]
    invalidas = [p for p in palavras if p not in ("autor", "fonte", "adicionada")]
    if invalidas:
        raise ErroApi(f"origem de palavra inválida: {invalidas[0]}")

    indices = dados.get("indices") or [
        "h", "g", "hg", "q2", "media", "soma", "minimo", "maximo"]
    if isinstance(indices, str):
        indices = [indices]
    invalidos = [i for i in indices if i not in
                 ("h", "g", "hg", "q2", "media", "soma", "minimo", "maximo")]
    if invalidos:
        raise ErroApi(f"índice inválido: {invalidos[0]}")

    bruto_corte = dados.get("corte")
    if bruto_corte is None or (isinstance(bruto_corte, str)
                               and not bruto_corte.strip()):
        corte = 0.0
    else:
        try:
            corte = float(str(bruto_corte).replace(",", "."))
        except (TypeError, ValueError):
            raise ErroApi(
                f"\"corte\" precisa ser numérico (recebido: {bruto_corte!r})"
            ) from None
    if corte < 0:
        raise ErroApi("\"corte\" não pode ser negativo")

    ignorar = dados.get("ignorar") or []
    if isinstance(ignorar, str):
        ignorar = [t for t in re.split(r"[;\n]", ignorar) if t.strip()]
    if not isinstance(ignorar, (list, tuple)):
        raise ErroApi("\"ignorar\" precisa ser uma lista de termos")

    return Configuracao(
        ignorar=tuple(str(t).strip() for t in ignorar if str(t).strip()),
        unidade=unidade,
        matriz=matriz,
        similaridade=similaridade,
        algoritmo=algoritmo,
        minimo_frequencia=minimo,
        minimo_coocorrencia=inteiro("minimo_coocorrencia", 1, 1),
        tamanho_minimo=tamanho_minimo,
        tamanho_maximo=maximo,
        corte=corte,
        mapeadores=tuple(mapeadores),
        k_core=inteiro("k_core", 2, 1),
        palavras=tuple(palavras),
        indices=tuple(indices),
    )


def _valida_projeto(caminho: str) -> Path:
    if not caminho:
        raise ErroApi(f"Informe o caminho do projeto ({EXTENSAO}). Abra um "
                      "projeto na lista ou importe um corpus.")
    destino = Path(caminho).expanduser().resolve()
    if not destino.exists() or not destino.is_file():
        raise ErroApi(f"Projeto não encontrado: {destino}. Ele pode ter sido "
                      "movido ou apagado; abra-o de novo na lista.")
    if not e_projeto(destino):
        raise ErroApi(f"O projeto precisa ser um arquivo {EXTENSAO} "
                      "(projetos antigos .scimat também abrem).")
    return destino


def _periodo(kb: ProjetoScimat, identificador):
    """Período pelo id, pelo nome ou por ``{"id": ..., "nome": ...}``.

    Um período chamado "2020" (nome numérico) não pode ser confundido com o
    período de id 2020: o id vence só quando existe; senão vale o nome.
    """
    periodos = kb.periodos()
    if not periodos:
        raise ErroApi("O projeto não tem períodos. Crie um na aba Base.")

    if isinstance(identificador, dict):
        identificador = identificador.get("id", identificador.get("nome"))
    if isinstance(identificador, str):
        identificador = identificador.strip()
    if identificador in (None, "", "todos"):
        return periodos[0]

    texto = str(identificador)
    for periodo in periodos:
        if texto == str(periodo.id):
            return periodo
    for periodo in periodos:
        if texto == periodo.nome or texto.casefold() == periodo.nome.casefold():
            return periodo
    nomes = ", ".join(f"{p.nome} (id {p.id})" for p in periodos)
    raise ErroApi(f"Período desconhecido: {identificador!r}. "
                  f"Períodos do projeto: {nomes}.")


def descreve_projeto(caminho: Path) -> dict:
    with ProjetoScimat(caminho) as kb:
        periodos = kb.periodos()
        documentos = kb.conexao.execute(
            "SELECT COUNT(*) FROM Document").fetchone()[0]
    nome = caminho.parent.name if nome_de_projeto(caminho) else caminho.stem
    return {
        "nome": nome,
        "caminho": str(caminho),
        "documentos": documentos,
        "periodos": [
            {"id": periodo.id, "nome": periodo.nome,
             "posicao": periodo.posicao}
            for periodo in periodos
        ],
        "unidades": list(UNIDADES),
    }


def analisa(dados: dict) -> dict:
    caminho = _valida_projeto(dados.get("projeto", ""))
    config = _config(dados)

    with ProjetoScimat(caminho) as kb:
        periodo = _periodo(kb, dados.get("periodo"))
        resultado = executa_periodo(kb, periodo.id, periodo.nome, config)
        paises = (colaboracao_do_periodo(kb, periodo.id, config.minimo_frequencia)
                  if config.unidade == "Countries"
                  and config.matriz == "CoOccurrence" else None)

    grupos = sorted(resultado.grupos,
                    key=lambda grupo: (-len(grupo.nos), grupo.rotulo or "Sem grupo"))
    faixas = {"motor": 0, "nicho": 0, "emergente": 0, "basico": 0}
    saida_grupos = []

    for indice, grupo in enumerate(grupos, start=1):
        quadrante = _quadrante(grupo.centralidade_faixa, grupo.densidade_faixa)
        faixas[quadrante] += 1
        saida_grupos.append({
            "selo": indice,
            "rotulo": grupo.rotulo,
            "itens": len(grupo.nos),
            "centralidade": round(grupo.centralidade, 1),
            "densidade": round(grupo.densidade, 1),
            "centralidade_faixa": round(grupo.centralidade_faixa, 3),
            "densidade_faixa": round(grupo.densidade_faixa, 3),
            "quadrante": quadrante,
            "documentos": len(grupo.documentos_nucleo),
            "medidas": _medidas(grupo),
            "nos": [resultado.rotulo(no) for no in grupo.nos],
        })

    detalhes = {}
    for indice, grupo in enumerate(grupos, start=1):
        itens = []
        for no in grupo.nos:
            itens.append({
                "rotulo": resultado.rotulo(no),
                "frequencia": resultado.frequencia_nos.get(
                    no, resultado.dataset.frequencia_item(no)),
                "grau": round(resultado.centralidades.get("grau", {}).get(no, 0), 2),
                "documentos": len(resultado.dataset.documentos_do_item(no)),
            })

        documentos = set(grupo.documentos_nucleo)
        if not documentos:
            for no in grupo.nos:
                documentos.update(resultado.dataset.documentos_do_item(no))

        detalhes[indice] = {
            "grupo": saida_grupos[indice - 1],
            "itens": sorted(itens, key=lambda item: -item["frequencia"]),
            "documentos": sorted(documentos),
            "medidas": _medidas(grupo),
            "documentos_por_mapeador": {
                nome: sorted(ids) for nome, ids in grupo.documentos.items()},
        }

    mapa_dados = (mapa_interativo(paises["documentos"], paises["ligacoes"],
                                  destaque=paises["mais_conectado"])
                  if paises and paises["documentos"] else None)
    diagrama_dados = dados_diagrama(saida_grupos, config.unidade)
    token = secrets.token_urlsafe(10)
    with TRAVA_REGISTRO:
        # Só as análises mais recentes mantêm a rede e o resultado completos em
        # memória (são grandes: dezenas de milhares de arestas). As demais
        # guardam os parâmetros e são recalculadas sob demanda quando a tela
        # volta a elas, em vez de responder "expirada".
        registro = ANALISES[token] = {"projeto": str(caminho), "grupos": detalhes,
                           "rede": None, "mapa": mapa_dados,
                           "diagrama": diagrama_dados,
                           "periodo_id": periodo.id,
                           "periodo": periodo.nome, "resultado": resultado,
                           "config": config}
        while len(ANALISES) > MAXIMO_ANALISES:
            ANALISES.popitem(last=False)
    _poda_pesados()

    figuras = {}
    pasta = None
    if grupos:
        pasta = CACHE / secrets.token_hex(6)
        pasta.mkdir(parents=True, exist_ok=True)

        halo = pasta / "halo.svg"

        def gera_halo(registro=registro, halo=halo, periodo_nome=periodo.nome,
                      unidade=config.unidade):
            _recalcula(registro)
            halo.write_text(
                halo_svg(registro["resultado"],
                         f"Rede de {UNIDADE_TITULO.get(unidade, 'itens')} — "
                         f"{periodo_nome}", layout=registro["rede"]),
                encoding="utf-8")

        figuras["halo"] = f"/figura/{_registra(halo, FIGURAS, gera_halo)}"

        estrategico = pasta / "estrategico.svg"
        estrategico.write_text(
            diagrama_svg(resultado, f"Diagrama estratégico — {periodo.nome}"),
            encoding="utf-8")
        figuras["estrategico"] = f"/figura/{_registra(estrategico, FIGURAS)}"

        agrupamentos = pasta / "agrupamentos.svg"

        def gera_agrupamentos(registro=registro, agrupamentos=agrupamentos,
                              periodo_nome=periodo.nome):
            _recalcula(registro)
            agrupamentos.write_text(
                rede_de_agrupamentos_svg(
                    registro["resultado"],
                    f"Rede de agrupamentos — {periodo_nome}"),
                encoding="utf-8")

        figuras["agrupamentos"] = (
            f"/figura/{_registra(agrupamentos, FIGURAS, gera_agrupamentos)}")

    if paises and paises["documentos"]:
        if pasta is None:
            pasta = CACHE / secrets.token_hex(6)
        pasta.mkdir(parents=True, exist_ok=True)
        mapa = pasta / "mapa.svg"
        mapa.write_text(
            mapa_svg(
                paises["documentos"], paises["ligacoes"],
                destaque=paises["mais_conectado"],
                subtitulo=(f"{paises['total']} documentos · "
                           f"{len(paises['documentos'])} países · "
                           f"{len(paises['ligacoes'])} cooperações"),
                legenda=(f"Coautoria internacional: {paises['internacionais']} de "
                         f"{paises['total']} documentos "
                         f"({paises['internacionais'] / max(1, paises['total']):.1%})"
                         .replace(".", ",")),
                metricas=_metricas_paises(paises),
            ),
            encoding="utf-8")
        figuras["mapa"] = f"/figura/{_registra(mapa, FIGURAS)}"

    total = len(grupos)
    avisos, genericos = _avisos(resultado, config, saida_grupos)
    return {
        "token": token,
        "projeto": str(caminho),
        "periodo": {"id": periodo.id, "nome": periodo.nome},
        "parametros": {
            "unidade": config.unidade,
            "matriz": config.matriz,
            "similaridade": config.similaridade,
            "algoritmo": config.algoritmo,
            "minimo_frequencia": config.minimo_frequencia,
            "minimo_coocorrencia": config.minimo_coocorrencia,
            "tamanho_minimo": config.tamanho_minimo,
            "tamanho_maximo": config.tamanho_maximo,
            "corte": config.corte,
            "mapeadores": list(config.mapeadores),
            "k_core": config.k_core,
            "palavras": list(config.palavras),
            "indices": list(config.indices),
            "ignorar": list(config.ignorar),
        },
        "avisos": avisos,
        "termos_genericos": genericos,
        "resumo": {
            "documentos": resultado.dataset_original.quantidade_documentos(),
            "itens": resultado.dataset_original.quantidade_itens(),
            "itens_reduzidos": resultado.dataset.quantidade_itens(),
            "grupos": total,
            "maior_grupo": max((len(g.nos) for g in grupos), default=0),
            "grupos_unitarios": sum(1 for g in grupos if len(g.nos) == 1),
            "nos": resultado.rede.quantidade_nos(),
            "arestas": resultado.rede.quantidade_arestas(),
            "centralidade_media": round(
                sum(g.centralidade for g in grupos) / total, 1) if total else 0.0,
            "densidade_media": round(
                sum(g.densidade for g in grupos) / total, 1) if total else 0.0,
        },
        "grupos": saida_grupos,
        "quadrantes": faixas,
        "figuras": figuras,
        "paises": ({
            "paises": len(paises["documentos"]),
            "documentos": paises["total"],
            "cooperacoes": len(paises["ligacoes"]),
            "internacionais": paises["internacionais"],
            "densidade": round(paises["densidade"], 4),
            "grau_medio": round(paises["grau_medio"], 2),
            "mais_conectado": paises["mais_conectado"],
            "grau_maximo": paises["grau_maximo"],
        } if paises else None),
    }


LIMITE_GENERICO = 0.35
LIMITE_GRUPOS_FRACOS = 0.5


def _avisos(resultado, config, saida_grupos) -> tuple[list[dict], list[dict]]:
    """Alertas de leitura: frequência mínima baixa e termo genérico dominante."""
    avisos: list[dict] = []
    total_docs = resultado.dataset_original.quantidade_documentos()

    if (saida_grupos and "nucleo" in config.mapeadores
            and config.matriz == "CoOccurrence"):
        fracos = sum(1 for g in saida_grupos if g["documentos"] <= 1)
        if fracos / len(saida_grupos) > LIMITE_GRUPOS_FRACOS:
            sugerida = 2
            avisos.append({
                "codigo": "grupos_fracos",
                "mensagem": (
                    f"{fracos} de {len(saida_grupos)} agrupamentos "
                    f"({fracos / len(saida_grupos):.0%}) têm no máximo um "
                    "documento. Com frequência mínima "
                    f"{config.minimo_frequencia}, itens raros formam grupos "
                    f"sem sustentação; experimente frequência mínima "
                    f"{sugerida} ou maior."),
                "frequencia_sugerida": sugerida,
            })

    genericos = []
    if total_docs >= 10:
        original = resultado.dataset_original
        for item_id in original.lista_itens():
            frequencia = original.frequencia_item(item_id)
            if frequencia / total_docs >= LIMITE_GENERICO:
                genericos.append({
                    "rotulo": original.rotulo_item(item_id),
                    "documentos": frequencia,
                    "proporcao": round(frequencia / total_docs, 3),
                })
        genericos.sort(key=lambda g: -g["documentos"])
        genericos = genericos[:10]
        from .text_utils import chave
        ignorados = {chave(t) for t in config.ignorar}
        pendentes = [g for g in genericos if chave(g["rotulo"]) not in ignorados]
        if pendentes:
            nomes = ", ".join(f"{g['rotulo']} ({g['proporcao']:.0%})"
                              for g in pendentes[:5])
            avisos.append({
                "codigo": "termo_generico",
                "mensagem": (
                    f"Termo(s) presente(s) em pelo menos "
                    f"{LIMITE_GENERICO:.0%} dos documentos: {nomes}. Eles "
                    "dominam a rede e escondem a estrutura; considere "
                    "ignorá-los (parâmetro \"ignorar\")."),
            })
    return avisos, genericos


def _documentos_do_projeto(projeto: str, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    marcadores = ",".join("?" for _ in ids)
    with ProjetoScimat(projeto) as kb:
        linhas = kb.conexao.execute(
            "SELECT d.idDocument, d.title, d.year, d.authors, "
            "d.citationsCount, j.source "
            "FROM Document d LEFT JOIN Journal j "
            "ON j.idJournal = d.Journal_idJournal "
            f"WHERE d.idDocument IN ({marcadores}) "
            "ORDER BY d.idDocument", ids).fetchall()
    return [
        {
            "id": linha["idDocument"],
            "titulo": linha["title"] or "",
            "ano": linha["year"] or "",
            "autores": linha["authors"] or "",
            "citacoes": linha["citationsCount"] or 0,
            "fonte": linha["source"] or "",
        }
        for linha in linhas
    ]


def dados_do_diagrama(token: str) -> dict:
    analise = _analise(token)
    if analise.get("diagrama") is None:
        raise ErroApi("Esta análise não gerou diagrama estratégico (não há "
                      "agrupamentos). Ajuste os parâmetros e pré-visualize.")
    return analise["diagrama"]


def dados_do_mapa(token: str) -> dict:
    analise = _analise(token)
    if analise.get("mapa") is None:
        unidade = analise["config"].unidade if analise.get("config") else ""
        if unidade != "Countries":
            raise ErroApi("O mapa-múndi só existe para a unidade Países. Esta "
                          "análise usa outra unidade; escolha Países "
                          "(colaboração entre países) e pré-visualize.")
        raise ErroApi("Nenhum documento deste período tem país identificado "
                      "nas afiliações, então não há o que desenhar no mapa.")
    return analise["mapa"]


def dados_rede(token: str) -> dict:
    analise = _analise(token)
    if analise.get("rede") is None:
        _recalcula(analise)
    return analise["rede"]


def exportar(token: str, tipo: str) -> tuple[bytes, str, str]:
    """Gera uma exportação da análise corrente.

    Devolve ``(conteúdo, nome do arquivo, tipo MIME)``. Os formatos são os do
    fork (Pajek, XML de grupos) mais GraphML, TSV de índices e TSV de
    documentos.
    """
    from . import exports

    analise = _analise(token)
    if analise.get("resultado") is None:
        _recalcula(analise)
    resultado = analise["resultado"]

    if tipo == "grupos-xml":
        with ProjetoScimat(analise["projeto"]) as kb:
            texto = exports.grupos_xml(kb.conexao)
        return texto.encode("utf-8"), "grupos.xml", "application/xml"

    rotulos = resultado.dataset.itens
    if tipo == "rede-pajek":
        texto = exports.pajek(resultado.rede, rotulos)
        return texto.encode("utf-8"), "rede.net", "text/plain"
    if tipo == "rede-graphml":
        texto = exports.graphml(resultado.rede, rotulos, resultado.grupos)
        return texto.encode("utf-8"), "rede.graphml", "application/xml"
    if tipo == "indices-tsv":
        texto = exports.indices_tsv(resultado)
        return texto.encode("utf-8"), "indices.tsv", "text/tab-separated-values"
    if tipo == "documentos-tsv":
        dados = lista_documentos(token)
        linhas = ["id\ttitulo\tano\tautores\tcitacoes\tfonte"]
        for item in dados["documentos"]:
            linhas.append("\t".join(
                str(item[campo]) for campo in
                ("id", "titulo", "ano", "autores", "citacoes", "fonte")))
        return ("\n".join(linhas) + "\n").encode("utf-8"), "documentos.tsv", \
            "text/tab-separated-values"

    raise ErroApi(f"Tipo de exportação desconhecido: {tipo!r}. Use: grupos-xml, "
                  "rede-pajek, rede-graphml, indices-tsv ou documentos-tsv.")


def lista_documentos(token: str, busca: str = "") -> dict:
    """Documentos do período da análise, com busca por título, autor ou fonte."""
    analise = _analise(token)

    termo = (busca or "").strip().lower()
    with ProjetoScimat(analise["projeto"]) as kb:
        linhas = kb.conexao.execute(
            "SELECT d.idDocument, d.title, d.year, d.authors, d.citationsCount, "
            "j.source FROM Document d "
            "JOIN PublishDate p ON p.idPublishDate = d.PublishDate_idPublishDate "
            "JOIN PublishDate_Period pp ON pp.PublishDate_idPublishDate = p.idPublishDate "
            "LEFT JOIN Journal j ON j.idJournal = d.Journal_idJournal "
            "WHERE pp.Period_idPeriod = ? ORDER BY d.idDocument",
            (analise["periodo_id"],)).fetchall()

    documentos = []
    for linha in linhas:
        item = {
            "id": linha["idDocument"],
            "titulo": linha["title"] or "",
            "ano": linha["year"] or "",
            "autores": linha["authors"] or "",
            "citacoes": linha["citationsCount"] or 0,
            "fonte": linha["source"] or "",
        }
        if termo and termo not in (
                item["titulo"] + " " + item["autores"] + " " + item["fonte"]).lower():
            continue
        documentos.append(item)
    return {"periodo": analise.get("periodo", ""), "total": len(documentos),
            "documentos": documentos}


def detalhe_grupo(token: str, selo) -> dict:
    analise = _analise(token)

    try:
        indice = int(str(selo).strip())
    except (TypeError, ValueError):
        raise ErroApi(f"Número do agrupamento inválido: {selo!r}.") from None

    grupo = analise["grupos"].get(indice)
    if grupo is None:
        raise ErroApi(f"Não há agrupamento {indice} nesta análise "
                      f"(vão de 1 a {len(analise['grupos'])}).")

    return {
        "grupo": grupo["grupo"],
        "itens": grupo["itens"],
        "medidas": grupo.get("medidas", {}),
        "documentos_por_mapeador": grupo.get("documentos_por_mapeador", {}),
        "documentos": _documentos_do_projeto(
            analise["projeto"], grupo["documentos"]),
    }


# ------------------------------------------------------ edição da base

def base_conhecimento(caminho: str) -> dict:
    from . import edit

    projeto = _valida_projeto(caminho)
    try:
        return edit.resume(projeto)
    except ValueError as erro:
        raise ErroApi(str(erro)) from None


def edita_base(dados: dict) -> dict:
    from . import edit

    projeto = _valida_projeto(dados.get("caminho") or dados.get("projeto", ""))
    acao = dados.get("acao", "")
    try:
        if acao == "criar-periodo":
            return edit.cria_periodo(projeto, dados.get("nome", "Período"),
                                     int(dados.get("inicio", 0)),
                                     int(dados.get("fim", 9999)))
        if acao == "sugerir-periodos":
            quantidade = dados.get("quantidade")
            return edit.sugere_periodos(
                projeto, int(quantidade) if quantidade else None)
        if acao == "renomear-periodo":
            return edit.renomeia_periodo(projeto, int(dados["id"]),
                                         dados.get("nome", ""))
        if acao == "redistribuir-periodo":
            return edit.redistribui_periodo(projeto, int(dados["id"]),
                                            int(dados.get("inicio", 0)),
                                            int(dados.get("fim", 9999)))
        if acao == "excluir-periodo":
            return edit.exclui_periodo(projeto, int(dados["id"]))
        if acao == "renomear-grupo":
            return edit.renomeia_grupo(projeto, dados.get("tipo", ""),
                                       int(dados["id"]), dados.get("nome", ""))
        if acao == "marcar-parada":
            return edit.marca_parada(projeto, dados.get("tipo", ""),
                                     int(dados["id"]), bool(dados.get("parada")))
        if acao == "juntar-grupos":
            return edit.junta_grupos(projeto, dados.get("tipo", ""),
                                     int(dados["origem"]), int(dados["destino"]))
        if acao == "substituir":
            return edit.substitui(projeto, dados.get("tipo", ""),
                                  dados.get("de", ""), dados.get("para", ""))
        if acao == "desfazer":
            return edit.desfaz(projeto)
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as erro:
        raise ErroApi(str(erro)) from None
    raise ErroApi(f"ação de edição desconhecida: {acao}")


# --------------------------------------------------------- relatório e mapas

def gera_relatorio(dados: dict) -> dict:
    """Gera o relatório HTML e devolve a URL de abertura."""
    from . import report

    caminho = _valida_projeto(dados.get("projeto", ""))
    config = _config(dados)
    formato = dados.get("formato") or "html"
    if formato != "html":
        raise ErroApi("O relatório é gerado somente em HTML.")
    estendido = bool(dados.get("estendido", False))
    medida = dados.get("medida_temporal", "EquivalenceIndex")

    with ProjetoScimat(caminho) as kb:
        periodos = kb.periodos()
        if not periodos:
            raise ErroApi("o projeto não tem períodos")
        token = secrets.token_urlsafe(10)
        destino = CACHE / f"rel-{token}"
        resumo = report.gera(destino, kb, periodos, config, formato,
                             estendido, medida)

    with TRAVA_REGISTRO:
        RELATORIOS[token] = destino
        while len(RELATORIOS) > 5:
            RELATORIOS.popitem(last=False)

    arquivo = "index.html"
    return {"token": token, "formato": formato, "resumo": resumo,
            "url": f"/relatorio/{token}/{arquivo}",
            "indice": f"/relatorio/{token}/index.html"}


def gera_longitudinal(dados: dict) -> dict:
    """Monta os mapas de evolução e sobreposição de todos os períodos."""
    from . import longitudinal

    caminho = _valida_projeto(dados.get("projeto", ""))
    config = _config(dados)
    medida = dados.get("medida_temporal", "EquivalenceIndex")
    if not dados.get("todos_os_periodos", True):
        raise ErroApi("o mapa longitudinal precisa de todos os períodos")

    with ProjetoScimat(caminho) as kb:
        periodos = kb.periodos()
        if len(periodos) < 2:
            raise ErroApi("o projeto precisa de pelo menos dois períodos")
        mapa = longitudinal.constroi(kb, config, periodos, medida)

    pasta = CACHE / secrets.token_hex(6)
    pasta.mkdir(parents=True, exist_ok=True)
    evolucao = pasta / "evolucao.svg"
    sobreposicao = pasta / "sobreposicao.svg"
    pajek = pasta / "evolucao.net"
    evolucao.write_text(longitudinal.evolucao_svg(mapa), encoding="utf-8")
    sobreposicao.write_text(longitudinal.sobreposicao_svg(mapa), encoding="utf-8")
    pajek.write_text(longitudinal.evolucao_pajek(mapa), encoding="utf-8")

    return {
        "periodos": mapa.periodos,
        "medida": mapa.medida,
        "nos": len(mapa.nos),
        "elos": len(mapa.elos),
        "sobreposicao": [[round(v, 4) for v in linha]
                         for linha in mapa.sobreposicao],
        "figuras": {
            "evolucao": f"/figura/{_registra(evolucao, FIGURAS)}",
            "sobreposicao": f"/figura/{_registra(sobreposicao, FIGURAS)}",
        },
        "download": f"/download/{_registra(pajek, ARQUIVOS)}",
    }


# --------------------------------------------------------------- trabalhos

class Trabalho:
    def __init__(self, tipo: str, total: int) -> None:
        self.id = secrets.token_urlsafe(9)
        self.tipo = tipo
        self.estado = "executando"
        self.feito = 0
        self.total = total
        self.mensagem = "Preparando"
        self.resultado = None
        self.erro = None
        self.cancelado = False

    def estado_json(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "estado": self.estado,
            "feito": self.feito,
            "total": self.total,
            "mensagem": self.mensagem,
            "resultado": self.resultado,
            "erro": self.erro,
        }


def _trabalho_ativo() -> bool:
    with TRAVA_TRABALHOS:
        return any(t.estado == "executando" for t in TRABALHOS.values())


def _executa_grade(trabalho: Trabalho, dados: dict) -> None:
    from .cli import CABECALHO, _linha

    caminho = _valida_projeto(dados.get("projeto", ""))
    try:
        with ProjetoScimat(caminho) as kb:
            periodos = kb.periodos()
            if not periodos:
                raise ErroApi("o projeto não tem períodos")

            saida = CACHE / f"grade-{trabalho.id[:6]}.tsv"

            with open(saida, "w", encoding="utf-8", newline="") as arquivo:
                escritor = csv.writer(arquivo, delimiter="\t")
                escritor.writerow(CABECALHO)

                for (eixo, unidade, matriz, algoritmo, similaridade, freq, cooc,
                     minimo, maximo, mapeador, medida) in combinacoes_grade():
                    if trabalho.cancelado:
                        raise _Cancelado()
                    config = Configuracao(
                        unidade=unidade, matriz=matriz, algoritmo=algoritmo,
                        similaridade=similaridade, minimo_frequencia=freq,
                        minimo_coocorrencia=cooc, tamanho_minimo=minimo,
                        tamanho_maximo=maximo, mapeadores=(mapeador,),
                        indices=(medida,) if medida else
                        ("h", "g", "hg", "q2", "media", "soma", "minimo", "maximo"))
                    for periodo in periodos:
                        if trabalho.cancelado:
                            raise _Cancelado()
                        resultado = executa_periodo(
                            kb, periodo.id, periodo.nome, config)
                        escritor.writerow(_linha(resultado, eixo, mapeador, medida))
                        trabalho.feito += 1
                        trabalho.mensagem = (
                            f"{unidade} · {algoritmo} · {periodo.nome}")

        trabalho.estado = "concluido"
        trabalho.mensagem = "Grade concluída"
        trabalho.resultado = {
            "analises": trabalho.feito,
            "periodos": len(periodos),
            "download": f"/download/{_registra(saida, ARQUIVOS)}",
            "nome": saida.name,
        }
    except _Cancelado:
        trabalho.estado = "cancelado"
        trabalho.mensagem = "Execução cancelada"
    except ErroApi as erro:
        trabalho.estado = "erro"
        trabalho.erro = str(erro)
        trabalho.mensagem = "Falha na execução"
    except Exception as erro:  # noqa: BLE001 - vira mensagem para a tela
        traceback.print_exc()
        trabalho.estado = "erro"
        trabalho.erro = f"falha interna: {erro}"
        trabalho.mensagem = "Falha na execução"


class _Cancelado(Exception):
    pass


def inicia_grade(dados: dict) -> dict:
    if _trabalho_ativo():
        raise ErroApi("já existe uma execução em andamento")

    caminho = _valida_projeto(dados.get("projeto", ""))
    with ProjetoScimat(caminho) as kb:
        periodos = kb.periodos()
    if not periodos:
        raise ErroApi("o projeto não tem períodos")

    trabalho = Trabalho("grade", 27 * len(UNIDADES) * len(periodos))
    with TRAVA_TRABALHOS:
        TRABALHOS[trabalho.id] = trabalho

    threading.Thread(target=_executa_grade, args=(trabalho, dados),
                     daemon=True).start()
    return trabalho.estado_json()


def estado_trabalho(identificador: str) -> dict:
    with TRAVA_TRABALHOS:
        trabalho = TRABALHOS.get(identificador)
    if trabalho is None:
        raise ErroApi("execução não encontrada")
    return trabalho.estado_json()


def cancela_trabalho(identificador: str) -> dict:
    with TRAVA_TRABALHOS:
        trabalho = TRABALHOS.get(identificador)
    if trabalho is None:
        raise ErroApi("execução não encontrada")
    if trabalho.estado == "executando":
        trabalho.cancelado = True
        trabalho.mensagem = "Cancelando"
    return trabalho.estado_json()


# ------------------------------------------------------------------ importação

def _nome_seguro(texto: str) -> str:
    nome = re.sub(r"[^\w. -]+", "-", (texto or "").strip(), flags=re.UNICODE)
    nome = re.sub(r"\s+", "-", nome).strip(" .-")
    return nome[:60] or "projeto"


def _faixas(texto: str):
    faixas = []
    for parte in (texto or "").split(","):
        parte = parte.strip()
        if not parte:
            continue
        achado = re.fullmatch(r"(\d{4})\s*[-–]\s*(\d{4})", parte)
        if not achado:
            raise ErroApi(f"faixa de período inválida: {parte}")
        inicio, fim = int(achado.group(1)), int(achado.group(2))
        if inicio > fim:
            raise ErroApi(f"faixa invertida: {parte}")
        faixas.append((f"{inicio}\u2013{fim}", inicio, fim))
    return faixas


def _periodo_automatico(documentos, texto: str = ""):
    anos = []
    for documento in documentos:
        achado = re.match(r"\d{4}", (documento.ano or "").strip())
        if achado:
            anos.append(int(achado.group(0)))
    if (texto or "").strip().lower() in ("unico", "único"):
        return [(f"{min(anos)}\u2013{max(anos)}", min(anos), max(anos))] if anos \
            else [("0\u20139999", 0, 9999)]
    return build.sugere_periodos(anos)


def importa(workspace: Path, corpo: bytes, nome_arquivo: str,
            formato: str, texto_periodos: str, nome_projeto: str,
            autores_referencia: str = "primeiro",
            remove_repetidos: bool = True) -> dict:
    from .loaders import le_corpus

    if formato not in FORMATOS and formato != "auto":
        raise ErroApi(f"Formato desconhecido: {formato!r}. Use um destes: "
                      f"auto, {', '.join(FORMATOS)}.")
    if autores_referencia not in ("primeiro", "todos", "lista"):
        raise ErroApi("autores_referencia precisa ser primeiro, todos ou lista")
    if not corpo:
        raise ErroApi("O arquivo está vazio.")
    if not nome_arquivo:
        raise ErroApi("O nome do arquivo não chegou ao servidor.")

    nome = _nome_seguro(nome_projeto or Path(nome_arquivo).stem)
    destino = workspace / nome
    sufixo = 2
    while destino.exists():
        destino = workspace / f"{nome}-{sufixo}"
        sufixo += 1
    destino.mkdir(parents=True)

    arquivo = destino / Path(nome_arquivo).name
    arquivo.write_bytes(corpo)
    # Os formatos tabulares se confundem pelo nome das colunas; o conteúdo
    # decide. Assim, escolher "CSV SciMAT" ou "CSV da Scopus" para um arquivo
    # OpenAlex ou Zotero não estraga autores e referências.
    try:
        documentos, formato = le_corpus(arquivo, formato)
    except (UnicodeError, ValueError, KeyError, csv.Error) as erro:
        raise ErroApi(f"Não foi possível ler o arquivo como {formato}: "
                      f"{erro}") from None

    if not documentos:
        raise ErroApi(
            "Nenhum registro com título foi encontrado no arquivo. Confira se "
            f"o formato escolhido ({formato}) é o do arquivo exportado.")

    if (texto_periodos or "").strip().lower() in ("unico", "único"):
        faixas = _periodo_automatico(documentos, texto_periodos)
    else:
        faixas = _faixas(texto_periodos) or _periodo_automatico(documentos)
    arquivo = destino / NOME_PADRAO
    resumo = build.constroi(documentos, arquivo, faixas,
                            remove_repetidos=remove_repetidos,
                            autores_referencia=autores_referencia)
    projeto = descreve_projeto(arquivo)
    return {"projeto": projeto, "resumo": resumo, "formato": formato}


def lista_projetos(workspace: Path) -> list[dict]:
    projetos = []
    if not workspace.exists():
        return projetos

    for entrada in workspace.iterdir():
        if entrada.is_file():
            # Projeto solto na pasta, sem subpasta própria.
            if entrada.suffix.lower() in (EXTENSAO, ".scimat") and e_projeto(entrada):
                projetos.append({
                    "nome": entrada.stem,
                    "caminho": str(entrada),
                    "modificado": entrada.stat().st_mtime,
                })
            continue
        if not entrada.is_dir():
            continue
        dados = entrada / NOME_PADRAO
        if not dados.exists():
            dados = entrada / "dados.scimat"
        if not dados.exists():
            continue
        projetos.append({
            "nome": entrada.name,
            "caminho": str(dados),
            "modificado": dados.stat().st_mtime,
        })
    projetos.sort(key=lambda item: item["modificado"], reverse=True)
    return projetos


# -------------------------------------------------------------------- servidor

class ServidorWeb(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, endereco, workspace: Path):
        super().__init__(endereco, Manipulador)
        self.workspace = workspace
        self.ui = Path(__file__).parent / "ui"


class Manipulador(BaseHTTPRequestHandler):
    server: ServidorWeb
    server_version = "scimatpy"

    def log_message(self, formato: str, *args) -> None:  # silêncio no terminal
        return

    # --------------------------------------------------------------- utilidades

    def _json(self, codigo: int, dados) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _arquivo(self, dados: bytes, nome: str, tipo: str, download: bool) -> None:
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        if download:
            self.send_header(
                "Content-Disposition",
                f"attachment; filename*=UTF-8''{quote(nome)}")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(dados)

    def _texto(self, codigo: int, corpo: str, tipo: str) -> None:
        dados = corpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(dados)

    def _corpo(self, limite: int) -> bytes:
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho > limite:
            raise ErroApi(f"arquivo muito grande (limite {limite // (1024 * 1024)} MB)")
        if tamanho <= 0:
            return b""
        return self.rfile.read(tamanho)

    def _json_pedido(self) -> dict:
        corpo = self._corpo(2 * 1024 * 1024)
        if not corpo:
            return {}
        try:
            dados = json.loads(corpo.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ErroApi("JSON inválido") from None
        if not isinstance(dados, dict):
            raise ErroApi("o corpo precisa ser um objeto JSON")
        return dados

    def _estatico(self, caminho: str) -> None:
        nome = Path(caminho).name
        if nome != caminho.lstrip("/") or nome.startswith("."):
            raise ErroApi("arquivo inválido")
        arquivo = self.server.ui / nome
        if not arquivo.exists() or not arquivo.is_file():
            self.send_error(404)
            return
        tipos = {".html": "text/html", ".css": "text/css",
                 ".js": "application/javascript", ".svg": "image/svg+xml"}
        tipo = tipos.get(arquivo.suffix.lower(), "application/octet-stream")
        self._texto(200, arquivo.read_text(encoding="utf-8"), tipo)

    # ------------------------------------------------------------------- rotas

    def do_GET(self) -> None:  # noqa: N802 - nome exigido pela biblioteca
        analisado = urlparse(self.path)
        rota = analisado.path
        parametros = parse_qs(analisado.query)

        try:
            if rota in ("/", "/index.html"):
                self._estatico("index.html")
            elif rota.startswith("/static/"):
                self._estatico(rota[len("/static/"):])
            elif rota == "/api/projetos":
                self._json(200, {
                    "workspace": str(self.server.workspace),
                    "projetos": lista_projetos(self.server.workspace),
                })
            elif rota == "/api/projeto":
                caminho = _valida_projeto(
                    (parametros.get("caminho") or [""])[0])
                self._json(200, descreve_projeto(caminho))
            elif rota.startswith("/figura/"):
                token = rota[len("/figura/"):]
                with TRAVA_REGISTRO:
                    arquivo = FIGURAS.get(token)
                if arquivo is not None and not arquivo.exists():
                    _materializa(token, arquivo)
                if arquivo is None or not arquivo.exists():
                    raise ErroApi("Figura não encontrada. Pré-visualize de novo.")
                baixar = (parametros.get("download") or ["0"])[0] == "1"
                dados = arquivo.read_text(encoding="utf-8").encode("utf-8")
                self._arquivo(dados, arquivo.name, "image/svg+xml", baixar)
            elif rota == "/api/base":
                self._json(200, base_conhecimento(
                    (parametros.get("caminho") or [""])[0]))
            elif rota == "/api/bibliometria":
                from . import bibliometria
                caminho = _valida_projeto(
                    (parametros.get("caminho") or [""])[0])
                with ProjetoScimat(caminho) as kb:
                    self._json(200, bibliometria.calcula(kb.conexao))
            elif rota == "/api/rajadas":
                from . import rajadas
                from .viz import descritiva
                caminho = _valida_projeto((parametros.get("caminho") or [""])[0])
                tipo = (parametros.get("tipo") or ["palavras"])[0]
                try:
                    minimo = int((parametros.get("minimo") or [rajadas.MINIMO_DOCUMENTOS])[0])
                except ValueError:
                    raise ErroApi("o mínimo de documentos precisa ser um número") from None
                try:
                    with ProjetoScimat(caminho) as kb:
                        dados = rajadas.calcula(kb.conexao, tipo, minimo_documentos=max(1, minimo))
                except ValueError as erro:
                    raise ErroApi(str(erro)) from None
                titulo = ("Palavras-chave com as rajadas mais fortes" if tipo == "palavras"
                          else "Referências com as rajadas mais fortes")
                dados["svg"] = descritiva.rajadas_svg(
                    dados, titulo, "Palavras-chave" if tipo == "palavras" else "Referência")
                self._json(200, dados)
            elif rota == "/api/nuvem":
                from . import termos
                from .viz import descritiva
                caminho = _valida_projeto((parametros.get("caminho") or [""])[0])
                fonte = (parametros.get("fonte") or ["palavras"])[0]
                ocultar = [t for t in re.split(r"[,;\n]", (parametros.get("ocultar") or [""])[0]) if t.strip()]
                try:
                    limite = max(10, min(150, int((parametros.get("limite") or ["70"])[0])))
                except ValueError:
                    raise ErroApi("o limite precisa ser um número") from None
                try:
                    with ProjetoScimat(caminho) as kb:
                        dados = termos.nuvem_dados(
                            kb.conexao, fonte, ocultar, limite,
                            tirar_academicas=(parametros.get("academicas") or ["1"])[0] != "0",
                            expressoes=(parametros.get("expressoes") or ["0"])[0] == "1")
                except ValueError as erro:
                    raise ErroApi(str(erro)) from None
                dados["svg"] = descritiva.nuvem_svg(
                    [(t["termo"], t["documentos"]) for t in dados["termos"]],
                    "Nuvem de palavras")
                self._json(200, dados)
            elif rota == "/api/documentos":
                self._json(200, lista_documentos(
                    _param(parametros, "token"),
                    (parametros.get("busca") or [""])[0]))
            elif rota == "/api/exportar":
                dados, nome, tipo = exportar(
                    _param(parametros, "token"),
                    (parametros.get("tipo") or [""])[0])
                self._arquivo(dados, nome, tipo, True)
            elif rota.startswith("/download/"):
                token = rota[len("/download/"):]
                with TRAVA_REGISTRO:
                    arquivo = ARQUIVOS.get(token)
                if arquivo is None or not arquivo.exists():
                    raise ErroApi("arquivo não encontrado")
                dados = arquivo.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/tab-separated-values")
                self.send_header(
                    "Content-Disposition",
                    f"attachment; filename*=UTF-8''{quote(arquivo.name)}")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)
            elif rota == "/api/estrategico":
                self._json(200, dados_do_diagrama(
                    _param(parametros, "token")))
            elif rota == "/api/mapa":
                self._json(200, dados_do_mapa(
                    _param(parametros, "token")))
            elif rota == "/api/rede":
                self._json(200, dados_rede(_param(parametros, "token")))
            elif rota == "/api/grupo":
                self._json(200, detalhe_grupo(
                    _param(parametros, "token"),
                    (parametros.get("selo") or [""])[0]))
            elif rota.startswith("/relatorio/"):
                partes = rota[len("/relatorio/"):].split("/", 1)
                if len(partes) != 2:
                    raise ErroApi("caminho de relatório inválido")
                token, nome = partes
                with TRAVA_REGISTRO:
                    pasta = RELATORIOS.get(token)
                if pasta is None or not pasta.exists():
                    raise ErroApi("relatório não encontrado")
                arquivo = (pasta / nome).resolve()
                if pasta.resolve() not in arquivo.parents:
                    raise ErroApi("caminho de relatório inválido")
                if not arquivo.is_file():
                    raise ErroApi(f"arquivo não encontrado: {nome}")
                tipos = {".html": "text/html", ".svg": "image/svg+xml",
                         ".net": "text/plain",
                         ".png": "image/png", ".csv": "text/csv"}
                tipo = tipos.get(arquivo.suffix.lower(), "application/octet-stream")
                self._arquivo(arquivo.read_bytes(), arquivo.name, tipo, False)
            elif rota.startswith("/api/trabalho/"):
                self._json(200, estado_trabalho(rota[len("/api/trabalho/"):]))
            elif rota == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            else:
                self.send_error(404)
        except ErroExpirado as erro:
            self._json(410, {"erro": str(erro), "expirada": True})
        except ErroApi as erro:
            self._json(400, {"erro": str(erro)})
        except Exception as erro:  # noqa: BLE001
            traceback.print_exc()
            self._json(500, {"erro": f"falha interna: {erro}"})

    def do_POST(self) -> None:  # noqa: N802
        analisado = urlparse(self.path)
        rota = analisado.path
        parametros = parse_qs(analisado.query)

        try:
            if rota == "/api/abrir":
                dados = self._json_pedido()
                caminho = _valida_projeto(dados.get("caminho", ""))
                self._json(200, descreve_projeto(caminho))
            elif rota == "/api/analisa":
                self._json(200, analisa(self._json_pedido()))
            elif rota == "/api/grade":
                self._json(202, inicia_grade(self._json_pedido()))
            elif rota == "/api/base":
                self._json(200, edita_base(self._json_pedido()))
            elif rota == "/api/relatorio":
                self._json(200, gera_relatorio(self._json_pedido()))
            elif rota == "/api/longitudinal":
                self._json(200, gera_longitudinal(self._json_pedido()))
            elif rota.startswith("/api/trabalho/") and rota.endswith("/cancelar"):
                identificador = rota[len("/api/trabalho/"):-len("/cancelar")]
                self._json(200, cancela_trabalho(identificador))
            elif rota == "/api/importar":
                formato = (parametros.get("formato") or ["csv"])[0]
                periodos = (parametros.get("periodos") or [""])[0]
                nome = (parametros.get("nome") or [""])[0]
                autores_ref = (parametros.get("autores_referencia")
                               or ["primeiro"])[0]
                repetidos = (parametros.get("manter_repetidos")
                             or ["0"])[0] not in ("1", "true", "sim")
                nome_arquivo = unquote(
                    self.headers.get("X-Nome-Arquivo") or "corpus")
                corpo = self._corpo(400 * 1024 * 1024)
                self._json(200, importa(self.server.workspace, corpo,
                                        nome_arquivo, formato, periodos, nome,
                                        autores_ref, repetidos))
            else:
                self.send_error(404)
        except ErroExpirado as erro:
            self._json(410, {"erro": str(erro), "expirada": True})
        except ErroApi as erro:
            self._json(400, {"erro": str(erro)})
        except Exception as erro:  # noqa: BLE001
            traceback.print_exc()
            self._json(500, {"erro": f"falha interna: {erro}"})


def cria_servidor(porta: int = 8765, workspace: str | Path | None = None,
                  host: str = "127.0.0.1") -> ServidorWeb:
    raiz = Path(workspace).expanduser().resolve() if workspace else (
        Path.home() / "scimatpy-projetos")
    raiz.mkdir(parents=True, exist_ok=True)
    return ServidorWeb((host, porta), raiz)


def serve(porta: int = 8765, workspace: str | Path | None = None,
          abrir: bool = True) -> None:
    servidor = None
    for deslocamento in range(12):
        try:
            servidor = cria_servidor(porta + deslocamento, workspace)
            break
        except OSError:
            continue

    if servidor is None:
        raise SystemExit("não foi possível abrir uma porta local para a interface")

    endereco = f"http://127.0.0.1:{servidor.server_address[1]}/"
    print(f"scimatpy web em {endereco}")
    print(f"projetos em {servidor.workspace}")
    print("Ctrl+C para encerrar")
    if abrir:
        threading.Timer(0.6, lambda: webbrowser.open(endereco)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrado")
    finally:
        servidor.server_close()

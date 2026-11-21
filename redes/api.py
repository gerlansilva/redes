"""Servidor local da interface web do redes.

Sem dependências além da biblioteca padrão: o navegador só envia parâmetros e
recebe JSON; toda a análise roda no processo Python, com o mesmo núcleo do CLI.
O servidor escuta apenas em 127.0.0.1 e não expõe nada fora da máquina.
"""

from __future__ import annotations

import atexit
import csv
import json
import math
import re
import secrets
import shutil
import sqlite3
import sys
import tempfile
import threading
import traceback
import webbrowser
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import avisos as modulo_avisos
from . import bibliometria as modulo_bibliometria
from . import build
from . import pivos as modulo_pivos
from . import qualidade as modulo_qualidade
from . import rotulos as modulo_rotulos
from .grade import UNIDADES as UNIDADES_GRADE, grade as combinacoes_grade
from .network import Cancelado as _Cancelado
from .ies import COMPONENTE_MINIMO_PADRAO, tabela_variantes
from .kb import ProjetoRedes
from .mappers import MAPEADORES
from .pipeline import (Configuracao, MENSAGEM_MAPEADOR_ACOPLAMENTO,
                       executa_periodo)
from .projeto import EXTENSAO, NOME_PADRAO, e_projeto, nome_de_projeto
from .texto import (NOMES_PROPRIOS, exibe_termo, rotulo_legivel, siglas as siglas_conhecidas,
                    termo_legivel)
from .viz.halo import UNIDADE_TITULO, halo_svg, layout_halo
from .viz.mapa import (colaboracao_do_periodo, dados_mapa as mapa_interativo,
                       mapa_svg)
from .viz.strategic import dados_diagrama, diagrama_svg
from .viz.cluster import rede_de_agrupamentos_svg

FORMATOS = ("csv", "bibtex", "ris", "openalex", "wos", "scopus", "zotero")
UNIDADES = ("Words", "Authors", "References", "AuthorsReference",
            "ReferenceSources", "Countries", "Institutions")
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

CACHE = Path(tempfile.mkdtemp(prefix="redes-web-"))
atexit.register(shutil.rmtree, CACHE, ignore_errors=True)
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
            with ProjetoRedes(caminho) as kb:
                analise["resultado"] = executa_periodo(
                    kb, analise["periodo_id"], analise["periodo"],
                    analise["config"])
            analise["rede"] = None
        if analise.get("rede") is None:
            # O layout é a etapa mais cara: só roda quando a tela pede a rede
            # ou a figura, não na própria prévia.
            analise["rede"] = layout_halo(analise["resultado"],
                                          rotulos=analise.get("rotulos"))
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
    if "acoplamento" in mapeadores and matriz != "BasicCoupling":
        raise ErroApi(MENSAGEM_MAPEADOR_ACOPLAMENTO.format(matriz=matriz))

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
        if not math.isfinite(corte):
            raise ErroApi(
                f"\"corte\" precisa ser um número finito (recebido: {bruto_corte!r})")
    if corte < 0:
        raise ErroApi("\"corte\" não pode ser negativo")

    ignorar = dados.get("ignorar") or []
    if isinstance(ignorar, str):
        ignorar = [t for t in re.split(r"[;\n]", ignorar) if t.strip()]
    if not isinstance(ignorar, (list, tuple)):
        raise ErroApi("\"ignorar\" precisa ser uma lista de termos")

    # Tamanho mínimo do agrupamento: "tamanho_minimo_agrupamento" é o nome novo e
    # "componente_minimo" o antigo (alias). Padrão: 3 em Institutions, 1 nas demais.
    nome_comp = ("tamanho_minimo_agrupamento"
                 if dados.get("tamanho_minimo_agrupamento") not in (None, "")
                 else "componente_minimo")
    componente = inteiro(nome_comp, COMPONENTE_MINIMO_PADRAO if unidade == "Institutions" else 1, 1)

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
        componente_minimo=componente,
    )


def _inteiro_limitado(valor, padrao: int, minimo: int, maximo: int, nome: str) -> int:
    if valor in (None, ""):
        return padrao
    try:
        return max(minimo, min(maximo, int(valor)))
    except OverflowError:
        raise ErroApi(f"{nome} precisa ser um número finito (recebeu infinito)") from None
    except (TypeError, ValueError):
        raise ErroApi(f"{nome} precisa ser um número") from None


def fluxo_autor_pais_ies(pedido: dict) -> dict:
    """Dados e SVG do fluxo Autor → País → IES (mesmos parâmetros no GET e no POST)."""
    from . import fluxos
    from .viz import sankey
    caminho = _valida_projeto(str(pedido.get("caminho") or ""))
    limites = {
        "limite_autores": _inteiro_limitado(pedido.get("autores"), fluxos.LIMITE_AUTORES, 3, 40, "autores"),
        "limite_paises": _inteiro_limitado(pedido.get("paises"), fluxos.LIMITE_PAISES, 3, 25, "paises"),
        "limite_ies": _inteiro_limitado(pedido.get("ies"), fluxos.LIMITE_IES, 3, 40, "ies"),
    }
    with ProjetoRedes(caminho) as kb:
        dados = fluxos.calcula(kb.conexao, **limites)
    # Na tela o título é o do cartão; o arquivo baixado leva o título dentro do SVG.
    dados["svg"] = sankey.svg(dados, "") if dados["nos"] else ""
    if dados["nos"] and pedido.get("baixar") in ("1", "true"):
        dados["svg"] = sankey.svg(dados, "Fluxo " + " → ".join(dados["colunas"]))
    return dados


def dendrograma_do_pedido(pedido: dict) -> dict:
    """Dendrograma de um período (GET e POST). Usa ``token`` de uma análise já
    calculada ou, sem ele, ``projeto``/``caminho`` + a configuração de /api/analisa."""
    from . import dendrograma, dendro_helper
    from .viz import dendrograma as viz_dendro
    ligacao = str(pedido.get("ligacao") or "media")
    if ligacao not in dendrograma.LIGACOES:
        raise ErroApi(f"Ligação inválida: {ligacao!r}. "
                      f"Use uma destas: {', '.join(dendrograma.LIGACOES)}.")
    limite = _inteiro_limitado(pedido.get("limite"), dendro_helper.LIMITE_NOS,
                               10, 120, "limite")
    bruto = pedido.get("n_grupos")
    n_pedido = None
    if bruto not in (None, ""):
        try:
            n_pedido = int(bruto)
        except OverflowError:
            raise ErroApi("n_grupos precisa ser um número finito (recebeu infinito)") from None
        except (TypeError, ValueError):
            raise ErroApi("n_grupos precisa ser um número inteiro") from None
        if n_pedido < 1:
            raise ErroApi("n_grupos precisa ser pelo menos 1")
    token = _token(pedido.get("token"))
    if token:
        analise = _analise(token)
        _recalcula(analise)
        resultado = analise["resultado"]
    else:
        caminho = _valida_projeto(str(pedido.get("projeto") or pedido.get("caminho") or ""))
        config = _config(pedido)
        with ProjetoRedes(caminho) as kb:
            periodo = _periodo(kb, pedido.get("periodo"))
            resultado = executa_periodo(kb, periodo.id, periodo.nome, config)
    res, omitidos = dendro_helper.dendrograma_do_periodo(resultado, limite, ligacao)
    if res is None:
        raise ErroApi("Poucos itens neste período para um dendrograma (mínimo de 3).")
    n_total = len(res["nos"])
    n_grupos = res["n_grupos_sugerido"] if n_pedido is None else min(n_pedido, n_total)
    particao = res.corte(n_grupos=n_grupos)
    titulo = ""
    if pedido.get("baixar") in ("1", "true"):
        titulo = f"Dendrograma — {resultado.periodo}"
    return {
        "svg": viz_dendro.svg(res, n_grupos, titulo),
        "n_grupos": n_grupos,
        "n_grupos_sugerido": res["n_grupos_sugerido"],
        "n_nos": n_total,
        "ligacao": ligacao,
        "coph": round(res["coph"], 4),
        "comparacao": res.comparacao(particao) if res.get("grupos_rede") else None,
        "frases": dendrograma.interpreta(res, n_grupos),
        "omitidos": omitidos,
        "limite": limite,
        "periodo": resultado.periodo,
    }


MENSAGEM_LT_SEM_SENTIDO = (
    "A linha do tempo mostra itens (palavras, autores, referências) ao longo dos anos. "
    "Com acoplamento, os nós são documentos e cada um já tem um só ano; escolha uma "
    "análise de co-ocorrência para ver a figura.")
MENSAGEM_LT_UNIDADE = (
    "A linha do tempo existe para palavras-chave, autores e referências em co-ocorrência. "
    "Para esta unidade de análise (autores citados, fontes citadas, países ou instituições) "
    "ela não é gerada; escolha uma dessas três unidades.")
MAX_NOS_LT = (10, 60)


def linha_do_tempo_do_pedido(pedido: dict) -> dict:
    """Linha do tempo do corpus completo (GET e POST). Usa ``token`` de uma análise já
    calculada ou, sem ele, ``projeto``/``caminho`` + a configuração de /api/analisa."""
    from . import linha_do_tempo, metodo, report
    from .viz import linha_do_tempo as viz_lt
    max_nos = _inteiro_limitado(pedido.get("max_nos"), linha_do_tempo.MAX_NOS,
                                MAX_NOS_LT[0], MAX_NOS_LT[1], "max_nos")
    token = _token(pedido.get("token"))
    if token:
        analise = _analise(token)
        caminho = Path(analise["projeto"])
        config = analise["config"]
        if not caminho.exists():
            raise ErroExpirado(f"O projeto desta análise não existe mais: {caminho}")
    else:
        caminho = _valida_projeto(str(pedido.get("projeto") or pedido.get("caminho") or ""))
        config = _config(pedido)
    if config.matriz != "CoOccurrence":
        raise ErroApi(MENSAGEM_LT_SEM_SENTIDO)
    if config.unidade not in metodo.UNIDADES_LINHA_DO_TEMPO:
        raise ErroApi(MENSAGEM_LT_UNIDADE)
    with ProjetoRedes(caminho) as kb:
        dados, rotulos_lt = report.linha_do_tempo_do_corpus(kb, config, max_nos)
    if not dados["faixas"]:
        raise ErroApi((dados.get("avisos") or ["Não há o que mostrar na linha do tempo."])[0])
    titulo = ""
    if pedido.get("baixar") in ("1", "true"):
        titulo = report.titulo_linha_do_tempo(config)
    nos = sum(len(f["nos"]) for f in dados["faixas"])
    return {
        "svg": viz_lt.svg(dados, titulo, rotulos=rotulos_lt),
        "unidade": dados["unidade"],
        "n_nos": nos,
        "n_faixas": len(dados["faixas"]),
        "anos": dados["anos"],
        "atividade": dados["atividade"],
        "posicao": dados.get("posicao"),
        "avisos": dados["avisos"],
        "omitidos": dados["omitidos"],
        "max_nos": max_nos,
        "por_faixa": linha_do_tempo.POR_FAIXA,
    }


MENSAGEM_DENS_SEM_SENTIDO = (
    "O mapa de densidade posiciona itens (palavras, autores, referências, países) pela "
    "co-ocorrência. Com acoplamento ou cocitação os nós são documentos; escolha uma "
    "análise de co-ocorrência para ver a figura.")
NOS_DENSIDADE = (20, 300)


def densidade_do_pedido(pedido: dict) -> dict:
    """Mapa de densidade do corpus completo (GET e POST). Usa ``token`` de uma análise já
    calculada ou, sem ele, ``projeto``/``caminho`` + a configuração de /api/analisa."""
    from . import report
    from .viz import densidade
    topo = _inteiro_limitado(pedido.get("max_nos"), densidade.TOPO_NOS,
                             NOS_DENSIDADE[0], NOS_DENSIDADE[1], "max_nos")
    suavizacao = _inteiro_limitado(pedido.get("suavizacao"), densidade.SUAVIZACAO,
                                   *densidade.LIMITE_SUAVIZACAO, "suavizacao")
    token = _token(pedido.get("token"))
    if token:
        analise = _analise(token)
        caminho = Path(analise["projeto"])
        config = analise["config"]
        if not caminho.exists():
            raise ErroExpirado(f"O projeto desta análise não existe mais: {caminho}")
    else:
        caminho = _valida_projeto(str(pedido.get("projeto") or pedido.get("caminho") or ""))
        config = _config(pedido)
    if config.matriz != "CoOccurrence":
        raise ErroApi(MENSAGEM_DENS_SEM_SENTIDO)
    with ProjetoRedes(caminho) as kb:
        resultado = report.densidade_do_corpus(kb, config)
    dados = densidade.calcula(resultado, topo, suavizacao)
    if not dados["nos"]:
        aviso = dados.get("aviso") or "Não há o que mostrar no mapa de densidade."
        if pedido.get("baixar") in ("1", "true"):
            raise ErroApi(aviso)
        # Sem itens suficientes não é erro: a interface mostra o aviso (resposta 200).
        return {"svg": None, "aviso": aviso, "unidade": config.unidade, "n_nos": 0,
                "n_total": dados.get("total", 0), "max_nos": topo, "suavizacao": suavizacao}
    titulo = report.titulo_densidade(config) if pedido.get("baixar") in ("1", "true") else ""
    figura = densidade.svg(resultado, titulo, topo, suavizacao, unidade=config.unidade,
                           dados=dados)
    return {
        "svg": figura,
        "unidade": config.unidade,
        "n_nos": len(dados["nos"]),
        "n_total": dados["total"],
        "max_nos": topo,
        "suavizacao": suavizacao,
    }


def duplo_mapa_do_pedido(pedido: dict) -> dict:
    """Duplo mapa de áreas das revistas (GET e POST). Usa ``token`` de uma análise já calculada
    ou, sem ele, ``projeto``/``caminho``; vale para o corpus completo, qualquer que seja a
    configuração da análise."""
    from . import duplo_mapa
    from .viz import duplo_mapa as viz_duplo
    n_esq = _inteiro_limitado(pedido.get("max_esq"), duplo_mapa.MAX_ESQ,
                              *duplo_mapa.LIMITE_ESQ, "max_esq")
    n_dir = _inteiro_limitado(pedido.get("max_dir"), duplo_mapa.MAX_DIR,
                              *duplo_mapa.LIMITE_DIR, "max_dir")
    token = _token(pedido.get("token"))
    if token:
        caminho = Path(_analise(token)["projeto"])
        if not caminho.exists():
            raise ErroExpirado(f"O projeto desta análise não existe mais: {caminho}")
    else:
        caminho = _valida_projeto(str(pedido.get("projeto") or pedido.get("caminho") or ""))
    with ProjetoRedes(caminho) as kb:
        dados = duplo_mapa.calcula_do_banco(kb.conexao, n_esq, n_dir)
    if not dados["aplicavel"]:
        raise ErroApi(dados["aviso"])
    titulo = duplo_mapa.TITULO if pedido.get("baixar") in ("1", "true") else ""
    cobertura = dados["cobertura"]
    return {
        "svg": viz_duplo.svg(dados, titulo),
        "nota": duplo_mapa.NOTA,
        "avisos": dados["avisos"],
        "areas": dados["areas"],
        "fluxos": dados["fluxos"],
        "tabela": dados["tabela"],
        "cobertura": cobertura,
        "n_esquerda": len(dados["esquerda"]),
        "n_direita": len(dados["direita"]),
        "total_esquerda": dados["total_esquerda"],
        "total_direita": dados["total_direita"],
        "max_esq": n_esq,
        "max_dir": n_dir,
    }


def similitude_do_pedido(pedido: dict) -> dict:
    """Análise de similitude dos resumos (GET e POST). Usa ``token`` de uma análise já calculada
    ou, sem ele, ``projeto``/``caminho``; vale para os resumos do corpus (ou de um ``periodo``),
    qualquer que seja a configuração da análise. ``baixar`` = svg, graphml, csv ou csv-arestas."""
    from . import similitude
    from .viz import similitude as viz_sim
    n_formas = _inteiro_limitado(pedido.get("n_formas"), similitude.N_FORMAS,
                                 *similitude.LIMITE_N_FORMAS, "n_formas")
    extras = _inteiro_limitado(pedido.get("arestas_extras"), similitude.EXTRAS_PADRAO,
                               *similitude.LIMITE_EXTRAS, "arestas_extras")

    def escolha(nome: str, validos: tuple, padrao: str) -> str:
        valor = str(pedido.get(nome) or padrao).strip().lower()
        if valor not in validos:
            raise ErroApi(f"{nome} precisa ser um destes: {', '.join(validos)} (recebeu {valor!r})")
        return valor

    indice = escolha("indice", similitude.INDICES, similitude.INDICE_PADRAO)
    segmento = escolha("segmento", similitude.SEGMENTOS, "resumo")
    idioma = escolha("idioma", ("todos",) + similitude.IDIOMAS, "todos")
    ignorar = pedido.get("ignorar") or ()
    if not isinstance(ignorar, (str, list, tuple)):
        raise ErroApi("ignorar precisa ser uma lista de palavras ou um texto separado por vírgulas")
    baixar = str(pedido.get("baixar") or "").strip().lower()
    if baixar in ("1", "true"):
        baixar = "svg"
    if baixar not in ("", "svg", "graphml", "csv", "csv-arestas"):
        raise ErroApi("baixar precisa ser svg, graphml, csv ou csv-arestas")
    token = _token(pedido.get("token"))
    if token:
        caminho = Path(_analise(token)["projeto"])
        if not caminho.exists():
            raise ErroExpirado(f"O projeto desta análise não existe mais: {caminho}")
    else:
        caminho = _valida_projeto(str(pedido.get("projeto") or pedido.get("caminho") or ""))
    with ProjetoRedes(caminho) as kb:
        bruto = pedido.get("periodo")
        periodo_id, periodo_nome = None, "todos"
        if bruto not in (None, "", "todos"):
            periodo = _periodo(kb, bruto)
            periodo_id, periodo_nome = periodo.id, periodo.nome
        try:
            dados = similitude.analisa(kb.conexao, periodo_id, periodo_nome, n_formas=n_formas,
                                       indice_nome=indice, segmento=segmento, extras=extras,
                                       idioma=idioma, ignorar=ignorar)
        except similitude.SemResumos as erro:
            raise ErroApi(str(erro)) from None
    dados["nota"] = similitude.NOTA
    dados["titulo"] = similitude.TITULO
    dados["tabela_parametros"] = similitude.descreve_parametros(dados)
    dados["svg"] = viz_sim.svg(dados, similitude.TITULO if baixar == "svg" else "")
    dados["_baixar"] = baixar
    return dados


def exportacao_similitude(dados: dict) -> tuple[bytes, str, str]:
    """Conteúdo, nome e tipo do arquivo pedido em ``baixar`` (já calculado por `similitude_do_pedido`)."""
    from . import similitude
    tipo = dados["_baixar"]
    if tipo == "graphml":
        return similitude.graphml(dados).encode("utf-8"), "similitude.graphml", "application/xml"
    if tipo == "csv":
        return similitude.csv_formas(dados).encode("utf-8"), "similitude-formas.csv", "text/csv; charset=utf-8"
    if tipo == "csv-arestas":
        return (similitude.csv_arestas(dados).encode("utf-8"), "similitude-arestas.csv",
                "text/csv; charset=utf-8")
    return dados["svg"].encode("utf-8"), "similitude.svg", "image/svg+xml"


# Acima disto, os pontos de virada (intermediação) ficam para quando a tela os pede.
LIMITE_PIVOS_INLINE = 300


def _nomes_dos_grupos(saida_grupos, posicao_original, grupos) -> dict:
    """Índice original do agrupamento → (selo, nome exibido)."""
    nomes = {}
    for saida, grupo in zip(saida_grupos, grupos):
        original = posicao_original.get(id(grupo))
        if original is not None:
            nomes[original] = (saida["selo"], saida.get("rotulo_novo") or saida["rotulo"])
    return nomes


def _numero_ou_none(valor, casas: int):
    if valor is None or valor != valor or valor in (float("inf"), float("-inf")):
        return None
    return round(float(valor), casas)


def _pivos_publicos(bruto, nomes: dict) -> dict | None:
    """Pontos de virada no formato da API (JSON seguro); None se não há cálculo."""
    if not bruto:
        return None
    itens = []
    for posicao, i in enumerate(bruto.get("pivos") or [], start=1):
        selo, nome = nomes.get(i.get("grupo"), (None, None))
        itens.append({
            "posicao": posicao, "no": int(i["no"]), "rotulo": i["rotulo"],
            "intermediacao": _numero_ou_none(i["intermediacao"], 6),
            "grupos_vizinhos": i["grupos_vizinhos"],
            "grupo_selo": selo, "grupo_rotulo": nome,
            "frequencia": i.get("frequencia", 0),
            "rajada": _numero_ou_none(i.get("rajada"), 3),
            "sigma": _numero_ou_none(i.get("sigma"), 3),
        })
    descritores = [{"rotulo": t["rotulo"],
                    "proporcao_documentos": _numero_ou_none(t.get("proporcao_documentos"), 4),
                    "motivo": t.get("motivo", "")}
                   for t in bruto.get("termos_descritores") or []]
    return {
        "adiado": False,
        "nao_calculado": bruto.get("nao_calculado"),
        "n_nos": bruto.get("n_nos", 0),
        "suficiente": bool(bruto.get("suficiente")),
        "minimo_nos": modulo_pivos.MINIMO_NOS,
        "proporcao_descritor": modulo_pivos.PROPORCAO_DESCRITOR,
        "pivos": itens,
        "tem_sigma": any(i["sigma"] is not None for i in itens),
        "termos_descritores": descritores,
        "avisos": list(bruto.get("avisos") or []),
    }


def _calcula_pivos(kb, resultado):
    """Pontos de virada brutos; None se falhar ou se a rede for grande (ficam adiados)."""
    try:
        if resultado.rede.quantidade_nos() > LIMITE_PIVOS_INLINE:
            return None
        return modulo_pivos.pontos_de_virada(resultado, kb)
    except Exception as erro:  # noqa: BLE001
        # Nunca derruba a análise, mas o aviso aparece: sumir em silêncio pareceria "sem pivôs".
        traceback.print_exc()
        try:
            n = resultado.rede.quantidade_nos()
        except Exception:  # noqa: BLE001
            n = 0
        return modulo_pivos.nao_calculado(
            n, f"houve um erro ao calcular os pontos de virada ({erro}).")


def pivos_da_analise(token: str) -> dict:
    """Pontos de virada de uma análise (os adiados por tamanho são calculados aqui)."""
    analise = _analise(token)
    publico = analise.get("pivos_pub")
    if publico and not publico.get("adiado"):
        return publico
    with TRAVA_RECALCULO:
        _recalcula(analise)
        resultado = analise["resultado"]
        try:
            with ProjetoRedes(analise["projeto"]) as kb:
                bruto = modulo_pivos.pontos_de_virada(resultado, kb)
        except Exception as erro:
            raise ErroApi(f"Não foi possível calcular os pontos de virada: {erro}") from None
        analise["pivos"] = bruto
        analise["pivos_pub"] = _pivos_publicos(bruto, analise.get("nomes_grupos") or {})
    return analise["pivos_pub"]


def _valida_projeto(caminho: str) -> Path:
    if not caminho:
        raise ErroApi(f"Informe o caminho do projeto ({EXTENSAO}). Abra um "
                      "projeto na lista ou importe um corpus.")
    try:
        destino = Path(caminho).expanduser().resolve()
        existe = destino.exists() and destino.is_file()
    except (ValueError, OSError):
        raise ErroApi("Caminho de projeto inválido.")
    if not existe or not destino.is_file():
        raise ErroApi(f"Projeto não encontrado: {destino}. Ele pode ter sido "
                      "movido ou apagado; abra-o de novo na lista.")
    if not e_projeto(destino):
        raise ErroApi(f"O projeto precisa ser um arquivo {EXTENSAO}.")
    try:
        ProjetoRedes(destino).fecha()
    except ValueError as erro:  # arquivo .redes que não é um projeto
        raise ErroApi(str(erro)) from None
    return destino


def _periodo(kb: ProjetoRedes, identificador):
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
    with ProjetoRedes(caminho) as kb:
        periodos = kb.periodos()
        documentos = kb.conexao.execute(
            "SELECT COUNT(*) FROM Document").fetchone()[0]
        corpus = modulo_bibliometria.corpus_do_projeto(kb.conexao)
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
        "corpus": corpus,
    }


def _ies_publico(resultado) -> dict | None:
    """Rede de IES: tabela "variantes unidas" e componentes sem agrupamento."""
    info = getattr(resultado, "ies", None)
    if not info:
        return None
    return {
        "componente_minimo": info["componente_minimo"],
        "variantes_unidas": info["variantes_unidas"],
        "unioes": info["unioes"],
        "tabela": tabela_variantes(info["unioes"]),
        "componentes": info["componentes"],
        "componentes_pequenos": info["componentes_pequenos"],
        "isolados": info["isolados"],
        "sem_agrupamento": len(resultado.conjunto.nos_sem_grupo()),
    }


def analisa(dados: dict) -> dict:
    caminho = _valida_projeto(dados.get("projeto", ""))
    config = _config(dados)

    with ProjetoRedes(caminho) as kb:
        periodo = _periodo(kb, dados.get("periodo"))
        resultado = executa_periodo(kb, periodo.id, periodo.nome, config)
        paises = (colaboracao_do_periodo(kb, periodo.id, config.minimo_frequencia)
                  if config.unidade == "Countries"
                  and config.matriz == "CoOccurrence" else None)
        # Qualidade e rótulos novos: falhar aqui nunca derruba a análise.
        qual, rotulos_novos, anos = _qualidade_e_rotulos(kb, resultado)
        pivos_bruto = _calcula_pivos(kb, resultado)
        corpus = modulo_bibliometria.corpus_do_projeto(kb.conexao)

        densidade_info = _densidade_viavel(kb, config, resultado)
    grupos = sorted(resultado.grupos,
                    key=lambda grupo: (-len(grupo.nos), grupo.rotulo or "Sem grupo"))
    faixas = {"motor": 0, "nicho": 0, "emergente": 0, "basico": 0}
    saida_grupos = []
    posicao_original = {id(g): i for i, g in enumerate(resultado.grupos)}

    for indice, grupo in enumerate(grupos, start=1):
        quadrante = _quadrante(grupo.centralidade_faixa, grupo.densidade_faixa)
        faixas[quadrante] += 1
        saida_grupos.append({
            "selo": indice,
            "rotulo": grupo.exibicao,
            **_campos_novos(grupo, posicao_original.get(id(grupo)), qual,
                            rotulos_novos, anos),
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

    nomes_grupos = _nomes_dos_grupos(saida_grupos, posicao_original, grupos)
    pivos_pub = None
    try:
        if pivos_bruto is not None:
            pivos_pub = _pivos_publicos(pivos_bruto, nomes_grupos)
        elif resultado.rede.quantidade_nos() > LIMITE_PIVOS_INLINE:
            pivos_pub = {"adiado": True, "n_nos": resultado.rede.quantidade_nos(),
                         "pivos": [], "termos_descritores": [], "avisos": []}
    except Exception:
        pivos_pub = None

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
                           "config": config, "rotulos": rotulos_novos,
                           "pivos": pivos_bruto, "pivos_pub": pivos_pub,
                           "nomes_grupos": nomes_grupos}
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
                         f"{periodo_nome}", layout=registro["rede"],
                         rotulos=registro.get("rotulos"),
                         pivos=(registro.get("pivos") or {}).get("pivos") or None),
                encoding="utf-8")

        figuras["halo"] = f"/figura/{_registra(halo, FIGURAS, gera_halo)}"

        estrategico = pasta / "estrategico.svg"
        estrategico.write_text(
            diagrama_svg(resultado, f"Diagrama estratégico — {periodo.nome}",
                         rotulos=rotulos_novos),
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
    avisos, genericos = _avisos(resultado, config, saida_grupos, corpus)
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
            "componente_minimo": config.agrupamento_minimo(),
            "tamanho_minimo_agrupamento": config.agrupamento_minimo(),
        },
        "filtro_agrupamento": getattr(resultado, "filtro_agrupamento", None),
        "ies": _ies_publico(resultado),
        "avisos": avisos,
        "termos_genericos": genericos,
        "densidade": densidade_info,
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
        "qualidade": _qualidade_publica(qual, grupos, posicao_original),
        "pivos": pivos_pub,
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


def _densidade_viavel(kb, config, resultado) -> dict | None:
    """O mapa de densidade (corpus completo) tem itens suficientes? A interface decide com isto
    antes de chamar o endpoint, para não pedir um mapa que não existe."""
    from . import report
    from .viz import densidade
    if config.matriz != "CoOccurrence":
        return None
    itens = resultado.rede.quantidade_nos()
    if itens < densidade.MINIMO_NOS:       # o corpus inteiro tem pelo menos os itens do período
        try:
            itens = report.densidade_do_corpus(kb, config).rede.quantidade_nos()
        except Exception:
            pass
    return {"itens": itens, "minimo": densidade.MINIMO_NOS,
            "disponivel": itens >= densidade.MINIMO_NOS}


def _qualidade_e_rotulos(kb, resultado) -> tuple[dict | None, dict, dict]:
    """Qualidade, rótulos novos e anos dos documentos; cada parte falha sozinha."""
    try:
        qual = modulo_qualidade.avalia(resultado)
    except Exception:
        qual = None
    try:
        rotulos_novos = modulo_rotulos.rotula_grupos(kb, resultado) or {}
    except Exception:
        rotulos_novos = {}
    try:
        ids: set[int] = set()
        for grupo in resultado.grupos:
            ids |= set(grupo.documentos_nucleo)
        anos = modulo_qualidade.anos_dos_documentos(kb, ids) if ids else {}
    except Exception:
        anos = {}
    return qual, rotulos_novos, anos


def _campos_novos(grupo, original, qual, rotulos_novos, anos) -> dict:
    """`rotulo_novo`, `rotulo_indicativo`, `silhueta` e `ano_medio` de um agrupamento."""
    from .viz.halo import texto_rotulo_novo

    r = rotulos_novos.get(original) if original is not None else None
    silhueta = None
    if qual and original is not None:
        silhueta = (qual.get("silhueta_por_grupo") or {}).get(original)
    try:
        anos_grupo = [anos[d] for d in grupo.documentos_nucleo if d in anos]
    except Exception:
        anos_grupo = []
    return {
        "rotulo_novo": rotulo_legivel(r.get("rotulo")) if r else None,
        "rotulo_novo_curto": texto_rotulo_novo(r) if r else None,
        "rotulo_indicativo": bool(r.get("indicativo")) if r else None,
        "silhueta": None if silhueta is None else round(silhueta, 3),
        "ano_medio": round(sum(anos_grupo) / len(anos_grupo), 1) if anos_grupo else None,
    }


def _qualidade_publica(qual, grupos, posicao_original) -> dict | None:
    """Qualidade do período para a UI; a silhueta por grupo passa a vir por selo."""
    if not qual:
        return None
    saida = {k: (None if isinstance(v, float) and v != v else v)   # NaN não é JSON
             for k, v in qual.items() if k != "silhueta_por_grupo"}
    por_grupo = qual.get("silhueta_por_grupo") or {}
    saida["silhueta_por_selo"] = {
        str(selo): (None if por_grupo.get(posicao_original.get(id(g))) is None
                    else round(por_grupo[posicao_original[id(g)]], 3))
        for selo, g in enumerate(grupos, start=1)}
    return saida


LIMITE_GENERICO = modulo_avisos.LIMITES["fracao_termo_generico"]
LIMITE_GRUPOS_FRACOS = modulo_avisos.LIMITES["fracao_grupos_fracos"]


def _avisos(resultado, config, saida_grupos, corpus=None) -> tuple[list[dict], list[dict]]:
    """Alertas de leitura: frequência mínima baixa e termo genérico dominante."""
    avisos: list[dict] = []
    total_docs = resultado.dataset_original.quantidade_documentos()

    if (saida_grupos and "nucleo" in config.mapeadores
            and config.matriz == "CoOccurrence"):
        fracos = sum(1 for g in saida_grupos
                     if g["documentos"] <= modulo_avisos.LIMITES["documentos_grupo_fraco"])
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

    if (config.matriz == "AggregatedCouplingBasedOnJournal"
            and resultado.agregado is not None
            and len(resultado.agregado.lista_alto_nivel()) <= 1):
        avisos.append({
            "codigo": "um_periodico",
            "mensagem": (
                "O corpus tem um só periódico neste período, então o "
                "acoplamento agregado por periódico não forma rede nem "
                "agrupamentos (é preciso pelo menos dois). Use outra matriz "
                "ou outro período."),
        })

    genericos = []
    if total_docs >= modulo_avisos.LIMITES["documentos_minimos_termo_generico"]:
        original = resultado.dataset_original
        for item_id in original.lista_itens():
            frequencia = original.frequencia_item(item_id)
            if frequencia / total_docs >= LIMITE_GENERICO:
                genericos.append({
                    "rotulo": exibe_termo(config.unidade, original.rotulo_item(item_id)),
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
    avisos.extend(modulo_avisos.avisos_de_limite(
        resultado, config, [(g["rotulo"], g["documentos"]) for g in saida_grupos], corpus))
    return avisos, genericos


def _documentos_do_projeto(projeto: str, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    marcadores = ",".join("?" for _ in ids)
    with ProjetoRedes(projeto) as kb:
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

    Devolve ``(conteúdo, nome do arquivo, tipo MIME)``. Os formatos são Pajek,
    XML de grupos, GraphML, TSV de índices e TSV de
    documentos.
    """
    from . import exports

    analise = _analise(token)
    if analise.get("resultado") is None:
        _recalcula(analise)
    resultado = analise["resultado"]

    if tipo == "grupos-xml":
        with ProjetoRedes(analise["projeto"]) as kb:
            texto = exports.grupos_xml(kb.conexao)
        return texto.encode("utf-8"), "grupos.xml", "application/xml"

    # Palavras-chave guardadas em caixa alta saem em forma legível; o dado guardado não muda.
    unidade_do_resultado = resultado.configuracao.unidade
    rotulos = {no: exibe_termo(unidade_do_resultado, nome)
               for no, nome in resultado.dataset.itens.items()}
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
    with ProjetoRedes(analise["projeto"]) as kb:
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


def sugere_grafias(dados: dict) -> dict:
    from . import sugestoes

    caminho = _valida_projeto(dados.get("caminho", ""))
    with ProjetoRedes(caminho) as kb:
        try:
            return sugestoes.sugere(kb.conexao, dados.get("tipo", ""),
                                    dados.get("lista", ""))
        except ValueError as erro:
            raise ErroApi(str(erro)) from None


def edita_base(dados: dict) -> dict:
    """Edita a base de um projeto; depois, esquece o que foi guardado em cache dos rótulos."""
    try:
        return _edita_base(dados)
    finally:
        modulo_rotulos.limpa_cache()


def _edita_base(dados: dict) -> dict:
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
        if acao == "agrupar-sugestoes":
            return edit.agrupa_sugestoes(projeto, dados.get("tipo", ""),
                                         dados.get("agrupamentos") or [])
        if acao == "substituir":
            return edit.substitui(projeto, dados.get("tipo", ""),
                                  dados.get("de", ""), dados.get("para", ""))
        if acao == "desfazer":
            return edit.desfaz(projeto)
    except (KeyError, TypeError, ValueError, OverflowError, sqlite3.IntegrityError) as erro:
        raise ErroApi(str(erro)) from None
    raise ErroApi(f"ação de edição desconhecida: {acao}")


# --------------------------------------------------------- relatório e mapas

def gera_relatorio(dados: dict) -> dict:
    """Gera o relatório HTML e devolve a URL de abertura."""
    from . import cache_figuras, report

    caminho = _valida_projeto(dados.get("projeto", ""))
    config = _config(dados)
    formato = dados.get("formato") or "html"
    if formato != "html":
        raise ErroApi("O relatório é gerado somente em HTML.")
    estendido = bool(dados.get("estendido", False))
    medida = dados.get("medida_temporal", "EquivalenceIndex")

    with cache_figuras.escopo(), ProjetoRedes(caminho) as kb:
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
            _, antigo = RELATORIOS.popitem(last=False)
            _apaga_relatorio(antigo)

    arquivo = "index.html"
    return {"token": token, "formato": formato, "resumo": resumo,
            "url": f"/relatorio/{token}/{arquivo}",
            "indice": f"/relatorio/{token}/index.html"}


# Análises do relatório completo: (chave, rótulo, descrição, parâmetros, requisito em SQL).
ANALISES_COMPLETO = [
    ("conceitual", "Estrutura conceitual (palavras-chave)",
     "Palavras-chave em co-ocorrência: os temas que estruturam o campo.",
     {"unidade": "Words", "matriz": "CoOccurrence"},
     "SELECT COUNT(*) FROM WordGroup WHERE COALESCE(stopGroup,0)=0", 3,
     "a base não tem palavras-chave suficientes"),
    ("autores", "Colaboração entre autores",
     "Quem publica com quem, pela co-ocorrência de autores nos documentos.",
     {"unidade": "Authors", "matriz": "CoOccurrence"},
     "SELECT COUNT(*) FROM AuthorGroup WHERE COALESCE(stopGroup,0)=0", 3,
     "a base não tem autores suficientes"),
    ("paises", "Colaboração entre países",
     "Cooperação internacional: países que assinam os mesmos documentos.",
     {"unidade": "Countries", "matriz": "CoOccurrence"},
     "SELECT COUNT(*) FROM CountryGroup WHERE COALESCE(stopGroup,0)=0", 2,
     "a base não traz país de afiliação (precisa de ao menos dois países)"),
    ("instituicoes", "Colaboração entre instituições (IES)",
     "Instituições que assinam os mesmos documentos, com os nomes unidos quando a "
     "variante é inequívoca; componentes com menos de 3 instituições ficam sem agrupamento.",
     {"unidade": "Institutions", "matriz": "CoOccurrence"},
     "SELECT COUNT(DISTINCT Affiliation_idAffiliation) FROM Document_Affiliation", 3,
     "a base não traz afiliações suficientes (precisa de ao menos três instituições)"),
    ("referencias", "Cocitação de referências",
     "Obras citadas em conjunto pelos documentos do corpus.",
     {"unidade": "References", "matriz": "CoOccurrence"},
     "SELECT COUNT(*) FROM ReferenceGroup", 3,
     "a base não traz referências"),
    ("citados", "Cocitação de autores",
     "Autores citados em conjunto, formando a base intelectual do campo.",
     {"unidade": "AuthorsReference", "matriz": "CoOccurrence"},
     "SELECT COUNT(*) FROM AuthorReferenceGroup", 3,
     "a base não traz referências"),
    ("frentes", "Frentes de pesquisa (acoplamento bibliográfico)",
     "Documentos ligados por referências compartilhadas.",
     {"unidade": "References", "matriz": "BasicCoupling", "mapeadores": ["acoplamento"]},
     "SELECT COUNT(*) FROM ReferenceGroup", 3,
     "a base não traz referências"),
    ("veiculos", "Periódicos citados",
     "Periódicos citados em conjunto nas referências do corpus.",
     {"unidade": "ReferenceSources", "matriz": "CoOccurrence"},
     "SELECT COUNT(*) FROM ReferenceSourceGroup WHERE COALESCE(stopGroup,0)=0", 3,
     "a base não traz referências"),
]


def _apaga_relatorio(pasta: Path) -> None:
    """Apaga o relatório expulso do registro, mas só se ele estiver no cache do servidor."""
    try:
        if CACHE.resolve() in Path(pasta).resolve().parents:
            shutil.rmtree(pasta, ignore_errors=True)
    except OSError:
        pass


# Frequência mínima inicial por tipo de análise. Palavras-chave e citações
# precisam de 2 para não virarem uma lista de temas de um documento só; as
# unidades sociais (autores, países, instituições) têm poucos itens e já se
# organizam com 1.
FREQUENCIA_POR_UNIDADE = {
    "Words": 2,
    "Authors": 1,
    "Countries": 1,
    "Institutions": 1,
    "References": 2,
    "AuthorsReference": 2,
    "ReferenceSources": 2,
}
# Limites de qualidade para aceitar uma frequência: acima disso o mapa fica
# poluído (muitos grupos, a maioria com um documento só); abaixo, fraco.
MAX_GRUPOS_POR_PERIODO = 8
MAX_FRACAO_GRUPOS_FRACOS = 0.5
MIN_NOS_AGRUPADOS = 15
# Acima disso a figura deixa de ser legível na tela e o layout demora segundos.
# A frequência sobe até o mapa caber, como faz a opção "Nós: top N".
MAX_NOS_POR_PERIODO = 300


def _avalia_frequencia(resultados, acoplamento: bool = False) -> dict:
    """Resume a qualidade de uma frequência: grupos, nós e grupos de um documento.

    No acoplamento bibliográfico o grupo reúne documentos, e um grupo de um
    documento é esperado quando ele não compartilha referências, então a
    contagem de grupos fracos não se aplica. ``denso`` marca período com mais
    de ``MAX_NOS_POR_PERIODO`` nós: a figura cabe na tela, mas não se lê.
    """
    grupos = [len(r.grupos) for r in resultados]
    com_itens = [r.dataset_original.quantidade_itens() > 0 for r in resultados]
    nos_por_periodo = [sum(len(g.nos) for g in r.grupos) for r in resultados]
    nos = sum(nos_por_periodo)
    fracos = 0 if acoplamento else sum(
        1 for r in resultados for g in r.grupos if len(g.documentos_nucleo) <= 1)
    total = sum(grupos)
    return {
        "grupos": grupos,
        "vazio": any(n == 0 for n, tem in zip(grupos, com_itens) if tem),
        "nos": nos,
        "nos_por_periodo": nos_por_periodo,
        "denso": any(n > MAX_NOS_POR_PERIODO for n in nos_por_periodo),
        "fracos": fracos,
        "fracao_fraca": (fracos / total) if total else 0.0,
        "excesso": max(grupos, default=0) > MAX_GRUPOS_POR_PERIODO,
    }


def _escolhe_frequencia(kb, periodos, base: dict, parametros: dict, fixa=None):
    """Frequência mínima adequada ao tipo de análise.

    Cada unidade começa na sua frequência padrão (``FREQUENCIA_POR_UNIDADE``) e
    é ajustada quando o resultado fica fraco (período com itens e nenhum grupo,
    poucos nós) ou poluído (mais de ``MAX_GRUPOS_POR_PERIODO`` grupos, metade
    deles com um documento só, ou mais de ``MAX_NOS_POR_PERIODO`` nós num
    período). Entre as candidatas saudáveis fica a mais próxima do padrão; sem
    nenhuma saudável, a mais próxima. Com `fixa` (pedido pelo usuário) só ela é
    tentada.
    """
    unidade = parametros.get("unidade") or base.get("unidade") or "Words"
    matriz = parametros.get("matriz") or base.get("matriz") or "CoOccurrence"
    acoplamento = matriz == "BasicCoupling"
    if fixa:
        candidatas = (int(fixa),)
        padrao = int(fixa)
    else:
        padrao = FREQUENCIA_POR_UNIDADE.get(unidade, 2)
        ordem = [padrao]
        for passo in range(1, 3):
            if padrao - passo >= 1:
                ordem.append(padrao - passo)
            ordem.append(padrao + passo)
        candidatas = tuple(dict.fromkeys(ordem))

    avaliadas = []
    for frequencia in candidatas:
        config = _config({**base, **parametros, "minimo_frequencia": frequencia})
        resultados = [executa_periodo(kb, p.id, p.nome, config) for p in periodos]
        metricas = _avalia_frequencia(resultados, acoplamento)
        if sum(metricas["grupos"]) == 0:
            continue
        metricas.update({"frequencia": frequencia, "config": config,
                         "resultados": resultados, "distancia": abs(frequencia - padrao)})
        avaliadas.append(metricas)
    if not avaliadas:
        return None

    # Densidade vem primeiro: entre frequências que caibam na tela, a escolha
    # segue os critérios de grupo; se nenhuma couber, fica a menos densa.
    cabe = [m for m in avaliadas if not m["denso"]]
    if cabe:
        avaliadas = cabe
    else:
        avaliadas = sorted(avaliadas, key=lambda m: (max(m["nos_por_periodo"]),
                                                     abs(m["frequencia"] - padrao)))[:1]

    completas = [m for m in avaliadas if not m["vazio"]] or avaliadas
    saudaveis = [m for m in completas
                 if not m["excesso"]
                 and not m["denso"]
                 and m["fracao_fraca"] <= MAX_FRACAO_GRUPOS_FRACOS
                 and m["nos"] >= MIN_NOS_AGRUPADOS]
    escolhida = min(saudaveis or completas,
                    key=lambda m: (m["distancia"], -m["nos"]))
    return escolhida["config"], escolhida["frequencia"], escolhida["resultados"]


def gera_relatorio_completo(dados: dict) -> dict:
    """Uma análise por seção (as que a base permite), num relatório só."""
    from . import cache_figuras, paralelo, report

    caminho = _valida_projeto(dados.get("projeto", ""))
    base = {k: v for k, v in dados.items()
            if k in ("similaridade", "algoritmo", "ignorar", "tamanho_minimo", "tamanho_maximo",
                     "minimo_coocorrencia", "corte")}
    # Frequência mínima vinda da interface vale para todas as análises, como na tela;
    # sem ela, cada análise escolhe a sua (`_escolhe_frequencia`).
    frequencia_fixa = dados.get("minimo_frequencia")
    medida = dados.get("medida_temporal", "EquivalenceIndex")
    avancado = bool(dados.get("avancado"))

    with cache_figuras.escopo(), ProjetoRedes(caminho) as kb:
        periodos = kb.periodos()
        if not periodos:
            raise ErroApi("o projeto não tem períodos")
        corpus = modulo_bibliometria.corpus_do_projeto(kb.conexao)
        formato = dados.get("formato") or "unico"
        if formato not in ("unico", "pastas"):
            raise ErroApi("formato do relatório completo: unico ou pastas")
        token = secrets.token_urlsafe(10)
        destino = CACHE / f"rel-{token}"
        destino.mkdir(parents=True, exist_ok=True)

        # Cada análise pronta segue para um processo trabalhador (figuras e cálculos
        # pesados) enquanto esta thread analisa a próxima; `espera()` junta tudo.
        aquecedor = paralelo.Aquecedor(kb, formato, medida, destino)
        secoes, ignoradas = [], []
        for chave, rotulo, descricao, parametros, sql, minimo, motivo in ANALISES_COMPLETO:
            poucos_informativa = (corpus["focal"] and parametros.get("unidade")
                                  in modulo_avisos.UNIDADES_SOCIAIS_INSTITUCIONAIS)
            if poucos_informativa and not avancado:
                ignoradas.append({"rotulo": rotulo, "motivo": (
                    f"{modulo_avisos.POUCO_INFORMATIVO} (um autor está em mais de "
                    f"{modulo_avisos.LIMITES['fracao_autor_focal']:.0%} dos documentos); "
                    "ligue o Modo avançado para incluí-la.")})
                continue
            disponivel = kb.conexao.execute(sql).fetchone()[0]
            if disponivel < minimo:
                ignoradas.append({"rotulo": rotulo, "motivo": motivo + "."})
                continue
            fixa = (dados.get("frequencias") or {}).get(chave) or frequencia_fixa
            escolhida = _escolhe_frequencia(kb, periodos, base, parametros, fixa)
            if escolhida is None:
                ignoradas.append({"rotulo": rotulo,
                                  "motivo": "nenhum agrupamento se formou com os dados disponíveis."})
                continue
            config, frequencia, resultados_previos = escolhida
            pasta = f"{chave}"
            # Arquivo único: não há pasta de páginas; só o resultado é necessário.
            resumo = {"resultados": resultados_previos}
            nota = ""
            por_periodo = [len(r.grupos) for r in resumo["resultados"]]
            if por_periodo and max(por_periodo) <= 2:
                nota = (" Poucos agrupamentos: o corpus é pequeno para este mapa; "
                        "leia como indício, não como estrutura firme.")
            elif any(n == 0 for n in por_periodo):
                nota = " Há período sem agrupamentos (poucos documentos nele)."
            if poucos_informativa:
                nota += f" Atenção: {modulo_avisos.POUCO_INFORMATIVO}."
            origem = ("a mesma da tela" if fixa else
                      ("escolhida automaticamente: padrão deste tipo de análise, para "
                       "não gerar temas de um documento só nem esvaziar a rede"
                       if frequencia == FREQUENCIA_POR_UNIDADE.get(
                           parametros.get("unidade"), 2) else
                       "escolhida automaticamente: ajustada em relação ao padrão deste "
                       "tipo de análise porque o mapa ficava fraco ou poluído neste corpus"))
            secoes.append({"rotulo": rotulo,
                           "descricao": descricao + f" Frequência mínima {frequencia} ({origem})." + nota,
                           "pasta": pasta, "config": config, "resultados": resumo["resultados"]})
            aquecedor.submete(secoes[-1])
        aquecedor.espera()
        if not secoes:
            raise ErroApi("Nenhuma análise de mapeamento pôde ser gerada com esta base.")
        if formato == "pastas":
            for secao in secoes:
                if secao.get("pronta_em_pasta"):
                    continue          # um trabalhador já gravou as páginas desta análise
                token_voltar = report._VOLTAR.set("../index.html")
                try:
                    report.gera_html(destino / secao["pasta"], kb, periodos, secao["config"],
                                     False, medida, com_bibliometria=False,
                                     devolve_resultados=True, resultados=secao["resultados"])
                finally:
                    report._VOLTAR.reset(token_voltar)
            report._pagina_bibliometria(destino, kb)
            report.gera_pagina_completa(destino, kb, secoes, ignoradas, medida)
        if formato == "unico":
            from . import relatorio_unico
            relatorio_unico.gera_arquivo_unico(destino / "relatorio-completo.html", kb,
                                               periodos, secoes, ignoradas, medida)

    with TRAVA_REGISTRO:
        RELATORIOS[token] = destino
        while len(RELATORIOS) > 5:
            _, antigo = RELATORIOS.popitem(last=False)
            _apaga_relatorio(antigo)
    resposta = {"token": token, "formato": formato,
                "url": f"/relatorio/{token}/index.html",
                "pastas": f"/relatorio/{token}/index.html",
                "secoes": [s["rotulo"] for s in secoes], "ignoradas": ignoradas}
    if formato == "unico":
        resposta["url"] = f"/relatorio/{token}/relatorio-completo.html"
        resposta["download"] = f"/relatorio/{token}/relatorio-completo.html?download=1"
    return resposta


def gera_longitudinal(dados: dict) -> dict:
    """Monta os mapas de evolução e sobreposição de todos os períodos."""
    from . import longitudinal

    caminho = _valida_projeto(dados.get("projeto", ""))
    config = _config(dados)
    medida = dados.get("medida_temporal", "EquivalenceIndex")
    if not dados.get("todos_os_periodos", True):
        raise ErroApi("o mapa longitudinal precisa de todos os períodos")

    with ProjetoRedes(caminho) as kb:
        periodos = kb.periodos()
        if len(periodos) < 2:
            raise ErroApi("o projeto precisa de pelo menos dois períodos")
        resultados = [executa_periodo(kb, p.id, p.nome, config) for p in periodos]
        mapa = longitudinal.constroi(kb, config, periodos, medida, resultados=resultados)
        corpus = modulo_bibliometria.corpus_do_projeto(kb.conexao)
        # Avisos de limite por período (não bloqueiam o mapa).
        avisos_periodos = []
        for periodo, resultado in zip(periodos, resultados):
            por_grupo = [(g.exibicao, len(g.documentos_nucleo)) for g in resultado.grupos]
            lista, _ = _avisos(resultado, config,
                               [{"rotulo": r, "documentos": d} for r, d in por_grupo], corpus)
            avisos_periodos.append({
                "periodo": periodo.nome,
                "documentos": resultado.dataset_original.quantidade_documentos(),
                "temas": len(resultado.grupos),
                "avisos": [a for a in lista if a.get("nivel") == "limite"
                           or a["codigo"] == "grupos_fracos"]})

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
        "transicoes": mapa.transicoes,
        "periodos_avisos": avisos_periodos,
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
        with ProjetoRedes(caminho) as kb:
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
                            kb, periodo.id, periodo.nome, config,
                            cancelado=lambda: trabalho.cancelado)
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


def inicia_grade(dados: dict) -> dict:
    if _trabalho_ativo():
        raise ErroApi("já existe uma execução em andamento")

    caminho = _valida_projeto(dados.get("projeto", ""))
    with ProjetoRedes(caminho) as kb:
        periodos = kb.periodos()
    if not periodos:
        raise ErroApi("o projeto não tem períodos")

    trabalho = Trabalho("grade", 27 * len(UNIDADES_GRADE) * len(periodos))
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
    nome_limpo = Path(nome_arquivo).name
    if nome_limpo in ("", ".", ".."):
        raise ErroApi("Nome de arquivo inválido.")
    destino.mkdir(parents=True)
    try:
        return _importa_em(destino, nome_limpo, corpo, formato, texto_periodos,
                           autores_referencia, remove_repetidos)
    except BaseException:
        shutil.rmtree(destino, ignore_errors=True)  # não deixa pasta órfã quando falha
        raise


def _importa_em(destino: Path, nome_limpo: str, corpo: bytes, formato: str,
                texto_periodos: str, autores_referencia: str, remove_repetidos: bool) -> dict:
    from .loaders import le_corpus

    arquivo = destino / nome_limpo
    arquivo.write_bytes(corpo)
    # Os formatos tabulares se confundem pelo nome das colunas; o conteúdo
    # decide. Assim, escolher "CSV tabulado (Redes/WoS)" ou "CSV da Scopus" para um arquivo
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
            if e_projeto(entrada):
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
            continue
        projetos.append({
            "nome": entrada.name,
            "caminho": str(dados),
            "modificado": dados.stat().st_mtime,
        })
    projetos.sort(key=lambda item: item["modificado"], reverse=True)
    return projetos


# -------------------------------------------------------------------- servidor

# Cliente que fecha a aba ou cancela o download no meio da resposta.
ABORTOS_DE_CONEXAO = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)


class ServidorWeb(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        if isinstance(sys.exc_info()[1], ABORTOS_DE_CONEXAO):
            return
        super().handle_error(request, client_address)

    def __init__(self, endereco, workspace: Path):
        super().__init__(endereco, Manipulador)
        self.workspace = workspace
        self.ui = Path(__file__).parent / "ui"


class Manipulador(BaseHTTPRequestHandler):
    server: ServidorWeb
    server_version = "redes"

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

    def _json_seguro(self, codigo: int, dados) -> None:
        """Como `_json`, mas sem erro quando o cliente já foi embora."""
        try:
            self._json(codigo, dados)
        except ABORTOS_DE_CONEXAO:
            pass

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
                    "siglas": sorted(siglas_conhecidas()),
                    "nomes_proprios": NOMES_PROPRIOS,
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
                with ProjetoRedes(caminho) as kb:
                    self._json(200, bibliometria.calcula(kb.conexao))
            elif rota == "/api/fluxo":
                pedido = {k: v[0] for k, v in parametros.items() if v}
                dados = fluxo_autor_pais_ies(pedido)
                if pedido.get("baixar") in ("1", "true"):
                    if not dados["svg"]:
                        raise ErroApi((dados["avisos"] or ["Sem dados para o fluxo."])[0])
                    self._arquivo(dados["svg"].encode("utf-8"), "fluxo-autor-pais-ies.svg",
                                  "image/svg+xml", True)
                else:
                    self._json(200, dados)
            elif rota == "/api/dendrograma":
                pedido = {k: v[0] for k, v in parametros.items() if v}
                dados = dendrograma_do_pedido(pedido)
                if pedido.get("baixar") in ("1", "true"):
                    self._arquivo(dados["svg"].encode("utf-8"), "dendrograma.svg",
                                  "image/svg+xml", True)
                else:
                    self._json(200, dados)
            elif rota == "/api/linha-do-tempo":
                pedido = {k: v[0] for k, v in parametros.items() if v}
                dados = linha_do_tempo_do_pedido(pedido)
                if pedido.get("baixar") in ("1", "true"):
                    self._arquivo(dados["svg"].encode("utf-8"), "linha-do-tempo.svg",
                                  "image/svg+xml", True)
                else:
                    self._json(200, dados)
            elif rota == "/api/densidade":
                pedido = {k: v[0] for k, v in parametros.items() if v}
                dados = densidade_do_pedido(pedido)
                if pedido.get("baixar") in ("1", "true"):
                    self._arquivo(dados["svg"].encode("utf-8"), "densidade.svg",
                                  "image/svg+xml", True)
                else:
                    self._json(200, dados)
            elif rota == "/api/duplo-mapa":
                pedido = {k: v[0] for k, v in parametros.items() if v}
                dados = duplo_mapa_do_pedido(pedido)
                if pedido.get("baixar") in ("1", "true"):
                    self._arquivo(dados["svg"].encode("utf-8"), "duplo-mapa.svg",
                                  "image/svg+xml", True)
                else:
                    self._json(200, dados)
            elif rota == "/api/similitude":
                pedido = {k: v[0] for k, v in parametros.items() if v}
                dados = similitude_do_pedido(pedido)
                if dados["_baixar"]:
                    arquivo, nome, tipo = exportacao_similitude(dados)
                    self._arquivo(arquivo, nome, tipo, True)
                else:
                    dados.pop("_baixar")
                    self._json(200, dados)
            elif rota == "/api/pivos":
                self._json(200, pivos_da_analise(_param(parametros, "token")))
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
                    with ProjetoRedes(caminho) as kb:
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
                    with ProjetoRedes(caminho) as kb:
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
                baixar = (parametros.get("download") or ["0"])[0] == "1"
                self._arquivo(arquivo.read_bytes(), arquivo.name, tipo, baixar)
            elif rota.startswith("/api/trabalho/"):
                self._json(200, estado_trabalho(rota[len("/api/trabalho/"):]))
            elif rota == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            else:
                self.send_error(404)
        except ABORTOS_DE_CONEXAO:
            return                    # o cliente desistiu; não há a quem responder
        except ErroExpirado as erro:
            self._json_seguro(410, {"erro": str(erro), "expirada": True})
        except ErroApi as erro:
            self._json_seguro(400, {"erro": str(erro)})
        except Exception as erro:  # noqa: BLE001
            traceback.print_exc()
            self._json_seguro(500, {"erro": f"falha interna: {erro}"})

    def do_POST(self) -> None:  # noqa: N802
        analisado = urlparse(self.path)
        rota = analisado.path
        parametros = parse_qs(analisado.query)

        try:
            if rota == "/api/abrir":
                dados = self._json_pedido()
                caminho = _valida_projeto(dados.get("caminho", ""))
                self._json(200, descreve_projeto(caminho))
            elif rota == "/api/fluxo":
                self._json(200, fluxo_autor_pais_ies(self._json_pedido()))
            elif rota == "/api/dendrograma":
                self._json(200, dendrograma_do_pedido(self._json_pedido()))
            elif rota == "/api/linha-do-tempo":
                self._json(200, linha_do_tempo_do_pedido(self._json_pedido()))
            elif rota == "/api/densidade":
                self._json(200, densidade_do_pedido(self._json_pedido()))
            elif rota == "/api/duplo-mapa":
                self._json(200, duplo_mapa_do_pedido(self._json_pedido()))
            elif rota == "/api/similitude":
                dados = similitude_do_pedido(self._json_pedido())
                if dados["_baixar"]:
                    arquivo, nome, tipo = exportacao_similitude(dados)
                    self._arquivo(arquivo, nome, tipo, True)
                else:
                    dados.pop("_baixar")
                    self._json(200, dados)
            elif rota == "/api/analisa":
                self._json(200, analisa(self._json_pedido()))
            elif rota == "/api/grade":
                self._json(202, inicia_grade(self._json_pedido()))
            elif rota == "/api/base":
                self._json(200, edita_base(self._json_pedido()))
            elif rota == "/api/sugestoes":
                self._json(200, sugere_grafias(self._json_pedido()))
            elif rota == "/api/relatorio":
                self._json(200, gera_relatorio(self._json_pedido()))
            elif rota == "/api/relatorio-completo":
                self._json(200, gera_relatorio_completo(self._json_pedido()))
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
        except ABORTOS_DE_CONEXAO:
            return                    # o cliente desistiu; não há a quem responder
        except ErroExpirado as erro:
            self._json_seguro(410, {"erro": str(erro), "expirada": True})
        except ErroApi as erro:
            self._json_seguro(400, {"erro": str(erro)})
        except Exception as erro:  # noqa: BLE001
            traceback.print_exc()
            self._json_seguro(500, {"erro": f"falha interna: {erro}"})


def cria_servidor(porta: int = 8765, workspace: str | Path | None = None,
                  host: str = "127.0.0.1") -> ServidorWeb:
    raiz = Path(workspace).expanduser().resolve() if workspace else (
        Path.home() / "redes-projetos")
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
    print(f"redes web em {endereco}")
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

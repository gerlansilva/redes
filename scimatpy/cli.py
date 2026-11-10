"""Linha de comando do scimatpy."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .kb import ProjetoScimat
from .pipeline import Configuracao, executa_periodo
from .projeto import NOME_PADRAO, com_extensao
from .viz.halo import halo_svg
from .viz.strategic import diagrama_svg

CABECALHO = ["periodo", "eixo", "unidade", "matriz", "algoritmo", "similaridade",
             "mapeador", "medida", "palavras", "min_freq", "min_cooc", "rede_min",
             "rede_max", "corte", "documentos", "itens", "itens_reduzidos",
             "grupos", "maior_grupo", "grupos_unitarios", "nos_rede",
             "arestas_rede", "centralidade_media", "densidade_media", "valor_medida"]


def _valor_medida(resultado, mapeador: str, medida: str | None) -> float | str:
    if not medida:
        return ""
    chave = f"{mapeador}:{medida}"
    valores = [g.medidas[chave] for g in resultado.grupos if chave in g.medidas]
    return round(sum(valores) / len(valores), 4) if valores else ""


def _linha(resultado, eixo: str = "", mapeador: str = "", medida: str | None = None) -> list:
    grupos = resultado.grupos
    config = resultado.configuracao
    return [
        resultado.periodo,
        eixo,
        config.unidade,
        config.matriz,
        config.algoritmo,
        config.similaridade,
        mapeador,
        medida or "",
        "+".join(config.palavras) or "todas",
        config.minimo_frequencia,
        config.minimo_coocorrencia,
        config.tamanho_minimo,
        config.tamanho_maximo,
        config.corte,
        resultado.dataset_original.quantidade_documentos(),
        resultado.dataset_original.quantidade_itens(),
        resultado.dataset.quantidade_itens(),
        len(grupos),
        max((len(g.nos) for g in grupos), default=0),
        sum(1 for g in grupos if len(g.nos) == 1),
        resultado.rede.quantidade_nos(),
        resultado.rede.quantidade_arestas(),
        round(sum(g.centralidade for g in grupos) / len(grupos), 4) if grupos else 0.0,
        round(sum(g.densidade for g in grupos) / len(grupos), 4) if grupos else 0.0,
        _valor_medida(resultado, mapeador, medida),
    ]


def _config(args) -> Configuracao:
    return Configuracao(
        unidade=args.unidade,
        matriz=args.matriz,
        algoritmo=args.algoritmo,
        similaridade=args.similaridade,
        minimo_frequencia=args.min_freq,
        minimo_coocorrencia=args.min_cooc,
        tamanho_minimo=args.rede_min,
        tamanho_maximo=args.rede_max,
        corte=args.corte,
        mapeadores=tuple(args.mapeadores),
        k_core=args.k_core,
        palavras=tuple(args.palavras),
        indices=tuple(args.indices),
    )


def comando_analisa(args) -> int:
    with ProjetoScimat(args.projeto) as kb:
        periodos = kb.periodos()
        if args.periodo:
            periodos = [p for p in periodos if p.nome in args.periodo]
        if not periodos:
            print("nenhum período selecionado", file=sys.stderr)
            return 1

        if args.saida:
            Path(args.saida).parent.mkdir(parents=True, exist_ok=True)
            arquivo = open(args.saida, "w", encoding="utf-8", newline="")
            escritor = csv.writer(arquivo, delimiter="\t")
            escritor.writerow(CABECALHO)
        else:
            arquivo = None
            escritor = csv.writer(sys.stdout, delimiter="\t")
            escritor.writerow(CABECALHO)

        for periodo in periodos:
            resultado = executa_periodo(kb, periodo.id, periodo.nome, _config(args))
            escritor.writerow(_linha(resultado))

            if args.halo:
                titulo = f"Rede de {{unidade}} — {periodo.nome}"
                svg = halo_svg(resultado, titulo)
                destino = Path(args.halo.format(periodo=periodo.posicao))
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(svg, encoding="utf-8")
                print(f"halo: {destino}", file=sys.stderr)

            if args.estrategico:
                titulo = f"Diagrama estratégico — {periodo.nome}"
                svg = diagrama_svg(resultado, titulo)
                destino = Path(args.estrategico.format(periodo=periodo.posicao))
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(svg, encoding="utf-8")
                print(f"estratégico: {destino}", file=sys.stderr)

        if arquivo:
            arquivo.close()
    return 0


def comando_grade(args) -> int:
    from .grade import grade  # import tardio para evitar ciclo

    with ProjetoScimat(args.projeto) as kb:
        periodos = kb.periodos()
        saida = Path(args.saida)
        saida.parent.mkdir(parents=True, exist_ok=True)
        with open(saida, "w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.writer(arquivo, delimiter="\t")
            escritor.writerow(CABECALHO)
            total = 0
            for (eixo, unidade, matriz, algoritmo, similaridade, freq, cooc,
                 minimo, maximo, mapeador, medida) in grade():
                if medida:
                    indices = (medida,)
                else:
                    indices = ("h", "g", "hg", "q2", "media", "soma", "minimo", "maximo")
                config = Configuracao(unidade=unidade, matriz=matriz, algoritmo=algoritmo,
                                      similaridade=similaridade, minimo_frequencia=freq,
                                      minimo_coocorrencia=cooc, tamanho_minimo=minimo,
                                      tamanho_maximo=maximo,
                                      mapeadores=(mapeador,), indices=indices)
                for periodo in periodos:
                    resultado = executa_periodo(kb, periodo.id, periodo.nome, config)
                    escritor.writerow(_linha(resultado, eixo, mapeador, medida))
                    total += 1
            print(f"{total} análises em {saida}", file=sys.stderr)
    return 0


def comando_constroi(args) -> int:
    from . import build
    from .loaders import (bibtex, csv as csv_loader, detecta_formato, openalex,
                          ris, scopus, wos)

    formato = args.formato
    if formato == "auto":
        formato = detecta_formato(args.entrada)
    if formato == "csv":
        documentos = csv_loader.le(args.entrada)
    elif formato == "bibtex":
        documentos = bibtex.le(args.entrada)
    elif formato == "ris":
        documentos = ris.le(args.entrada)
    elif formato == "wos":
        documentos = wos.le(args.entrada)
    elif formato == "scopus":
        documentos = scopus.le(args.entrada)
    else:
        documentos = openalex.le(args.entrada, args.sinonimos)

    faixas = []
    for faixa in (args.periodos or "").split(","):
        if not faixa.strip():
            continue
        inicio, fim = faixa.strip().split("-")
        inicio, fim = int(inicio), int(fim)
        faixas.append((f"{inicio}\u2013{fim}", inicio, fim))

    saida = com_extensao(args.saida)
    resumo = build.constroi(documentos, saida, faixas)

    print(f"{resumo['documentos']} documentos → {saida}")
    print(f"palavras: {resumo['palavras']} grafias, {resumo['grupos_palavra']} grupos")
    print(f"autores: {resumo['autores']} grafias, {resumo['grupos_autor']} grupos")
    print(f"referências: {resumo['referencias']} itens, {resumo['grupos_referencia']} grupos")
    print(f"autores de referência: {resumo['autores_referencia']} grafias, "
          f"{resumo['grupos_autor_referencia']} grupos")
    print(f"fontes: {resumo['fontes']} grafias, {resumo['grupos_fonte']} grupos")
    print(f"países: {resumo['paises']}")
    for unidade, dados in resumo["unidades"].items():
        print(f"  {unidade}: {dados['itens']} itens em {dados['documentos']} documentos")
    return 0


def comando_web(args) -> int:
    from .api import serve

    serve(porta=args.porta, workspace=args.projetos, abrir=not args.nao_abrir)
    return 0


def monta_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scimatpy", description="Redes — análise da produção científica.")
    sub = parser.add_subparsers(dest="comando", required=True)

    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("projeto", help="arquivo do projeto (dados.redes)")
    comum.add_argument("--unidade", default="Words",
                       choices=["Words", "Authors", "References",
                                "AuthorsReference", "ReferenceSources",
                                "Countries"])
    comum.add_argument("--matriz", default="CoOccurrence",
                       choices=["CoOccurrence", "BasicCoupling",
                                "AggregatedCouplingBasedOnAuthor",
                                "AggregatedCouplingBasedOnJournal"])
    comum.add_argument("--algoritmo", default="CentersSimples",
                       choices=["CentersSimples", "AverageLink", "CompleteLink",
                                "SingleLink", "SumLink", "Louvain"])
    comum.add_argument("--similaridade", default="EquivalenceIndex",
                       choices=["AssociationStrength", "EquivalenceIndex",
                                "InclusionIndex", "JaccardIndex", "SaltonCosine"])
    comum.add_argument("--min-freq", type=int, default=1)
    comum.add_argument("--min-cooc", type=int, default=1)
    comum.add_argument("--rede-min", type=int, default=2)
    comum.add_argument("--rede-max", type=int, default=15)
    comum.add_argument("--corte", type=float, default=0.0,
                       help="similaridade mínima para unir grupos hierárquicos")
    comum.add_argument("--mapeadores", nargs="+", default=["nucleo"],
                       choices=["nucleo", "interseccao", "secundarios", "kcore",
                                "uniao", "acoplamento"],
                       help="mapeadores de documentos a aplicar")
    comum.add_argument("--k-core", type=int, default=2, dest="k_core",
                       help="valor de k do mapeador k-core")
    comum.add_argument("--palavras", nargs="+", default=["autor", "fonte"],
                       choices=["autor", "fonte", "adicionada"],
                       help="origens das palavras usadas na unidade Words")
    comum.add_argument("--indices", nargs="+",
                       default=["h", "g", "hg", "q2", "media", "soma", "minimo", "maximo"],
                       choices=["h", "g", "hg", "q2", "media", "soma", "minimo", "maximo"],
                       help="índices de desempenho a calcular")
    comum.add_argument("--periodo", nargs="*", help="nomes dos períodos")
    comum.add_argument("--saida", help="arquivo TSV de saída")

    analisa = sub.add_parser("analisa", parents=[comum],
                             help="executa uma configuração e grava TSV")
    analisa.add_argument("--halo", help="padrão do SVG, ex.: figuras/{periodo}.svg")
    analisa.add_argument("--estrategico", help="padrão do SVG do diagrama estratégico")
    analisa.set_defaults(funcao=comando_analisa)

    constroi = sub.add_parser("constroi", help="importa um corpus e grava o projeto")
    constroi.add_argument("entrada", help="arquivo de origem")
    constroi.add_argument("--formato", default="auto",
                          choices=["auto", "csv", "bibtex", "ris", "openalex",
                                   "wos", "scopus"])
    constroi.add_argument("--saida", default=NOME_PADRAO)
    constroi.add_argument("--periodos", default=None,
                          help="faixas separadas por vírgula, ex.: 2008-2014,2015-2020 "
                               "(padrão: intervalo real de anos do corpus)")
    constroi.add_argument("--sinonimos", help="arquivo de sinônimos (formato OpenAlex)")
    constroi.set_defaults(funcao=comando_constroi)

    grade = sub.add_parser("grade", help="executa a grade completa de análises")
    grade.add_argument("projeto", help="arquivo do projeto (dados.redes)")
    grade.add_argument("--saida", default="analises.tsv")
    grade.set_defaults(funcao=comando_grade)

    web = sub.add_parser("web", help="abre a interface web local")
    web.add_argument("--porta", type=int, default=8765)
    web.add_argument("--projetos", help="diretório dos projetos (padrão: ~/scimatpy-projetos)")
    web.add_argument("--nao-abrir", action="store_true",
                     help="não abre o navegador automaticamente")
    web.set_defaults(funcao=comando_web)

    return parser


def main(argv=None) -> int:
    args = monta_parser().parse_args(argv)
    return args.funcao(args)


if __name__ == "__main__":
    raise SystemExit(main())

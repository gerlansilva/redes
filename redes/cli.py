"""Linha de comando do redes."""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path

from . import __version__
from .kb import ProjetoRedes
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


CABECALHO_GRUPOS = ["periodo", "unidade", "grupo", "nome", "itens", "n_itens",
                    "documentos", "centralidade", "densidade", "quadrante"]


def _linhas_grupos(resultado) -> list[list]:
    """Uma linha por grupo/tema: nome, itens, documentos, medidas e quadrante."""
    from .viz.strategic import _quadrante, _quadrantes

    unidade = resultado.configuracao.unidade
    nomes = _quadrantes(unidade)
    linhas = []
    for posicao, grupo in enumerate(resultado.grupos, start=1):
        chave = _quadrante(grupo.centralidade_faixa, grupo.densidade_faixa)
        itens = [resultado.item(no) for no in grupo.nos]
        linhas.append([
            resultado.periodo, unidade, posicao, grupo.exibicao,
            "; ".join(itens), len(grupo.nos), len(grupo.documentos_nucleo),
            round(grupo.centralidade, 4), round(grupo.densidade, 4),
            nomes[chave][0],
        ])
    return linhas


def _caminho_grupos(args) -> Path | None:
    if getattr(args, "saida_grupos", None):
        return Path(args.saida_grupos)
    if args.saida:
        saida = Path(args.saida)
        return saida.with_name(saida.stem + "_grupos.tsv")
    return None


def _lista_ignorar(valores) -> tuple[str, ...]:
    """Itens a descartar: aceita vários argumentos e ";" ou quebra de linha como separador.

    A vírgula não separa, porque ela faz parte de nomes como "Lopes, C.E.".
    """
    saida = []
    for valor in valores or ():
        for parte in str(valor).replace("\n", ";").split(";"):
            if parte.strip():
                saida.append(parte.strip())
    return tuple(saida)


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
        componente_minimo=args.componente_min,
        ignorar=_lista_ignorar(getattr(args, "ignorar", None)),
    )


def comando_analisa(args) -> int:
    with ProjetoRedes(args.projeto) as kb:
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

        caminho_grupos = _caminho_grupos(args)
        arquivo_grupos = escritor_grupos = None
        if caminho_grupos:
            caminho_grupos.parent.mkdir(parents=True, exist_ok=True)
            arquivo_grupos = open(caminho_grupos, "w", encoding="utf-8", newline="")
            escritor_grupos = csv.writer(arquivo_grupos, delimiter="\t")
            escritor_grupos.writerow(CABECALHO_GRUPOS)

        for periodo in periodos:
            resultado = executa_periodo(kb, periodo.id, periodo.nome, _config(args))
            escritor.writerow(_linha(resultado))
            if escritor_grupos:
                escritor_grupos.writerows(_linhas_grupos(resultado))

            # Período sem documentos não tem agrupamento para desenhar; o TSV
            # continua registrando o período vazio, mas as figuras são puladas.
            vazio = resultado.dataset_original.quantidade_itens() == 0
            if vazio and (args.halo or args.estrategico):
                print(f"sem documentos em {periodo.nome}: figuras não geradas",
                      file=sys.stderr)

            if args.halo and not vazio:
                titulo = f"Rede de {{unidade}} — {periodo.nome}"
                svg = halo_svg(resultado, titulo)
                destino = Path(args.halo.format(periodo=periodo.posicao))
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(svg, encoding="utf-8")
                print(f"halo: {destino}", file=sys.stderr)

            if args.estrategico and not vazio:
                titulo = f"Diagrama estratégico — {periodo.nome}"
                svg = diagrama_svg(resultado, titulo)
                destino = Path(args.estrategico.format(periodo=periodo.posicao))
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(svg, encoding="utf-8")
                print(f"estratégico: {destino}", file=sys.stderr)

        if arquivo:
            arquivo.close()
        if arquivo_grupos:
            arquivo_grupos.close()
            print(f"grupos: {caminho_grupos}", file=sys.stderr)
    return 0


def comando_grade(args) -> int:
    from .grade import grade  # import tardio para evitar ciclo

    with ProjetoRedes(args.projeto) as kb:
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
    from .loaders import le_corpus

    documentos, formato = le_corpus(
        args.entrada, args.formato, args.sinonimos, sinonimos_em=tuple(args.sinonimos_em),
        autor_por=args.autor_por, normaliza_palavras=args.normaliza_palavras)
    if not documentos:
        raise ValueError(
            "nenhum registro com título foi encontrado em "
            f"{args.entrada} (formato {formato}); confira o formato do arquivo "
            "ou use --formato.")

    faixas = []
    for faixa in (args.periodos or "").split(","):
        if not faixa.strip():
            continue
        try:
            inicio, fim = (int(parte) for parte in faixa.strip().split("-"))
        except ValueError:
            raise ValueError(
                f"período inválido: {faixa.strip()!r}; use o formato 2008-2014, "
                "separando as faixas por vírgula.") from None
        faixas.append((f"{inicio}\u2013{fim}", inicio, fim))

    saida = com_extensao(args.saida)
    resumo = build.constroi(documentos, saida, faixas,
                            remove_repetidos=not args.manter_repetidos,
                            autores_referencia=args.autores_referencia,
                            unir_periodicos=not args.nao_unir_periodicos)

    print(f"{resumo['documentos']} documentos ({formato}) → {saida}")
    if resumo["duplicatas_removidas"]:
        print(f"duplicatas removidas: {resumo['duplicatas_removidas']} "
              f"de {resumo['documentos_lidos']} registros lidos")
    if resumo["sem_citacoes"]:
        print(f"AVISO: {resumo['sem_citacoes']} documento(s) sem 'Cited by' (campo vazio): "
              "guardados como ausentes, não como zero citações", file=sys.stderr)
    print(f"sem palavras-chave: {resumo['sem_palavras']}; sem país: "
          f"{resumo['sem_pais']}; sem referências: {resumo['sem_referencias']}")
    print(f"palavras: {resumo['palavras']} grafias, {resumo['grupos_palavra']} grupos")
    print(f"autores: {resumo['autores']} grafias, {resumo['grupos_autor']} grupos")
    print(f"referências: {resumo['referencias']} itens, {resumo['grupos_referencia']} grupos")
    print(f"autores de referência: {resumo['autores_referencia']} grafias, "
          f"{resumo['grupos_autor_referencia']} grupos")
    print(f"fontes: {resumo['fontes']} grafias, {resumo['grupos_fonte']} grupos")
    for adotada, variantes in resumo["periodicos_unidos"].items():
        print(f"periódico unido: {adotada} <- {' | '.join(variantes)}")
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
        prog="redes", description="Redes — análise da produção científica.")
    parser.add_argument("--version", action="version",
                        version=f"redes {__version__}")
    sub = parser.add_subparsers(dest="comando", required=True)

    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("projeto", help="arquivo do projeto (dados.redes)")
    comum.add_argument("--unidade", default="Words",
                       choices=["Words", "Authors", "References",
                                "AuthorsReference", "ReferenceSources",
                                "Countries", "Institutions"])
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
    comum.add_argument("--tamanho-minimo-agrupamento", "--componente-min", type=int,
                       default=None, dest="componente_min",
                       help="unidades Authors, Countries e Institutions: componentes "
                            "com menos nós que isto ficam sem agrupamento "
                            "(padrão: 3 em Institutions; 1 = sem filtro nas demais)")
    comum.add_argument("--k-core", type=int, default=2, dest="k_core",
                       help="valor de k do mapeador k-core")
    comum.add_argument("--palavras", nargs="+", default=["autor", "fonte"],
                       choices=["autor", "fonte", "adicionada"],
                       help="origens das palavras usadas na unidade Words")
    comum.add_argument("--indices", nargs="+",
                       default=["h", "g", "hg", "q2", "media", "soma", "minimo", "maximo"],
                       choices=["h", "g", "hg", "q2", "media", "soma", "minimo", "maximo"],
                       help="índices de desempenho a calcular")
    comum.add_argument("--ignorar", nargs="+", default=None, metavar="ITEM",
                       help="itens a descartar antes de montar a rede (sem distinguir caixa, "
                            "acento ou pontuação), ex.: --ignorar 'Lopes C.E.' ; "
                            "aceita vários, ou separados por ';'")
    comum.add_argument("--periodo", nargs="*", help="nomes dos períodos")
    comum.add_argument("--saida", help="arquivo TSV de saída")
    comum.add_argument("--saida-grupos", dest="saida_grupos",
                       help="TSV com uma linha por grupo/tema (analisa; padrão: "
                            "<saida>_grupos.tsv quando --saida é dado)")

    analisa = sub.add_parser("analisa", parents=[comum],
                             help="executa uma configuração e grava TSV")
    analisa.add_argument("--halo", help="padrão do SVG, ex.: figuras/{periodo}.svg")
    analisa.add_argument("--estrategico", help="padrão do SVG do diagrama estratégico")
    analisa.set_defaults(funcao=comando_analisa)

    constroi = sub.add_parser("constroi", help="importa um corpus e grava o projeto")
    constroi.add_argument("entrada", help="arquivo de origem")
    constroi.add_argument("--formato", default="auto",
                          choices=["auto", "csv", "bibtex", "ris", "openalex",
                                   "wos", "scopus", "zotero"])
    constroi.add_argument("--saida", default=NOME_PADRAO)
    constroi.add_argument("--periodos", default=None,
                          help="faixas separadas por vírgula, ex.: 2008-2014,2015-2020 "
                               "(padrão: intervalo real de anos do corpus)")
    constroi.add_argument("--sinonimos", help="arquivo de sinônimos (formato OpenAlex)")
    constroi.add_argument("--sinonimos-em", nargs="+", default=["palavras"],
                          choices=["palavras", "autores", "instituicoes", "periodicos",
                                   "paises", "todas"],
                          help="unidades em que o mapa de sinônimos vale (padrão: palavras); "
                               "linhas com # e comentários no fim da linha são ignorados")
    constroi.add_argument("--autor-por", default="abreviado",
                          choices=["abreviado", "nome-completo"],
                          help="como identificar o autor: grafia curta (padrão, "
                               "'Lopes, C.E.') ou a coluna 'Author full names' quando existir")
    constroi.add_argument("--normaliza-palavras", default="nenhuma",
                          choices=["nenhuma", "radical"],
                          help="'radical' une palavras-chave de mesmo radical "
                               "(statistics education = statistical education); desligado por padrão")
    constroi.add_argument("--manter-repetidos", action="store_true",
                          help="não junta registros com o mesmo DOI ou título e ano")
    constroi.add_argument("--autores-referencia", default="primeiro",
                          choices=["primeiro", "todos", "lista"],
                          help="quem conta como autor citado: o primeiro autor "
                               "da obra (padrão), todos, ou a lista inteira "
                               "como um só item (comportamento antigo)")
    constroi.add_argument("--nao-unir-periodicos", action="store_true",
                          help="não junta periódicos que só diferem por caixa, "
                               "acento ou pontuação (ex.: Suma/SUMA)")
    constroi.set_defaults(funcao=comando_constroi)

    grade = sub.add_parser("grade", help="executa a grade completa de análises")
    grade.add_argument("projeto", help="arquivo do projeto (dados.redes)")
    grade.add_argument("--saida", default="analises.tsv")
    grade.set_defaults(funcao=comando_grade)

    web = sub.add_parser("web", help="abre a interface web local")
    web.add_argument("--porta", type=int, default=8765)
    web.add_argument("--projetos", help="diretório dos projetos (padrão: ~/redes-projetos)")
    web.add_argument("--nao-abrir", action="store_true",
                     help="não abre o navegador automaticamente")
    web.set_defaults(funcao=comando_web)

    return parser


def main(argv=None) -> int:
    args = monta_parser().parse_args(argv)
    try:
        return args.funcao(args)
    except BrokenPipeError:  # saída fechada por `| head`: não é erro
        return 0
    except (OSError, ValueError, OverflowError, sqlite3.DatabaseError, csv.Error) as erro:
        # Mensagem curta em vez de traceback para os erros de uso mais comuns
        # (arquivo ausente, formato errado, projeto inválido, porta inválida).
        # REDES_DEBUG=1 devolve o traceback completo.
        if os.environ.get("REDES_DEBUG"):
            raise
        if isinstance(erro, OverflowError):
            erro = "porta inválida (use um número de 1 a 65535)"
        elif isinstance(erro, FileNotFoundError) and erro.filename:
            erro = f"arquivo não encontrado: {erro.filename}"
        print(f"redes: erro: {erro}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

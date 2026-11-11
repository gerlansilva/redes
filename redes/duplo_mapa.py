"""Duplo mapa simplificado (dual-map overlay do CiteSpace): de que áreas para que áreas.

À esquerda ficam as revistas que **publicam** os documentos do corpus (as ``N`` que
mais citam) e à direita as revistas **citadas** por elas (as ``M`` mais citadas por
esse conjunto). Cada revista pertence a uma área, inferida por palavras do **nome**
(`redes.areas`: aproximada, configurável e conferível na tabela devolvida). As
faixas entre as colunas somam as citações de uma área da esquerda para uma área da
direita, só entre as revistas desenhadas.

Cada referência de cada documento do corpus completo conta uma citação, da revista do
documento para a revista (ou grupo de revistas, como editado na base) da referência.
Referências sem periódico identificado (``Sem fonte``) e grupos ocultos ficam de fora, e
o total de ambos é informado. Não é o mapa do CiteSpace: lá as áreas vêm das categorias
das bases e as faixas são ponderadas por z-score; aqui são contagens simples.

`calcula` é puro (recebe contagens e devolve dados); `le_citacoes` lê o projeto.
"""
from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict

from . import areas as _areas
from .references import SEM_FONTE
from .texto import termo_legivel

MAX_ESQ = 10                 # revistas que publicam (padrão)
MAX_DIR = 16                 # revistas citadas (padrão)
LIMITE_ESQ = (3, 30)
LIMITE_DIR = (5, 40)
EXTRAS_NAO_CLASSIFICADAS = 15   # revistas frequentes sem área, fora do desenho, na tabela
AVISO_APROXIMADA = ("A área de cada revista é inferida por palavras do nome da revista; é uma "
                    "classificação aproximada, que pode errar ou deixar revistas sem área. "
                    "Confira a tabela revista → área.")

COLUNAS = ("Revistas que publicam o corpus", "Revistas citadas")
TITULO = "Duplo mapa — áreas das revistas que publicam e das revistas citadas (corpus completo)"
NOTA = (
    "Como ler: à esquerda estão as revistas que publicam os documentos do corpus completo "
    "(as que mais citam) e à direita as revistas que elas citam (as mais citadas por esse "
    "conjunto), agrupadas e coloridas por área. Cada faixa liga uma área da esquerda a uma "
    "área da direita, e a largura é o número de citações (referências) entre revistas "
    "desenhadas; uma faixa larga mostra de onde o corpus tira o seu conhecimento. A área de "
    "cada revista é inferida por palavras do NOME da revista, não por uma base de categorias: "
    "a classificação é aproximada, pode errar e deixa revistas em \"Não classificado\". "
    "A tabela revista → área, com o termo que decidiu cada caso, serve para conferir; "
    "referências sem periódico identificado não entram.")


def le_citacoes(conexao) -> dict:
    """Contagens do projeto: ``{(revista do documento, revista citada): n}`` e totais.

    Devolve ``citacoes`` (Counter), ``documentos`` (total), ``documentos_com_revista``,
    ``referencias_sem_fonte`` (citações descartadas por falta de periódico ou grupo oculto).
    """
    citacoes: Counter = Counter()
    base = ("FROM Document d JOIN Journal j ON j.idJournal = d.Journal_idJournal "
            "JOIN Document_Reference dr ON dr.Document_idDocument = d.idDocument "
            "JOIN Reference r ON r.idReference = dr.Reference_idReference "
            "JOIN ReferenceSource rs ON rs.idReferenceSource = r.ReferenceSource_idReferenceSource "
            "LEFT JOIN ReferenceSourceGroup g "
            "ON g.idReferenceSourceGroup = rs.ReferenceSourceGroup_idReferencesourceGroup "
            "WHERE COALESCE(j.source, '') <> '' ")
    oculta = "(COALESCE(g.stopGroup, 0) <> 0 OR rs.source = ? OR COALESCE(rs.source, '') = '')"
    try:
        for citante, citada, n in conexao.execute(
                "SELECT j.source, COALESCE(g.groupName, rs.source), COUNT(*) " + base
                + f"AND NOT {oculta} GROUP BY 1, 2", (SEM_FONTE,)):
            if citante and citada:
                citacoes[(citante, citada)] += n
        sem_fonte = conexao.execute("SELECT COUNT(*) " + base + f"AND {oculta}",
                                    (SEM_FONTE,)).fetchone()[0]
        documentos = conexao.execute("SELECT COUNT(*) FROM Document").fetchone()[0]
        com_revista = conexao.execute(
            "SELECT COUNT(*) FROM Document d JOIN Journal j ON j.idJournal = d.Journal_idJournal "
            "WHERE COALESCE(j.source, '') <> ''").fetchone()[0]
    except sqlite3.Error:
        return {"citacoes": Counter(), "documentos": 0, "documentos_com_revista": 0,
                "referencias_sem_fonte": 0}
    return {"citacoes": citacoes, "documentos": documentos,
            "documentos_com_revista": com_revista, "referencias_sem_fonte": sem_fonte}


def aplicavel(conexao) -> bool:
    """Há ao menos um documento com revista que cita alguma referência com periódico?"""
    try:
        return conexao.execute(
            "SELECT 1 FROM Document d JOIN Journal j ON j.idJournal = d.Journal_idJournal "
            "JOIN Document_Reference dr ON dr.Document_idDocument = d.idDocument "
            "JOIN Reference r ON r.idReference = dr.Reference_idReference "
            "JOIN ReferenceSource rs ON rs.idReferenceSource = r.ReferenceSource_idReferenceSource "
            "WHERE COALESCE(j.source, '') <> '' AND COALESCE(rs.source, '') NOT IN ('', ?) "
            "LIMIT 1", (SEM_FONTE,)).fetchone() is not None
    except sqlite3.Error:
        return False


def _vazio(aviso: str) -> dict:
    return {"aplicavel": False, "aviso": aviso, "esquerda": [], "direita": [], "areas": [],
            "fluxos": [], "tabela": [], "avisos": [], "colunas": list(COLUNAS),
            "cobertura": {}, "cores": _areas.cores()}


def calcula(contexto: dict, max_esq: int = MAX_ESQ, max_dir: int = MAX_DIR,
            regras=None) -> dict:
    """Dados do duplo mapa a partir de `le_citacoes` (ou de um dict com as mesmas chaves)."""
    regras = regras or _areas.regras_ativas()
    citacoes: Counter = contexto.get("citacoes") or Counter()
    documentos = contexto.get("documentos", 0)
    com_revista = contexto.get("documentos_com_revista", 0)
    if documentos and not com_revista:
        return _vazio("A base não traz o periódico dos documentos; o duplo mapa precisa saber "
                      "em que revista cada documento foi publicado.")
    if not citacoes:
        return _vazio("A base não traz referências com periódico identificado; o duplo mapa "
                      "precisa do periódico de cada referência citada.")

    emitidas: Counter = Counter()      # citações feitas por cada revista do corpus
    recebidas: Counter = Counter()     # citações recebidas de qualquer revista do corpus
    for (citante, citada), n in citacoes.items():
        emitidas[citante] += n
        recebidas[citada] += n
    cache: dict[str, tuple[str, str]] = {}

    def classe(nome: str) -> tuple[str, str]:
        if nome not in cache:
            cache[nome] = _areas.classifica(nome, regras)
        return cache[nome]

    esq = [r for r, _ in sorted(emitidas.items(), key=lambda kv: (-kv[1], kv[0]))[:max_esq]]
    conjunto_esq = set(esq)
    das_esq: Counter = Counter()
    for (citante, citada), n in citacoes.items():
        if citante in conjunto_esq:
            das_esq[citada] += n
    dir_ = [r for r, _ in sorted(das_esq.items(), key=lambda kv: (-kv[1], kv[0]))[:max_dir]]
    conjunto_dir = set(dir_)

    pares: Counter = Counter()
    fluxo_area: Counter = Counter()
    saida_revista: Counter = Counter()
    for (citante, citada), n in citacoes.items():
        if citante in conjunto_esq and citada in conjunto_dir:
            fluxo_area[(classe(citante)[0], classe(citada)[0])] += n
            saida_revista[citante] += n
            pares[(citante, citada)] += n
    desenhadas = sum(fluxo_area.values())
    if not desenhadas:
        return _vazio("Nenhuma das revistas que publicam o corpus cita as revistas mais citadas.")

    def item(nome, valor, extra=None):
        area, termo = classe(nome)
        return {"nome": termo_legivel(nome), "original": nome, "area": area, "termo": termo,
                "valor": valor, **(extra or {})}

    ordem_areas = [a.nome for a in regras[0]] + [_areas.NAO_CLASSIFICADO]
    posicao = {a: i for i, a in enumerate(ordem_areas)}

    esquerda = [item(r, emitidas[r], {"no_desenho": saida_revista[r]}) for r in esq]
    direita = [item(r, das_esq[r], {"total": recebidas[r]}) for r in dir_]
    por_saida: Counter = Counter()
    por_entrada: Counter = Counter()
    for (a, b), n in fluxo_area.items():
        por_saida[a] += n
        por_entrada[b] += n
    nomes_areas = sorted({i["area"] for i in esquerda + direita},
                         key=lambda a: (a == _areas.NAO_CLASSIFICADO, -(por_saida[a] + por_entrada[a]),
                                        posicao.get(a, 99), a))
    cor_de = _areas.cores(regras)
    extras_cor = iter(_areas.PALETA_EXTRA)
    for a in nomes_areas:
        if a not in cor_de:
            cor_de[a] = next(extras_cor, _areas.COR_NAO_CLASSIFICADO)
    esquerda.sort(key=lambda i: (nomes_areas.index(i["area"]), -i["valor"], i["nome"]))
    direita.sort(key=lambda i: (nomes_areas.index(i["area"]), -i["valor"], i["nome"]))
    lista_areas = [{"nome": a, "cor": cor_de[a],
                    "esquerda": sum(1 for i in esquerda if i["area"] == a),
                    "direita": sum(1 for i in direita if i["area"] == a),
                    "saida": por_saida[a], "entrada": por_entrada[a]} for a in nomes_areas]
    fluxos = [{"origem": a, "destino": b, "valor": n, "pct": n / desenhadas}
              for (a, b), n in sorted(fluxo_area.items(), key=lambda kv: (-kv[1], kv[0]))]

    # Tabela auditável: as revistas desenhadas e as sem área mais frequentes de fora.
    linhas: dict[str, dict] = {}
    for i in esquerda:
        linhas[i["original"]] = {"revista": i["nome"], "area": i["area"], "termo": i["termo"],
                                 "publica": i["valor"], "citada": recebidas.get(i["original"], 0),
                                 "no_desenho": True}
    for i in direita:
        linha = linhas.setdefault(i["original"], {
            "revista": i["nome"], "area": i["area"], "termo": i["termo"], "publica": 0,
            "citada": 0, "no_desenho": True})
        linha["publica"] = emitidas.get(i["original"], 0)
        linha["citada"] = recebidas[i["original"]]
    todas = Counter()
    for nome, n in emitidas.items():
        todas[nome] += n
    for nome, n in recebidas.items():
        todas[nome] += n
    extras = 0
    for nome, _ in sorted(todas.items(), key=lambda kv: (-kv[1], kv[0])):
        if extras >= EXTRAS_NAO_CLASSIFICADAS:
            break
        if nome in linhas or classe(nome)[0] != _areas.NAO_CLASSIFICADO:
            continue
        linhas[nome] = {"revista": termo_legivel(nome), "area": _areas.NAO_CLASSIFICADO,
                        "termo": "", "publica": emitidas.get(nome, 0),
                        "citada": recebidas.get(nome, 0), "no_desenho": False}
        extras += 1
    tabela = sorted(linhas.values(), key=lambda l: (not l["no_desenho"], posicao.get(l["area"], 99),
                                                    -(l["publica"] + l["citada"]), l["revista"]))

    total_refs = sum(citacoes.values())
    nc = _areas.NAO_CLASSIFICADO
    refs_nc_citadas = sum(n for r, n in recebidas.items() if classe(r)[0] == nc)
    refs_nc_citantes = sum(n for r, n in emitidas.items() if classe(r)[0] == nc)
    revistas = set(emitidas) | set(recebidas)
    cobertura = {
        "referencias": total_refs,
        "desenhadas": desenhadas,
        "sem_fonte": int(contexto.get("referencias_sem_fonte", 0)),
        "revistas": len(revistas),
        "revistas_nao_classificadas": sum(1 for r in revistas if classe(r)[0] == nc),
        "pct_revistas_nao_classificadas": (sum(1 for r in revistas if classe(r)[0] == nc)
                                           / len(revistas)),
        "pct_citadas_nao_classificadas": refs_nc_citadas / total_refs,
        "pct_citantes_nao_classificadas": refs_nc_citantes / total_refs,
        "pct_desenho_nao_classificadas": (sum(i["valor"] for i in esquerda + direita
                                              if i["area"] == nc)
                                          / max(1, sum(i["valor"] for i in esquerda + direita))),
        "documentos": documentos, "documentos_com_revista": com_revista,
    }
    avisos = [AVISO_APROXIMADA]
    if len(emitidas) == 1:
        avisos.append("O corpus tem uma única revista de publicação; o lado esquerdo mostra "
                      "apenas ela.")
    return {"aplicavel": True, "aviso": "", "colunas": list(COLUNAS), "esquerda": esquerda,
            "direita": direita, "areas": lista_areas, "fluxos": fluxos, "tabela": tabela,
            "cobertura": cobertura, "avisos": avisos, "cores": cor_de,
            "max_esq": max_esq, "max_dir": max_dir,
            "total_esquerda": len(emitidas), "total_direita": len(recebidas),
            "ligacoes": [{"origem": o, "destino": d, "valor": n}
                         for (o, d), n in sorted(pares.items())]}


def calcula_do_banco(conexao, max_esq: int = MAX_ESQ, max_dir: int = MAX_DIR, regras=None) -> dict:
    return calcula(le_citacoes(conexao), max_esq, max_dir, regras)


def porcentagem(valor: float) -> str:
    """Fração como porcentagem com vírgula (``0,184`` → ``18%``; abaixo de 10%, uma casa)."""
    p = valor * 100
    texto = f"{p:.1f}" if 0 < p < 10 else f"{p:.0f}"
    return texto.replace(".", ",") + "%"

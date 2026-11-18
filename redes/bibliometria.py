"""Bibliometria descritiva do corpus: produção, autores, fontes, países, palavras e leis.

Reúne:
informações principais, produção e citações por ano, autores, fontes, países e
palavras-chave mais frequentes, documentos mais citados, indicadores de
coautoria e as leis de Lotka, Bradford e Zipf. Respeita a edição da base:
autores, palavras e países são contados pelo nome do grupo, quando há grupo.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from itertools import combinations

from .texto import termo_legivel

LIMITE = 20


def _indice_h(citacoes: list[int]) -> int:
    ordenadas = sorted(citacoes, reverse=True)
    return sum(1 for posicao, valor in enumerate(ordenadas, start=1) if valor >= posicao)


def _inclinacao(xs: list[float], ys: list[float]) -> tuple[float, float] | None:
    """Mínimos quadrados de y sobre x: devolve (inclinação, intercepto)."""
    if len(xs) < 3:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    denominador = sum((x - mx) ** 2 for x in xs)
    if denominador == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denominador
    return b, my - b * mx


def _ano(valor) -> int | None:
    try:
        ano = int(str(valor)[:4])
    except (TypeError, ValueError):
        return None
    return ano if 1000 <= ano <= 2999 else None


def _documentos(conexao) -> dict[int, dict]:
    linhas = conexao.execute(
        "SELECT d.idDocument, d.title, d.year, d.citationsCount, d.authors, "
        "d.Journal_idJournal, p.year AS ano_pub "
        "FROM Document d LEFT JOIN PublishDate p "
        "ON p.idPublishDate = d.PublishDate_idPublishDate").fetchall()
    documentos = {}
    for linha in linhas:
        documentos[linha[0]] = {
            "id": linha[0], "titulo": linha[1] or f"Documento {linha[0]}",
            "ano": _ano(linha[6]) or _ano(linha[2]),
            "citacoes": None if linha[3] is None else int(linha[3]), "autores_texto": linha[4] or "",
            "fonte_id": linha[5],
        }
    return documentos


def _por_documento(conexao, consulta: str) -> dict[int, list[str]]:
    resultado: dict[int, list[str]] = defaultdict(list)
    for documento_id, nome in conexao.execute(consulta):
        if nome and nome not in resultado[documento_id]:
            resultado[documento_id].append(nome)
    return resultado


def _ranking(contagem: Counter, citacoes: dict, limite: int = LIMITE,
             com_h: dict | None = None) -> list[dict]:
    itens = sorted(contagem.items(), key=lambda par: (-par[1], par[0]))[:limite]
    saida = []
    for nome, documentos in itens:
        linha = {"nome": nome, "documentos": documentos,
                 "citacoes": citacoes.get(nome, 0)}
        if com_h is not None:
            linha["h"] = _indice_h(com_h.get(nome, []))
        saida.append(linha)
    return saida


def _acumula(por_documento: dict[int, list[str]], documentos: dict[int, dict]):
    contagem: Counter = Counter()
    citacoes: dict[str, int] = defaultdict(int)
    lista_citacoes: dict[str, list[int]] = defaultdict(list)
    for documento_id, nomes in por_documento.items():
        documento = documentos.get(documento_id)
        if not documento:
            continue
        for nome in nomes:
            contagem[nome] += 1
            if documento["citacoes"] is None:      # ausente: não soma como zero
                continue
            citacoes[nome] += documento["citacoes"]
            lista_citacoes[nome].append(documento["citacoes"])
    return contagem, citacoes, lista_citacoes


def lotka(producao: Counter) -> dict:
    """Lei de Lotka: quantos autores publicaram n documentos."""
    if not producao:
        return {"pontos": [], "beta": None, "constante": None, "autores": 0}
    por_quantidade = Counter(producao.values())
    total = sum(por_quantidade.values())
    pontos = []
    for n in sorted(por_quantidade):
        observado = por_quantidade[n]
        pontos.append({"documentos": n, "autores": observado,
                       "proporcao": round(observado / total, 4),
                       # Seis algarismos significativos: com round(..., 4) a curva
                       # esperada virava 0 a partir de ~110 documentos por autor e o
                       # gráfico log-log recebia log(0).
                       "esperada": float(f"{(6 / math.pi ** 2) / n ** 2:.6g}")})
    ajuste = _inclinacao([math.log(p["documentos"]) for p in pontos],
                         [math.log(p["autores"] / total) for p in pontos])
    beta = round(-ajuste[0], 3) if ajuste else None
    constante = round(math.exp(ajuste[1]), 3) if ajuste else None
    return {"pontos": pontos, "beta": beta, "constante": constante,
            "autores": total}


def bradford(contagem_fontes: Counter) -> dict:
    """Lei de Bradford: zonas de fontes com cerca de um terço dos documentos."""
    ordenadas = sorted(contagem_fontes.items(), key=lambda par: (-par[1], par[0]))
    total = sum(contagem_fontes.values())
    if not total:
        return {"zonas": [], "fontes": 0}
    alvo = total / 3
    zonas = [{"zona": z, "fontes": 0, "documentos": 0} for z in (1, 2, 3)]
    acumulado = 0
    for nome, documentos in ordenadas:
        zona = min(2, int(acumulado // alvo)) if alvo else 0
        zonas[zona]["fontes"] += 1
        zonas[zona]["documentos"] += documentos
        acumulado += documentos
    zonas = [z for z in zonas if z["fontes"]]
    nucleo = zonas[0]["fontes"] if zonas else 0
    for zona in zonas:
        zona["multiplicador"] = round(zona["fontes"] / nucleo, 2) if nucleo else None
    return {"zonas": zonas, "fontes": len(ordenadas)}


def zipf(contagem_palavras: Counter) -> dict:
    """Lei de Zipf: frequência de cada palavra-chave contra a posição no ranking."""
    frequencias = sorted(contagem_palavras.values(), reverse=True)
    pontos = [{"posto": i, "frequencia": f}
              for i, f in enumerate(frequencias[:200], start=1)]
    ajuste = _inclinacao([math.log(p["posto"]) for p in pontos],
                         [math.log(p["frequencia"]) for p in pontos])
    return {"pontos": pontos, "expoente": round(-ajuste[0], 3) if ajuste else None,
            "palavras": len(frequencias)}


def _resumo_fluxo(conexao) -> dict | None:
    """Resumo do fluxo Autor → País → IES (os nós e o SVG vêm de /api/fluxo)."""
    try:
        from . import fluxos
        dados = fluxos.calcula(conexao)
    except Exception:  # noqa: BLE001 - a bibliometria não pode cair por causa do fluxo
        return None
    return {chave: dados[chave] for chave in ("modo", "qualidade", "cobertura", "avisos")}


def corpus_do_projeto(conexao) -> dict:
    """Autores focais do corpus (presentes em mais de 80% dos documentos)."""
    from .avisos import corpus_focal
    total = conexao.execute("SELECT COUNT(*) FROM Document").fetchone()[0]
    autores = _por_documento(
        conexao,
        "SELECT da.Document_idDocument, COALESCE(g.groupName, a.authorName) "
        "FROM Document_Author da JOIN Author a ON a.idAuthor = da.Author_idAuthor "
        "LEFT JOIN AuthorGroup g ON g.idAuthorGroup = a.AuthorGroup_idAuthorGroup "
        "WHERE COALESCE(g.stopGroup, 0) = 0")
    contagem: Counter = Counter()
    for nomes in autores.values():
        contagem.update(nomes)
    return corpus_focal(contagem, total)


def calcula(conexao) -> dict:
    documentos = _documentos(conexao)
    if not documentos:
        return {"vazio": True}

    autores_doc = _por_documento(
        conexao,
        "SELECT da.Document_idDocument, COALESCE(g.groupName, a.authorName) "
        "FROM Document_Author da JOIN Author a ON a.idAuthor = da.Author_idAuthor "
        "LEFT JOIN AuthorGroup g ON g.idAuthorGroup = a.AuthorGroup_idAuthorGroup "
        "WHERE COALESCE(g.stopGroup, 0) = 0 ORDER BY da.Document_idDocument, da.position")
    palavras_doc = _por_documento(
        conexao,
        "SELECT dw.Document_idDocument, COALESCE(g.groupName, w.wordName) "
        "FROM Document_Word dw JOIN Word w ON w.idWord = dw.Word_idWord "
        "LEFT JOIN WordGroup g ON g.idWordGroup = w.WordGroup_idWordGroup "
        "WHERE dw.isAuthorWord = 1 AND COALESCE(g.stopGroup, 0) = 0")
    paises_doc = _por_documento(
        conexao,
        "SELECT dc.Document_idDocument, COALESCE(g.groupName, c.countryName) "
        "FROM Document_Country dc JOIN Country c ON c.idCountry = dc.Country_idCountry "
        "LEFT JOIN CountryGroup g ON g.idCountryGroup = c.CountryGroup_idCountryGroup "
        "WHERE COALESCE(g.stopGroup, 0) = 0")
    fontes = {linha[0]: linha[1] for linha in conexao.execute(
        "SELECT idJournal, source FROM Journal")}
    fontes_doc = {i: [fontes[d["fonte_id"]]] for i, d in documentos.items()
                  if d["fonte_id"] in fontes and fontes[d["fonte_id"]]}
    fontes_citadas_doc = _por_documento(
        conexao,
        "SELECT dr.Document_idDocument, COALESCE(g.groupName, s.source) "
        "FROM Document_Reference dr JOIN Reference r ON r.idReference = dr.Reference_idReference "
        "JOIN ReferenceSource s ON s.idReferenceSource = r.ReferenceSource_idReferenceSource "
        "LEFT JOIN ReferenceSourceGroup g "
        "ON g.idReferenceSourceGroup = s.ReferenceSourceGroup_idReferencesourceGroup "
        "WHERE COALESCE(g.stopGroup, 0) = 0")
    referencias = conexao.execute(
        "SELECT COUNT(DISTINCT Reference_idReference) FROM Document_Reference"
    ).fetchone()[0]

    cont_autores, cit_autores, lista_autores = _acumula(autores_doc, documentos)
    cont_fontes, cit_fontes, _ = _acumula(fontes_doc, documentos)
    cont_paises, cit_paises, _ = _acumula(paises_doc, documentos)
    cont_citadas, _, _ = _acumula(fontes_citadas_doc, documentos)
    cont_palavras, cit_palavras, _ = _acumula(palavras_doc, documentos)
    # Mesma regra da unidade Institutions (redes.ies): variantes inequívocas do
    # mesmo nome contam uma vez, e o mesmo nome em países diferentes conta duas.
    from .ies import indice_de_ies
    _indice_ies = indice_de_ies(conexao)
    ies_doc = {i: sorted(_indice_ies.nomes[n] for n in ids)
               for i, ids in _indice_ies.por_documento.items()}
    cont_ies, cit_ies, _ = _acumula(ies_doc, documentos)

    # Produção e citações por ano (todos os anos do intervalo, inclusive vazios).
    por_ano: dict[int, dict] = {}
    for documento in documentos.values():
        if documento["ano"] is None:
            continue
        linha = por_ano.setdefault(documento["ano"], {"ano": documento["ano"],
                                                      "documentos": 0, "citacoes": 0})
        linha["documentos"] += 1
        linha["citacoes"] += documento["citacoes"] or 0
    producao = []
    acumulado = 0
    if por_ano:
        for ano in range(min(por_ano), max(por_ano) + 1):
            linha = por_ano.get(ano, {"ano": ano, "documentos": 0, "citacoes": 0})
            acumulado += linha["documentos"]
            producao.append({**linha, "acumulado": acumulado})
    anos = sorted(por_ano)

    total = len(documentos)
    total_citacoes = sum(d["citacoes"] or 0 for d in documentos.values())
    sem_citacao = sum(1 for d in documentos.values() if d["citacoes"] is None)
    com_citacao = total - sem_citacao
    autores_por_documento = [len(autores_doc.get(i, [])) for i in documentos]
    com_autores = [n for n in autores_por_documento if n]
    unicos = sum(1 for n in com_autores if n == 1)
    internacionais = sum(1 for i in documentos if len(paises_doc.get(i, [])) > 1)
    com_pais = sum(1 for i in documentos if paises_doc.get(i))
    crescimento = None
    if len(anos) > 1 and por_ano[anos[0]]["documentos"] > 0:
        periodos = anos[-1] - anos[0]
        crescimento = round(((por_ano[anos[-1]]["documentos"]
                              / por_ano[anos[0]]["documentos"]) ** (1 / periodos) - 1) * 100, 1)

    principal = {
        "documentos": total,
        "primeiro_ano": anos[0] if anos else None,
        "ultimo_ano": anos[-1] if anos else None,
        "fontes": len(cont_fontes),
        "autores": len(cont_autores),
        "palavras_chave": len(cont_palavras),
        "referencias": referencias,
        "paises": len(cont_paises),
        "instituicoes": len(cont_ies),
        "citacoes": total_citacoes,
        # a média só conta os documentos com "Cited by" informado
        "citacoes_por_documento": round(total_citacoes / com_citacao, 2) if com_citacao else None,
        "documentos_sem_citacao": sem_citacao,
        "autores_por_documento": round(sum(com_autores) / len(com_autores), 2) if com_autores else None,
        "documentos_autor_unico": unicos,
        "indice_colaboracao": round(sum(n for n in com_autores if n > 1)
                                    / max(1, len([n for n in com_autores if n > 1])), 2)
        if any(n > 1 for n in com_autores) else None,
        "coautoria_internacional": round(100 * internacionais / com_pais, 1) if com_pais else None,
        "crescimento_anual": crescimento,
        "sem_ano": sum(1 for d in documentos.values() if d["ano"] is None),
    }

    lacunas = []
    n = len(documentos)

    def falta(condicao, texto):
        if condicao:
            lacunas.append(texto)

    falta(not cont_paises, "Sem países: a rede de colaboração entre países e o mapa não podem ser feitos. "
          "A base de origem não trouxe afiliações com país.")
    falta(not cont_ies, "Sem afiliações: não há ranking de instituições (IES).")
    falta(referencias == 0, "Sem referências: cocitação, acoplamento bibliográfico, fontes citadas e rajadas "
          "de referências não podem ser feitos.")
    falta(sem_citacao, f"{sem_citacao} de {total} documentos sem contagem de citações ('Cited by' "
          "vazio): tratados como ausentes (não como zero) nos totais e médias.")
    falta(total_citacoes == 0, "Sem contagem de citações: o eixo de citações, o índice h e os documentos mais "
          "citados ficam vazios.")
    falta(not cont_palavras, "Sem palavras-chave dos autores: não há mapa nem nuvem de palavras-chave "
          "(a nuvem de títulos continua disponível).")
    falta(cont_palavras and sum(1 for v in palavras_doc.values() if v) < 0.5 * n,
          "Menos da metade dos documentos tem palavras-chave: os mapas de palavras cobrem só parte do corpus.")
    falta(not cont_fontes, "Sem periódico dos documentos: o ranking de fontes fica vazio.")

    fluxo = _resumo_fluxo(conexao)
    if fluxo and fluxo["qualidade"] != "exata" and cont_ies:
        relevantes = [a for a in fluxo["avisos"] if "nem país" not in a]
        if relevantes:
            lacunas.append("Fluxo Autor – País – IES: " + relevantes[0])

    pares: Counter = Counter()
    for nomes in autores_doc.values():
        for a, b in combinations(sorted(set(nomes)), 2):
            pares[(a, b)] += 1
    distribuicao = Counter(autores_por_documento)

    mais_citados = sorted(documentos.values(),
                          key=lambda d: (-(d["citacoes"] or 0), d["titulo"]))[:15]
    from .avisos import corpus_focal
    return {
        "vazio": False,
        "corpus": corpus_focal(cont_autores, total),
        "lacunas": lacunas,
        "principal": principal,
        "producao": producao,
        "autores": _ranking(cont_autores, cit_autores, com_h=lista_autores),
        "fontes": _ranking(cont_fontes, cit_fontes),
        "fontes_citadas": [{"nome": n, "documentos": d}
                           for n, d in sorted(cont_citadas.items(),
                                              key=lambda par: (-par[1], par[0]))[:LIMITE]],
        "paises": _ranking(cont_paises, cit_paises),
        "instituicoes": _ranking(cont_ies, cit_ies),
        "palavras": [{**linha, "nome": termo_legivel(linha["nome"])}
                     for linha in _ranking(cont_palavras, cit_palavras)],
        "mais_citados": [{"titulo": d["titulo"], "ano": d["ano"],
                          "autores": d["autores_texto"], "citacoes": d["citacoes"]}
                         for d in mais_citados],
        "coautoria": {
            "distribuicao": [{"autores": n, "documentos": distribuicao[n]}
                             for n in sorted(distribuicao) if n > 0],
            "pares": [{"autores": f"{a}; {b}", "documentos": n}
                      for (a, b), n in sorted(pares.items(),
                                              key=lambda par: (-par[1], par[0]))[:10]],
        },
        "lotka": lotka(Counter({a: n for a, n in cont_autores.items()})),
        "bradford": bradford(cont_fontes),
        "zipf": zipf(cont_palavras),
        "fluxo": fluxo,
    }

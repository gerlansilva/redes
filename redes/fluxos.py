"""Fluxo Autor → País → IES: de quais países e instituições vêm os autores mais produtivos.

A base guarda as afiliações *por documento* (``Document_Affiliation``); a ligação
de cada autor à sua afiliação (``Author_Affiliation``) não é preenchida pelas
importações. O que existe, e por isso o que este módulo usa, em ordem de
confiança:

1. ``exata``: a coluna "Authors with affiliations" do Scopus (guardada em
   ``DocumentMetadata``) diz a afiliação de cada autor. Vale por autor.
2. ``unica``: o documento traz uma única instituição; todos os autores do
   documento herdam esse vínculo. É uma inferência, e fica marcada como tal.
3. ``pais_unico``: sem instituição, mas o documento tem um único país; o
   autor liga ao país, sem IES.

Documentos que não cabem em nenhum caso (várias instituições e nenhuma
ligação por autor, como em Zotero, RIS sem autor na afiliação ou no CSV do site
do OpenAlex) não entram no fluxo: nenhum vínculo é inventado. Quando não há
ligação alguma entre autores e afiliações, o fluxo cai para País → IES, que
sai direto das afiliações do documento.

Os nomes seguem os agrupamentos da base: ``AuthorGroup``, ``CountryGroup`` e
``InstitutionAlias``.
"""
from __future__ import annotations

import html
import re
from collections import Counter, defaultdict

from .paises import pais_da_afiliacao
from .sugestoes import aliases_de_ies, instituicao_da_afiliacao
from .text_utils import sem_acentos

LIMITE_AUTORES, LIMITE_PAISES, LIMITE_IES = 15, 10, 15
SEM_PAIS = "Sem país identificado"
CAMPO_AFILIACAO_AUTOR = "Authors with affiliations"

ROTULO_QUALIDADE = {
    "exata": "ligação autor–instituição lida da base de origem",
    "parcial": "ligação autor–instituição lida da base de origem em parte dos documentos; "
               "no restante, inferida ou ausente",
    "aproximada": "ligação autor–instituição inferida, não informada pela base de origem",
    "indisponivel": "sem ligação autor–instituição",
}


def _norma(texto: str) -> str:
    return " ".join(sem_acentos(texto or "").lower().split())


def _tabela_existe(conexao, nome: str) -> bool:
    return bool(conexao.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nome,)).fetchone())


# ------------------------------------------------------------------ leitura


def _autores(conexao) -> dict[int, list[tuple[str, str]]]:
    """Por documento: [(nome original, nome do grupo)] na ordem de autoria."""
    saida: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for documento, original, grupo in conexao.execute(
            "SELECT da.Document_idDocument, a.authorName, COALESCE(g.groupName, a.authorName) "
            "FROM Document_Author da JOIN Author a ON a.idAuthor = da.Author_idAuthor "
            "LEFT JOIN AuthorGroup g ON g.idAuthorGroup = a.AuthorGroup_idAuthorGroup "
            "WHERE COALESCE(g.stopGroup, 0) = 0 "
            "ORDER BY da.Document_idDocument, da.position"):
        if grupo and all(grupo != g for _, g in saida[documento]):
            saida[documento].append((original or grupo, grupo))
    return saida


def _grupos_de_pais(conexao) -> dict[str, str | None]:
    """Nome do país → nome do grupo (None quando o grupo está oculto)."""
    return {nome: (grupo if not parado else None)
            for nome, grupo, parado in conexao.execute(
                "SELECT c.countryName, COALESCE(g.groupName, c.countryName), "
                "COALESCE(g.stopGroup, 0) FROM Country c "
                "LEFT JOIN CountryGroup g ON g.idCountryGroup = c.CountryGroup_idCountryGroup")}


def _paises_do_documento(conexao, grupos: dict) -> dict[int, list[str]]:
    saida: dict[int, list[str]] = defaultdict(list)
    for documento, nome in conexao.execute(
            "SELECT dc.Document_idDocument, c.countryName FROM Document_Country dc "
            "JOIN Country c ON c.idCountry = dc.Country_idCountry "
            "ORDER BY dc.Document_idDocument"):
        grupo = grupos.get(nome, nome)
        if grupo and grupo not in saida[documento]:
            saida[documento].append(grupo)
    return saida


def _afiliacoes_do_documento(conexao) -> dict[int, list[str]]:
    saida: dict[int, list[str]] = defaultdict(list)
    for documento, texto in conexao.execute(
            "SELECT da.Document_idDocument, a.fullAffiliation FROM Document_Affiliation da "
            "JOIN Affiliation a ON a.idAffiliation = da.Affiliation_idAffiliation "
            "ORDER BY da.Document_idDocument, a.idAffiliation"):
        if texto and texto not in saida[documento]:
            saida[documento].append(texto)
    return saida


def divide_segmentos(valor: str) -> list[str]:
    """Separa "A (Inst, País); B (Inst, País)" em ";" fora de parênteses.

    O ";" dentro de parênteses (várias instituições de um mesmo autor) não divide.
    """
    saida, atual, nivel = [], [], 0
    for caractere in valor or "":
        if caractere == "(":
            nivel += 1
        elif caractere == ")":
            nivel = max(0, nivel - 1)
        if caractere == ";" and nivel == 0:
            saida.append("".join(atual).strip())
            atual = []
        else:
            atual.append(caractere)
    saida.append("".join(atual).strip())
    return [s for s in saida if s]


# segunda parte do nome em dois pedaços: "C.", "C.E.", "J.-D." ou até duas maiúsculas soltas
_SO_INICIAIS = re.compile(r"^(?:(?:[A-ZÀ-Ý]\.-?){1,4}[A-Z]?|[A-ZÀ-Ý]{1,2})$")


def le_autor_afiliacao(valor: str) -> list[tuple[str, str]]:
    """Lê "Authors with affiliations" em pares (autor, afiliação).

    Aceita os dois formatos: Scopus ("Nome, Instituição, Cidade, País; ...") e
    o do OpenAlex enriquecido ("Nome (Instituição, País); ..."). No formato
    Scopus o nome é o par "Sobrenome, Iniciais" do começo do segmento.
    """
    pares = []
    for segmento in divide_segmentos(valor):
        entre = re.match(r"^([^,()]+,[^,()]+?)\s*\((.+)\)$", segmento)
        if entre:
            pares.append((entre.group(1).strip(), entre.group(2).strip()))
            continue
        partes = [p.strip() for p in segmento.split(",")]
        # "Sobrenome, Iniciais, Instituição..." (nome em duas partes) ou
        # "Sobrenome Iniciais, Instituição..." (formato da Scopus, nome em uma só).
        if len(partes) >= 3 and _SO_INICIAIS.match(partes[1]):
            pares.append((", ".join(partes[:2]), ", ".join(partes[2:])))
        elif len(partes) >= 2:
            pares.append((partes[0], ", ".join(partes[1:])))
    return pares


def _afiliacoes_por_autor(conexao) -> dict[int, list[str]]:
    if not _tabela_existe(conexao, "DocumentMetadata"):
        return {}
    return {documento: divide_segmentos(valor)
            for documento, valor in conexao.execute(
                "SELECT Document_idDocument, metaValue FROM DocumentMetadata "
                "WHERE metaKey = ?", (CAMPO_AFILIACAO_AUTOR,)) if valor}


def _pais_e_ies(texto: str, aliases: dict, grupos: dict,
                pais_padrao: str = "") -> tuple[str, str]:
    """(país do grupo, IES com alias) de uma afiliação; vazio quando não dá para saber."""
    ies = instituicao_da_afiliacao(texto)
    ies = aliases.get(ies, ies) if ies else ""
    pais = pais_da_afiliacao(texto)
    if pais:
        pais = grupos.get(pais, pais)      # None: país oculto na edição da base
    elif pais_padrao:
        pais = pais_padrao
    return pais, ies


# iniciais: "j.d.", "j.-d." ou até duas letras soltas ("jd"); "juan" não é inicial
_INICIAIS = re.compile(r"^(?:[a-z]\.-?)+[a-z]?\.?$|^[a-z]{1,2}$")


def _sobrenome_e_iniciais(nome: str) -> tuple[str, str]:
    """"Godino, Juan D." / "Godino, J.D." / "Godino J.D." → ("godino", "jd")."""
    nome = _norma(nome)
    if "," in nome:
        sobrenome, resto = nome.split(",", 1)
        tokens = resto.split()
    else:
        partes = nome.split()
        tokens = []
        while len(partes) > 1 and _INICIAIS.match(partes[-1]):
            tokens.insert(0, partes.pop())
        sobrenome = " ".join(partes)
    iniciais = ""
    for token in tokens:
        if _INICIAIS.match(token):
            iniciais += re.sub(r"[^a-z]", "", token)
        else:
            iniciais += token[0]
    return sobrenome.strip(), iniciais


def _mesmo_autor(a: str, b: str) -> bool:
    if _norma(a) == _norma(b):
        return True
    sa, ia = _sobrenome_e_iniciais(a)
    sb, ib = _sobrenome_e_iniciais(b)
    if not sa or sa != sb or not ia or not ib:
        return False
    return ia.startswith(ib) or ib.startswith(ia)


def _vinculos_exatos(autores: list[tuple[str, str]], segmentos: list[str],
                     aliases: dict, grupos: dict) -> list[tuple[str, str, str]]:
    """Tríades (autor, país, IES) pelos segmentos "Autor, Instituição, ..., País".

    Também lê "Autor (Instituição, País)" e compara o nome do segmento com o do
    autor por sobrenome e iniciais ("Godino, Juan D." = "Godino J.D.").
    """
    pares = [par for segmento in segmentos for par in le_autor_afiliacao(segmento)]
    saida = []
    for original, grupo in autores:
        if not _norma(original):
            continue
        for nome, resto in pares:
            if not (_mesmo_autor(original, nome) or _mesmo_autor(grupo, nome)):
                continue
            if not resto:
                continue
            pais, ies = _pais_e_ies(resto, aliases, grupos)
            if pais is None:
                continue
            if pais or ies:
                saida.append((grupo, pais, ies))
    return saida


# ------------------------------------------------------------------ cálculo


def _coleta(conexao) -> dict:
    """Reúne as tríades por documento e a cobertura de cada tipo de ligação."""
    aliases = aliases_de_ies(conexao)
    grupos = _grupos_de_pais(conexao)
    autores = _autores(conexao)
    paises_doc = _paises_do_documento(conexao, grupos)
    afiliacoes = _afiliacoes_do_documento(conexao)
    por_autor = _afiliacoes_por_autor(conexao)
    documentos = [linha[0] for linha in conexao.execute("SELECT idDocument FROM Document")]

    triades: dict[int, list[tuple[str, str, str, str]]] = {}   # doc -> (autor, país, ies, tipo)
    pares_doc: dict[int, set[tuple[str, str]]] = {}            # doc -> (país, ies), sem autor
    cobertura = Counter()
    for documento in documentos:
        nomes = autores.get(documento, [])
        institucionais = []
        pais_unico = paises_doc[documento][0] if len(paises_doc.get(documento, [])) == 1 else ""
        for texto in afiliacoes.get(documento, []):
            pais, ies = _pais_e_ies(texto, aliases, grupos, pais_unico)
            if ies and pais is not None:
                institucionais.append((pais, ies))
        institucionais = list(dict.fromkeys(institucionais))
        if institucionais:
            pares_doc[documento] = set(institucionais)

        if not nomes:
            cobertura["sem_autores"] += 1
            if not institucionais and not paises_doc.get(documento):
                cobertura["sem_afiliacao"] += 1
            continue
        feitas = _vinculos_exatos(nomes, por_autor.get(documento, []), aliases, grupos) \
            if documento in por_autor else []
        if feitas:
            triades[documento] = [(a, p, i, "exata") for a, p, i in dict.fromkeys(feitas)]
            cobertura["exata"] += 1
        elif len(institucionais) == 1:
            pais, ies = institucionais[0]
            triades[documento] = [(grupo, pais, ies, "unica") for _, grupo in nomes]
            cobertura["unica"] += 1
        elif not institucionais and len(paises_doc.get(documento, [])) == 1:
            pais = paises_doc[documento][0]
            triades[documento] = [(grupo, pais, "", "pais_unico") for _, grupo in nomes]
            cobertura["pais_unico"] += 1
        elif institucionais or paises_doc.get(documento):
            cobertura["sem_ligacao"] += 1
        else:
            cobertura["sem_afiliacao"] += 1
    produtividade = Counter(grupo for lista in autores.values() for _, grupo in lista)
    cobertura["documentos"] = len(documentos)
    cobertura["com_instituicao"] = len(pares_doc)
    cobertura["com_pais"] = sum(1 for d in documentos if paises_doc.get(d))
    return {"triades": triades, "pares_doc": pares_doc, "produtividade": produtividade,
            "cobertura": cobertura, "tem_campo_autor": bool(por_autor)}


def _qualidade(cobertura: Counter, modo: str | None) -> str:
    if modo is None or modo == "pais_ies":
        return "indisponivel"
    ligados = cobertura["exata"] + cobertura["unica"] + cobertura["pais_unico"]
    if not ligados:
        return "indisponivel"
    if cobertura["exata"] == ligados and cobertura["sem_ligacao"] == 0:
        return "exata"
    if cobertura["exata"]:
        return "parcial"
    return "aproximada"


def _vazio(cobertura: Counter, avisos: list[str]) -> dict:
    return {"modo": None, "colunas": [], "nos": [], "ligacoes": [], "qualidade": "indisponivel",
            "cobertura": dict(cobertura), "avisos": avisos, "notas": [], "limites": {}}


def calcula(conexao, limite_autores: int = LIMITE_AUTORES, limite_paises: int = LIMITE_PAISES,
            limite_ies: int = LIMITE_IES) -> dict:
    """Dados do Sankey Autor → País → IES.

    Devolve ``modo`` (``autor_pais_ies``, ``autor_pais``, ``pais_ies`` ou ``None``),
    ``colunas``, ``nos`` (``id``, ``coluna``, ``nome``, ``valor``, ``pais`` para a cor),
    ``ligacoes`` (``origem``, ``destino``, ``valor`` em documentos, ``pais``),
    ``qualidade`` (``exata``, ``parcial``, ``aproximada`` ou ``indisponivel``),
    ``cobertura`` (documentos por tipo de ligação), ``avisos`` ("o que falta") e ``notas``.
    """
    limite_autores, limite_paises, limite_ies = (
        max(1, int(limite_autores)), max(1, int(limite_paises)), max(1, int(limite_ies)))
    coleta = _coleta(conexao)
    cobertura: Counter = coleta["cobertura"]
    total = cobertura["documentos"]
    avisos: list[str] = []
    if not total:
        return _vazio(cobertura, ["O projeto não tem documentos."])
    if not cobertura["com_instituicao"] and not cobertura["com_pais"]:
        return _vazio(cobertura, [
            "A base de origem não trouxe afiliações nem países. Sem eles não há o que ligar "
            "aos autores. Reimporte um corpus do Scopus, do Web of Science ou do OpenAlex com "
            "a coluna de afiliações."])

    triades = coleta["triades"]
    tem_ies = any(i for lista in triades.values() for _, _, i, _ in lista)
    if triades and not tem_ies:
        modo = "autor_pais"
    elif triades:
        modo = "autor_pais_ies"
    elif coleta["pares_doc"]:
        modo = "pais_ies"
    else:
        modo = None
    if modo is None:
        return _vazio(cobertura, [
            "Há países, mas nenhum documento permite ligar os autores a eles: todos têm "
            "mais de um país e a base não diz qual autor pertence a qual."])

    notas: list[str] = []
    if modo == "pais_ies":
        mostrados = _pais_ies(coleta["pares_doc"], limite_paises, limite_ies)
        nos, ligacoes, docs_mostrados = mostrados
        colunas = ["País", "IES"]
        avisos.append(
            "Falta a ligação autor–instituição: a base de origem traz as afiliações do documento, "
            "sem dizer qual autor pertence a qual. O fluxo mostra só País → IES, que sai direto "
            "das afiliações; a coluna de autores não foi desenhada para não inventar vínculos.")
    else:
        nos, ligacoes, docs_mostrados = _tres_colunas(
            triades, coleta["produtividade"], limite_autores, limite_paises, limite_ies,
            com_ies=(modo == "autor_pais_ies"))
        colunas = ["Autor", "País", "IES"] if modo == "autor_pais_ies" else ["Autor", "País"]
        if modo == "autor_pais":
            avisos.append(
                "Faltam as instituições: as afiliações não chegaram à base (só os países). O fluxo "
                "mostra Autor → País.")
        exatos, unicos = cobertura["exata"], cobertura["unica"]
        if cobertura["pais_unico"]:
            notas.append(f"{cobertura['pais_unico']} documento(s) sem instituição ligam o autor só ao "
                         "único país do documento.")
        if unicos:
            avisos.append(
                f"{unicos} de {total} documentos têm uma única instituição; os autores deles herdam "
                "esse vínculo (inferido, não informado pela base).")
        if cobertura["sem_ligacao"]:
            avisos.append(
                f"{cobertura['sem_ligacao']} de {total} documentos têm várias afiliações e a base não "
                "diz qual autor pertence a qual; ficaram fora do fluxo (nenhum vínculo foi inventado).")
        if not exatos and not coleta["tem_campo_autor"] and unicos:
            avisos.append(
                "A base de origem não traz a afiliação de cada autor (no Scopus, a coluna "
                "\"Authors with affiliations\"). A ligação autor–instituição é aproximada.")
        elif not exatos and not coleta["tem_campo_autor"]:
            avisos.append(
                "A base de origem não traz a afiliação de cada autor (no Scopus, a coluna "
                "\"Authors with affiliations\").")
    if cobertura["sem_autores"]:
        avisos.append(f"{cobertura['sem_autores']} documento(s) não têm autores e ficam fora do fluxo.")
    if cobertura["sem_afiliacao"]:
        avisos.append(f"{cobertura['sem_afiliacao']} documento(s) não têm afiliação nem país.")
    if not nos or not ligacoes:
        return _vazio(cobertura, avisos or ["Sem vínculos suficientes para desenhar o fluxo."])
    notas.append("Espessura = número de documentos em que o par ocorre; um documento conta uma vez "
                 "por par, mesmo com vários coautores.")
    qualidade = _qualidade(cobertura, modo)
    rotulo = ROTULO_QUALIDADE[qualidade]
    if modo == "autor_pais":
        rotulo = "ligação autor–país inferida do país único de cada documento"
    return {"modo": modo, "colunas": colunas, "nos": nos, "ligacoes": ligacoes,
            "qualidade": qualidade, "cobertura": {**dict(cobertura), "mostrados": docs_mostrados},
            "rotulo_qualidade": rotulo,
            "avisos": avisos, "notas": notas,
            "limites": {"autores": limite_autores, "paises": limite_paises, "ies": limite_ies}}


def _tres_colunas(triades, produtividade, limite_autores, limite_paises, limite_ies, com_ies):
    docs_autor: dict[str, set[int]] = defaultdict(set)
    for documento, lista in triades.items():
        for autor, _, _, _ in lista:
            docs_autor[autor].add(documento)
    ranking = sorted(docs_autor, key=lambda a: (-produtividade[a], -len(docs_autor[a]), a))
    autores = ranking[:limite_autores]
    escolhidos = set(autores)

    docs_pais: dict[str, set[int]] = defaultdict(set)
    for documento, lista in triades.items():
        for autor, pais, _, _ in lista:
            if autor in escolhidos:
                docs_pais[pais or SEM_PAIS].add(documento)
    paises = sorted(docs_pais, key=lambda p: (p == SEM_PAIS, -len(docs_pais[p]), p))[:limite_paises]
    paises_ok = set(paises)

    docs_ies: dict[str, set[int]] = defaultdict(set)
    par_pais_ies: dict[tuple[str, str], set[int]] = defaultdict(set)
    if com_ies:
        for documento, lista in triades.items():
            for autor, pais, ies, _ in lista:
                pais = pais or SEM_PAIS
                if autor in escolhidos and ies and pais in paises_ok:
                    docs_ies[ies].add(documento)
                    par_pais_ies[(pais, ies)].add(documento)
    instituicoes = sorted(docs_ies, key=lambda i: (-len(docs_ies[i]), i))[:limite_ies]
    ies_ok = set(instituicoes)

    par_autor_pais: dict[tuple[str, str], set[int]] = defaultdict(set)
    for documento, lista in triades.items():
        for autor, pais, _, _ in lista:
            pais = pais or SEM_PAIS
            if autor in escolhidos and pais in paises_ok:
                par_autor_pais[(autor, pais)].add(documento)

    ligacoes = [{"origem": f"a:{a}", "destino": f"p:{p}", "valor": len(d), "pais": p}
                for (a, p), d in sorted(par_autor_pais.items(), key=lambda x: (-len(x[1]), x[0]))]
    ligacoes += [{"origem": f"p:{p}", "destino": f"i:{i}", "valor": len(d), "pais": p}
                 for (p, i), d in sorted(par_pais_ies.items(), key=lambda x: (-len(x[1]), x[0]))
                 if i in ies_ok]
    nos = [{"id": f"a:{a}", "coluna": 0, "nome": a, "valor": len(docs_autor[a]),
            "total": produtividade[a]} for a in autores]
    nos += [{"id": f"p:{p}", "coluna": 1, "nome": p, "valor": len(docs_pais[p])} for p in paises]
    nos += [{"id": f"i:{i}", "coluna": 2, "nome": i, "valor": len(docs_ies[i])}
            for i in instituicoes]
    _define_cores(nos, ligacoes)
    docs_mostrados = len({d for ds in par_autor_pais.values() for d in ds})
    return _sem_orfaos(nos, ligacoes), [l for l in ligacoes if l["valor"] > 0], docs_mostrados


def _pais_ies(pares_doc, limite_paises, limite_ies):
    docs_pais: dict[str, set[int]] = defaultdict(set)
    docs_ies: dict[str, set[int]] = defaultdict(set)
    par: dict[tuple[str, str], set[int]] = defaultdict(set)
    for documento, pares in pares_doc.items():
        for pais, ies in pares:
            pais = pais or SEM_PAIS
            docs_pais[pais].add(documento)
            docs_ies[ies].add(documento)
            par[(pais, ies)].add(documento)
    paises = sorted(docs_pais, key=lambda p: (p == SEM_PAIS, -len(docs_pais[p]), p))[:limite_paises]
    paises_ok = set(paises)
    candidatas = {i for (p, i) in par if p in paises_ok}
    instituicoes = sorted(candidatas, key=lambda i: (-len(docs_ies[i]), i))[:limite_ies]
    ies_ok = set(instituicoes)
    ligacoes = [{"origem": f"p:{p}", "destino": f"i:{i}", "valor": len(d), "pais": p}
                for (p, i), d in sorted(par.items(), key=lambda x: (-len(x[1]), x[0]))
                if p in paises_ok and i in ies_ok]
    nos = [{"id": f"p:{p}", "coluna": 0, "nome": p, "valor": len(docs_pais[p])} for p in paises]
    nos += [{"id": f"i:{i}", "coluna": 1, "nome": i, "valor": len(docs_ies[i])}
            for i in instituicoes]
    _define_cores(nos, ligacoes)
    mostrados = len({d for l in ligacoes for d in par[(l["origem"][2:], l["destino"][2:])]})
    return _sem_orfaos(nos, ligacoes), ligacoes, mostrados


def _define_cores(nos: list[dict], ligacoes: list[dict]) -> None:
    """Cada nó leva o país que mais pesa nas suas ligações; países levam o próprio nome."""
    peso: dict[str, Counter] = defaultdict(Counter)
    for ligacao in ligacoes:
        peso[ligacao["origem"]][ligacao["pais"]] += ligacao["valor"]
        peso[ligacao["destino"]][ligacao["pais"]] += ligacao["valor"]
    for no in nos:
        if no["id"].startswith("p:"):
            no["pais"] = no["nome"]
        elif peso[no["id"]]:
            no["pais"] = sorted(peso[no["id"]].items(), key=lambda x: (-x[1], x[0]))[0][0]
        else:
            no["pais"] = ""


def _sem_orfaos(nos: list[dict], ligacoes: list[dict]) -> list[dict]:
    usados = {l["origem"] for l in ligacoes} | {l["destino"] for l in ligacoes}
    return [n for n in nos if n["id"] in usados]


# ------------------------------------------------------------- bloco de relatório

_ESTILO_BLOCO = (
    "<style>.fluxo-sankey{margin:14px 0 18px}.fluxo-sankey figure{margin:10px 0;text-align:center}"
    ".fluxo-sankey svg{display:block;margin:0 auto;max-width:100%;height:auto}"
    ".fluxo-sankey figcaption{font-size:12.5px;color:#475569;margin-top:6px;text-align:left}"
    ".fluxo-sankey .fluxo-aviso{border:1px solid #F0D98A;border-left:4px solid #FFC400;"
    "background:#FFF8D6;color:#4A3500;border-radius:8px;padding:8px 14px;margin:8px 0;"
    "font-size:13px;break-inside:avoid}.fluxo-sankey .fluxo-aviso ul{margin:4px 0 0;padding-left:18px}"
    ".fluxo-sankey .fluxo-nota{font-size:12px;color:#64748B;margin:6px 0}"
    ".fluxo-sankey.contagem{counter-increment:fig-fluxo}"
    ".fluxo-sankey.contagem figcaption::before{content:\"Figura \" counter(fig-fluxo) \" \\2014  \"}"
    "</style>")


def _legenda(dados: dict) -> str:
    colunas = " → ".join(dados["colunas"])
    c = dados["cobertura"]
    base = (f"Fluxo {colunas}: espessura proporcional ao número de documentos em que o par ocorre; "
            f"cor pelo país. Foram desenhados {len(dados['nos'])} nós, a partir de "
            f"{c.get('mostrados', 0)} de {c['documentos']} documentos.")
    if dados["modo"] != "pais_ies":
        base += f" Qualidade da ligação: {dados['rotulo_qualidade']}."
    return base


def corpo_sankey_html(conexao, numero: int | None = None, titulo: str = "Fluxo Autor – País – IES",
                      **limites) -> str | None:
    """Bloco HTML para os relatórios: aviso "O que falta", figura SVG e nota.

    ``numero`` escreve "Figura N —" na legenda; sem ele, a numeração fica por conta de um
    contador CSS (funciona sem JavaScript, mas conta só as figuras deste tipo). Devolve
    ``None`` quando o projeto não tem documentos.
    """
    from .viz import sankey
    dados = calcula(conexao, **limites)
    if not dados["cobertura"].get("documentos"):
        return None
    avisos = ""
    if dados["avisos"]:
        itens = "".join(f"<li>{html.escape(a)}</li>" for a in dados["avisos"])
        avisos = (f'<div class="fluxo-aviso" role="note"><strong>O que falta</strong>'
                  f"<ul>{itens}</ul></div>")
    svg = sankey.svg(dados, "") if dados["nos"] else ""
    if not svg:
        return (f'{_ESTILO_BLOCO}<section class="fluxo-sankey" id="fluxo-autor-pais-ies">'
                f"{avisos}</section>")
    ident = "fig-fluxo-autor-pais-ies"
    classe = "" if numero is not None else " contagem"
    prefixo = f"Figura {numero} — " if numero is not None else ""
    nota = " ".join(html.escape(n) for n in dados["notas"])
    return (f'{_ESTILO_BLOCO}<section class="fluxo-sankey{classe}" id="fluxo-autor-pais-ies">'
            f"{avisos}<figure id=\"{ident}\">{svg}"
            f"<figcaption>{prefixo}{html.escape(_legenda(dados))}</figcaption></figure>"
            f'<p class="fluxo-nota">{nota}</p></section>')

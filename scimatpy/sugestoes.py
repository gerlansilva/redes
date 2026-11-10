"""Sugestão de grafias e de agrupamentos para autores, palavras-chave, IES e países.

Duas entradas, o mesmo resultado (grupos de variantes com uma grafia proposta):

- automática: os itens da base são comparados entre si e as variantes prováveis
  do mesmo termo saem agrupadas (caixa, acento, pontuação, singular/plural,
  ordem das palavras, iniciais do autor, erro de digitação);
- informada: a pessoa digita a lista de grafias corretas (uma por linha, com
  apelidos opcionais depois de `=`, separados por `|`) e a base é varrida atrás
  das variantes de cada uma.

Cada grupo traz uma confiança: `alta` (a diferença é só de forma, pode aplicar
direto) ou `media` (pede conferência: iniciais compatíveis, ordem trocada,
grafia parecida). Nada é alterado aqui; `aplica` grava os grupos escolhidos.
"""
from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from difflib import SequenceMatcher

from .text_utils import LIGACOES, chave, mesmo_termo, sem_acentos

TIPOS_SUGESTAO = ("palavra", "autor", "ies", "pais")
LIMITE_GRUPOS = 300

# ------------------------------------------------------------------ IES

_UNIVERSIDADE = re.compile(r"\b(univ\w*|college|hochschule|polit[eé]cnic\w*|polytechni\w*)\b", re.I)
_OUTRAS = re.compile(
    r"\b(instit\w*|school|escola|faculd\w*|facult\w*|centro|center|centre|academ\w*|"
    r"laborat\w*|hospital|ministr\w*|secretaria|foundation|funda[cç][aã]o|"
    r"ecole|école|council|agency|association|embrapa|fiocruz|cnpq|capes|ufscar)\b", re.I)

_EQUIVALENTES = {
    "universidade": "univ", "universidad": "univ", "universite": "univ", "universita": "univ",
    "universitat": "univ", "university": "univ", "univ": "univ", "universitaet": "univ",
    "instituto": "inst", "institute": "inst", "institut": "inst", "instituition": "inst",
    "faculdade": "fac", "facultad": "fac", "faculty": "fac", "college": "college",
}
_LIGACOES_IES = LIGACOES | {"del", "di", "la", "le", "los", "las", "du", "des", "van", "von"}


def instituicao_da_afiliacao(afiliacao: str) -> str:
    """Trecho da afiliação que nomeia a instituição ("Depto, Universidade X, Cidade, País")."""
    partes = [p.strip() for p in (afiliacao or "").split(",") if p.strip()]
    if not partes:
        return ""
    for padrao in (_UNIVERSIDADE, _OUTRAS):
        for parte in partes:
            if padrao.search(parte):
                return parte
    return partes[0]


def _tokens_ies(nome: str) -> list[str]:
    texto = sem_acentos(nome or "").lower()
    texto = re.sub(r"\([^)]*\)", " ", texto)
    palavras = [p for p in re.split(r"[^a-z0-9]+", texto) if p]
    saida = []
    for palavra in palavras:
        palavra = _EQUIVALENTES.get(palavra, palavra)
        if palavra in _LIGACOES_IES:
            continue
        saida.append(palavra)
    return saida


# --------------------------------------------------------------- autores

_INICIAIS = re.compile(r"^(?:[A-Za-zÀ-ÿ]\.?){1,4}$")


def _analisa_autor(nome: str) -> tuple[str, str, str]:
    """(sobrenome comparável, iniciais, prenomes completos comparáveis)."""
    texto = re.sub(r"\s+", " ", nome or "").strip()
    if "," in texto:
        sobrenome, _, prenomes = texto.partition(",")
        palavras = prenomes.split()
    else:
        palavras = texto.split()
        sobrenome = ""
        if len(palavras) > 1 and _INICIAIS.match(palavras[-1]) and (
                "." in palavras[-1] or palavras[-1].isupper()):
            prenomes = palavras[-1]
            sobrenome = " ".join(palavras[:-1])
            palavras = [prenomes]
        else:
            sobrenome = texto
            palavras = []
    iniciais = ""
    completos = []
    for palavra in palavras:
        limpa = palavra.replace(".", "")
        if _INICIAIS.match(palavra) and (palavra.endswith(".") or palavra.isupper()) and len(limpa) <= 4:
            iniciais += limpa.upper()
        elif limpa:
            iniciais += limpa[0].upper()
            completos.append(chave(limpa))
    return chave(sobrenome), sem_acentos(iniciais).upper(), "".join(completos)


# ------------------------------------------------------------ comparação


def _parecidos(a: str, b: str, minimo: float) -> float:
    if not a or not b or abs(len(a) - len(b)) > max(2, len(a) // 8):
        return 0.0
    if re.findall(r"\d+", a) != re.findall(r"\d+", b):
        return 0.0
    ruim = SequenceMatcher(None, a, b)
    if ruim.real_quick_ratio() < minimo or ruim.quick_ratio() < minimo:
        return 0.0
    razao = ruim.ratio()
    return razao if razao >= minimo else 0.0


def _compara(tipo: str, a: str, b: str) -> tuple[str, str] | None:
    """Devolve (confiança, motivo) se os dois nomes parecem o mesmo termo."""
    if a == b:
        return None
    ka, kb = chave(a), chave(b)
    if ka and ka == kb:
        return "alta", "só caixa, acento ou pontuação"

    if tipo == "autor":
        sa, ia, ca = _analisa_autor(a)
        sb, ib, cb = _analisa_autor(b)
        if sa and sa == sb and ia and ib:
            if ia == ib and (not ca or not cb or ca == cb):
                return "alta", "mesmo sobrenome e iniciais"
            curta, longa = sorted((ia, ib), key=len)
            if longa.startswith(curta) and (not ca or not cb or ca.startswith(cb) or cb.startswith(ca)):
                return "media", "iniciais compatíveis (uma versão mais curta)"
            return None
        razao = _parecidos(ka, kb, 0.93)
        if razao and len(ka) >= 8 and sa and ia and ib and ia[0] == ib[0]:
            return "media", "sobrenome muito parecido (possível erro de digitação)"
        return None

    if tipo == "ies":
        ta, tb = _tokens_ies(a), _tokens_ies(b)
        if ta and ta == tb:
            return "alta", "mesma instituição escrita em outro idioma ou forma"
        if len(ta) > 1 and sorted(ta) == sorted(tb):
            return "alta", "mesmas palavras em outra ordem"
        razao = _parecidos(" ".join(ta), " ".join(tb), 0.9)
        if razao:
            return "media", "nome muito parecido (possível erro de digitação)"
        return None

    # palavra e pais
    if tipo == "palavra" and mesmo_termo(a.upper(), b.upper()):
        return "alta", "singular e plural"
    ta, tb = re.split(r"[^a-z0-9]+", sem_acentos(a).lower()), re.split(r"[^a-z0-9]+", sem_acentos(b).lower())
    if len(ta) > 1 and sorted(ta) == sorted(tb):
        return "media", "mesmas palavras em outra ordem"
    razao = _parecidos(ka, kb, 0.9 if tipo == "palavra" else 0.88)
    if razao and len(ka) >= 6:
        return "media", "grafia muito parecida (possível erro de digitação)"
    return None


def _bloco(tipo: str, nome: str) -> str:
    if tipo == "autor":
        return _analisa_autor(nome)[0][:3]
    if tipo == "ies":
        tokens = _tokens_ies(nome)
        return tokens[-1][:3] if tokens else ""
    return chave(nome)[:2]


# ---------------------------------------------------------------- leitura


def _itens(conexao: sqlite3.Connection, tipo: str) -> list[dict]:
    """Unidades comparadas: grupos (palavra, autor, país) ou instituições."""
    if tipo == "ies":
        return _instituicoes(conexao)
    tabela, coluna, contagem = {
        "palavra": ("WordGroup", "idWordGroup", "wordGroup_documentsCount"),
        "autor": ("AuthorGroup", "idAuthorGroup", "authorGroup_documentsCount"),
        "pais": ("CountryGroup", "idCountryGroup", "countryGroup_documentsCount"),
    }[tipo]
    return [{"id": linha[0], "nome": linha[1], "documentos": linha[2] or 0}
            for linha in conexao.execute(
                f"SELECT {coluna}, groupName, {contagem} FROM {tabela} "
                f"WHERE COALESCE(stopGroup, 0) = 0")]


def aliases_de_ies(conexao: sqlite3.Connection) -> dict[str, str]:
    existe = conexao.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='InstitutionAlias'").fetchone()
    if not existe:
        return {}
    return {linha[0]: linha[1] for linha in conexao.execute(
        "SELECT instituicao, canonico FROM InstitutionAlias")}


def instituicoes_por_documento(conexao: sqlite3.Connection) -> dict[int, set[str]]:
    """Instituições de cada documento, já com os agrupamentos aplicados."""
    aliases = aliases_de_ies(conexao)
    por_documento: dict[int, set[str]] = defaultdict(set)
    for documento, afiliacao in conexao.execute(
            "SELECT da.Document_idDocument, a.fullAffiliation FROM Document_Affiliation da "
            "JOIN Affiliation a ON a.idAffiliation = da.Affiliation_idAffiliation"):
        nome = instituicao_da_afiliacao(afiliacao)
        if nome:
            por_documento[documento].add(aliases.get(nome, nome))
    return por_documento


def _instituicoes(conexao: sqlite3.Connection) -> list[dict]:
    contagem: dict[str, int] = defaultdict(int)
    for nomes in instituicoes_por_documento(conexao).values():
        for nome in nomes:
            contagem[nome] += 1
    return [{"id": nome, "nome": nome, "documentos": vezes} for nome, vezes in contagem.items()]


# --------------------------------------------------------------- clusters


def _escolhe_canonico(membros: list[dict]) -> str:
    return sorted(membros, key=lambda m: (-m["documentos"], -len(m["nome"]), m["nome"]))[0]["nome"]


def sugere_automaticas(itens: list[dict], tipo: str) -> list[dict]:
    pai = list(range(len(itens)))

    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    arestas: list[tuple[int, int, str, str]] = []
    blocos: dict[str, list[int]] = defaultdict(list)
    for i, item in enumerate(itens):
        blocos[_bloco(tipo, item["nome"])].append(i)
        if tipo in ("palavra", "pais"):
            blocos["o:" + "".join(sorted(re.split(r"[^a-z0-9]+", sem_acentos(item["nome"]).lower())))].append(i)
        if tipo == "ies":
            blocos["t:" + " ".join(sorted(_tokens_ies(item["nome"])))].append(i)
        if tipo == "palavra":
            blocos["k:" + chave(item["nome"])].append(i)
    vistos: set[tuple[int, int]] = set()
    for membros in blocos.values():
        if len(membros) < 2 or len(membros) > 1500:
            continue
        for x in range(len(membros)):
            for y in range(x + 1, len(membros)):
                i, j = membros[x], membros[y]
                if (i, j) in vistos:
                    continue
                vistos.add((i, j))
                resultado = _compara(tipo, itens[i]["nome"], itens[j]["nome"])
                if resultado:
                    arestas.append((i, j, *resultado))
    for i, j, _, _ in arestas:
        pai[raiz(i)] = raiz(j)

    grupos: dict[int, list[int]] = defaultdict(list)
    for i in range(len(itens)):
        grupos[raiz(i)].append(i)
    motivos: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for i, _, nivel, motivo in arestas:
        motivos[raiz(i)].append((nivel, motivo))

    saida = []
    for r, indices in grupos.items():
        if len(indices) < 2:
            continue
        membros = [itens[i] for i in indices]
        niveis = {nivel for nivel, _ in motivos[r]}
        nomes_motivo = sorted({motivo for _, motivo in motivos[r]})
        saida.append({
            "canonico": _escolhe_canonico(membros),
            "confianca": "alta" if niveis == {"alta"} else "media",
            "motivo": "; ".join(nomes_motivo),
            "informada": False,
            "membros": sorted(membros, key=lambda m: (-m["documentos"], m["nome"])),
        })
    return saida


def interpreta_lista(texto: str) -> list[dict]:
    """Linhas `Grafia correta = apelido | apelido` viram {canonico, apelidos}."""
    lista = []
    for linha in (texto or "").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        canonico, _, resto = linha.partition("=")
        apelidos = [a.strip() for a in resto.split("|") if a.strip()]
        if canonico.strip():
            lista.append({"canonico": canonico.strip(), "apelidos": apelidos})
    return lista


def _casa_informada(tipo: str, entrada: dict, item: dict) -> tuple[str, str] | None:
    nome = item["nome"]
    formas = [entrada["canonico"], *entrada["apelidos"]]
    for forma in formas:
        if nome == forma:
            return "alta", "grafia informada"
    for forma in formas:
        if chave(nome) == chave(forma):
            return "alta", "só caixa, acento ou pontuação"
    for forma in entrada["apelidos"]:
        resultado = _compara(tipo, forma, nome)
        if resultado:
            return resultado
    resultado = _compara(tipo, entrada["canonico"], nome)
    if resultado:
        return resultado
    if tipo == "ies":
        alvo = set(_tokens_ies(entrada["canonico"]))
        if len(alvo) >= 3 and alvo <= set(_tokens_ies(nome)):
            return "media", "contém todas as palavras da grafia informada"
    if tipo == "autor":
        sa, ia, _ = _analisa_autor(entrada["canonico"])
        sb, ib, _ = _analisa_autor(nome)
        if sa and sa == sb and ia and ib and (ia.startswith(ib) or ib.startswith(ia)):
            return "media", "mesmo sobrenome e iniciais compatíveis"
    return None


def sugere_informadas(itens: list[dict], tipo: str, lista: list[dict]) -> tuple[list[dict], list[str]]:
    grupos, sem_correspondencia = [], []
    usados: set = set()
    melhor: dict = {}
    for indice, entrada in enumerate(lista):
        for item in itens:
            resultado = _casa_informada(tipo, entrada, item)
            if not resultado:
                continue
            ordem = 0 if resultado[0] == "alta" else 1
            atual = melhor.get(item["id"])
            if atual is None or ordem < atual[0]:
                melhor[item["id"]] = (ordem, indice, resultado)
    por_entrada: dict[int, list[tuple[dict, tuple[str, str]]]] = defaultdict(list)
    for item in itens:
        if item["id"] in melhor:
            _, indice, resultado = melhor[item["id"]]
            por_entrada[indice].append((item, resultado))
            usados.add(item["id"])
    for indice, entrada in enumerate(lista):
        encontrados = por_entrada.get(indice, [])
        if not encontrados:
            sem_correspondencia.append(entrada["canonico"])
            continue
        membros = [item for item, _ in encontrados]
        so_canonico = len(membros) == 1 and membros[0]["nome"] == entrada["canonico"]
        if so_canonico:
            continue
        niveis = {r[0] for _, r in encontrados}
        grupos.append({
            "canonico": entrada["canonico"],
            "confianca": "alta" if niveis == {"alta"} else "media",
            "motivo": "; ".join(sorted({r[1] for _, r in encontrados})),
            "informada": True,
            "membros": sorted(membros, key=lambda m: (-m["documentos"], m["nome"])),
        })
    return grupos, sem_correspondencia


def sugere(conexao: sqlite3.Connection, tipo: str, lista_texto: str = "") -> dict:
    if tipo not in TIPOS_SUGESTAO:
        raise ValueError(f"tipo inválido: {tipo}. Use {', '.join(TIPOS_SUGESTAO)}")
    itens = _itens(conexao, tipo)
    lista = interpreta_lista(lista_texto)
    sem_correspondencia: list[str] = []
    if lista:
        grupos, sem_correspondencia = sugere_informadas(itens, tipo, lista)
        ja = {m["id"] for g in grupos for m in g["membros"]}
        restante = [i for i in itens if i["id"] not in ja]
        grupos += sugere_automaticas(restante, tipo)
    else:
        grupos = sugere_automaticas(itens, tipo)
    grupos.sort(key=lambda g: (g["confianca"] != "alta", not g["informada"],
                               -sum(m["documentos"] for m in g["membros"])))
    total = len(grupos)
    return {
        "tipo": tipo,
        "itens": len(itens),
        "total": total,
        "grupos": grupos[:LIMITE_GRUPOS],
        "sem_correspondencia": sem_correspondencia,
    }


# ---------------------------------------------------------------- gravação

_TABELAS = {"palavra": ("Word", "WordGroup", "idWordGroup", "WordGroup_idWordGroup"),
            "autor": ("Author", "AuthorGroup", "idAuthorGroup", "AuthorGroup_idAuthorGroup"),
            "pais": ("Country", "CountryGroup", "idCountryGroup", "CountryGroup_idCountryGroup")}


def grava_ies(conexao: sqlite3.Connection, agrupamentos: list[dict]) -> int:
    conexao.execute(
        "CREATE TABLE IF NOT EXISTS InstitutionAlias("
        "instituicao TEXT PRIMARY KEY NOT NULL, canonico TEXT NOT NULL)")
    total = 0
    for agrupamento in agrupamentos:
        canonico = (agrupamento.get("canonico") or "").strip()
        if not canonico:
            raise ValueError("a grafia final não pode ser vazia")
        for membro in agrupamento.get("membros", []):
            nome = str(membro)
            # Quem já apontava para um nome que agora é variante passa a apontar para o novo.
            conexao.execute("UPDATE InstitutionAlias SET canonico = ? WHERE canonico = ?",
                            (canonico, nome))
            if nome != canonico:
                conexao.execute(
                    "INSERT OR REPLACE INTO InstitutionAlias(instituicao, canonico) VALUES(?, ?)",
                    (nome, canonico))
                total += 1
    return total

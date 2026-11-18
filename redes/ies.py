"""Rede de colaboração entre instituições (IES): nomes unificados e componentes.

As afiliações chegam grafadas de muitas formas ("Universidade de São Paulo",
"Universidade de Sao Paulo", "Univ. Sao Paulo - Brazil"). Antes de montar a
rede, as variantes do mesmo nome são unidas, **só quando a normalização é
inequívoca**:

- caixa, acentos, pontuação e espaços não contam;
- ligações ("de", "of", "the"...) não contam;
- "Univ.", "University", "Universidade", "Universidad"... valem o mesmo;
  o mesmo vale para instituto/institute e faculdade/faculty;
- sigla entre parênteses é ignorada: "Universidade de São Paulo (USP)";
- país depois de hífen ou barra é ignorado: "Univ. de São Paulo - Brazil".

Não une: ordem de palavras diferente, nomes que diferem por uma palavra
("Federal" a mais), tradução de palavras além das listadas, nem erros de
digitação (isso é com as sugestões de grafia, que a pessoa confere). Quando o
mesmo nome aparece com dois países diferentes ("Universidad Nacional",
Colômbia e Argentina), as ocorrências **não** são unidas entre países.

Cada união feita fica registrada em ``IndiceIES.unioes`` (tabela "variantes
unidas" do relatório e da tela), com as variantes, o nome adotado e o motivo.
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

from .paises import pais as _nome_de_pais, pais_da_afiliacao
from .sugestoes import _tokens_ies, aliases_de_ies, instituicao_da_afiliacao
from .text_utils import chave, sem_acentos

COMPONENTE_MINIMO_PADRAO = 3

_SUFIXO_PAIS = re.compile(r"\s+[-–—/|]\s+([^-–—/|]+)$")


def _sem_sufixo_de_pais(nome: str) -> tuple[str, bool]:
    """Tira " - Brazil" do fim; devolve (nome, houve_sufixo)."""
    achado = _SUFIXO_PAIS.search(nome or "")
    if achado and _nome_de_pais(achado.group(1)):
        return nome[:achado.start()], True
    return nome, False


def chave_ies(nome: str) -> tuple[str, ...]:
    """Chave de comparação do nome de uma instituição (vazia = não comparável)."""
    limpo, _ = _sem_sufixo_de_pais((nome or "").strip())
    return tuple(_tokens_ies(limpo))


def _motivo(nome: str, adotado: str) -> str:
    """Por que `nome` foi unido a `adotado` (texto curto para a tabela)."""
    if chave(nome) == chave(adotado):
        return "caixa, acentos ou pontuação"
    motivos = []
    sem_sufixo, houve = _sem_sufixo_de_pais(nome)
    sem_sufixo_ad, houve_ad = _sem_sufixo_de_pais(adotado)
    if houve != houve_ad:
        motivos.append("país no fim do nome")
    base_a = re.sub(r"\([^)]*\)", " ", sem_acentos(sem_sufixo).lower())
    base_b = re.sub(r"\([^)]*\)", " ", sem_acentos(sem_sufixo_ad).lower())
    if chave(base_a) == chave(base_b):
        if not motivos:
            motivos.append("sigla entre parênteses")
    else:
        palavras_a = [p for p in re.split(r"[^a-z0-9]+", base_a) if p]
        palavras_b = [p for p in re.split(r"[^a-z0-9]+", base_b) if p]
        if [p for p in palavras_a if p not in ("de", "of", "the", "da", "do", "del")] != \
                [p for p in palavras_b if p not in ("de", "of", "the", "da", "do", "del")]:
            motivos.append("Univ./University e termos equivalentes")
        else:
            motivos.append("ligações (de/of/the)")
    return "; ".join(motivos)


@dataclass
class IndiceIES:
    """Instituições do projeto, já unificadas."""

    nomes: dict[int, str] = field(default_factory=dict)             # id -> nome adotado
    por_documento: dict[int, list[int]] = field(default_factory=dict)
    unioes: list[dict] = field(default_factory=list)                # tabela auditável

    def quantidade_variantes_unidas(self) -> int:
        """Quantas grafias deixaram de existir por causa das uniões."""
        return sum(len(u["variantes"]) - 1 for u in self.unioes)


def _ocorrencias(conexao: sqlite3.Connection) -> list[tuple[int, str, str]]:
    """(documento, nome da instituição, país) de cada afiliação de documento."""
    aliases = aliases_de_ies(conexao)
    tabelas = {linha[0] for linha in conexao.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"Affiliation", "Document_Affiliation"} <= tabelas:
        return []
    saida = []
    for documento, afiliacao in conexao.execute(
            "SELECT da.Document_idDocument, a.fullAffiliation FROM Document_Affiliation da "
            "JOIN Affiliation a ON a.idAffiliation = da.Affiliation_idAffiliation "
            "ORDER BY da.Document_idDocument, a.idAffiliation"):
        nome = instituicao_da_afiliacao(afiliacao)
        if not nome:
            continue
        nome = aliases.get(nome, nome)
        saida.append((documento, nome.strip(), pais_da_afiliacao(afiliacao)))
    return saida


def _adotado(variantes: dict[str, set[int]]) -> str:
    """Grafia adotada: a mais usada; no empate, a com acentos, com menos maiúsculas e a mais completa."""
    def preferencia(item):
        nome, docs = item
        acentuados = sum(1 for c in nome if ord(c) > 127)
        maiusculas = sum(1 for c in nome if c.isupper())
        return (-len(docs), -acentuados, maiusculas, -len(nome), nome)
    return sorted(variantes.items(), key=preferencia)[0][0]


def unifica(ocorrencias: list[tuple[int, str, str]]) -> IndiceIES:
    """Une variantes inequívocas e devolve o índice (ids estáveis por nome)."""
    grupos: dict[tuple[str, ...], list[tuple[int, str, str]]] = defaultdict(list)
    for ocorrencia in ocorrencias:
        grupos[chave_ies(ocorrencia[1]) or ("#" + ocorrencia[1],)].append(ocorrencia)

    # cluster = (chave, país ou "") -> ocorrências
    clusters: dict[tuple[tuple[str, ...], str], list[tuple[int, str, str]]] = {}
    for chave_grupo, itens in grupos.items():
        paises = {p for _, _, p in itens if p}
        if len(paises) <= 1:
            clusters[(chave_grupo, next(iter(paises), ""))] = itens
            continue
        # Mesmo nome em países diferentes: não une entre países; sem país fica por grafia.
        for item in itens:
            destino = (chave_grupo, item[2]) if item[2] else (chave_grupo + ("@" + item[1],), "")
            clusters.setdefault(destino, []).append(item)

    partilhados = {}      # chave -> quantos clusters usam (para sufixar o país)
    for (chave_grupo, _) in clusters:
        base = chave_grupo[:-1] if chave_grupo and chave_grupo[-1].startswith("@") else chave_grupo
        partilhados[base] = partilhados.get(base, 0) + 1

    indice = IndiceIES()
    finais: list[tuple[str, list[tuple[int, str, str]], dict[str, set[int]], str]] = []
    for (chave_grupo, pais), itens in clusters.items():
        variantes: dict[str, set[int]] = defaultdict(set)
        for documento, nome, _ in itens:
            variantes[nome].add(documento)
        adotado = _adotado(variantes)
        base = chave_grupo[:-1] if chave_grupo and chave_grupo[-1].startswith("@") else chave_grupo
        rotulo = f"{adotado} ({pais})" if pais and partilhados.get(base, 1) > 1 else adotado
        finais.append((rotulo, itens, variantes, adotado))

    finais.sort(key=lambda f: (sem_acentos(f[0]).lower(), f[0]))
    for numero, (rotulo, itens, variantes, adotado) in enumerate(finais, start=1):
        indice.nomes[numero] = rotulo
        for documento, _, _ in itens:
            lista = indice.por_documento.setdefault(documento, [])
            if numero not in lista:
                lista.append(numero)
        if len(variantes) > 1:
            indice.unioes.append({
                "id": numero,
                "adotado": rotulo,
                "documentos": len({d for d, _, _ in itens}),
                "variantes": [
                    {"nome": nome, "documentos": len(docs),
                     "motivo": "nome adotado" if nome == adotado else _motivo(nome, adotado)}
                    for nome, docs in sorted(
                        variantes.items(), key=lambda v: (v[0] != adotado, -len(v[1]), v[0]))],
            })
    indice.unioes.sort(key=lambda u: (-len(u["variantes"]), sem_acentos(u["adotado"]).lower()))
    return indice


def indice_de_ies(conexao: sqlite3.Connection) -> IndiceIES:
    """Índice de instituições de um projeto (afiliações dos documentos)."""
    return unifica(_ocorrencias(conexao))


def tabela_variantes(unioes: list[dict]) -> list[dict]:
    """Linhas planas da tabela "variantes unidas" (uma por variante)."""
    linhas = []
    for uniao in unioes:
        for variante in uniao["variantes"]:
            linhas.append({
                "adotado": uniao["adotado"], "variante": variante["nome"],
                "documentos": variante["documentos"], "motivo": variante["motivo"],
            })
    return linhas

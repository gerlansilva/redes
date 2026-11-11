"""Áreas de conhecimento das revistas, inferidas por palavras do NOME (duplo mapa).

A classificação é **aproximada**: cada área traz uma lista de termos e a revista
fica na primeira área da lista cujo termo aparece no nome. Não há base de
categorias (Scopus, WoS, OpenAlex) por trás: uma revista cujo nome não diz a área
(``Cognition``, ``Science``) pode ficar em "Não classificado" ou na área errada.
Por isso o duplo mapa mostra uma tabela "revista → área → termo que casou" para
conferência e correção, e a parte de revistas não classificadas.

Sintaxe dos termos (o nome é comparado sem acento, em minúsculas e só com
letras e números):

* ``educ*``: palavra que começa com ``educ`` (educação, education, educational);
* ``math``: a palavra inteira ``math``;
* ``early childhood``: as palavras seguidas, nessa ordem;
* ``=nature``: o nome inteiro é ``nature``.

Configuração: edite `AREAS` aqui ou aponte a variável de ambiente ``REDES_AREAS``
(ou chame `usa_arquivo`) para um JSON::

    {"areas": [{"nome": "Física", "cor": "#0284C7", "termos": ["physic*", "optic*"]}],
     "revistas": {"Nome exato da revista": "Física"},
     "substitui": false}

``areas`` entram **antes** das padrão (ou no lugar delas, com ``"substitui": true``)
e ``revistas`` fixa a área de uma revista pelo nome exato (comparado sem caixa e sem
acento), acima de qualquer termo.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .text_utils import sem_acentos

NAO_CLASSIFICADO = "Não classificado"
COR_NAO_CLASSIFICADO = "#8A94A6"
PALETA_EXTRA = ["#DB2777", "#65A30D", "#0284C7", "#A16207", "#0F766E", "#BE185D", "#4D7C0F"]


@dataclass(frozen=True)
class Area:
    nome: str
    cor: str
    termos: tuple[str, ...] = field(default_factory=tuple)


# A ordem importa: vale a primeira área que casar. "Educação" vem antes de "Matemática e
# estatística" (assim "Educational Studies in Mathematics" fica em Educação) e
# "Psicologia" antes de "Ciências sociais".
AREAS: list[Area] = [
    Area("Educação", "#4C6FFF", (
        "educ*", "teach*", "learn*", "school*", "instruct*", "curricul*", "pedagog*",
        "classroom*", "early years", "early childhood", "childhood research",
        "ensin*", "ensen*", "escol*", "didat*", "formacao", "aprendiz*", "professor*",
        "docen*")),
    Area("Matemática e estatística", "#D97706", (
        "math*", "matem*", "statist*", "estatist*", "estadist*", "psychometr*",
        "structural equation", "probab*", "numer*", "quantit*", "biometr*",
        "decision making")),
    Area("Saúde e psiquiatria", "#DC2626", (
        "psychiat*", "schizo*", "mental", "autis*", "anxiety", "affect*", "depress*",
        "epileps*", "medic*", "med", "health", "clinic*", "lancet", "pediatr*",
        "paediatr*", "jama", "bmj", "allerg*", "nurs*", "surg*", "disorder*", "neuro*",
        "brain", "cortex", "drug", "addict*", "gambl*", "accid*", "epidemi*",
        "public health", "saude", "medicin*", "psiquiat*")),
    Area("Psicologia", "#00A344", (
        "psychol*", "psychon*", "psicolog*", "thinking", "reasoning", "cognit*", "behav*",
        "developmental*", "memory", "personality", "child*", "infan*", "experiment*",
        "perception")),
    Area("Ciências sociais", "#8B5CF6", (
        "social*", "sociol*", "demograph*", "econom*", "polit*", "anthropol*", "famil*",
        "communic*", "language", "linguist*", "gender", "societ*", "lingua*", "sociedad*")),
    Area("Multidisciplinar", "#0E7490", (
        "=nature", "=science", "plos*", "pnas", "proceedings of the national",
        "scientific*", "royal society")),
]
REVISTAS: dict[str, str] = {}

_cache: dict[str, tuple] = {}


def normaliza(texto) -> str:
    """Nome sem acento, em minúsculas, só letras e números separados por um espaço."""
    base = sem_acentos(str(texto or "")).lower()
    return re.sub(r"[^a-z0-9]+", " ", base).strip()


def _casa(termo: str, nome: str, palavras: list[str]) -> bool:
    termo = termo.strip().lower()
    if not termo:
        return False
    if termo.startswith("="):
        return nome == normaliza(termo[1:])
    if termo.endswith("*"):
        prefixo = normaliza(termo[:-1])
        return bool(prefixo) and any(p.startswith(prefixo) for p in palavras)
    t = normaliza(termo)
    return bool(t) and f" {t} " in f" {nome} "


def _normaliza_cor(cor, indice: int) -> str:
    cor = str(cor or "").strip()
    return cor if re.fullmatch(r"#[0-9A-Fa-f]{6}", cor) else PALETA_EXTRA[indice % len(PALETA_EXTRA)]


def _le_arquivo(caminho: str) -> tuple[list[Area], dict[str, str]]:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    novas = []
    for i, item in enumerate(dados.get("areas") or []):
        nome = " ".join(str(item.get("nome") or "").split())
        termos = tuple(str(t) for t in (item.get("termos") or []) if str(t).strip())
        if nome and nome != NAO_CLASSIFICADO and termos:
            novas.append(Area(nome, _normaliza_cor(item.get("cor"), i), termos))
    base = [] if dados.get("substitui") else list(AREAS)
    revistas = {normaliza(k): " ".join(str(v).split())
                for k, v in (dados.get("revistas") or {}).items() if normaliza(k) and str(v).strip()}
    return novas + base, revistas


def regras_ativas() -> tuple[list[Area], dict[str, str]]:
    """(áreas, fixações por revista) em uso: as do módulo, mais o arquivo ``REDES_AREAS``."""
    caminho = os.environ.get("REDES_AREAS", "").strip()
    if not caminho:
        return list(AREAS), {normaliza(k): v for k, v in REVISTAS.items()}
    try:
        chave = f"{caminho}|{Path(caminho).stat().st_mtime_ns}"
        if chave not in _cache:
            _cache.clear()
            _cache[chave] = _le_arquivo(caminho)
        areas, revistas = _cache[chave]
        return list(areas), {**{normaliza(k): v for k, v in REVISTAS.items()}, **revistas}
    except (OSError, ValueError, AttributeError):
        return list(AREAS), {normaliza(k): v for k, v in REVISTAS.items()}


def usa_arquivo(caminho: str | None) -> None:
    """Liga (ou, com None, desliga) o arquivo de áreas para o processo."""
    if caminho:
        os.environ["REDES_AREAS"] = str(caminho)
    else:
        os.environ.pop("REDES_AREAS", None)
    _cache.clear()


def cores(regras=None) -> dict[str, str]:
    areas, _ = regras or regras_ativas()
    saida = {a.nome: a.cor for a in areas}
    saida[NAO_CLASSIFICADO] = COR_NAO_CLASSIFICADO
    return saida


def classifica(nome, regras=None) -> tuple[str, str]:
    """(área, termo que casou) de uma revista; ``("Não classificado", "")`` se nenhum casa.

    Quando a área vem de uma fixação por nome exato, o termo devolvido é ``"(fixada)"``.
    """
    areas, revistas = regras or regras_ativas()
    chave = normaliza(nome)
    if chave in revistas:
        return revistas[chave], "(fixada)"
    palavras = chave.split()
    for area in areas:
        for termo in area.termos:
            if _casa(termo, chave, palavras):
                return area.nome, termo
    return NAO_CLASSIFICADO, ""


def assinatura() -> str:
    """Texto curto que muda quando muda qualquer regra em uso (para chaves de cache)."""
    import hashlib
    areas_, revistas = regras_ativas()
    return hashlib.sha1(repr((areas_, sorted(revistas.items()))).encode("utf-8")).hexdigest()[:12]

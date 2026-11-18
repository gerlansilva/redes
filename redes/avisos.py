"""Avisos de limite mínimo: alertas de leitura que nunca bloqueiam a análise.

Cada aviso é um dicionário ``{"codigo", "mensagem", "nivel"}`` e aparece numa
faixa discreta no topo da análise. Os valores abaixo são os limites usados
(todos podem ser ajustados nesta tabela, sem mexer no resto do código):

``documentos_por_periodo`` (20)
    Período com menos documentos que isto avisa que a classificação dos temas
    pode mudar muito de uma execução para outra.
``fracao_grupos_fracos`` (0,5)
    Se mais da metade dos temas do diagrama tem no máximo um documento, avisa.
``documentos_grupo_fraco`` (1)
    Um tema é "fraco" quando tem até este número de documentos.
``fracao_tema_dominante`` (0,40)
    Tema (agrupamento) que cobre mais que esta fração dos documentos do período.
``fracao_termo_generico`` (0,35)
    Termo presente em pelo menos esta fração dos documentos (aviso já existente).
``documentos_minimos_termo_generico`` (10)
    Só procura termos genéricos em períodos com pelo menos este número de documentos.
``itens_comuns_cocitacao`` (10)
    Cocitação: número mínimo de itens (autores, obras ou periódicos) citados por
    dois ou mais documentos; abaixo disso a rede quase não tem base.
``fracao_autor_focal`` (0,80)
    Um autor presente em mais que esta fração dos documentos é "focal".
``maximo_autores_focais`` (2)
    Com 1 ou 2 autores focais o corpus é "de autor focal": colaboração entre
    países e instituições e as leis de Lotka, Bradford e Zipf dizem pouco.
"""
from __future__ import annotations

LIMITES: dict[str, float] = {
    "documentos_por_periodo": 20,
    "fracao_grupos_fracos": 0.5,
    "documentos_grupo_fraco": 1,
    "fracao_tema_dominante": 0.40,
    "fracao_termo_generico": 0.35,
    "documentos_minimos_termo_generico": 10,
    "itens_comuns_cocitacao": 10,
    "fracao_autor_focal": 0.80,
    "maximo_autores_focais": 2,
}

UNIDADES_COCITACAO = ("AuthorsReference", "References", "ReferenceSources")
UNIDADES_TEMAS = ("Words",) + UNIDADES_COCITACAO
UNIDADES_SOCIAIS_INSTITUCIONAIS = ("Countries", "Institutions")
POUCO_INFORMATIVO = "pouco informativo para este corpus"
_ITENS = {"AuthorsReference": "autores citados", "References": "obras",
          "ReferenceSources": "periódicos citados"}


def _aviso(codigo: str, mensagem: str, **extra) -> dict:
    return {"codigo": codigo, "mensagem": mensagem, "nivel": "limite", **extra}


def corpus_focal(contagem_autores: dict, total_documentos: int,
                 limites: dict | None = None) -> dict:
    """Autores presentes em mais de 80% dos documentos e se o corpus é focal."""
    lim = {**LIMITES, **(limites or {})}
    focais = []
    if total_documentos:
        focais = [(nome, n) for nome, n in contagem_autores.items()
                  if n / total_documentos > lim["fracao_autor_focal"]]
        focais.sort(key=lambda par: (-par[1], par[0]))
    return {
        "documentos": total_documentos,
        "autores_focais": [{"nome": n, "documentos": d,
                            "proporcao": round(d / total_documentos, 3)} for n, d in focais],
        "focal": 1 <= len(focais) <= lim["maximo_autores_focais"],
    }


def avisos_de_limite(resultado, config, documentos_por_grupo: list[tuple[str, int]],
                     corpus: dict | None = None, limites: dict | None = None) -> list[dict]:
    """Avisos de limite mínimo de uma análise.

    `documentos_por_grupo`: (rótulo, documentos) de cada tema/agrupamento.
    `corpus`: resultado de `corpus_focal` (opcional).
    """
    lim = {**LIMITES, **(limites or {})}
    avisos: list[dict] = []
    original = resultado.dataset_original
    total = original.quantidade_documentos()

    if 0 < total < lim["documentos_por_periodo"]:
        avisos.append(_aviso(
            "periodo_pequeno",
            f"Só {total} {'documento' if total == 1 else 'documentos'} neste período; "
            "a classificação dos temas pode mudar muito.", documentos=total))

    if total and documentos_por_grupo and config.unidade in UNIDADES_TEMAS:
        for rotulo, docs in sorted(documentos_por_grupo, key=lambda par: -par[1]):
            if docs / total > lim["fracao_tema_dominante"]:
                avisos.append(_aviso(
                    "tema_dominante",
                    f"O tema \"{rotulo}\" cobre {docs} de {total} documentos "
                    f"({docs / total:.0%}); um tema tão amplo tende a esconder a estrutura "
                    "do restante.", documentos=docs))
            break  # só o maior importa

    if config.unidade in UNIDADES_COCITACAO and config.matriz in ("CoOccurrence", "BasicCoupling"):
        comuns = sum(1 for i in original.lista_itens() if original.frequencia_item(i) >= 2)
        if comuns < lim["itens_comuns_cocitacao"]:
            avisos.append(_aviso(
                "poucas_referencias_em_comum",
                f"Só {comuns} {_ITENS[config.unidade]} aparecem em dois ou mais documentos "
                f"(o ideal seria pelo menos {int(lim['itens_comuns_cocitacao'])}); "
                "a rede de cocitação tem pouca base e deve ser lida como indício.",
                itens=comuns))

    if corpus and corpus.get("focal") and config.unidade in UNIDADES_SOCIAIS_INSTITUCIONAIS:
        foco = corpus["autores_focais"][0]
        avisos.append(_aviso(
            "autor_focal",
            f"Corpus de autor focal ({foco['nome']} está em {foco['proporcao']:.0%} dos "
            "documentos): a rede de "
            f"{'países' if config.unidade == 'Countries' else 'instituições'} reflete "
            f"sobretudo as parcerias dessa pessoa; {POUCO_INFORMATIVO}."))
    return avisos

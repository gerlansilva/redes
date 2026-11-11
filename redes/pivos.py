"""Pontos de virada (pivotal points) e medida sigma, como no CiteSpace.

Um ponto de virada é um nó que liga agrupamentos diferentes: tem intermediação
alta (decil superior) e vizinhos em pelo menos dois agrupamentos. A medida
sigma combina essa intermediação com a força da rajada do termo:

    sigma = (intermediação normalizada + 1) ** força da rajada

Só há sigma para nós que têm rajada; sem rajada o valor é None, nunca 1,0.
Os rótulos saem sem escape: quem exibe é quem escapa.
"""
from __future__ import annotations

from . import measures, rajadas
from .text_utils import chave

MINIMO_NOS = 40
LIMITE_NOS = 800
PROPORCAO_DESCRITOR = 0.5
PERCENTIL = 90.0
_TIPO_RAJADA = {"Words": "palavras", "References": "referencias"}


def sigma(intermediacao_norm: float, forca) -> float | None:
    """Sigma do CiteSpace; None quando o termo não tem rajada."""
    if forca is None or forca <= 0:
        return None
    return (float(intermediacao_norm) + 1.0) ** float(forca)


def _percentil(valores: list[float], p: float) -> float:
    """Percentil com interpolação linear (igual ao padrão do numpy)."""
    ordenados = sorted(valores)
    posicao = (len(ordenados) - 1) * p / 100.0
    baixo = int(posicao)
    alto = min(baixo + 1, len(ordenados) - 1)
    return ordenados[baixo] + (ordenados[alto] - ordenados[baixo]) * (posicao - baixo)


def _forcas_de_rajada(resultado, kb, avisos: list[str]) -> dict[str, float]:
    """Força de rajada por nome normalizado, para as unidades que têm rajada."""
    config = getattr(resultado, "configuracao", None)
    tipo = _TIPO_RAJADA.get(getattr(config, "unidade", None))
    if kb is None or tipo is None or getattr(config, "matriz", "CoOccurrence") != "CoOccurrence":
        return {}
    try:
        dados = rajadas.calcula(kb.conexao, tipo, limite=10 ** 9, minimo_documentos=2)
    except Exception:  # base sem as tabelas esperadas: segue sem sigma
        avisos.append("Não foi possível calcular as rajadas; sigma indisponível.")
        return {}
    forcas: dict[str, float] = {}
    for linha in dados["rajadas"]:
        k = chave(linha["termo"])
        if k and linha["forca"] > forcas.get(k, 0.0):
            forcas[k] = linha["forca"]
    return forcas


def _intermediacao(resultado) -> dict[int, float]:
    cache = getattr(resultado, "centralidades", None)
    if cache is not None:
        try:
            valor = cache.get("intermediacao")
        except Exception:
            valor = None
        if valor is not None:
            return valor
    return measures.intermediacao(resultado.rede)


def _nos(n: int) -> str:
    return f"{n} {'nó' if n == 1 else 'nós'}"


def _vazio(n: int, avisos: list[str], nao_calculado: str | None = None) -> dict:
    """Resultado sem pivôs. `nao_calculado` (texto) marca que o cálculo foi pulado ou falhou:
    nesse caso "não há pivôs" seria enganoso, e quem exibe mostra esse texto."""
    return {"n_nos": n, "suficiente": n >= MINIMO_NOS, "pivos": [],
            "termos_descritores": [], "nos_com_rajada": [], "avisos": avisos,
            "nao_calculado": nao_calculado}


def nao_calculado(n: int, motivo: str) -> dict:
    """Resultado de uma rede cujos pontos de virada não puderam ser calculados."""
    texto = f"Não calculado: {motivo}"
    return _vazio(n, [texto], nao_calculado=texto)


def pontos_de_virada(resultado, kb=None, topo: int = 10) -> dict:
    """Pivôs de uma rede analisada, num dicionário serializável.

    `kb` (ProjetoScimat) só serve para as rajadas; sem ele não há sigma.
    `nos_com_rajada` lista todos os nós com rajada (inclusive termos-descritor),
    ordenados como em `tabela_sigma`; é a base da coluna sigma.
    """
    rede = resultado.rede
    n = rede.quantidade_nos()
    avisos: list[str] = []
    if n < MINIMO_NOS:
        avisos.append(f"Poucos dados: só {_nos(n)} (o mínimo confiável é {MINIMO_NOS}); "
                      "leia como indício.")
    if n < 3 or rede.quantidade_arestas() == 0:
        avisos.append("A rede tem menos de 3 nós ou nenhuma ligação; não há pontos de virada.")
        return _vazio(n, avisos)
    grupo_do_no = getattr(getattr(resultado, "conjunto", None), "grupo_do_no", None) or {}
    if not getattr(resultado, "grupos", None) or not grupo_do_no:
        avisos.append("Não há agrupamentos; sem eles não se identificam pontos de virada.")
        return _vazio(n, avisos)
    if n > LIMITE_NOS:
        texto = (f"Não calculado: rede com {n} nós (limite {LIMITE_NOS}); a intermediação "
                 "foi pulada para não travar. Filtre a rede e tente de novo.")
        avisos.append(texto)
        return _vazio(n, avisos, nao_calculado=texto)

    bc = _intermediacao(resultado)
    norma = (n - 1) * (n - 2) / 2
    bcn = {no: bc.get(no, 0.0) / norma for no in rede.nos}
    freq = getattr(resultado, "frequencia_nos", {}) or {}
    forcas = _forcas_de_rajada(resultado, kb, avisos)

    # Termos-descritor: presentes em mais da metade dos documentos do período.
    descritores: dict[int, float] = {}
    config = getattr(resultado, "configuracao", None)
    if getattr(config, "matriz", "CoOccurrence") == "CoOccurrence":
        base = getattr(resultado, "dataset_original", None) or getattr(resultado, "dataset", None)
        total = base.quantidade_documentos() if base is not None else 0
        if total:
            for no in rede.nos:
                proporcao = freq.get(no, 0) / total
                if proporcao > PROPORCAO_DESCRITOR:
                    descritores[no] = proporcao

    def rotulo(no):
        return resultado.rotulo(no)

    def item(no):
        vizinhos = {grupo_do_no[v] for v in rede.adjacencia[no] if v in grupo_do_no}
        if no in grupo_do_no:
            vizinhos.add(grupo_do_no[no])
        forca = forcas.get(chave(rotulo(no)))
        return {"no": no, "rotulo": rotulo(no), "intermediacao": bcn[no],
                "grau": len(rede.adjacencia[no]), "grupos_vizinhos": len(vizinhos),
                "grupo": grupo_do_no.get(no), "frequencia": freq.get(no, 0),
                "rajada": forca, "sigma": sigma(bcn[no], forca)}

    ordem = lambda d: (-d["intermediacao"], d["rotulo"], d["no"])
    candidatos = [no for no in rede.nos if no not in descritores]
    positivos = [bcn[no] for no in candidatos if bcn[no] > 0]
    pivos = []
    if positivos:
        limiar = _percentil(positivos, PERCENTIL)
        itens = [item(no) for no in candidatos if bcn[no] > 0 and bcn[no] >= limiar]
        pivos = sorted((i for i in itens if i["grupos_vizinhos"] >= 2), key=ordem)[:max(topo, 0)]
    else:
        avisos.append("Nenhum nó tem intermediação positiva; não há pontos de virada.")
    if not pivos and positivos:
        avisos.append("Nenhum nó de intermediação alta tem vizinhos em dois ou mais agrupamentos.")

    termos = []
    for no, proporcao in sorted(descritores.items(), key=lambda p: (-p[1], rotulo(p[0]), p[0])):
        d = item(no)
        d["proporcao_documentos"] = proporcao
        d["motivo"] = (f"Presente em {proporcao:.0%} dos documentos do período: descreve o "
                       "corpus, não distingue temas; fora do ranking.")
        termos.append(d)
    if termos:
        avisos.append(f"{len(termos)} termo(s) em mais de 50% dos documentos ficaram fora do ranking.")

    com_rajada = [item(no) for no in rede.nos if forcas.get(chave(rotulo(no)))]
    com_rajada = tabela_sigma({"nos_com_rajada": com_rajada})
    return {"n_nos": n, "suficiente": n >= MINIMO_NOS, "pivos": pivos,
            "termos_descritores": termos, "nos_com_rajada": com_rajada, "avisos": avisos,
            "nao_calculado": None}


def tabela_sigma(dicionario: dict) -> list:
    """Itens com rajada, por (sigma desc, intermediação desc); vazia sem rajada."""
    base = dicionario.get("nos_com_rajada")
    if base is None:
        base = list(dicionario.get("pivos", [])) + list(dicionario.get("termos_descritores", []))
    linhas = [i for i in base if i.get("sigma") is not None]
    return sorted(linhas, key=lambda i: (-i["sigma"], -i["intermediacao"],
                                         i.get("rotulo", ""), i.get("no", 0)))

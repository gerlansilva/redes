"""Rajadas (bursts) de palavras-chave e de referências, pelo algoritmo de Kleinberg.

Para cada termo, a série é a fração dos documentos de cada ano que o contêm.
O autômato de dois estados de Kleinberg (2002) compara a taxa de base do termo
com uma taxa `s` vezes maior e escolhe, por programação dinâmica, os anos em que
vale a pena "ficar" no estado de rajada. A força é o ganho de verossimilhança
acumulado nesses anos, como a "Strength" do CiteSpace.

Diferença em relação ao CiteSpace: aqui a contagem é de documentos do corpus
que usam o termo (ou citam a referência), não de citações recebidas.
"""
from __future__ import annotations

import math
from collections import defaultdict

from .texto import termo_legivel

S_PADRAO = 2.0
GAMA_PADRAO = 1.0
MINIMO_DOCUMENTOS = 3


def _log_binomial(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def _custo(n: int, k: int, p: float) -> float:
    """-log da verossimilhança binomial de k de n documentos com taxa p."""
    p = min(max(p, 1e-9), 1 - 1e-9)
    return -(_log_binomial(n, k) + k * math.log(p) + (n - k) * math.log(1 - p))


def kleinberg(contagens: list[int], totais: list[int], s: float = S_PADRAO,
              gama: float = GAMA_PADRAO) -> list[tuple[int, int, float]]:
    """Rajadas de uma série: lista de (início, fim, força), com índices inclusivos."""
    n = len(contagens)
    total_termo, total_docs = sum(contagens), sum(totais)
    if n == 0 or total_docs == 0 or total_termo == 0:
        return []
    p0 = total_termo / total_docs
    p1 = min(s * p0, 0.95)
    if p1 <= p0:
        return []
    custo0 = [_custo(totais[t], contagens[t], p0) for t in range(n)]
    custo1 = [_custo(totais[t], contagens[t], p1) for t in range(n)]
    subida = gama * math.log(max(n, 2))

    # Viterbi de dois estados: subir custa `subida`, descer é grátis.
    melhor = [(custo0[0], custo1[0] + subida)]
    origem: list[tuple[int, int]] = [(0, 0)]
    for t in range(1, n):
        a0, a1 = melhor[-1]
        para0, de0 = (a0, 0) if a0 <= a1 else (a1, 1)
        subir = a0 + subida
        para1, de1 = (a1, 1) if a1 <= subir else (subir, 0)
        melhor.append((para0 + custo0[t], para1 + custo1[t]))
        origem.append((de0, de1))
    estado = 0 if melhor[-1][0] <= melhor[-1][1] else 1
    estados = [0] * n
    for t in range(n - 1, -1, -1):
        estados[t] = estado
        estado = origem[t][estado]

    rajadas = []
    t = 0
    while t < n:
        if estados[t] == 1:
            inicio = t
            while t + 1 < n and estados[t + 1] == 1:
                t += 1
            forca = sum(custo0[i] - custo1[i] for i in range(inicio, t + 1))
            if forca > 0:
                rajadas.append((inicio, t, forca))
        t += 1
    return rajadas


def _anos_dos_documentos(conexao) -> dict[int, int]:
    anos = {}
    for documento_id, ano in conexao.execute(
            "SELECT d.idDocument, COALESCE(p.year, d.year) FROM Document d "
            "LEFT JOIN PublishDate p ON p.idPublishDate = d.PublishDate_idPublishDate"):
        try:
            valor = int(str(ano)[:4])
        except (TypeError, ValueError):
            continue
        if 1000 <= valor <= 2999:
            anos[documento_id] = valor
    return anos


_SQL = {
    "palavras": (
        "SELECT dw.Document_idDocument, COALESCE(g.groupName, w.wordName) "
        "FROM Document_Word dw JOIN Word w ON w.idWord = dw.Word_idWord "
        "LEFT JOIN WordGroup g ON g.idWordGroup = w.WordGroup_idWordGroup "
        "WHERE dw.isAuthorWord = 1 AND COALESCE(g.stopGroup, 0) = 0"),
    "referencias": (
        "SELECT dr.Document_idDocument, COALESCE(g.groupName, r.fullReference) "
        "FROM Document_Reference dr JOIN Reference r ON r.idReference = dr.Reference_idReference "
        "LEFT JOIN ReferenceGroup g ON g.idReferenceGroup = r.ReferenceGroup_idReferenceGroup "
        "WHERE COALESCE(g.stopGroup, 0) = 0"),
}


def calcula(conexao, tipo: str = "palavras", limite: int = 20,
            minimo_documentos: int = MINIMO_DOCUMENTOS, s: float = S_PADRAO,
            gama: float = GAMA_PADRAO) -> dict:
    """Rajadas mais fortes de palavras-chave dos autores ou de referências."""
    if tipo not in _SQL:
        raise ValueError("tipo de rajada desconhecido: use palavras ou referencias")
    anos_doc = _anos_dos_documentos(conexao)
    termos: dict[str, dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))
    com_termo: dict[int, set[int]] = defaultdict(set)
    for documento_id, nome in conexao.execute(_SQL[tipo]):
        ano = anos_doc.get(documento_id)
        if ano is None or not nome:
            continue
        termos[nome][ano].add(documento_id)
        com_termo[ano].add(documento_id)

    if not com_termo:
        return {"tipo": tipo, "anos": [], "rajadas": [], "documentos_na_base": 0,
                "avisos": ["Não há dados suficientes para esta análise."]}
    primeiro, ultimo = min(com_termo), max(com_termo)
    anos = list(range(primeiro, ultimo + 1))
    totais = [len(com_termo.get(a, ())) for a in anos]
    base = sum(totais)

    resultado = []
    for nome, por_ano in termos.items():
        contagens = [len(por_ano.get(a, ())) for a in anos]
        total = sum(contagens)
        if total < minimo_documentos:
            continue
        existente = [i for i, c in enumerate(contagens) if c]
        for inicio, fim, forca in kleinberg(contagens, totais, s, gama):
            resultado.append({
                "termo": nome,
                # O termo guardado serve de chave; a exibição passa por `termo_legivel`.
                "termo_exibicao": termo_legivel(nome) if tipo == "palavras" else nome,
                "primeiro_ano": anos[existente[0]],
                "forca": round(forca, 2), "inicio": anos[inicio], "fim": anos[fim],
                "documentos": total,
            })
    resultado.sort(key=lambda r: (-r["forca"], r["termo"]))
    # Como no CiteSpace, cada termo aparece uma vez, com a rajada mais forte.
    vistos: set[str] = set()
    unicos = []
    for linha in resultado:
        if linha["termo"] not in vistos:
            vistos.add(linha["termo"])
            unicos.append(linha)
    resultado = unicos

    avisos = []
    if len(anos) < 8:
        avisos.append(f"O corpus cobre só {len(anos)} anos; rajadas pedem séries mais longas.")
    if base < 100:
        avisos.append(f"Só {base} documentos entram nesta análise; com tão poucos, "
                      "as rajadas são instáveis e devem ser lidas com cautela.")
    if not resultado:
        avisos.append(f"Nenhum termo com pelo menos {minimo_documentos} documentos formou "
                      "uma rajada. Reduza o mínimo de documentos para procurar termos mais raros.")
    return {"tipo": tipo, "anos": [anos[0], anos[-1]], "rajadas": resultado[:limite],
            "documentos_na_base": base, "avisos": avisos,
            "parametros": {"s": s, "gama": gama, "minimo_documentos": minimo_documentos}}

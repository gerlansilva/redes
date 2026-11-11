"""Dendrograma de um período: sub-rede dos itens mais frequentes, SVG e texto."""

from __future__ import annotations

from . import dendrograma
from .network import Rede
from .viz import dendrograma as viz_dendro

LIMITE_NOS = 60


def dendrograma_do_periodo(r, limite: int = LIMITE_NOS, ligacao: str = "media"):
    """(resultado, n_nos_omitidos) ou (None, 0) se a rede tem menos de 3 nós."""
    nos = list(r.rede.nos)
    if len(nos) < 3:
        return None, 0
    freq = r.frequencia_nos or {}
    escolhidos = sorted(nos, key=lambda n: (-freq.get(n, 0), n))[:limite]
    sub = Rede(escolhidos)
    for a, b, v in r.rede.arestas():
        sub.adiciona_aresta(a, b, v)
    grupos_rede = {no: i for i, g in enumerate(r.grupos) for no in g.nos
                   if no in sub._conjunto}
    nomes = {no: r.rotulo(no) for no in escolhidos}
    pesos = {no: float(freq.get(no, 1)) for no in escolhidos}
    res = dendrograma.constroi(sub, ligacao, nomes, pesos, grupos_rede or None)
    return res, len(nos) - len(escolhidos)


def bloco(r, titulo: str, figura, limite: int = LIMITE_NOS) -> str:
    """HTML (figura + leitura) do dendrograma do período; `figura(svg, legenda)`."""
    from html import escape
    res, omitidos = dendrograma_do_periodo(r, limite)
    if res is None:
        return ('<p class="nota">Poucos itens neste período para um dendrograma '
                "(mínimo de 3).</p>")
    n_grupos = res["n_grupos_sugerido"]
    svg = viz_dendro.svg(res, n_grupos, titulo)
    partes = [figura(svg, f"{titulo}. Ligação média sobre 1 − similaridade; linha "
                          f"tracejada = corte em {n_grupos} grupos.")]
    if omitidos:
        partes.append(f'<p class="nota">Foram usados os {limite} itens mais frequentes; '
                      f"{omitidos} itens menos frequentes ficaram de fora.</p>")
    partes.append("<ul>" + "".join(f"<li>{escape(f)}</li>"
                                    for f in dendrograma.interpreta(res, n_grupos)) + "</ul>")
    return "\n".join(partes)

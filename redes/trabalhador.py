"""Processo trabalhador da geração paralela (ver `paralelo.py`).

Uso interno: ``python -m redes.trabalhador``. Lê da entrada padrão linhas
"ENTRADA.pkl<TAB>SAIDA.pkl"; cada entrada traz a análise (configuração e
resultados por período) já calculada pelo processo principal. Produz as figuras
e os cálculos no cache compartilhado, grava as entradas novas em SAIDA.pkl e
responde "ok" (ou "erro") numa linha da saída padrão. Termina quando a entrada
fecha.
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path


def principal(entrada: str, saida: str) -> int:
    from . import cache_figuras, relatorio_unico, report, texto
    from .kb import ProjetoScimat

    with open(entrada, "rb") as f:
        carga = pickle.load(f)
    if carga.get("siglas"):
        texto.registra_siglas(*carga["siglas"])
    secao = carga["secao"]
    resultados = secao["resultados"]
    # Mesma impressão que a do principal: senão as chaves não casariam e o trabalho se perderia.
    if [cache_figuras.base(r) for r in resultados] != carga["esperado"]:
        return 3
    # Constantes de cálculo diferentes (versão ou ajuste): as chaves não as distinguem.
    if cache_figuras.digesto_de_constantes() != carga["digesto"]:
        return 3
    antes = cache_figuras.chaves()
    with cache_figuras.escopo(), ProjetoScimat(carga["projeto"]) as kb:
        periodos = kb.periodos()
        if carga["formato"] == "pastas":
            token = report._VOLTAR.set("../index.html")
            try:
                report.gera_html(Path(carga["destino"]) / secao["pasta"], kb, periodos,
                                 secao["config"], False, carga["medida"],
                                 com_bibliometria=False, devolve_resultados=True,
                                 resultados=resultados)
            finally:
                report._VOLTAR.reset(token)
        else:
            relatorio_unico.aquece_secao(kb, periodos, secao, carga["medida"],
                                         carga.get("parte", "tudo"))
    with open(saida, "wb") as f:
        pickle.dump({"entradas": cache_figuras.delta(antes), "pronta": True}, f, protocol=4)
    return 0


def laco() -> int:
    # A saída padrão é só o canal de respostas: qualquer print vai para o erro padrão.
    canal = sys.stdout
    sys.stdout = sys.stderr
    for linha in sys.stdin:
        linha = linha.rstrip("\n")
        if not linha:
            continue
        entrada, saida = linha.split("\t")
        try:
            codigo = principal(entrada, saida)
        except Exception:  # noqa: BLE001
            codigo = 1
        canal.write("ok\n" if codigo == 0 else "erro\n")
        canal.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(laco())

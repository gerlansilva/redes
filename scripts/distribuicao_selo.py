"""Distribuição do selo de qualidade nos projetos reais, com o motivo de cada Atenção/Ruim.

Uso: python3 scripts/distribuicao_selo.py SAIDA.json projeto1.redes [projeto2.redes ...]

Para cada projeto percorre as unidades e matrizes, em duas frequências mínimas, mais as
análises do relatório completo (frequência escolhida como no relatório), avalia cada
período com `qualidade.avalia` e grava um registro por (análise, período). Serve para
calibrar os limiares de `qualidade.py` (ver `docs/qualidade.md`) e para conferir o
efeito de uma mudança: rode antes e depois e compare com `--resumo`.

    python3 scripts/distribuicao_selo.py --resumo saida.json
"""
from __future__ import annotations

import collections
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scimatpy import api, qualidade  # noqa: E402
from scimatpy.kb import ProjetoScimat  # noqa: E402
from scimatpy.pipeline import executa_periodo  # noqa: E402

LIMITE_NOS = 1500        # redes maiores não entram na grade (lentas e fora do uso comum)


def motivos(a: dict, unidade: str) -> list[str]:
    """Quais critérios de `qualidade.avalia` dispararam (espelha a ordem do código)."""
    m = []
    q = a["q"]
    if q is not None:
        if q < 0.15:
            m.append("q<0,15 (ruim)")
        elif q < 0.30:
            m.append("q<0,30")
    if a["razao"] is not None and a["razao"] < 0.6:
        m.append("razão<0,6")
    sm = a["silhueta_media"]
    if sm is not None:
        if sm < 0:
            m.append("silhueta<0 (ruim)")
        elif sm < 0.05:
            m.append("silhueta<0,05")
    if a["pct_silhueta_negativa"] is not None and a["pct_silhueta_negativa"] > 30:
        m.append(">30% silhueta negativa")
    if a["pct_agrupados"] < 60:
        m.append("<60% agrupados")
    if a["componentes"] > a["n_nos"] / 2:
        m.append("rede fragmentada")
    if unidade == "Authors":
        m.append("coautoria")
    return m


def coleta(caminho: str) -> list[dict]:
    registros = []
    nome = Path(caminho).name
    with ProjetoScimat(caminho) as kb:
        periodos = kb.periodos()
        configs = []
        for unidade in api.UNIDADES:
            for matriz in api.MATRIZES:
                for freq in (1, 2):
                    configs.append(("grade", {"unidade": unidade, "matriz": matriz,
                                              "minimo_frequencia": freq}))
        for chave, _r, _d, parametros, sql, minimo, _m in api.ANALISES_COMPLETO:
            if kb.conexao.execute(sql).fetchone()[0] < minimo:
                continue
            escolhida = api._escolhe_frequencia(kb, periodos, {}, parametros, None)
            if escolhida:
                configs.append(("relatorio:" + chave, {**parametros,
                                                       "minimo_frequencia": escolhida[1]}))
        for origem, dados in configs:
            try:
                config = api._config(dados)
            except Exception:  # noqa: BLE001
                continue
            for p in periodos:
                try:
                    r = executa_periodo(kb, p.id, p.nome, config)
                    if len(r.rede.nos) > LIMITE_NOS:
                        continue
                    a = qualidade.avalia(r)
                except Exception:  # noqa: BLE001
                    continue
                registros.append({
                    "projeto": nome, "origem": origem, "unidade": dados["unidade"],
                    "matriz": dados.get("matriz", "CoOccurrence"),
                    "freq": dados["minimo_frequencia"], "periodo": p.nome,
                    "n_nos": a["n_nos"], "n_grupos": a["n_grupos"], "nivel": a["nivel"],
                    "q": a["q"], "razao": a["razao"], "silhueta": a["silhueta_media"],
                    "pct_neg": a["pct_silhueta_negativa"], "pct_agr": a["pct_agrupados"],
                    "componentes": a["componentes"], "motivos": motivos(a, dados["unidade"])})
    return registros


def resumo(registros: list[dict]) -> str:
    saida = []

    def bloco(titulo: str, filtro) -> None:
        sel = [r for r in registros if filtro(r)]
        if not sel:
            return
        c = collections.Counter(r["nivel"] for r in sel)
        total = len(sel)
        saida.append(f"{titulo}: {total} períodos  " + "  ".join(
            f"{n}={c.get(n, 0)} ({100 * c.get(n, 0) / total:.0f}%)"
            for n in ("ok", "atencao", "ruim", "indefinido")))

    bloco("Tudo", lambda r: True)
    bloco("Só com selo definido", lambda r: r["nivel"] != "indefinido")
    bloco("Análises do relatório", lambda r: r["origem"].startswith("relatorio"))
    for projeto in sorted({r["projeto"] for r in registros}):
        bloco(f"  {projeto}", lambda r, p=projeto: r["projeto"] == p)
    for unidade in sorted({r["unidade"] for r in registros}):
        bloco(f"  unidade {unidade}", lambda r, u=unidade: r["unidade"] == u)
    for matriz in sorted({r["matriz"] for r in registros}):
        bloco(f"  matriz {matriz}", lambda r, m=matriz: r["matriz"] == m)
    definidos = [r for r in registros if r["nivel"] in ("atencao", "ruim")]
    conta = collections.Counter(m for r in definidos for m in r["motivos"])
    unico = collections.Counter(r["motivos"][0] for r in definidos if len(r["motivos"]) == 1)
    saida.append("Motivos (Atenção/Ruim; um período pode ter vários):")
    for m, n in conta.most_common():
        saida.append(f"  {m}: {n}  (único motivo em {unico.get(m, 0)})")
    return "\n".join(saida)


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "--resumo":
        print(resumo(json.loads(Path(argv[1]).read_text())))
        return 0
    if len(argv) < 2:
        print(__doc__)
        return 2
    destino, projetos = argv[0], argv[1:]
    todos = []
    for caminho in projetos:
        t = time.time()
        reg = coleta(caminho)
        print(f"{Path(caminho).name}: {len(reg)} registros em {time.time() - t:.0f} s", flush=True)
        todos.extend(reg)
    Path(destino).write_text(json.dumps(todos, ensure_ascii=False))
    print(resumo(todos))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

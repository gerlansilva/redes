#!/usr/bin/env python3
"""Paridade do importador Rust com o Python.

Uso: python3 paridade.py ARQUIVO... [-- opções de `redes constroi`]

Para cada arquivo roda `python3 -m redes constroi` (na raiz do repositório) e o
`redes-importa-cli` (caminho em $REDES_IMPORTA_CLI ou target/release), e compara
o conteúdo de todas as tabelas, linha a linha na ordem de gravação, e o esquema.
"""
import os, sqlite3, subprocess, sys, tempfile

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), *[".."] * 5))
CLI = os.environ.get("REDES_IMPORTA_CLI", os.path.join(RAIZ, "rust", "target", "release", "redes-importa-cli"))


def compara(a, b):
    ca, cb = sqlite3.connect(a), sqlite3.connect(b)
    ok = True
    q = "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name"
    tabs = [r[0] for r in ca.execute(q)]
    if tabs != [r[0] for r in cb.execute(q)]:
        print("  tabelas diferem"); ok = False
    sql = "select sql from sqlite_master where sql is not null"
    if sorted(r[0] for r in ca.execute(sql)) != sorted(r[0] for r in cb.execute(sql)):
        print("  esquema difere"); ok = False
    for t in tabs:
        ra = ca.execute(f"select * from {t} order by rowid").fetchall()
        rb = cb.execute(f"select * from {t} order by rowid").fetchall()
        if ra != rb:
            ok = False
            print(f"  {t}: python={len(ra)} rust={len(rb)} linhas; diferem")
    return ok


def main():
    args = sys.argv[1:]
    extra = []
    if "--" in args:
        i = args.index("--"); extra = args[i + 1:]; args = args[:i]
    todos = True
    for arq in args:
        with tempfile.TemporaryDirectory() as d:
            py, rs = os.path.join(d, "py.redes"), os.path.join(d, "rs.redes")
            subprocess.run([sys.executable, "-m", "redes", "constroi", arq, "--saida", py, *extra],
                           cwd=RAIZ, check=True, stdout=subprocess.DEVNULL)
            subprocess.run([CLI, arq, "--saida", rs, "-q", *extra], check=True, stdout=subprocess.DEVNULL)
            ok = compara(py, rs)
            print(("IDÊNTICO  " if ok else "DIFERENTE ") + arq)
            todos &= ok
    sys.exit(0 if todos else 1)


main()

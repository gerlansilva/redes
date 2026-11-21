"""Ponto de entrada do servidor embutido no app desktop.

O binário gerado pelo PyInstaller recebe os mesmos argumentos de `redes web`
(`--porta`, `--projetos`, `--nao-abrir`) e roda o servidor HTTP local.

O app Tauri passa o próprio PID em `REDES_PAI_PID`. O PyInstaller onefile cria
um processo filho para rodar o Python; se o app for encerrado (inclusive à
força), esse filho ficaria servindo sozinho. A thread abaixo encerra o servidor
assim que o processo pai desaparece.
"""
import os
import sys
import threading
import time

from redes.cli import main


def vigia_do_pai() -> None:
    try:
        pai = int(os.environ.get("REDES_PAI_PID", ""))
    except ValueError:
        return

    def vigia() -> None:
        while True:
            time.sleep(2)
            try:
                os.kill(pai, 0)
            except OSError:
                os._exit(0)

    threading.Thread(target=vigia, name="vigia-do-pai", daemon=True).start()


if __name__ == "__main__":
    vigia_do_pai()
    raise SystemExit(main(["web", *sys.argv[1:]]))

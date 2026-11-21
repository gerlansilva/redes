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


def _pai_vivo(pai: int) -> bool:
    """Diz se o processo do app ainda existe, sem encerrá-lo."""
    if os.name == "nt":
        # No Windows `os.kill(pid, 0)` chamaria TerminateProcess: não serve.
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        processo = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pai)
        if not processo:
            return False
        try:
            codigo = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(processo, ctypes.byref(codigo)):
                return False
            return codigo.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(processo)
    try:
        os.kill(pai, 0)
    except OSError:
        return False
    return True


def vigia_do_pai() -> None:
    try:
        pai = int(os.environ.get("REDES_PAI_PID", ""))
    except ValueError:
        return

    def vigia() -> None:
        while True:
            time.sleep(2)
            if not _pai_vivo(pai):
                os._exit(0)

    threading.Thread(target=vigia, name="vigia-do-pai", daemon=True).start()


if __name__ == "__main__":
    vigia_do_pai()
    raise SystemExit(main(["web", *sys.argv[1:]]))

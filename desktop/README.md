# Redes para macOS e Windows (Tauri)

Aplicativo desktop que abre a interface local do Redes em uma janela própria, sem
navegador. O servidor Python (`redes web`) vai embutido como sidecar, gerado pelo
PyInstaller — não é preciso instalar Python na máquina.

## Estrutura

- `splash/`: tela de abertura exibida enquanto o servidor sobe.
- `servidor/redes_servidor.py`: ponto de entrada do sidecar.
- `src-tauri/`: app Tauri 2 (Rust). Sobe o sidecar em uma porta livre e navega a
  janela para `http://127.0.0.1:<porta>/`. A porta preferida é 47823; manter a
  mesma entre execuções preserva o último projeto e a última análise salvos no
  `localStorage`.
- `scripts/build-sidecar.sh`: gera `src-tauri/binaries/redes-servidor-<triple>`
  (`.exe` no Windows).
- `scripts/gerar-icones.sh`: gera os ícones a partir de
  `redes/assets/logo.png` — o arquivo oficial da marca, usado como está.
- `scripts/ajustar-versao.sh`: alinha a versão de `tauri.conf.json` e `Cargo.toml`.

O app passa o próprio PID ao servidor (`REDES_PAI_PID`). Se o app for fechado,
inclusive à força, o servidor encerra sozinho — o PyInstaller onefile cria dois
processos, e sem esse vigia o filho continuaria ocupando a porta. No Windows o
vigia usa `OpenProcess`/`GetExitCodeProcess`, porque `os.kill(pid, 0)` encerraria
o processo em vez de apenas consultá-lo.

## Build local (macOS, Apple Silicon)

```bash
cd desktop
npm install
bash scripts/gerar-icones.sh
python3 -m venv .venv-desktop
.venv-desktop/bin/pip install pyinstaller ..
PYTHON=.venv-desktop/bin/python bash scripts/build-sidecar.sh
npm run tauri build -- --target aarch64-apple-darwin
```

Saídas em `src-tauri/target/aarch64-apple-darwin/release/bundle/`:

- `macos/Redes.app`
- `dmg/Redes_0.4.2_aarch64.dmg`

O app é assinado *ad hoc* e não é notarizado. Na primeira abertura, clique com o
botão direito em **Redes** e escolha **Abrir**.

## Build local (Windows, x64)

Em um terminal Git Bash, com Python 3.12 e Rust (MSVC) instalados:

```bash
cd desktop
npm install
python -m venv .venv-desktop
.venv-desktop/Scripts/python.exe -m pip install pyinstaller ..
PYTHON=.venv-desktop/Scripts/python.exe bash scripts/build-sidecar.sh
npm run tauri build -- --target x86_64-pc-windows-msvc --bundles nsis
```

Saída em `src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/`:
`Redes_0.4.2_x64-setup.exe`.

## Release

O workflow `.github/workflows/tauri.yml` tem dois trabalhos de build —
`macos-latest` (arm64) e `windows-latest` (x64) — e um trabalho de release que
roda depois dos dois. Em tag `v*` ou execução manual com `versao`, publica no
GitHub Releases:

- `Redes-<versão>-macOS-<arquitetura>.dmg`
- `Redes-<versão>-Windows-x64-setup.exe`

Cada arquivo vai acompanhado do `.sha256`.

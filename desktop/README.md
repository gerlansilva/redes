# Redes para macOS (Tauri)

Aplicativo desktop para macOS que abre a interface local do Redes em uma janela
própria, sem navegador. O servidor Python (`redes web`) vai embutido como
sidecar, gerado pelo PyInstaller — não é preciso instalar Python na máquina.

## Estrutura

- `splash/`: tela de abertura exibida enquanto o servidor sobe.
- `servidor/redes_servidor.py`: ponto de entrada do sidecar.
- `src-tauri/`: app Tauri 2 (Rust). Sobe o sidecar em uma porta livre e navega a
  janela para `http://127.0.0.1:<porta>/`. A porta preferida é 47823; manter a
  mesma entre execuções preserva o último projeto e a última análise salvos no
  `localStorage`.
- `scripts/build-sidecar.sh`: gera `src-tauri/binaries/redes-servidor-<triple>`.
- `scripts/gerar-icones.sh`: gera os ícones a partir de `redes/assets/logo.svg`.

O app passa o próprio PID ao servidor (`REDES_PAI_PID`). Se o app for fechado,
inclusive à força, o servidor encerra sozinho — o PyInstaller onefile cria dois
processos, e sem esse vigia o filho continuaria ocupando a porta.

## Build local (Apple Silicon)

```bash
cd desktop
npm install
bash scripts/gerar-icones.sh
python3 -m venv .venv-desktop
.venv-desktop/bin/pip install pyinstaller .
PYTHON=.venv-desktop/bin/python bash scripts/build-sidecar.sh
npm run tauri build -- --target aarch64-apple-darwin
```

Saídas em `src-tauri/target/aarch64-apple-darwin/release/bundle/`:

- `macos/Redes.app`
- `dmg/Redes_0.3.0_aarch64.dmg`

O app é assinado *ad hoc* e não é notarizado. Na primeira abertura, clique com o
botão direito em **Redes** e escolha **Abrir**.

## Release

O workflow `.github/workflows/tauri.yml` roda no `macos-latest` (arm64), gera o
DMG e, em tag `v*` ou execução manual com `versao`, publica no GitHub Releases.
O arquivo publicado recebe o nome `Redes-<versão>-macOS-<arquitetura>.dmg`, com
o `.sha256` ao lado.

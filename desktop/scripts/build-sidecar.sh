#!/usr/bin/env bash
# Gera o sidecar Python (redes web) para o app desktop.
# Saída: desktop/src-tauri/binaries/redes-servidor-<triple>
# Requer PyInstaller no Python usado (padrão: python3).
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
ALVO="${ALVO:-$(rustc -vV | sed -n 's/^host: //p')}"
PYTHON="${PYTHON:-python3}"
SAIDA="$RAIZ/desktop/src-tauri/binaries"

mkdir -p "$SAIDA"
cd "$RAIZ"

"$PYTHON" -m PyInstaller \
  --noconfirm --clean --onefile \
  --name redes-servidor \
  --distpath "$SAIDA" \
  --workpath "$RAIZ/desktop/.pyinstaller" \
  --specpath "$RAIZ/desktop/.pyinstaller" \
  --collect-data redes \
  --collect-submodules redes \
  --paths "$RAIZ" \
  "$RAIZ/desktop/servidor/redes_servidor.py"

mv "$SAIDA/redes-servidor" "$SAIDA/redes-servidor-$ALVO"
chmod +x "$SAIDA/redes-servidor-$ALVO"
echo "Sidecar pronto: $SAIDA/redes-servidor-$ALVO"

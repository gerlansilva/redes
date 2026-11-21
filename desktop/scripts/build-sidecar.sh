#!/usr/bin/env bash
# Gera o sidecar Python (redes web) para o app desktop.
# Saída: desktop/src-tauri/binaries/redes-servidor-<triple>[.exe]
# Requer PyInstaller no Python usado (padrão: python3).
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
ALVO="${ALVO:-$(rustc -vV | sed -n 's/^host: //p')}"
PYTHON="${PYTHON:-python3}"
SAIDA="$RAIZ/desktop/src-tauri/binaries"

# No Windows o executável sai como `redes-servidor.exe` e o Tauri espera o
# sufixo do triple com a mesma extensão.
EXT=""
case "$ALVO" in
  *windows*) EXT=".exe" ;;
esac

mkdir -p "$SAIDA"
cd "$RAIZ"

rm -f "$SAIDA/redes-servidor" "$SAIDA/redes-servidor.exe"

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

mv "$SAIDA/redes-servidor$EXT" "$SAIDA/redes-servidor-$ALVO$EXT"
chmod +x "$SAIDA/redes-servidor-$ALVO$EXT" 2>/dev/null || true
echo "Sidecar pronto: $SAIDA/redes-servidor-$ALVO$EXT"

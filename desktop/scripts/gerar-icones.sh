#!/usr/bin/env bash
# Gera os ícones do app a partir do arquivo oficial da marca (PNG, usado como
# está, sem redesenho). Usa o CLI do Tauri para os tamanhos e formatos.
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
ICONES="$RAIZ/desktop/src-tauri/icons"
MARCA="$RAIZ/redes/assets/logo.png"

[ -f "$MARCA" ] || {
  echo "Falta $MARCA." >&2
  exit 1
}
mkdir -p "$ICONES"
cp "$MARCA" "$ICONES/icon.png"
cd "$RAIZ/desktop"
npx tauri icon src-tauri/icons/icon.png
echo "Ícones prontos em $ICONES"

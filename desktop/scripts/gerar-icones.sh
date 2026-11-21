#!/usr/bin/env bash
# Gera os ícones do app a partir da marca do Redes (usa rsvg-convert e o CLI do Tauri).
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
ICONES="$RAIZ/desktop/src-tauri/icons"

command -v rsvg-convert >/dev/null || {
  echo "Instale o librsvg: brew install librsvg" >&2
  exit 1
}
mkdir -p "$ICONES"
rsvg-convert -w 1024 -h 1024 "$RAIZ/redes/assets/logo.svg" -o "$ICONES/icon.png"
cd "$RAIZ/desktop"
npx tauri icon src-tauri/icons/icon.png
echo "Ícones prontos em $ICONES"

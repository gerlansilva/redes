#!/usr/bin/env bash
# Gera os ícones do app a partir da marca do Redes (só a imagem da rede, sem o
# nome). Usa rsvg-convert quando disponível e o CLI do Tauri para os tamanhos.
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
ICONES="$RAIZ/desktop/src-tauri/icons"
MARCA="$RAIZ/redes/assets/logo-icone.svg"

mkdir -p "$ICONES"

if command -v rsvg-convert >/dev/null; then
  rsvg-convert -w 1024 -h 1024 "$MARCA" -o "$ICONES/icon.png"
elif [ -f "$ICONES/icon.png" ]; then
  # Sem librsvg (ex.: runner Windows), usa o PNG já versionado no repositório.
  echo "rsvg-convert ausente: usando $ICONES/icon.png" >&2
else
  echo "Instale o librsvg (brew install librsvg) ou versione icons/icon.png." >&2
  exit 1
fi

cd "$RAIZ/desktop"
npx tauri icon src-tauri/icons/icon.png
echo "Ícones prontos em $ICONES"

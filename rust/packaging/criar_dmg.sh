#!/usr/bin/env bash
# Monta o .dmg com fundo e atalho para Aplicativos.
# Uso: packaging/criar_dmg.sh <Redes.app> <saida.dmg>
# Usa create-dmg (brew install create-dmg) e, se ele faltar ou falhar, cai para
# um hdiutil simples (app + atalho, sem fundo).
set -euo pipefail
APP="$1"; DMG="$2"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
rm -f "$DMG"

feito=""
if command -v create-dmg >/dev/null 2>&1; then
  FUNDO="$TMP/fundo.png"
  if command -v rsvg-convert >/dev/null 2>&1 && rsvg-convert "$RAIZ/packaging/dmg-fundo.svg" -o "$FUNDO"; then
    mkdir -p "$TMP/conteudo"; cp -R "$APP" "$TMP/conteudo/"
    if create-dmg \
        --volname "Redes" \
        --background "$FUNDO" \
        --window-pos 200 120 --window-size 660 400 \
        --icon-size 104 \
        --icon "Redes.app" 170 190 \
        --hide-extension "Redes.app" \
        --app-drop-link 490 190 \
        --no-internet-enable \
        "$DMG" "$TMP/conteudo"; then
      feito=1
    else
      echo "create-dmg falhou; usando hdiutil simples." >&2
      rm -f "$DMG"
    fi
  fi
fi

if [ -z "$feito" ]; then
  STAGE="$TMP/stage"; mkdir -p "$STAGE"
  cp -R "$APP" "$STAGE/"; ln -s /Applications "$STAGE/Applications"
  hdiutil create -volname "Redes" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
fi
echo "DMG: $DMG"

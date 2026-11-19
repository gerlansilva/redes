#!/usr/bin/env bash
# Gera dist/Redes.app e dist/Redes-<versão>.dmg (binário universal x86_64+arm64).
# Rodar no macOS, a partir de qualquer pasta:  scripts/empacotar_mac.sh
# Variáveis opcionais:
#   FEATURES="redes-core"   ativa o núcleo real (padrão: o que o Cargo.toml do app define)
#   ASSINATURA="Developer ID Application: ..."   assina com codesign (padrão: ad hoc "-")
#   SO_UM_ALVO=1            compila só para a arquitetura da máquina (mais rápido)
#   VERSAO=0.2.1            sobrescreve a versão do Cargo.toml (nome do .dmg e Info.plist)
# Saídas em dist/: Redes.app, Redes-<versão>.dmg e Redes-<versão>.dmg.sha256.
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"
[ "$(uname -s)" = "Darwin" ] || { echo "Este script só roda no macOS." >&2; exit 1; }

VERSAO_CARGO="$(cargo metadata --no-deps --format-version 1 | python3 -c 'import sys,json; print([p for p in json.load(sys.stdin)["packages"] if p["name"]=="redes-app"][0]["version"])')"
DIST="$RAIZ/dist"; APP="$DIST/Redes.app"
FEATURES_ARG=()
[ -n "${FEATURES:-}" ] && FEATURES_ARG=(--features "$FEATURES")

if [ -n "${SO_UM_ALVO:-}" ]; then
  ALVOS=("$(rustc -vV | sed -n 's/host: //p')")
else
  ALVOS=(x86_64-apple-darwin aarch64-apple-darwin)
  rustup target add "${ALVOS[@]}"
fi
BINS=()
for t in "${ALVOS[@]}"; do
  cargo build --release -p redes-app --target "$t" ${FEATURES_ARG[@]+"${FEATURES_ARG[@]}"}
  BINS+=("target/$t/release/redes")
done
# O destino do cargo pode ser alterado por CARGO_TARGET_DIR.
ALVO_DIR="${CARGO_TARGET_DIR:-target}"
BINS=(); for t in "${ALVOS[@]}"; do BINS+=("$ALVO_DIR/$t/release/redes"); done

rm -rf "$DIST"; mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
if [ "${#BINS[@]}" -gt 1 ]; then
  lipo -create "${BINS[@]}" -output "$APP/Contents/MacOS/redes"
else
  cp "${BINS[0]}" "$APP/Contents/MacOS/redes"
fi
chmod +x "$APP/Contents/MacOS/redes"
sed "s/@VERSAO@/$VERSAO/g" packaging/Info.plist > "$APP/Contents/Info.plist"
printf 'APPL????' > "$APP/Contents/PkgInfo"

if [ ! -f packaging/Redes.icns ]; then scripts/gerar_icns.sh packaging/Redes.icns; fi
cp packaging/Redes.icns "$APP/Contents/Resources/Redes.icns"

# Assinatura ad hoc (sem conta de desenvolvedor): dá ao app uma identidade mínima,
# necessária para rodar em Macs com Apple Silicon. Não a notariza; veja o LEIA-ME.md.
xattr -cr "$APP" || true
codesign --force --deep --sign "${ASSINATURA:--}" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

DMG="$DIST/Redes-$VERSAO.dmg"
packaging/criar_dmg.sh "$APP" "$DMG"
codesign --force --sign "${ASSINATURA:--}" "$DMG" || true
(cd "$DIST" && shasum -a 256 "Redes-$VERSAO.dmg" > "Redes-$VERSAO.dmg.sha256")
echo "Pronto: $APP"; echo "Pronto: $DMG"; cat "$DIST/Redes-$VERSAO.dmg.sha256"
lipo -info "$APP/Contents/MacOS/redes" || true

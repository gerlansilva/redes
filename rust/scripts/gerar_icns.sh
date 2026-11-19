#!/usr/bin/env bash
# Gera packaging/Redes.icns a partir de redes/ui/logo-mark.svg.
# Usa rsvg-convert (brew install librsvg; apt install librsvg2-bin) e, no macOS,
# iconutil. Fora do macOS, monta o .icns com Python puro (PNGs embutidos).
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SVG="${SVG:-$RAIZ/crates/redes-app/assets/logo-mark.svg}"
SAIDA="${1:-$RAIZ/packaging/Redes.icns}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
command -v rsvg-convert >/dev/null || { echo "Instale rsvg-convert (librsvg)." >&2; exit 1; }

# Fundo branco arredondado com a marca, como ícones do macOS.
ic() { # tamanho arquivo
  local t=$1 f=$2 m=$(( $1 * 14 / 100 ))
  local lado=$(( t - 2 * m ))
  rsvg-convert -w "$lado" -h "$lado" "$SVG" -o "$TMP/marca_$t.png"
  python3 - "$t" "$m" "$TMP/marca_$t.png" "$f" <<'PY'
import sys, subprocess
t, m, marca, saida = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4]
r = int(t * 0.2237)
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{t}" height="{t}">
<rect x="0" y="0" width="{t}" height="{t}" rx="{r}" fill="#FFFFFF"/>
<image x="{m}" y="{m}" width="{t-2*m}" height="{t-2*m}" xlink:href="file://{marca}"/></svg>'''
subprocess.run(["rsvg-convert", "-w", str(t), "-h", str(t), "-o", saida], input=svg.encode(), check=True)
PY
}

if command -v iconutil >/dev/null; then
  SET="$TMP/Redes.iconset"; mkdir "$SET"
  for t in 16 32 128 256 512; do
    ic $t "$SET/icon_${t}x${t}.png"; ic $((t*2)) "$SET/icon_${t}x${t}@2x.png"
  done
  iconutil -c icns "$SET" -o "$SAIDA"
else
  for t in 16 32 64 128 256 512 1024; do ic $t "$TMP/p$t.png"; done
  python3 - "$TMP" "$SAIDA" <<'PY'
import struct, sys
d, saida = sys.argv[1], sys.argv[2]
tipos = [("icp4",16),("icp5",32),("icp6",64),("ic07",128),("ic08",256),("ic09",512),("ic10",1024)]
blocos = b""
for tag, t in tipos:
    dados = open(f"{d}/p{t}.png","rb").read()
    blocos += tag.encode() + struct.pack(">I", len(dados)+8) + dados
open(saida,"wb").write(b"icns" + struct.pack(">I", len(blocos)+8) + blocos)
PY
fi
echo "Ícone gerado: $SAIDA"

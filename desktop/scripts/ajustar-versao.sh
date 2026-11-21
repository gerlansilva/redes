#!/usr/bin/env bash
# Ajusta a versão do app desktop (tauri.conf.json e Cargo.toml).
set -euo pipefail

VERSAO="${1:-}"
case "$VERSAO" in
  [0-9]*.[0-9]*.[0-9]*) ;;
  *) echo "Uso: $0 <versao x.y.z>" >&2; exit 1 ;;
esac

AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"

python3 - "$RAIZ" "$VERSAO" <<'PY'
import json
import re
import sys
from pathlib import Path

raiz = Path(sys.argv[1])
versao = sys.argv[2]

config = raiz / "desktop/src-tauri/tauri.conf.json"
dados = json.loads(config.read_text(encoding="utf-8"))
dados["version"] = versao
config.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

cargo = raiz / "desktop/src-tauri/Cargo.toml"
texto = cargo.read_text(encoding="utf-8")
texto, total = re.subn(r'(?m)^version = "[^"]+"$', f'version = "{versao}"', texto, count=1)
if total != 1:
    raise SystemExit("versão não encontrada no Cargo.toml")
cargo.write_text(texto, encoding="utf-8")
print(f"Versão do desktop: {versao}")
PY

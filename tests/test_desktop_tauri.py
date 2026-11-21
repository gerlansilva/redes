"""App desktop (Tauri): configuração, versionamento e empacotamento coerentes."""
import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DESKTOP = RAIZ / "desktop"
CONFIG = DESKTOP / "src-tauri" / "tauri.conf.json"
CARGO = DESKTOP / "src-tauri" / "Cargo.toml"
PACOTE = DESKTOP / "package.json"
SCRIPT = DESKTOP / "scripts" / "build-sidecar.sh"
WORKFLOW = RAIZ / ".github" / "workflows" / "tauri.yml"

pytestmark = pytest.mark.skipif(not CONFIG.exists(), reason="app desktop não está neste ramo")


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_config_do_app():
    config = _config()
    assert config["productName"] == "Redes"
    assert config["identifier"] == "br.gerlan.redes"
    assert set(config["bundle"]["targets"]) == {"app", "dmg"}
    assert config["bundle"]["externalBin"] == ["binaries/redes-servidor"]
    # A janela abre na tela de abertura; o Rust navega para o servidor local.
    assert config["app"]["windows"][0]["label"] == "main"
    assert config["app"]["windows"][0]["url"] == "index.html"


def test_versao_unica_entre_config_cargo_e_pacote():
    versao = _config()["version"]
    cargo = re.search(r'^version = "([^"]+)"', CARGO.read_text(encoding="utf-8"), re.M)
    assert cargo and cargo.group(1) == versao
    assert json.loads(PACOTE.read_text(encoding="utf-8"))["version"] == versao


def test_icone_e_so_a_imagem_da_rede():
    marca = (RAIZ / "redes" / "assets" / "logo-icone.svg").read_text(encoding="utf-8")
    assert "<text" not in marca and "<tspan" not in marca
    # Só a marca: os três traços da rede e os nós coloridos.
    assert marca.count("<circle") >= 8
    assert marca.count("<ellipse") == 2
    icones = _config()["bundle"]["icon"]
    assert "icons/icon.icns" in icones and "icons/icon.ico" in icones
    script = (DESKTOP / "scripts" / "gerar-icones.sh").read_text(encoding="utf-8")
    assert "logo-icone.svg" in script
    assert "logo.svg" not in script


def test_sidecar_e_o_servidor_web():
    rust = (DESKTOP / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")
    assert 'sidecar("redes-servidor")' in rust
    assert '"--nao-abrir"' in rust
    assert "navigate(" in rust
    assert "filho.kill()" in rust
    assert "REDES_PAI_PID" in rust
    entrada = (DESKTOP / "servidor" / "redes_servidor.py").read_text(encoding="utf-8")
    assert 'main(["web", *sys.argv[1:]])' in entrada
    assert "vigia_do_pai" in entrada
    assert "os._exit(0)" in entrada
    # No Windows `os.kill(pid, 0)` encerraria o app; usa a API do sistema.
    assert "OpenProcess" in entrada and 'os.name == "nt"' in entrada


def test_script_gera_o_sidecar_com_o_triplo_do_alvo():
    script = SCRIPT.read_text(encoding="utf-8")
    assert "--onefile" in script and "--name redes-servidor" in script
    assert 'redes-servidor-$ALVO' in script
    assert "--collect-data redes" in script
    assert 'EXT=".exe"' in script


def test_workflow_publica_macos_e_windows():
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "macos-latest" in texto and "windows-latest" in texto
    assert "tauri build" in texto
    assert "--bundles nsis" in texto
    assert "gh release create" in texto and "gh release upload" in texto
    assert "Redes-${VERSAO}-macOS-" in texto
    assert "Redes-${VERSAO}-Windows-x64-setup.exe" in texto
    assert "sha256sum" in texto

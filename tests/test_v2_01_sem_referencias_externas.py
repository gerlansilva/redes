"""O pacote não pode citar nem depender de nomenclatura de outras ferramentas."""
import re
from pathlib import Path

import pytest

import redes
from redes import kb, projeto

RAIZ = Path(redes.__file__).parent
# Montados por partes para que este arquivo não contenha os próprios termos.
PROIBIDOS = re.compile("|".join(["sci" + "mat", "biblio" + "mapa", "si" + "mat\\b", "\\bfo" + "rk\\b"]),
                       re.IGNORECASE)
SUFIXOS = {".py", ".js", ".html", ".css", ".svg", ".json", ".md", ".txt"}


def _arquivos():
    return [p for p in RAIZ.rglob("*") if p.is_file() and "__pycache__" not in p.parts]


@pytest.mark.parametrize("caminho", [p for p in _arquivos() if p.suffix in SUFIXOS],
                         ids=lambda p: str(p.relative_to(RAIZ)))
def test_arquivo_sem_termos_proibidos(caminho):
    texto = caminho.read_text(encoding="utf-8", errors="ignore")
    assert not PROIBIDOS.search(texto), f"{caminho} cita outra ferramenta"


def test_nomes_de_arquivo_limpos():
    assert not [p for p in _arquivos() if PROIBIDOS.search(p.name)]


def test_classe_renomeada():
    assert hasattr(kb, "ProjetoRedes")
    assert not hasattr(kb, "Projeto" + "Sci" + "mat")


def test_so_extensao_redes():
    antiga = "." + "sci" + "mat"
    assert projeto.EXTENSOES == (".redes",)
    assert projeto.e_projeto("x/dados.redes")
    assert not projeto.e_projeto("x/dados" + antiga)


def test_lista_projetos_ignora_extensao_antiga(tmp_path, projeto):
    from redes.api import lista_projetos
    antiga = "." + "sci" + "mat"
    (tmp_path / ("solto" + antiga)).write_bytes(projeto.read_bytes())
    pasta = tmp_path / "subpasta"
    pasta.mkdir()
    (pasta / ("dados" + antiga)).write_bytes(projeto.read_bytes())
    nomes = {p["nome"] for p in lista_projetos(tmp_path)}
    assert nomes == {"dados"}


def test_rotulo_do_csv_neutro():
    ui = RAIZ / "ui"
    assert "CSV tabulado (Redes/WoS)" in (ui / "index.html").read_text(encoding="utf-8")
    assert 'csv: "CSV tabulado (Redes/WoS)"' in (ui / "app.js").read_text(encoding="utf-8")
    assert '<option value="csv">' in (ui / "index.html").read_text(encoding="utf-8")


def test_sobre_cita_o_autor():
    html = (RAIZ / "ui" / "index.html").read_text(encoding="utf-8")
    assert "Gerlan Silva da Silva (UFSCar)" in html


def test_versao():
    assert re.fullmatch(r"\d+\.\d+\.\d+", redes.__version__)

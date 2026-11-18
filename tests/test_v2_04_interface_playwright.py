"""Teste de navegador: o gráfico log-log não gera caminhos inválidos e o Sobre está limpo.

Pula sozinho quando o Playwright ou o Chrome não estão disponíveis.
"""
import shutil
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

import redes  # noqa: E402

UI = Path(redes.__file__).parent / "ui"
CHROME = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")


@pytest.fixture
def pagina():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            navegador = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"]) \
                if CHROME else p.chromium.launch()
        except Exception as erro:  # navegador não instalado
            pytest.skip(f"sem navegador: {erro}")
        pg = navegador.new_page()
        yield pg
        navegador.close()


def test_grafico_loglog_ignora_esperada_zero(pagina):
    erros = []
    pagina.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    pagina.set_content("<div id='x'></div>")
    pagina.add_script_tag(path=str(UI / "bibliometria.js"))
    svg = pagina.evaluate("""() => {
      const pontos = [
        {documentos: 1, proporcao: 0.6, esperada: 0.6079},
        {documentos: 5, proporcao: 0.05, esperada: 0.0243},
        {documentos: 147, proporcao: 0.01, esperada: 0}];
      return graficoLogLog(pontos, 'documentos', 'proporcao', (p) => p.esperada, 'x', 'y');
    }""")
    assert "Infinity" not in svg and "NaN" not in svg
    assert "stroke-dasharray" in svg  # a curva esperada ainda é desenhada
    pagina.evaluate("(s) => { document.getElementById('x').innerHTML = s; }", svg)
    assert not erros


def test_sobre_sem_marca_e_sem_aba_inexistente(pagina):
    pagina.set_content((UI / "index.html").read_text(encoding="utf-8"))
    texto = pagina.inner_text("#modalSobre") if pagina.locator("#modalSobre").count() else ""
    assert "Gerlan Silva da Silva" in texto
    assert "na tela Base" in texto
    assert "aba Períodos" not in texto

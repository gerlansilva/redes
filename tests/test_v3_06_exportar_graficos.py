"""Visão geral descritiva: cada gráfico exporta SVG, PNG (2x) e dados (CSV) no navegador.

Pula sozinho quando o Playwright ou o Chrome não estão disponíveis.
"""
import re
import shutil
import struct
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import redes
from redes import api

UI = Path(redes.__file__).parent / "ui"
CHROME = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")


def test_cada_secao_tem_botao_salvar_grafico():
    js = (UI / "bibliometria.js").read_text(encoding="utf-8")
    assert "botaoExportarBib()" in js and "instalarExportacaoBib" in js
    exp = (UI / "exportar_bib.js").read_text(encoding="utf-8")
    assert 'title="Salvar gráfico"' in exp and 'aria-label="Salvar gráfico"' in exp
    assert "const escala = 2" in exp and "#ffffff" in exp
    assert "/static/exportar_bib.js" in (UI / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"https?://(?!www.w3.org)", exp)


@pytest.fixture
def navegador_e_servidor(tmp_path, projeto):
    playwright = pytest.importorskip("playwright.sync_api")
    pasta = tmp_path / "ws"
    pasta.mkdir()
    shutil.copy(projeto, pasta / "demo.redes")
    servidor = api.cria_servidor(0, pasta)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    with playwright.sync_playwright() as p:
        try:
            nav = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"]) \
                if CHROME else p.chromium.launch()
        except Exception as erro:
            servidor.shutdown()
            pytest.skip(f"sem navegador: {erro}")
        yield nav, f"http://127.0.0.1:{servidor.server_address[1]}/", pasta / "demo.redes"
        nav.close()
    servidor.shutdown()


def test_download_de_svg_png_e_csv(navegador_e_servidor, tmp_path):
    nav, url, projeto = navegador_e_servidor
    pagina = nav.new_page(accept_downloads=True)
    erros = []
    pagina.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    pagina.goto(url)
    if pagina.locator("#btnComecar").is_visible():
        pagina.click("#btnComecar")
    pagina.evaluate("(c) => abrir(c)", str(projeto))
    pagina.wait_for_selector("#visaoBibliometria .bib-secao", timeout=20000)
    secao = "document.querySelectorAll('#visaoBibliometria .bib-secao')[0]"
    for formato in ("svg", "png", "csv"):
        pagina.wait_for_timeout(1200)
        pagina.evaluate(f"{secao}.querySelector('.bib-exportar').click()")
        with pagina.expect_download(timeout=10000) as info:
            pagina.evaluate(f"{secao}.querySelector('[data-exp-bib={formato}]').click()")
        baixado = info.value
        assert baixado.suggested_filename == f"demo-producao-e-citacoes-por-ano.{formato}"
        destino = tmp_path / baixado.suggested_filename
        baixado.save_as(destino)
        dados = destino.read_bytes()
        assert dados
        if formato == "svg":
            assert ET.fromstring(dados).tag.endswith("svg")
            assert "Produção e citações por ano".encode() in dados and b'fill="#ffffff"' in dados
        elif formato == "png":
            assert dados[:8] == b"\x89PNG\r\n\x1a\n"
            largura, altura = struct.unpack(">II", dados[16:24])
            assert largura >= 1280 and altura > 300      # 2x de uma figura de pelo menos 640 de largura
        else:
            texto = dados.decode("utf-8-sig").splitlines()
            assert texto[0] == "ano;documentos;citacoes;acumulado" and len(texto) >= 2
    assert not erros

"""Ícones inline: abas e menu com nome completo em title e aria-label, sem biblioteca externa."""
import re
from pathlib import Path

import redes

UI = Path(redes.__file__).parent / "ui"
HTML = (UI / "index.html").read_text(encoding="utf-8")


def test_abas_tem_icone_e_nome_acessivel():
    abas = re.findall(r'<div class="aba[^"]*" data-aba="(\w+)"[^>]*>(.*?)</div>', HTML, flags=re.S)
    assert len(abas) >= 16
    for chave, interior in abas:
        assert "<svg" in interior and 'aria-hidden="true"' in interior, chave
        assert "aba-texto" in interior, chave
    for m in re.finditer(r'<div class="aba[^"]*" data-aba="(\w+)"([^>]*)>', HTML):
        assert "title=" in m.group(2) and "aria-label=" in m.group(2), m.group(1)


def test_menu_com_rotulo_curto_e_nome_completo_no_titulo():
    itens = re.findall(r'<button type="button" class="nav-analise[^"]*" data-analise="(\w+)" '
                       r'title="([^"]+)" aria-label="([^"]+)">.*?<span class="nav-texto">([^<]+)</span>',
                       HTML, flags=re.S)
    assert len(itens) == 9
    for chave, titulo, rotulo, curto in itens:
        assert " " not in curto.strip() or chave == "visao", (chave, curto)
        assert titulo == rotulo, (chave, titulo, rotulo)
        # O rótulo curto é prefixo do nome completo ou a categoria que o nome
        # qualifica ("Autores" em "Cocitação de autores").
        assert (titulo.startswith(curto)
                or curto.casefold() in titulo.casefold()), (chave, curto, titulo)


def test_sem_biblioteca_externa_de_icones():
    for arquivo in ("index.html", "app.js", "style.css"):
        texto = (UI / arquivo).read_text(encoding="utf-8")
        assert not re.search(r'src="https?://', texto), arquivo
        assert "@import" not in texto and "url(http" not in texto, arquivo

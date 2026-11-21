"""Ícones inline: abas e menu com nome completo em title e aria-label, sem biblioteca externa."""
import re
from pathlib import Path

import redes

UI = Path(redes.__file__).parent / "ui"
HTML = (UI / "index.html").read_text(encoding="utf-8")
JS = (UI / "app.js").read_text(encoding="utf-8")
CSS = (UI / "style.css").read_text(encoding="utf-8")


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


def test_menu_lateral_com_grupos_e_descricoes():
    for grupo in ("Temas", "Citações", "Colaboração"):
        assert f'<p class="grupo-titulo">{grupo}</p>' in HTML, grupo
    assert HTML.count('class="grupo-titulo"') == 3
    assert HTML.count('class="nav-desc"') == 9
    for texto in ("Coocorrência entre termos", "Quem publica com quem",
                  "Cooperação internacional", "Revistas citadas juntas"):
        assert texto in HTML, texto


def test_menu_nao_repete_o_titulo_do_grupo_no_item():
    # O cabeçalho do bloco é a categoria; o item nomeia o objeto analisado.
    grupos = re.findall(r'<p class="grupo-titulo">([^<]+)</p>', HTML)
    itens = re.findall(r'<span class="nav-texto">([^<]+)</span>', HTML)
    assert grupos and itens
    repetidos = [g for g in grupos if g.casefold() in {i.casefold() for i in itens}]
    assert not repetidos, repetidos


def test_descricao_nao_repete_o_nome_do_item():
    # A segunda linha acrescenta informação; repetir o nome só ocupa espaço.
    pares = re.findall(
        r'<span class="nav-texto">([^<]+)</span><span class="nav-desc">([^<]+)</span>',
        HTML)
    assert len(pares) == 9
    for nome, descricao in pares:
        palavras = [p for p in re.split(r"[\s\-]+", nome.casefold()) if len(p) > 3]
        assert not any(p in descricao.casefold() for p in palavras), (nome, descricao)


def test_abas_visiveis_e_agrupadas_por_bloco():
    # Nenhuma aba some no modo simples e a personalizada não perde visões.
    assert "ABAS_SIMPLES" not in JS and "ABAS_SO_AVANCADO" not in JS
    grupos = re.search(r"const GRUPOS_ABAS = \[.*?\];", JS, flags=re.S).group(0)
    for chave in ("resumo", "rede", "grupos", "dendrograma", "similitude", "longitudinal"):
        assert f'"{chave}"' in grupos, chave
    assert "montarGruposAbas();" in JS
    # O nome de todas as abas fica à vista, não só o da ativa.
    assert ".aba .aba-texto { display: inline; }" in CSS


def test_sem_biblioteca_externa_de_icones():
    for arquivo in ("index.html", "app.js", "style.css"):
        texto = (UI / arquivo).read_text(encoding="utf-8")
        assert not re.search(r'src="https?://', texto), arquivo
        assert "@import" not in texto and "url(http" not in texto, arquivo

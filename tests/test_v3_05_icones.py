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
    assert len(abas) >= 15
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


def test_barra_de_resultados_sem_rotulo_repetido():
    # O bloco "Mapas" não se chama "Rede" para não parecer a aba "Rede de ...".
    grupos = re.search(r"const GRUPOS_ABAS = \[.*?\];", JS, flags=re.S).group(0)
    rotulos = re.findall(r'rotulo: "([^"]+)"', grupos)
    assert "Mapas" in rotulos and "Rede" not in rotulos
    itens = re.findall(r'<span class="aba-texto">([^<]+)</span>', HTML)
    # Nomes de aba não repetem o rótulo do próprio bloco.
    assert "Agrupamentos" not in itens
    assert "Rede de agrupamentos" not in itens
    assert "Ligações entre grupos" in itens and "Grupos" in itens


def test_evolucao_fala_da_unidade_da_analise():
    # A evolução não pode dizer "tema" quando a análise é de autores ou referências.
    assert "function textosEvolucao(" in JS
    assert "Tema no período anterior" not in JS
    assert "evolução dos temas…" not in JS
    assert "SUBSTANTIVO_GRUPO[unidade]" in JS


def test_cada_analise_so_oferece_abas_que_se_aplicam():
    config = re.search(r"const CONFIG_ABAS = \{.*?\n\};", JS, flags=re.S).group(0)
    entradas = dict(re.findall(r"(\w+): \{\s*abas: \[(.*?)\]", config, flags=re.S))
    assert len(entradas) == 8
    abas = {chave: re.findall(r'"(\w+)"', lista) for chave, lista in entradas.items()}
    # Só palavras-chave pede similitude de resumos.
    assert [k for k, v in abas.items() if "similitude" in v] == ["conceitual"]
    # Só periódicos pede duplo mapa de áreas das revistas.
    assert [k for k, v in abas.items() if "duplomapa" in v] == ["veiculos"]
    # Mapa de países só na análise de países; a aba de variantes unidas não
    # entra mais na barra (a consolidação continua no relatório).
    assert [k for k, v in abas.items() if "paises" in v] == ["paises"]
    assert not any("ies" in v for v in abas.values())
    # Documentos só onde o agrupamento é de documentos.
    assert sorted(k for k, v in abas.items() if "documentos" in v) == ["conceitual", "frentes"]
    # Densidade vale em todas as unidades; dendrograma e linha do tempo nas
    # análises gerais. Países fica com mapa e densidade; instituições, com a
    # rede e a densidade; coautoria, com rede, dendrograma, linha do tempo e
    # densidade.
    assert all("densidade" in v for v in abas.values())
    for chave in ("dendrograma", "linhatempo"):
        assert all(chave in v for k, v in abas.items()
                   if k not in ("paises", "instituicoes")), chave
    assert abas["paises"] == ["paises", "densidade"]
    assert abas["instituicoes"] == ["rede", "densidade"]
    assert abas["autores"] == ["rede", "dendrograma", "linhatempo", "densidade"]


def test_troca_de_analise_limpa_o_resultado_anterior():
    trecho = re.search(r"function escolherAnalise\(.*?\n}\n", JS, flags=re.S).group(0)
    assert "limparResultado();" in trecho
    limpar = re.search(r"function limparResultado\(.*?\n}\n", JS, flags=re.S).group(0)
    assert "limparEvolucao();" in limpar


def test_modo_avancado_nao_oferece_paises_nem_ies():
    # As duas unidades têm análise própria no menu; na configuração manual
    # ficam ocultas para não duplicar a escolha.
    for valor in ("Countries", "Institutions"):
        opcao = re.search(rf'<option value="{valor}"([^>]*)>', HTML)
        assert opcao, valor
        assert "hidden" in opcao.group(1) and "disabled" in opcao.group(1), valor


def test_sem_alternador_de_modo_e_parametros_a_vista():
    # O antigo "Modo avançado" saiu: todos os parâmetros ficam à vista.
    assert 'id="modoAvancado"' not in HTML
    assert 'class="sidebar-modo"' not in HTML
    assert "body:not(.modo-avancado) .so-avancado" not in CSS
    assert '<details class="mais-opcoes" id="maisOpcoes" open>' in HTML
    assert '<details class="avancado so-avancado" id="avancado" open>' in HTML
    assert "avancado: true" in JS


def test_sem_faixa_de_avisos_na_analise():
    # Os avisos continuam na API e no relatório; a tela não repete a faixa amarela.
    assert "faixaAvisos" not in HTML
    assert "faixaAvisos" not in JS
    assert "mostrarFaixaAvisos" not in JS
    assert ".faixa-avisos" not in CSS and "faixa-aviso" not in CSS
    assert "nav-pouco" not in HTML


def test_abas_visiveis_e_agrupadas_por_bloco():
    # Nenhuma aba some no modo simples e a personalizada não perde visões.
    assert "ABAS_SIMPLES" not in JS and "ABAS_SO_AVANCADO" not in JS
    grupos = re.search(r"const GRUPOS_ABAS = \[.*?\];", JS, flags=re.S).group(0)
    for chave in ("rede", "grupos", "dendrograma", "similitude", "longitudinal"):
        assert f'"{chave}"' in grupos, chave
    assert "montarGruposAbas();" in JS
    # O nome de todas as abas fica à vista, não só o da ativa.
    assert ".aba .aba-texto { display: inline; }" in CSS


def test_sem_aba_resumo():
    # O resumo em prosa saiu da tela: cada análise começa numa visão aplicada.
    assert 'data-aba="resumo"' not in HTML
    assert 'id="blocoResumo"' not in HTML
    assert "blocoResumo" not in JS
    assert "renderizarResumo(" not in JS
    assert "renderizarResumoVazio(" not in JS
    assert "mostrarCarregandoResumo(" not in JS


def test_sem_biblioteca_externa_de_icones():
    for arquivo in ("index.html", "app.js", "style.css"):
        texto = (UI / arquivo).read_text(encoding="utf-8")
        assert not re.search(r'src="https?://', texto), arquivo
        assert "@import" not in texto and "url(http" not in texto, arquivo

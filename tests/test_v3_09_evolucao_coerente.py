"""Evolução temática: relatório e interface usam os mesmos parâmetros e os dizem na figura."""
import re
from pathlib import Path

from redes import api, longitudinal
from redes.build import constroi
from redes.kb import ProjetoRedes
from redes.loaders.base import DocumentoFonte

PERIODOS_3 = [("2010–2011", 2010, 2011), ("2012–2013", 2012, 2013), ("2014–2015", 2014, 2015)]
PERIODOS_4 = PERIODOS_3 + [("2016–2017", 2016, 2017)]


def _docs(anos):
    docs = []
    for k, ano in enumerate(anos):
        for i in range(4):
            # "base" aparece em todos os documentos (frequência alta); os demais
            # termos aparecem uma ou duas vezes, de modo que frequência 1 e 3
            # dão números de temas diferentes.
            palavras = ["base", f"tema {k} a", f"tema {k} b"] + ([f"tema {k} c"] if i % 2 else [])
            if i == 3:      # par de termos raros: só existe com frequência mínima 1
                palavras = [f"raro {k} x", f"raro {k} y"]
            docs.append(DocumentoFonte(
                titulo=f"Artigo {ano}-{i}", autores=["Silva, A.", f"Autor {i}, X."],
                ano=str(ano), citacoes=i, periodico="Revista X",
                palavras_autor=palavras, palavras_fonte=[]))
    return docs


def _projeto(tmp_path, periodos=PERIODOS_3):
    destino = tmp_path / "dados.redes"
    anos = [p[1] for p in periodos] + [p[2] for p in periodos]
    constroi(_docs(sorted(set(anos))), destino, periodos)
    return destino


def _svg_evolucao(html: str) -> str:
    inicio = html.index('aria-label="Mapa de evolução dos temas"')
    inicio = html.rindex("<svg", 0, inicio)
    return html[inicio:html.index("</svg>", inicio)]


def _html_relatorio(projeto, **extra):
    r = api.gera_relatorio_completo({"projeto": str(projeto), "formato": "unico", **extra})
    return Path(api.CACHE / f"rel-{r['token']}" / "relatorio-completo.html").read_text(encoding="utf-8")


def test_relatorio_com_parametros_da_tela_tem_os_mesmos_temas_da_aba(tmp_path):
    projeto = _projeto(tmp_path)
    aba = api.gera_longitudinal({"projeto": str(projeto), "unidade": "Words",
                                 "matriz": "CoOccurrence", "minimo_frequencia": 1})
    svg = _svg_evolucao(_html_relatorio(projeto, minimo_frequencia=1))
    assert svg.count("<circle") == aba["nos"]
    assert "frequência mínima 1" in svg
    # a aba usa o mesmo texto de parâmetros na figura
    svg_aba = Path(api.FIGURAS[aba["figuras"]["evolucao"].rsplit("/", 1)[1]]).read_text(encoding="utf-8")
    assert re.search(r"frequência mínima 1 · coocorrência mínima 1 · rede de 2 a 15", svg_aba)
    assert re.search(r"frequência mínima 1 · coocorrência mínima 1 · rede de 2 a 15", svg)


def test_frequencia_diferente_muda_so_a_contagem_declarada(tmp_path):
    projeto = _projeto(tmp_path)
    contagens = {}
    with ProjetoRedes(projeto) as kb:
        periodos = kb.periodos()
        for freq in (1, 3):
            config = api._config({"unidade": "Words", "matriz": "CoOccurrence",
                                  "minimo_frequencia": freq})
            mapa = longitudinal.constroi(kb, config, periodos)
            contagens[freq] = len(mapa.nos)
            assert f"frequência mínima {freq}" in mapa.parametros
    assert contagens[1] > contagens[3]          # a diferença vem só da frequência mínima
    # fixar a frequência no relatório reproduz a mesma contagem da análise direta
    for freq in (1, 3):
        svg = _svg_evolucao(_html_relatorio(projeto, minimo_frequencia=freq))
        assert svg.count("<circle") == contagens[freq]


def test_relatorio_sem_frequencia_explicita_diz_que_e_automatica(tmp_path):
    projeto = _projeto(tmp_path)
    html = _html_relatorio(projeto)
    assert "escolhida automaticamente" in html
    assert "a mesma da tela" not in html
    assert "a mesma da tela" in _html_relatorio(projeto, minimo_frequencia=1)


def test_numeros_por_periodo_nao_mudam_com_a_frequencia_declarada(tmp_path):
    projeto = _projeto(tmp_path)
    with ProjetoRedes(projeto) as kb:
        periodos = kb.periodos()
        auto = api._escolhe_frequencia(kb, periodos, {}, {"unidade": "Words", "matriz": "CoOccurrence"})
        fixa = api._escolhe_frequencia(kb, periodos, {}, {"unidade": "Words", "matriz": "CoOccurrence"},
                                       auto[1])
    assert auto[1] == fixa[1]
    assert [len(r.grupos) for r in auto[2]] == [len(r.grupos) for r in fixa[2]]


def _ys(svg: str, trecho: str) -> list[float]:
    return [float(y) for y in re.findall(rf'<text[^>]* y="([\d.]+)"[^>]*>{trecho}', svg)]


def test_rotulo_do_periodo_nao_encosta_na_legenda(tmp_path):
    for periodos in (PERIODOS_3, PERIODOS_4):
        projeto = tmp_path / f"p{len(periodos)}"
        projeto.mkdir()
        caminho = _projeto(projeto, periodos)
        with ProjetoRedes(caminho) as kb:
            config = api._config({"unidade": "Words", "matriz": "CoOccurrence"})
            mapa = longitudinal.constroi(kb, config, kb.periodos())
        svg = longitudinal.evolucao_svg(mapa, "Mapa de evolução dos temas", largura=980)
        legenda = _ys(svg, "medida de sobreposição") + _ys(svg, "frequência mínima")
        rotulos = [y for nome in mapa.periodos for y in _ys(svg, nome)]
        assert len(legenda) == 2 and len(rotulos) == len(periodos)
        # fonte de 11 px: o rótulo começa ~9 px acima da linha de base
        assert min(rotulos) - 9 - max(legenda) >= 8


def test_texto_do_pacote_nao_cita_o_nome_de_origem():
    raiz = Path(api.__file__).parent
    achados = [str(p) for p in raiz.rglob("*") if p.is_file()
               and p.suffix in {".py", ".js", ".html", ".css", ".md"}
               and "celii" in p.read_text(encoding="utf-8", errors="ignore").lower()]
    assert not achados

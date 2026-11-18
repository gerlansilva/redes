"""Créditos das medidas pelo nome do autor e descrição do nó principal."""


def test_textos_nao_citam_ferramenta_de_terceiros():
    import re
    from pathlib import Path

    import redes
    proibido = re.compile("Cite" + "Space", re.IGNORECASE)
    for caminho in Path(redes.__file__).parent.rglob("*"):
        if caminho.suffix in {".py", ".js", ".html", ".md", ".txt"} and "__pycache__" not in caminho.parts:
            assert not proibido.search(caminho.read_text(encoding="utf-8", errors="ignore")), caminho


def test_creditos_de_medidas_pelo_nome_do_autor():
    from redes import metodo, pivos, rajadas
    assert "Chen, 2006" in pivos.__doc__
    assert "Kleinberg" in rajadas.__doc__
    assert "Chen e Leydesdorff" in __import__("redes.duplo_mapa", fromlist=["x"]).__doc__


def test_descricao_do_no_principal_em_centros_simples_e_precisa():
    from redes import metodo
    texto = open(metodo.__file__, encoding="utf-8").read()
    assert "último nó do agrupamento cuja similaridade média com os vizinhos é menor que a do primeiro nó" in texto
    assert "critério fixo, que não escolhe o máximo" in texto

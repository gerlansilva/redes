from redes.loaders.base import DocumentoFonte
from redes.normaliza import aplica_sinonimos
from redes.words import Sinonimos


def _doc():
    return DocumentoFonte(
        titulo="T", autores=["Lopes, C.E.", "Silva, A."], periodico="Suma",
        afiliacoes=["Univ. Cruzeiro do Sul, Sao Paulo, Brazil"], paises=["Brasil", "Spain"],
        palavras_autor=["stat ed"],
        metadados={"Authors with affiliations": "Lopes, C.E. (Univ. Cruzeiro do Sul, Brazil)"})


def _mapa(tmp_path):
    arq = tmp_path / "sin.txt"
    arq.write_text(
        "# comentário de linha\n"
        "Lopes, Celi E. = Lopes, C.E.   # inline\n"
        "SUMA = Suma;  suma\n"
        "Universidade Cruzeiro do Sul = Univ. Cruzeiro do Sul # sigla\n"
        "Brazil = Brasil\n"
        "statistics education = stat ed\n", encoding="utf-8")
    return Sinonimos(arq)


def test_comentarios_inline_ignorados(tmp_path):
    s = _mapa(tmp_path)
    assert s.aplica("Lopes, C.E.") == "Lopes, Celi E."
    assert all("inline" not in k and "sigla" not in k for k in s.canonico)


def test_aplica_a_cada_unidade_escolhida(tmp_path):
    s = _mapa(tmp_path)
    d = _doc()
    aplica_sinonimos([d], s, ("palavras",))
    assert d.palavras_autor == ["statistics education"] and d.autores[0] == "Lopes, C.E."
    d = _doc()
    feitas = aplica_sinonimos([d], s, ("autores", "periodicos", "paises", "instituicoes"))
    assert d.autores == ["Lopes, Celi E.", "Silva, A."]
    assert d.periodico == "SUMA"
    assert d.paises == ["Brazil", "Spain"]
    assert d.afiliacoes == ["Universidade Cruzeiro do Sul, Sao Paulo, Brazil"]
    assert "Universidade Cruzeiro do Sul" in d.metadados["Authors with affiliations"]
    assert d.palavras_autor == ["stat ed"]     # palavras não escolhidas ficam como estão
    assert set(feitas) == {"autores", "periodicos", "paises", "instituicoes"}

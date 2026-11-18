from redes.loaders.base import DocumentoFonte
from redes.normaliza import chave_radical, normaliza_palavras_por_radical


def test_radical_une_variantes():
    assert chave_radical("statistics education") == chave_radical("statistical education")
    assert chave_radical("Educação Estatística") == chave_radical("educacao estatistica")
    assert chave_radical("mathematics teachers") == chave_radical("mathematical teacher")
    assert chave_radical("statistics education") != chave_radical("teacher education")


def test_normaliza_palavras_escolhe_mais_frequente():
    docs = [DocumentoFonte(titulo=str(i), palavras_autor=[p])
            for i, p in enumerate(["statistics education", "statistics education",
                                   "statistical education", "probability"])]
    unidos = normaliza_palavras_por_radical(docs)
    assert [d.palavras_autor[0] for d in docs] == ["statistics education"] * 3 + ["probability"]
    assert unidos == {"statistics education": ["statistical education", "statistics education"]}

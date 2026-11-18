"""Apresentação de termos e títulos: GT12, GeoGebra, siglas e numerais romanos."""
import pytest

from redes.texto import exibe_termo, restaura_romanos, termo_de_rotulo, termo_legivel


@pytest.mark.parametrize("entrada,esperado", [
    ("GT12", "GT12"), ("GEOGEBRA", "GeoGebra"), ("SIPEM", "SIPEM"), ("ENEM", "ENEM"),
    ("IRAMUTEQ", "IRAMUTEQ"), ("COVID19", "COVID19"), ("TIMSS 2019", "TIMSS 2019"),
    ("GeoGebra", "GeoGebra"),                      # caixa mista nunca é reescrita
    ("STATISTICAL-REASONING", "Statistical reasoning"), ("E-LEARNING", "E-learning"),
    ("WORLD WAR II", "World war II"), ("TEACHING OF STATISTICS III", "Teaching of statistics III"),
])
def test_termo_legivel_preserva_tokens_especiais(entrada, esperado):
    assert termo_legivel(entrada) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    ("Anais do Iv Seminario Internacional", "Anais do IV Seminario Internacional"),
    ("Iii Sipem Pp. 1-11", "III Sipem Pp. 1-11"), ("Vii Sipem", "VII Sipem"),
    ("Xiii Ciaem", "XIII Ciaem"), ("Civil Engineering", "Civil Engineering"),
    ("Anais do IV Seminario", "Anais do IV Seminario"),
])
def test_restaura_romanos_em_titulos(entrada, esperado):
    assert restaura_romanos(entrada) == esperado


def test_exibe_termo_por_unidade_e_rotulos():
    assert exibe_termo("ReferenceSources", "Anais do Iv Seminario") == "Anais do IV Seminario"
    assert exibe_termo("Authors", "Iv, A.") == "Iv, A."          # nomes de pessoas não mudam
    assert exibe_termo("Words", "GT12") == "GT12"
    assert termo_de_rotulo("geogebra e sipem") == "GeoGebra e SIPEM"

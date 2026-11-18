import sqlite3

from redes import fluxos
from redes.build import constroi
from redes.loaders.base import DocumentoFonte


def test_le_autor_afiliacao_dois_formatos():
    assert fluxos.le_autor_afiliacao(
        "Lopes, C.E. (Universidade X, Brazil); Mondoni, M.H.A. (Universidade X, Brazil)") == [
        ("Lopes, C.E.", "Universidade X, Brazil"), ("Mondoni, M.H.A.", "Universidade X, Brazil")]
    assert fluxos.le_autor_afiliacao(
        "Batanero, C., Universidad de Granada, Granada, Spain; Díaz, C., Universidad de Huelva, Huelva, Spain") == [
        ("Batanero, C.", "Universidad de Granada, Granada, Spain"),
        ("Díaz, C.", "Universidad de Huelva, Huelva, Spain")]


def test_fluxo_usa_vinculo_autor_afiliacao_openalex(tmp_path):
    docs = [DocumentoFonte(
        titulo="A", autores=["Lopes, C.E.", "Silva, A."], ano="2020",
        periodico="J", afiliacoes=["Universidade X, Brazil", "University Y, Spain"],
        paises=["Brazil", "Spain"], palavras_autor=["t"],
        metadados={"Authors with affiliations":
                   "Lopes, C.E. (Universidade X, Brazil); Silva, A. (University Y, Spain)"})]
    destino = tmp_path / "p.redes"
    constroi(docs, destino, [("2020", 2020, 2020)])
    dados = fluxos.calcula(sqlite3.connect(destino))
    assert dados["cobertura"]["exata"] == 1
    assert dados["modo"] == "autor_pais_ies"
    nomes = {n["nome"] for n in dados["nos"]}
    assert {"Lopes, C.E.", "Silva, A."} <= nomes


def test_nome_curto_contra_nome_completo():
    assert fluxos._mesmo_autor("Godino J.D.", "Godino, Juan D.")
    assert fluxos._mesmo_autor("Batanero Bernabeu C.", "Batanero Bernabeu, Carmen")
    assert fluxos._mesmo_autor("Lopes, C.E.", "Lopes, Celi Espasandin")
    assert not fluxos._mesmo_autor("Lopes, C.E.", "Lopes, Maria")
    assert not fluxos._mesmo_autor("Silva A.", "Souza, A.")

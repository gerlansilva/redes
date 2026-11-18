from redes.loaders.base import DocumentoFonte
from redes.normaliza import autor_por_nome_completo


def test_nome_completo_so_quando_existe():
    com = DocumentoFonte(titulo="A", autores=["Lopes, C.E."],
                         autores_completos=["Lopes, Celi Espasandin"])
    sem = DocumentoFonte(titulo="B", autores=["Silva, A."])
    desalinhado = DocumentoFonte(titulo="C", autores=["X, Y.", "Z, W."],
                                 autores_completos=["X, Yuri"])
    assert autor_por_nome_completo([com, sem, desalinhado]) == 1
    assert com.autores == ["Lopes, Celi Espasandin"]
    assert sem.autores == ["Silva, A."]
    assert desalinhado.autores == ["X, Y.", "Z, W."]


def test_padrao_continua_curto(tmp_path):
    from redes.loaders import le_corpus
    arq = tmp_path / "c.csv"
    arq.write_text('Authors,Author full names,Title,Year,Source title,Cited by\n'
                   '"Lopes, C.E.","Lopes, Celi Espasandin",T,2020,J,1\n', encoding="utf-8")
    docs, _ = le_corpus(arq, "openalex")
    assert docs[0].autores == ["Lopes, C.E."]
    docs, _ = le_corpus(arq, "openalex", autor_por="nome-completo")
    assert docs[0].autores == ["Lopes, Celi Espasandin"]

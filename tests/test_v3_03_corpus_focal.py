"""Corpus de autor focal: países, instituições e leis ficam no modo avançado ou com aviso."""
from pathlib import Path

from redes import api, bibliometria
from redes.kb import ProjetoRedes


def test_descreve_projeto_marca_corpus_focal(projeto):
    d = api.descreve_projeto(Path(projeto))
    assert d["corpus"]["focal"] is True
    assert {a["nome"] for a in d["corpus"]["autores_focais"]} == {"Silva, A.", "Costa, B."}


def test_bibliometria_traz_corpus(projeto):
    with ProjetoRedes(projeto) as kb:
        dados = bibliometria.calcula(kb.conexao)
    assert dados["corpus"]["focal"] is True


def _motivos(r):
    return {i["rotulo"]: i["motivo"] for i in r["ignoradas"]}


def test_relatorio_completo_poe_paises_e_ies_no_modo_avancado(projeto):
    simples = api.gera_relatorio_completo({"projeto": str(projeto), "formato": "unico"})
    m = _motivos(simples)
    assert "pouco informativo para este corpus" in m["Colaboração entre países"]
    assert "pouco informativo para este corpus" in m["Colaboração entre instituições (IES)"]
    assert "Modo avançado" in m["Colaboração entre países"]
    avancado = api.gera_relatorio_completo({"projeto": str(projeto), "formato": "unico",
                                            "avancado": True})
    assert "pouco informativo" not in _motivos(avancado).get("Colaboração entre países", "")
    html = Path(api.CACHE / f"rel-{avancado['token']}" / "relatorio-completo.html").read_text(encoding="utf-8")
    assert "pouco informativo para este corpus" in html      # aviso nas leis

"""Evolução temática: tabela de continuidade e avisos por período na API."""
from redes import api
from redes.build import constroi
from redes.longitudinal import MEDIDAS_TEMPORAIS  # noqa: F401
from tests.conftest import docs_sinteticos


def _projeto(tmp_path):
    destino = tmp_path / "dados.redes"
    constroi(docs_sinteticos(), destino, [("2010–2012", 2010, 2012), ("2013–2015", 2013, 2015)])
    return destino


def test_longitudinal_devolve_transicoes_e_avisos_por_periodo(tmp_path):
    r = api.gera_longitudinal({"projeto": str(_projeto(tmp_path)), "unidade": "Words",
                               "matriz": "CoOccurrence"})
    assert len(r["transicoes"]) == 1
    t = r["transicoes"][0]
    assert (t["de"], t["para"]) == ("2010–2012", "2013–2015")
    assert set(t) >= {"continuam", "somem", "surgem"}
    assert len(t["continuam"]) + len(t["somem"]) >= 1 or t["surgem"]
    assert len(r["periodos_avisos"]) == 2
    for p in r["periodos_avisos"]:
        assert any(a["codigo"] == "periodo_pequeno" for a in p["avisos"])
    # os números do mapa seguem os mesmos de antes
    assert r["nos"] and "elos" in r and len(r["sobreposicao"]) == 2


def test_continuam_somem_surgem_sao_coerentes_com_o_mapa(tmp_path):
    from redes import longitudinal
    from redes.kb import ProjetoRedes
    caminho = _projeto(tmp_path)
    config = api._config({"unidade": "Words", "matriz": "CoOccurrence"})
    with ProjetoRedes(caminho) as kb:
        mapa = longitudinal.constroi(kb, config, kb.periodos())
    t = mapa.transicoes[0]
    origem = len(mapa.nos_do_periodo(0))
    destino = len(mapa.nos_do_periodo(1))
    assert len(t["continuam"]) + len(t["somem"]) == origem
    assert len(t["surgem"]) <= destino


def test_densidade_com_poucos_itens_nao_e_erro(projeto):
    d = api.descreve_projeto(__import__("pathlib").Path(projeto))
    r = api.analisa({"projeto": str(projeto), "unidade": "Authors", "periodo": d["periodos"][0]["id"]})
    assert r["densidade"] == {"itens": r["densidade"]["itens"], "minimo": 5, "disponivel": False}
    resposta = api.densidade_do_pedido({"token": r["token"]})      # 200 com aviso, não ErroApi
    assert resposta["svg"] is None and "Poucos itens" in resposta["aviso"]
    import pytest
    with pytest.raises(api.ErroApi):                               # o download continua exigindo o mapa
        api.densidade_do_pedido({"token": r["token"], "baixar": "1"})

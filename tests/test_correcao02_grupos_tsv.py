import csv

from redes.cli import main


def _le(caminho):
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.reader(f, delimiter="\t"))


def test_tsv_antigo_intacto_e_grupos_ao_lado(projeto, tmp_path):
    saida = tmp_path / "saida.tsv"
    assert main(["analisa", str(projeto), "--algoritmo", "Louvain", "--rede-min", "2",
                 "--saida", str(saida)]) == 0
    resumo = _le(saida)
    assert resumo[0][0] == "periodo" and len(resumo) == 2  # uma linha-resumo por período
    grupos = _le(tmp_path / "saida_grupos.tsv")
    assert grupos[0][:4] == ["periodo", "unidade", "grupo", "nome"]
    assert len(grupos) - 1 == int(resumo[1][resumo[0].index("grupos")])
    assert {"itens", "documentos", "centralidade", "densidade", "quadrante"} <= set(grupos[0])
    assert all(linha[-1] for linha in grupos[1:])

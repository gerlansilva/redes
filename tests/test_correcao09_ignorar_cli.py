import csv

from redes.cli import _lista_ignorar, main


def test_lista_ignorar():
    assert _lista_ignorar(["Lopes, C.E.; Silva A.", "x"]) == ("Lopes, C.E.", "Silva A.", "x")
    assert _lista_ignorar(None) == ()


def test_ignorar_remove_autor_da_rede(projeto, tmp_path):
    def nos(extra):
        saida = tmp_path / ("a%d.tsv" % len(extra))
        main(["analisa", str(projeto), "--unidade", "Authors", "--saida", str(saida), *extra])
        with open(saida, encoding="utf-8", newline="") as f:
            linhas = list(csv.DictReader(f, delimiter="\t"))
        return int(linhas[0]["itens_reduzidos"])

    assert nos([]) - nos(["--ignorar", "Silva A."]) == 1

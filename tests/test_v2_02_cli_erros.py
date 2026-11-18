"""Erros de uso da CLI viram mensagem curta (código 2), sem traceback e sem lixo no disco."""
import pytest

from redes import cli
from redes.cli import main


def _roda(capsys, *argv):
    codigo = main(list(argv))
    return codigo, capsys.readouterr().err


def test_entrada_inexistente(tmp_path, capsys):
    codigo, erro = _roda(capsys, "constroi", str(tmp_path / "nao.csv"),
                         "--saida", str(tmp_path / "p.redes"))
    assert codigo == 2 and "arquivo não encontrado" in erro
    assert not (tmp_path / "p.redes").exists()


def test_csv_sem_registros_nao_grava_projeto(tmp_path, capsys):
    lixo = tmp_path / "lixo.csv"
    lixo.write_text("coluna,outra\n1,2\n", encoding="utf-8")
    codigo, erro = _roda(capsys, "constroi", str(lixo), "--saida", str(tmp_path / "p.redes"))
    assert codigo == 2 and "nenhum registro" in erro
    assert not (tmp_path / "p.redes").exists()


def test_periodos_invalidos(tmp_path, capsys):
    csv = tmp_path / "c.csv"
    csv.write_text("Title,Authors,Year\nA,Silva A.,2010\n", encoding="utf-8")
    codigo, erro = _roda(capsys, "constroi", str(csv), "--formato", "csv",
                         "--periodos", "abc", "--saida", str(tmp_path / "p.redes"))
    assert codigo == 2 and "período inválido" in erro


def test_projeto_inexistente_nao_cria_arquivo(tmp_path, capsys):
    alvo = tmp_path / "fantasma.redes"
    codigo, erro = _roda(capsys, "analisa", str(alvo))
    assert codigo == 2 and "não encontrado" in erro
    assert not alvo.exists()


def test_arquivo_que_nao_e_projeto(tmp_path, capsys):
    falso = tmp_path / "falso.redes"
    falso.write_text("nada", encoding="utf-8")
    codigo, erro = _roda(capsys, "analisa", str(falso))
    assert codigo == 2 and "não é um projeto" in erro


def test_versao(capsys):
    with pytest.raises(SystemExit) as saida:
        main(["--version"])
    assert saida.value.code == 0
    assert "redes 0.1.1" in capsys.readouterr().out


def test_debug_devolve_traceback(tmp_path, monkeypatch):
    monkeypatch.setenv("REDES_DEBUG", "1")
    with pytest.raises(FileNotFoundError):
        main(["analisa", str(tmp_path / "x.redes")])

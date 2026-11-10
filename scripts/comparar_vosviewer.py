"""Compara as contagens do corpus com as que o VOSviewer apresenta.

Uso:
    python3 scripts/comparar_vosviewer.py ~/Downloads/batanero.csv

O script separa três coisas que costumam ser confundidas: citações brutas,
grafias distintas e itens depois da normalização do importador. As contagens
"redes" vêm do mesmo construtor usado na importação.
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scimatpy.build import Construtor
from scimatpy.loaders import detecta_formato
from scimatpy.loaders import openalex, scopus
from scimatpy.references import SEPARADOR_REFERENCIA, converte_referencia

CAMPOS = 6


def _campos(completa: str) -> list[str]:
    partes = [c.strip() for c in completa.split(", ", 5)]
    return partes + [""] * (CAMPOS - len(partes))


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", "", texto.lower()).strip()


def _documentos(caminho: Path):
    formato = detecta_formato(caminho)
    if formato == "openalex":
        return openalex.le(caminho)
    if formato == "scopus":
        return scopus.le(caminho)
    raise SystemExit(f"formato não suportado: {formato}")


def _citacoes(caminho: Path) -> list[str]:
    """Converte o campo References sem deduplicar entre documentos."""
    convertidas = []
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            for bruta in SEPARADOR_REFERENCIA.split(
                    (linha.get("References") or "").replace("\n", " ")):
                item = converte_referencia(bruta)
                if item:
                    convertidas.append(item)
    return convertidas


def compara(caminho: Path) -> dict:
    documentos = _documentos(caminho)
    citacoes = _citacoes(caminho)
    construtor = Construtor(documentos)
    construtor.importa()

    sem_titulo = [c for c in citacoes if not _campos(c)[5]]
    autores_individuais = {
        _norm(nome)
        for completa in citacoes
        for nome in _campos(completa)[0].split(";")
        if nome.strip()
    }
    sem_titulo_redes = sum(
        1 for referencia in construtor.referencias.values()
        if not _campos(referencia.completa)[5])
    sem_autor_redes = sum(
        1 for referencia in construtor.referencias.values()
        if referencia.autor.lower() == "sem autor")

    return {
        "documentos": len(documentos),
        "citacoes_brutas": len(citacoes),
        "referencias_exatas": len(set(citacoes)),
        "referencias_redes": len(construtor.referencias),
        "fontes_exatas": len({_campos(c)[2] for c in citacoes}),
        "fontes_redes": len(construtor.fontes),
        "grupos_fonte": len(construtor.agrupa_fontes()),
        "autores_lista_exatos": len({_campos(c)[0] for c in citacoes}),
        "autores_lista_redes": len(construtor.autores_ref),
        "grupos_autor_lista": len(construtor.agrupa_autores_de_referencia()),
        "autores_individuais": len(autores_individuais),
        "titulos": len({_norm(_campos(c)[5]) for c in citacoes if _campos(c)[5]}),
        "sem_titulo_brutas": len(sem_titulo),
        "sem_titulo_unicas": len({c for c in sem_titulo}),
        "sem_titulo_redes": sem_titulo_redes,
        "sem_autor": sum(1 for c in citacoes if _campos(c)[0].lower() == "sem autor"),
        "sem_autor_redes": sem_autor_redes,
    }


def principal() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("informe o arquivo do corpus")
    for chave, valor in compara(Path(sys.argv[1]).expanduser()).items():
        print(f"{chave}: {valor}")


if __name__ == "__main__":
    principal()

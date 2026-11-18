"""Exportações do redes.

Formatos de saída:

- grupos da base em XML;
- rede em Pajek (`.net`) e em GraphML;
- índices de desempenho em TSV;
- documentos do período em CSV;
- SVG das figuras, com conversão opcional para PNG quando existe um
  rasterizador instalado (``cairosvg``, ``rsvg-convert`` ou ``qlmanage``).
"""

from __future__ import annotations

import shutil
import subprocess
import xml.sax.saxutils as sax
from pathlib import Path


def _num(valor: float) -> str:
    return f"{valor:.6g}"


# ------------------------------------------------------------------- grupos XML


def grupos_xml(conexao) -> str:
    """XML dos grupos de autores, palavras, referências, autores de referência
    e fontes."""
    partes = ['<?xml version="1.0" encoding="UTF-8"?>', "<groups>"]

    def abre(tag: str) -> None:
        partes.append(f"  <{tag}>")

    def fecha(tag: str) -> None:
        partes.append(f"  </{tag}>")

    def grupo(nome: str, parada: bool, itens, tag_item: str, campos) -> None:
        partes.append(
            f'    <group name={sax.quoteattr(str(nome))} '
            f'stop="{str(bool(parada)).lower()}">')
        for item in itens:
            partes.append(f"      <{tag_item}>")
            for campo, valor in zip(campos, item):
                if valor is None:
                    continue
                partes.append(f"        <{campo}>{sax.escape(str(valor))}</{campo}>")
            partes.append(f"      </{tag_item}>")
        partes.append("    </group>")

    abre("authorGroups")
    for linha in conexao.execute(
            "SELECT idAuthorGroup, groupName, stopGroup FROM AuthorGroup "
            "ORDER BY idAuthorGroup"):
        membros = conexao.execute(
            "SELECT authorName, fullAuthorName FROM Author "
            "WHERE AuthorGroup_idAuthorGroup = ? ORDER BY idAuthor", (linha[0],))
        grupo(linha[1], linha[2], membros, "author",
              ("authorName", "fullAuthorName"))
    fecha("authorGroups")

    abre("wordGroups")
    for linha in conexao.execute(
            "SELECT idWordGroup, groupName, stopGroup FROM WordGroup "
            "ORDER BY idWordGroup"):
        membros = conexao.execute(
            "SELECT wordName FROM Word WHERE WordGroup_idWordGroup = ? "
            "ORDER BY idWord", (linha[0],))
        grupo(linha[1], linha[2], membros, "word", ("wordName",))
    fecha("wordGroups")

    abre("referenceGroups")
    for linha in conexao.execute(
            "SELECT idReferenceGroup, groupName, stopGroup FROM ReferenceGroup "
            "ORDER BY idReferenceGroup"):
        membros = conexao.execute(
            "SELECT fullReference FROM Reference "
            "WHERE ReferenceGroup_idReferenceGroup = ? ORDER BY idReference",
            (linha[0],))
        grupo(linha[1], linha[2], membros, "reference", ("fullReference",))
    fecha("referenceGroups")

    abre("authorReferenceGroups")
    for linha in conexao.execute(
            "SELECT idAuthorReferenceGroup, groupName, stopGroup "
            "FROM AuthorReferenceGroup ORDER BY idAuthorReferenceGroup"):
        membros = conexao.execute(
            "SELECT authorName FROM AuthorReference "
            "WHERE AuthorReferenceGroup_idAuthorReferenceGroup = ? "
            "ORDER BY idAuthorReference", (linha[0],))
        grupo(linha[1], linha[2], membros, "authorReference", ("authorName",))
    fecha("authorReferenceGroups")

    abre("referenceSourceGroups")
    for linha in conexao.execute(
            "SELECT idReferenceSourceGroup, groupName, stopGroup "
            "FROM ReferenceSourceGroup ORDER BY idReferenceSourceGroup"):
        membros = conexao.execute(
            "SELECT source FROM ReferenceSource "
            "WHERE ReferenceSourceGroup_idReferencesourceGroup = ? "
            "ORDER BY idReferenceSource", (linha[0],))
        grupo(linha[1], linha[2], membros, "referenceSource", ("source",))
    fecha("referenceSourceGroups")

    partes.append("</groups>")
    return "\n".join(partes) + "\n"


# ---------------------------------------------------------------------- rede


def pajek(rede, rotulos: dict[int, str]) -> str:
    """Rede no formato Pajek (`.net`), como lista de arestas."""
    ordem = list(rede.nos)
    indice = {no: posicao + 1 for posicao, no in enumerate(ordem)}
    linhas = ["*Vertices " + str(len(ordem))]
    for posicao, no in enumerate(ordem, start=1):
        linhas.append(f'{posicao} "{rotulos.get(no, str(no)).replace(chr(34), chr(39))}"')
    linhas.append("*Edges")
    for a, b, valor in rede.arestas():
        linhas.append(f"{indice[a]} {indice[b]} {_num(valor)}")
    return "\n".join(linhas) + "\n"


def graphml(rede, rotulos: dict[int, str], grupos: list | None = None) -> str:
    """Rede em GraphML, com o agrupamento de cada nó como atributo."""
    pertence: dict[int, int] = {}
    for selo, grupo in enumerate(grupos or [], start=1):
        for no in grupo.nos:
            pertence[no] = selo

    partes = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '  <key id="rotulo" for="node" attr.name="rotulo" attr.type="string"/>',
        '  <key id="grupo" for="node" attr.name="grupo" attr.type="int"/>',
        '  <key id="peso" for="edge" attr.name="peso" attr.type="double"/>',
        '  <graph id="rede" edgedefault="undirected">',
    ]
    for no in rede.nos:
        partes.append(
            f'    <node id="n{no}">'
            f'<data key="rotulo">{sax.escape(rotulos.get(no, str(no)))}</data>'
            f'<data key="grupo">{pertence.get(no, 0)}</data></node>')
    for a, b, valor in rede.arestas():
        partes.append(
            f'    <edge source="n{a}" target="n{b}">'
            f'<data key="peso">{_num(valor)}</data></edge>')
    partes += ["  </graph>", "</graphml>"]
    return "\n".join(partes) + "\n"


# --------------------------------------------------------------------- tabelas


def indices_tsv(resultado) -> str:
    """Uma linha por agrupamento e mapeador, com todos os índices calculados."""
    nomes = ["h", "g", "hg", "q2", "media", "soma", "minimo", "maximo", "documentos"]
    titulos = ["selo", "agrupamento", "mapeador"] + nomes
    linhas = ["\t".join(titulos)]
    for selo, grupo in enumerate(
            sorted(resultado.grupos,
                   key=lambda g: (-len(g.nos), g.rotulo or "")), start=1):
        for mapeador in resultado.configuracao.mapeadores:
            prefixo = f"{mapeador}:"
            valores = [str(int(grupo.medidas.get(prefixo + nome, 0)))
                       if nome in ("documentos", "h", "g", "hg", "q2")
                       else _num(grupo.medidas.get(prefixo + nome, 0.0))
                       for nome in nomes]
            linhas.append("\t".join(
                [str(selo), grupo.exibicao, mapeador] + valores))
    return "\n".join(linhas) + "\n"


# ------------------------------------------------------------------------ SVG


def converte_png(origem: Path, destino: Path, escala: float = 2.0) -> Path:
    """Converte um SVG em PNG usando o primeiro rasterizador disponível.

    Levanta ``RuntimeError`` quando não há nenhum. O redes não depende de
    bibliotecas gráficas: sem rasterizador, o SVG continua sendo a figura
    vetorial oficial.
    """
    try:
        import cairosvg  # type: ignore
    except ImportError:
        cairosvg = None

    if cairosvg is not None:
        cairosvg.svg2png(url=str(origem), write_to=str(destino), scale=escala)
        return destino

    rsvg = shutil.which("rsvg-convert")
    if rsvg:
        subprocess.run([rsvg, "-z", str(escala), "-o", str(destino), str(origem)],
                       check=True, capture_output=True)
        return destino

    qlmanage = shutil.which("qlmanage")
    if qlmanage:
        saida = destino.parent
        subprocess.run([qlmanage, "-t", "-s", "1600", "-o", str(saida), str(origem)],
                       check=True, capture_output=True)
        gerado = saida / (origem.name + ".png")
        if gerado.exists():
            gerado.replace(destino)
            return destino

    raise RuntimeError(
        "nenhum conversor de SVG para PNG disponível "
        "(instale cairosvg ou rsvg-convert)")

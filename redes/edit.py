"""Edição da base de conhecimento do projeto `.redes`.

Cobre as operações que mudam o conteúdo sem exigir outra ferramenta:

- períodos: criar, renomear, excluir e redistribuir as datas de publicação;
- grupos: renomear, marcar/desmarcar como grupo de parada e juntar dois grupos
  do mesmo tipo (o destino absorve os itens e o grupo de origem é removido);
- substituição global de uma grafia por outra, dentro de um tipo de item;
- desfazer: cada gravação guarda uma cópia do arquivo antes da mudança, e o
  comando ``desfazer`` restaura a última cópia.

Os contadores desnormalizados (`itemsCount`, contagens de documentos etc.) são
mantidos pelos gatilhos do esquema, mas as operações que removem linhas em
massa recalculam os contadores afetados explicitamente, porque os gatilhos do
esquema só cobrem inserções e atualizações.
"""

from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path

from .projeto import EXTENSAO, e_projeto
from .texto import termo_legivel

TIPOS = {
    "palavra": ("Word", "WordGroup", "idWord", "idWordGroup",
                "WordGroup_idWordGroup", "wordName"),
    "autor": ("Author", "AuthorGroup", "idAuthor", "idAuthorGroup",
              "AuthorGroup_idAuthorGroup", "authorName"),
    "referencia": ("Reference", "ReferenceGroup", "idReference",
                   "idReferenceGroup", "ReferenceGroup_idReferenceGroup",
                   "fullReference"),
    "autor_referencia": ("AuthorReference", "AuthorReferenceGroup",
                         "idAuthorReference", "idAuthorReferenceGroup",
                         "AuthorReferenceGroup_idAuthorReferenceGroup",
                         "authorName"),
    "pais": ("Country", "CountryGroup", "idCountry", "idCountryGroup",
             "CountryGroup_idCountryGroup", "countryName"),
    "fonte": ("ReferenceSource", "ReferenceSourceGroup", "idReferenceSource",
              "idReferenceSourceGroup",
              "ReferenceSourceGroup_idReferencesourceGroup", "source"),
}


def _copia_de_seguranca(caminho: Path) -> Path:
    pasta = caminho.parent / f".{caminho.name}.desfazer"
    pasta.mkdir(exist_ok=True)
    destino = pasta / f"{int(time.time() * 1000)}{EXTENSAO}"
    shutil.copy2(caminho, destino)
    copias = sorted(copia for copia in pasta.glob("*") if e_projeto(copia))
    for antiga in copias[:-10]:
        antiga.unlink()
    return destino


def _abre(caminho: str | Path) -> tuple[sqlite3.Connection, Path]:
    arquivo = Path(caminho).expanduser().resolve()
    if not arquivo.is_file():
        raise ValueError(f"projeto não encontrado: {arquivo}")
    conexao = sqlite3.connect(str(arquivo))
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON;")
    return conexao, arquivo


# ------------------------------------------------------------------ resumo


def resume(caminho: str | Path) -> dict:
    conexao, arquivo = _abre(caminho)
    try:
        periodos = []
        for linha in conexao.execute(
                "SELECT * FROM Period ORDER BY position"):
            anos = conexao.execute(
                "SELECT MIN(CAST(SUBSTR(pu.year, 1, 4) AS INTEGER)), "
                "MAX(CAST(SUBSTR(pu.year, 1, 4) AS INTEGER)) "
                "FROM PublishDate_Period pp, PublishDate pu "
                "WHERE pp.Period_idPeriod = ? AND "
                "pp.PublishDate_idPublishDate = pu.idPublishDate",
                (linha["idPeriod"],)).fetchone()
            periodos.append({
                "id": linha["idPeriod"],
                "nome": linha["name"],
                "posicao": linha["position"],
                "documentos": linha["period_documentsCount"],
                "datas": linha["period_publishDatesCount"],
                "inicio": anos[0],
                "fim": anos[1],
            })
        grupos = {}
        for chave, (_, tabela, _, coluna, _, _) in TIPOS.items():
            contagem_documentos = {
                "WordGroup": "wordGroup_documentsCount",
                "AuthorGroup": "authorGroup_documentsCount",
                "ReferenceGroup": "referenceGroup_documentsCount",
                "AuthorReferenceGroup": "authorReferenceGroup_documentsCount",
                "ReferenceSourceGroup": "referenceSourceGroup_documentsCount",
                "CountryGroup": "countryGroup_documentsCount",
            }[tabela]
            grupos[chave] = [
                {"id": linha["id"], "nome": linha["nome"],
                 # Só a exibição muda; `nome` é o dado guardado (e o que se renomeia).
                 "exibicao": (termo_legivel(linha["nome"]) if chave == "palavra"
                              else linha["nome"]),
                 "parada": bool(linha["parada"]),
                 "itens": linha["itens"], "documentos": linha["documentos"]}
                for linha in conexao.execute(
                    f"SELECT g.{coluna} AS id, g.groupName AS nome, "
                    f"g.stopGroup AS parada, g.itemsCount AS itens, "
                    f"g.{contagem_documentos} AS documentos "
                    f"FROM {tabela} g ORDER BY g.groupName")
            ]
        return {
            "caminho": str(arquivo),
            "documentos": conexao.execute(
                "SELECT COUNT(*) FROM Document").fetchone()[0],
            "periodos": periodos,
            "grupos": grupos,
            "desfazer": len(list(
                (arquivo.parent / f".{arquivo.name}.desfazer").glob("*"))),
        }
    finally:
        conexao.close()


# ---------------------------------------------------------------- períodos


def cria_periodo(caminho, nome: str, inicio: int, fim: int) -> dict:
    conexao, arquivo = _abre(caminho)
    try:
        _copia_de_seguranca(arquivo)
        posicao = conexao.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM Period").fetchone()[0]
        cursor = conexao.execute(
            "INSERT INTO Period(name, position) VALUES (?, ?)", (nome, posicao))
        periodo_id = cursor.lastrowid
        _liga_datas(conexao, periodo_id, inicio, fim)
        _recalcula_periodo(conexao, periodo_id)
        conexao.commit()
    finally:
        conexao.close()
    return resume(arquivo)


def sugere_periodos(caminho, quantidade: int | None = None) -> dict:
    """Refaz os períodos do projeto a partir dos anos dos documentos."""
    from .build import sugere_periodos as divide

    conexao, arquivo = _abre(caminho)
    try:
        anos = []
        for (ano,) in conexao.execute(
                "SELECT p.year FROM Document d, PublishDate p "
                "WHERE p.idPublishDate = d.PublishDate_idPublishDate"):
            try:
                anos.append(int(str(ano)[:4]))
            except (TypeError, ValueError):
                pass
        if not anos:
            raise ValueError("os documentos não têm ano de publicação")
        faixas = divide(anos, quantidade)
        _copia_de_seguranca(arquivo)
        conexao.execute("DELETE FROM PublishDate_Period")
        conexao.execute("DELETE FROM Period")
        for posicao, (nome, inicio, fim) in enumerate(faixas, start=1):
            periodo_id = conexao.execute(
                "INSERT INTO Period(name, position) VALUES (?, ?)",
                (nome, posicao)).lastrowid
            _liga_datas(conexao, periodo_id, inicio, fim)
            _recalcula_periodo(conexao, periodo_id)
        conexao.commit()
    finally:
        conexao.close()
    return resume(arquivo)


def renomeia_periodo(caminho, periodo_id: int, nome: str) -> dict:
    conexao, arquivo = _abre(caminho)
    try:
        _copia_de_seguranca(arquivo)
        conexao.execute("UPDATE Period SET name = ? WHERE idPeriod = ?",
                        (nome, periodo_id))
        conexao.commit()
    finally:
        conexao.close()
    return resume(arquivo)


def redistribui_periodo(caminho, periodo_id: int, inicio: int, fim: int) -> dict:
    conexao, arquivo = _abre(caminho)
    try:
        _copia_de_seguranca(arquivo)
        conexao.execute("DELETE FROM PublishDate_Period WHERE Period_idPeriod = ?",
                        (periodo_id,))
        _liga_datas(conexao, periodo_id, inicio, fim)
        _recalcula_periodo(conexao, periodo_id)
        conexao.commit()
    finally:
        conexao.close()
    return resume(arquivo)


def exclui_periodo(caminho, periodo_id: int) -> dict:
    conexao, arquivo = _abre(caminho)
    try:
        _copia_de_seguranca(arquivo)
        conexao.execute("DELETE FROM PublishDate_Period WHERE Period_idPeriod = ?",
                        (periodo_id,))
        conexao.execute("DELETE FROM Period WHERE idPeriod = ?", (periodo_id,))
        for posicao, linha in enumerate(conexao.execute(
                "SELECT idPeriod FROM Period ORDER BY position"), start=1):
            conexao.execute("UPDATE Period SET position = ? WHERE idPeriod = ?",
                            (posicao, linha[0]))
        conexao.commit()
    finally:
        conexao.close()
    return resume(arquivo)


def _liga_datas(conexao, periodo_id: int, inicio: int, fim: int) -> None:
    for linha in conexao.execute(
            "SELECT idPublishDate, year FROM PublishDate"):
        try:
            ano = int(str(linha["year"]).strip()[:4])
        except ValueError:
            continue
        if inicio <= ano <= fim:
            conexao.execute(
                "INSERT OR IGNORE INTO PublishDate_Period"
                "(PublishDate_idPublishDate, Period_idPeriod) VALUES (?, ?)",
                (linha["idPublishDate"], periodo_id))


def _recalcula_periodo(conexao, periodo_id: int) -> None:
    conexao.execute(
        "UPDATE Period SET period_publishDatesCount = ("
        " SELECT COUNT(*) FROM PublishDate_Period WHERE Period_idPeriod = ?),"
        " period_documentsCount = ("
        " SELECT COUNT(*) FROM Document d, PublishDate_Period pp"
        " WHERE pp.Period_idPeriod = ?"
        " AND pp.PublishDate_idPublishDate = d.PublishDate_idPublishDate)"
        " WHERE idPeriod = ?", (periodo_id, periodo_id, periodo_id))


# ------------------------------------------------------------------ grupos


def renomeia_grupo(caminho, tipo: str, grupo_id: int, nome: str) -> dict:
    tabela, coluna = _tabela_grupo(tipo)
    conexao, arquivo = _abre(caminho)
    try:
        _copia_de_seguranca(arquivo)
        conexao.execute(f"UPDATE {tabela} SET groupName = ? WHERE {coluna} = ?",
                        (nome, grupo_id))
        conexao.commit()
    finally:
        conexao.close()
    return resume(arquivo)


def marca_parada(caminho, tipo: str, grupo_id: int, parada: bool) -> dict:
    tabela, coluna = _tabela_grupo(tipo)
    conexao, arquivo = _abre(caminho)
    try:
        _copia_de_seguranca(arquivo)
        conexao.execute(
            f"UPDATE {tabela} SET stopGroup = ? WHERE {coluna} = ?",
            (1 if parada else 0, grupo_id))
        conexao.commit()
    finally:
        conexao.close()
    return resume(arquivo)


def _junta(conexao, tipo: str, origem: int, destino: int) -> None:
    tabela, coluna_grupo = _tabela_grupo(tipo)
    item, _, _, _, coluna_fk, _ = TIPOS[tipo]
    conexao.execute(
        f"UPDATE {item} SET {coluna_fk} = ? WHERE {coluna_fk} = ?",
        (destino, origem))
    conexao.execute(f"DELETE FROM {tabela} WHERE {coluna_grupo} = ?", (origem,))
    _recalcula_grupo(conexao, tipo, destino)


def junta_grupos(caminho, tipo: str, origem: int, destino: int) -> dict:
    """Move os itens do grupo de origem para o destino e remove a origem."""
    _tabela_grupo(tipo)
    conexao, arquivo = _abre(caminho)
    try:
        _copia_de_seguranca(arquivo)
        _junta(conexao, tipo, origem, destino)
        conexao.commit()
    finally:
        conexao.close()
    return resume(arquivo)


def agrupa_sugestoes(caminho, tipo: str, agrupamentos: list[dict]) -> dict:
    """Aplica de uma vez os agrupamentos sugeridos e confirmados.

    Cada agrupamento é `{canonico, membros}`: em palavra, autor e país os
    membros são ids de grupos, que se fundem no grupo que ficará com a grafia
    final; em `ies` os membros são nomes de instituição e viram apelidos da
    grafia final. Uma única cópia de segurança cobre o lote inteiro.
    """
    from . import sugestoes

    if tipo != "ies":
        _tabela_grupo(tipo)
    if not agrupamentos:
        raise ValueError("nenhum agrupamento escolhido")
    conexao, arquivo = _abre(caminho)
    try:
        _copia_de_seguranca(arquivo)
        if tipo == "pais":
            # Projetos antigos tinham índice único: um país por grupo. Agrupar exige índice comum.
            conexao.execute("DROP INDEX IF EXISTS fk_Country_CountryGroup")
            conexao.execute("CREATE INDEX IF NOT EXISTS fk_Country_CountryGroup "
                            "ON Country(CountryGroup_idCountryGroup)")
        if tipo == "ies":
            sugestoes.grava_ies(conexao, agrupamentos)
        else:
            for agrupamento in agrupamentos:
                _agrupa_um(conexao, tipo, agrupamento)
        conexao.commit()
    finally:
        conexao.close()
    return resume(arquivo)


def _agrupa_um(conexao, tipo: str, agrupamento: dict) -> None:
    tabela, coluna = _tabela_grupo(tipo)
    canonico = (agrupamento.get("canonico") or "").strip()
    if not canonico:
        raise ValueError("a grafia final não pode ser vazia")
    ids = [int(m) for m in agrupamento.get("membros", [])]
    existentes = {linha[0]: linha for linha in conexao.execute(
        f"SELECT {coluna}, groupName, stopGroup FROM {tabela} WHERE {coluna} IN "
        f"({','.join('?' * len(ids))})", ids)} if ids else {}
    if any(linha["stopGroup"] for linha in existentes.values()):
        raise ValueError("grupos de parada não podem ser agrupados com outros")
    # Se a grafia final já é o nome de outro grupo da base, ele entra e vira o destino.
    outro = conexao.execute(
        f"SELECT {coluna} FROM {tabela} WHERE groupName = ?", (canonico,)).fetchone()
    if outro is not None and outro[0] not in existentes:
        existentes[outro[0]] = conexao.execute(
            f"SELECT {coluna}, groupName, stopGroup FROM {tabela} WHERE {coluna} = ?",
            (outro[0],)).fetchone()
    if len(existentes) < 2:
        raise ValueError("escolha ao menos dois itens para agrupar")
    destino = next((i for i, linha in existentes.items() if linha["groupName"] == canonico), None)
    if destino is None:
        destino = max(existentes, key=lambda i: conexao.execute(
            f"SELECT itemsCount FROM {tabela} WHERE {coluna} = ?", (i,)).fetchone()[0] or 0)
    for origem in list(existentes):
        if origem != destino:
            _junta(conexao, tipo, origem, destino)
    conexao.execute(f"UPDATE {tabela} SET groupName = ? WHERE {coluna} = ?", (canonico, destino))


def _tabela_grupo(tipo: str) -> tuple[str, str]:
    if tipo not in TIPOS:
        raise ValueError(f"tipo de grupo inválido: {tipo}")
    _, tabela, _, coluna, _, _ = TIPOS[tipo]
    return tabela, coluna


def _recalcula_grupo(conexao, tipo: str, grupo_id: int) -> None:
    item, tabela, chave, coluna_grupo, coluna_item, _ = TIPOS[tipo]
    documentos = {
        "WordGroup": ("Document_Word", "Document_idDocument", "Word_idWord"),
        "AuthorGroup": ("Document_Author", "Document_idDocument", "Author_idAuthor"),
        "ReferenceGroup": ("Document_Reference", "Document_idDocument",
                           "Reference_idReference"),
        "CountryGroup": ("Document_Country", "Document_idDocument", "Country_idCountry"),
    }
    if tabela in documentos:
        ligacao, doc, alvo = documentos[tabela]
        total = conexao.execute(
            f"SELECT COUNT(DISTINCT l.{doc}) FROM {ligacao} l, {item} i "
            f"WHERE i.{coluna_item} = ? AND i.{chave} = l.{alvo}",
            (grupo_id,)).fetchone()[0]
    else:
        total = conexao.execute(
            f"SELECT COUNT(*) FROM {item} WHERE {coluna_item} = ?",
            (grupo_id,)).fetchone()[0]
    conexao.execute(
        f"UPDATE {tabela} SET itemsCount = (SELECT COUNT(*) FROM {item} "
        f"WHERE {coluna_item} = ?) WHERE {coluna_grupo} = ?", (grupo_id, grupo_id))
    coluna_contagem = {
        "WordGroup": "wordGroup_documentsCount",
        "AuthorGroup": "authorGroup_documentsCount",
        "ReferenceGroup": "referenceGroup_documentsCount",
        "AuthorReferenceGroup": "authorReferenceGroup_documentsCount",
        "ReferenceSourceGroup": "referenceSourceGroup_documentsCount",
        "CountryGroup": "countryGroup_documentsCount",
    }[tabela]
    conexao.execute(
        f"UPDATE {tabela} SET {coluna_contagem} = ? WHERE {coluna_grupo} = ?",
        (total, grupo_id))


# --------------------------------------------------------- substituição global


def substitui(caminho, tipo: str, de: str, para: str) -> dict:
    """Troca uma grafia por outra; se a nova já existir, funde os dois itens."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo de grupo inválido: {tipo}")
    if not (para or "").strip():
        raise ValueError("a grafia nova não pode ser vazia")

    item, _, chave, coluna_grupo, coluna_item, nome = TIPOS[tipo]
    conexao, arquivo = _abre(caminho)
    try:
        antigos = conexao.execute(
            f"SELECT {chave} FROM {item} WHERE {nome} = ?", (de,)).fetchall()
        if not antigos:
            raise ValueError(f"grafia não encontrada: {de}")
        if de == para:
            return resume(arquivo)

        _copia_de_seguranca(arquivo)
        for antigo in antigos:
            grupo = conexao.execute(
                f"SELECT {coluna_item} FROM {item} WHERE {chave} = ?",
                (antigo[0],)).fetchone()[0]
            novo = conexao.execute(
                f"SELECT {chave}, {coluna_item} FROM {item} WHERE {nome} = ?",
                (para,)).fetchone()
            if novo is None:
                conexao.execute(
                    f"UPDATE {item} SET {nome} = ? WHERE {chave} = ?",
                    (para, antigo[0]))
            else:
                _funde(conexao, tipo, antigo[0], novo[0])
                conexao.execute(f"DELETE FROM {item} WHERE {chave} = ?",
                                (antigo[0],))
                _recalcula_grupo(conexao, tipo, novo[1])
            _ajusta_grupo(conexao, tipo, grupo, para)
        conexao.commit()
    finally:
        conexao.close()
    return resume(arquivo)


def _ajusta_grupo(conexao, tipo: str, grupo_id, novo_nome: str) -> None:
    """Depois da troca, renomeia ou remove o grupo afetado.

    Um grupo de um único item acompanha a grafia nova; um grupo que ficou
    vazio é removido, exceto quando é grupo de parada (``Sem autor``,
    ``Sem fonte``), que são mantidos de propósito.
    """
    if grupo_id is None:
        return
    item, tabela, chave, coluna_grupo, coluna_item, nome = TIPOS[tipo]
    linha = conexao.execute(
        f"SELECT groupName, stopGroup FROM {tabela} WHERE {coluna_grupo} = ?",
        (grupo_id,)).fetchone()
    if linha is None:
        return
    itens = conexao.execute(
        f"SELECT COUNT(*) FROM {item} WHERE {coluna_item} = ?",
        (grupo_id,)).fetchone()[0]
    if itens == 0:
        if not linha["stopGroup"]:
            conexao.execute(
                f"DELETE FROM {tabela} WHERE {coluna_grupo} = ?", (grupo_id,))
        return
    if linha["stopGroup"] or itens != 1:
        return
    unico = conexao.execute(
        f"SELECT {nome} FROM {item} WHERE {coluna_item} = ?",
        (grupo_id,)).fetchone()[0]
    if unico == linha["groupName"]:
        return
    try:
        conexao.execute(
            f"UPDATE {tabela} SET groupName = ? WHERE {coluna_grupo} = ?",
            (unico, grupo_id))
    except sqlite3.IntegrityError:
        # Outro grupo já usa esse nome; o grupo antigo fica como está.
        pass


def _funde(conexao, tipo: str, origem: int, destino: int) -> None:
    """Move os vínculos do item de origem para o destino, sem duplicar."""
    if tipo == "palavra":
        conexao.execute(
            "INSERT OR IGNORE INTO Document_Word(Document_idDocument, Word_idWord, "
            "isAuthorWord, isSourceWord, isAddedWord) "
            "SELECT Document_idDocument, ?, isAuthorWord, isSourceWord, isAddedWord "
            "FROM Document_Word WHERE Word_idWord = ?", (destino, origem))
        conexao.execute(
            "UPDATE Document_Word SET "
            "isAuthorWord = MAX(isAuthorWord, (SELECT MAX(isAuthorWord) FROM "
            "Document_Word WHERE Word_idWord = ?)), "
            "isSourceWord = MAX(isSourceWord, (SELECT MAX(isSourceWord) FROM "
            "Document_Word WHERE Word_idWord = ?)), "
            "isAddedWord = MAX(isAddedWord, (SELECT MAX(isAddedWord) FROM "
            "Document_Word WHERE Word_idWord = ?)) "
            "WHERE Word_idWord = ?", (origem, origem, origem, destino))
        conexao.execute("DELETE FROM Document_Word WHERE Word_idWord = ?", (origem,))
    elif tipo == "autor":
        conexao.execute(
            "INSERT OR IGNORE INTO Document_Author(Author_idAuthor, "
            "Document_idDocument, position) "
            "SELECT ?, Document_idDocument, position FROM Document_Author "
            "WHERE Author_idAuthor = ?", (destino, origem))
        conexao.execute("DELETE FROM Document_Author WHERE Author_idAuthor = ?",
                        (origem,))
    elif tipo == "referencia":
        conexao.execute(
            "INSERT OR IGNORE INTO Document_Reference(Reference_idReference, "
            "Document_idDocument) SELECT ?, Document_idDocument "
            "FROM Document_Reference WHERE Reference_idReference = ?",
            (destino, origem))
        conexao.execute(
            "DELETE FROM Document_Reference WHERE Reference_idReference = ?",
            (origem,))
    elif tipo == "fonte":
        conexao.execute(
            "UPDATE Reference SET ReferenceSource_idReferenceSource = ? "
            "WHERE ReferenceSource_idReferenceSource = ?", (destino, origem))
    elif tipo == "autor_referencia":
        conexao.execute(
            "INSERT OR IGNORE INTO AuthorReference_Reference("
            "AuthorReference_idAuthorReference, Reference_idReference, position) "
            "SELECT ?, Reference_idReference, position FROM "
            "AuthorReference_Reference WHERE AuthorReference_idAuthorReference = ?",
            (destino, origem))
        conexao.execute(
            "UPDATE AuthorReference SET Author_idAuthor = ("
            " SELECT Author_idAuthor FROM AuthorReference WHERE "
            "idAuthorReference = ?) WHERE idAuthorReference = ? AND "
            "Author_idAuthor IS NULL", (origem, destino))
        conexao.execute(
            "DELETE FROM AuthorReference_Reference "
            "WHERE AuthorReference_idAuthorReference = ?", (origem,))


def desfaz(caminho) -> dict:
    conexao, arquivo = _abre(caminho)
    conexao.close()
    pasta = arquivo.parent / f".{arquivo.name}.desfazer"
    copias = (sorted(copia for copia in pasta.glob("*") if e_projeto(copia))
              if pasta.exists() else [])
    if not copias:
        raise ValueError("nada para desfazer")
    restaura = copias[-1]
    shutil.copy2(restaura, arquivo)
    restaura.unlink()
    return resume(arquivo)

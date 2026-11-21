"""Leitura de um projeto .redes (SQLite) para o modelo do redes.

A ordem de leitura importa: a ordem dos documentos e dos itens determina os
identificadores dos nós e, portanto, o desempate dos algoritmos de
agrupamento.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .dataset import Dataset

UNIDADES = ("Words", "Authors", "References", "AuthorsReference",
            "ReferenceSources", "Countries", "Institutions")

_SQL_PERIODOS = "SELECT * FROM Period ORDER BY position ASC;"

_SQL_PUBLISHDATES = (
    "SELECT pu.* FROM PublishDate_Period pdp, PublishDate pu "
    "WHERE pdp.Period_idPeriod = ? AND pdp.PublishDate_idPublishDate = pu.idPublishDate;"
)

_SQL_DOCUMENTOS = (
    "SELECT d.* FROM Document d, PublishDate p "
    "WHERE p.idPublishDate = ? AND p.idPublishDate = d.PublishDate_idPublishDate;"
)

_SQL_PALAVRAS_DOCUMENTO = (
    "SELECT w.*, dw.isAuthorWord, dw.isSourceWord, dw.isAddedWord "
    "FROM Document_Word dw, Word w "
    "WHERE dw.Document_idDocument = ? AND dw.Word_idWord = w.idWord;"
)

_SQL_AUTORES = (
    "SELECT a.* FROM Document_Author da, Author a "
    "WHERE da.Document_idDocument = ? AND da.Author_idAuthor = a.idAuthor "
    "ORDER BY da.position ASC;"
)

_SQL_REFERENCIAS = (
    "SELECT r.* FROM Document_Reference dr, Reference r "
    "WHERE dr.Document_idDocument = ? AND dr.Reference_idReference = r.idReference;"
)

_SQL_AUTORES_DA_REFERENCIA = (
    "SELECT r.*, ar.*, arr.position "
    "FROM AuthorReference_Reference arr, AuthorReference ar, Reference r "
    "WHERE r.idReference = ? AND r.idReference = arr.Reference_idReference "
    "AND arr.AuthorReference_idAuthorReference = ar.idAuthorReference;"
)

_SQL_PAISES = (
    "SELECT c.* FROM Document_Country dc, Country c "
    "WHERE dc.Document_idDocument = ? AND dc.Country_idCountry = c.idCountry;"
)


@dataclass
class Periodo:
    id: int
    nome: str
    posicao: int


class ProjetoRedes:
    """Acesso somente leitura ao banco de um projeto `.redes`."""

    def __init__(self, caminho: str | Path) -> None:
        self.caminho = str(caminho)
        # Sem esta checagem o sqlite cria um arquivo vazio no lugar do projeto.
        if not Path(self.caminho).is_file():
            raise FileNotFoundError(f"Projeto não encontrado: {self.caminho}")
        self.conexao = sqlite3.connect(self.caminho)
        self.conexao.row_factory = sqlite3.Row
        try:
            self.conexao.execute("SELECT 1 FROM Period LIMIT 1;")
        except sqlite3.DatabaseError:
            self.conexao.close()
            raise ValueError(
                f"{self.caminho} não é um projeto do Redes (.redes) válido.") from None
        self._grupos: dict[str, dict[int, tuple[str, bool]]] = {}
        self._ies = None

    def _grupo(self, tabela: str, coluna: str, grupo: int) -> tuple[str, bool] | None:
        """Nome e marca de parada de um agrupamento, com cache por tabela."""
        if tabela not in self._grupos:
            self._grupos[tabela] = {
                linha[0]: (linha[1], bool(linha[2]))
                for linha in self.conexao.execute(
                    f"SELECT {coluna}, groupName, stopGroup FROM {tabela};")
            }
        return self._grupos[tabela].get(grupo)

    def fecha(self) -> None:
        self.conexao.close()

    def __enter__(self) -> "ProjetoRedes":
        return self

    def __exit__(self, *_) -> None:
        self.fecha()

    # ---------------------------------------------------------------- períodos

    def periodos(self) -> list[Periodo]:
        linhas = self.conexao.execute(_SQL_PERIODOS).fetchall()
        return [Periodo(linha["idPeriod"], linha["name"], linha["position"]) for linha in linhas]

    def titulos(self, ids) -> dict[int, str]:
        """Títulos dos documentos pedidos, para rotular redes de acoplamento."""
        lista = list(ids)
        if not lista:
            return {}
        marcas = ",".join("?" * len(lista))
        linhas = self.conexao.execute(
            f"SELECT idDocument, title FROM Document WHERE idDocument IN ({marcas})",
            lista).fetchall()
        return {linha["idDocument"]: (linha["title"] or f"Documento {linha['idDocument']}")
                for linha in linhas}

    def _publish_dates(self, periodo_id: int) -> list[int]:
        return [linha["idPublishDate"] for linha in
                self.conexao.execute(_SQL_PUBLISHDATES, (periodo_id,))]

    def _documentos(self, publish_date_id: int) -> list[sqlite3.Row]:
        return self.conexao.execute(_SQL_DOCUMENTOS, (publish_date_id,)).fetchall()

    # ------------------------------------------------------------ construção

    def _documentos_do_corpus(self) -> list[sqlite3.Row]:
        """Todos os documentos do projeto, inclusive os que não têm data."""
        documentos: list[sqlite3.Row] = []
        for publish_date_id in [linha[0] for linha in self.conexao.execute(
                "SELECT idPublishDate FROM PublishDate ORDER BY idPublishDate")]:
            documentos.extend(self._documentos(publish_date_id))
        documentos.extend(self.conexao.execute(
            "SELECT * FROM Document WHERE PublishDate_idPublishDate IS NULL "
            "ORDER BY idDocument").fetchall())
        return documentos

    def dataset(self, unidade: str, periodo_id: int | None = None,
                palavras: tuple[str, ...] = ("autor", "fonte")) -> Dataset:
        """Constrói o conjunto documento × item de uma unidade e de um período.

        `periodo_id=None` usa o corpus completo (todos os períodos). `palavras`
        escolhe as origens usadas quando a unidade é ``Words``, como os três
        seletores de `AnalysisConfiguration`: palavras do autor, da fonte e
        adicionadas. Quando nenhuma é marcada, entram todas.
        """
        if unidade not in UNIDADES:
            raise ValueError(f"unidade desconhecida: {unidade}")

        construtor = getattr(self, f"_unidade_{unidade}")
        ds = Dataset()
        vistos: set[int] = set()
        if periodo_id is None:
            documentos = self._documentos_do_corpus()
        else:
            documentos = [documento
                          for publish_date_id in self._publish_dates(periodo_id)
                          for documento in self._documentos(publish_date_id)]
        for documento in documentos:
            doc_id = documento["idDocument"]
            if doc_id in vistos:
                continue
            vistos.add(doc_id)
            ds.adiciona_documento(doc_id, documento["citationsCount"] or 0)
            if unidade == "Words":
                self._unidade_Words(ds, doc_id, palavras)
            else:
                construtor(ds, doc_id)
        return ds

    def _unidade_Words(self, ds: Dataset, doc_id: int,
                       palavras: tuple[str, ...] = ("autor", "fonte")) -> None:
        colunas = {"autor": "isAuthorWord", "fonte": "isSourceWord",
                   "adicionada": "isAddedWord"}
        ativas = [colunas[origem] for origem in palavras if origem in colunas]
        for linha in self.conexao.execute(_SQL_PALAVRAS_DOCUMENTO, (doc_id,)):
            if ativas and not any(linha[coluna] for coluna in ativas):
                continue
            grupo = linha["WordGroup_idWordGroup"]
            if grupo is None:
                continue
            dados = self._grupo("WordGroup", "idWordGroup", grupo)
            if dados is None or dados[1]:
                continue
            ds.adiciona_item_ao_documento(doc_id, grupo, dados[0])

    def _unidade_Authors(self, ds: Dataset, doc_id: int) -> None:
        for linha in self.conexao.execute(_SQL_AUTORES, (doc_id,)):
            grupo = linha["AuthorGroup_idAuthorGroup"]
            if grupo is None:
                continue
            dados = self._grupo("AuthorGroup", "idAuthorGroup", grupo)
            if dados is None or dados[1]:
                continue
            ds.adiciona_item_ao_documento(doc_id, grupo, dados[0])

    def _unidade_Countries(self, ds: Dataset, doc_id: int) -> None:
        try:
            linhas = self.conexao.execute(_SQL_PAISES, (doc_id,)).fetchall()
        except sqlite3.OperationalError:
            # Projetos antigos, gravados antes da unidade Países, não têm as
            # tabelas Country/Document_Country.
            return
        for linha in linhas:
            grupo = linha["CountryGroup_idCountryGroup"]
            if grupo is None:
                continue
            dados = self._grupo("CountryGroup", "idCountryGroup", grupo)
            if dados is None or dados[1]:
                continue
            ds.adiciona_item_ao_documento(doc_id, grupo, dados[0])

    def indice_ies(self):
        """Instituições do projeto com as variantes unidas (calculado uma vez)."""
        if self._ies is None:
            from .ies import indice_de_ies
            self._ies = indice_de_ies(self.conexao)
        return self._ies

    def _unidade_Institutions(self, ds: Dataset, doc_id: int) -> None:
        indice = self.indice_ies()
        for ies in indice.por_documento.get(doc_id, ()):
            ds.adiciona_item_ao_documento(doc_id, ies, indice.nomes[ies])

    def _unidade_References(self, ds: Dataset, doc_id: int) -> None:
        for linha in self.conexao.execute(_SQL_REFERENCIAS, (doc_id,)):
            grupo = linha["ReferenceGroup_idReferenceGroup"]
            if grupo is None:
                continue
            dados = self._grupo("ReferenceGroup", "idReferenceGroup", grupo)
            if dados is None or dados[1]:
                continue
            ds.adiciona_item_ao_documento(doc_id, grupo, dados[0])

    def _unidade_AuthorsReference(self, ds: Dataset, doc_id: int) -> None:
        for referencia in self.conexao.execute(_SQL_REFERENCIAS, (doc_id,)):
            for linha in self.conexao.execute(_SQL_AUTORES_DA_REFERENCIA,
                                              (referencia["idReference"],)):
                grupo = linha["AuthorReferenceGroup_idAuthorReferenceGroup"]
                if grupo is None:
                    continue
                dados = self._grupo("AuthorReferenceGroup", "idAuthorReferenceGroup", grupo)
                if dados is None or dados[1]:
                    continue
                ds.adiciona_item_ao_documento(doc_id, grupo, dados[0])

    def _unidade_ReferenceSources(self, ds: Dataset, doc_id: int) -> None:
        for referencia in self.conexao.execute(_SQL_REFERENCIAS, (doc_id,)):
            fonte = referencia["ReferenceSource_idReferenceSource"]
            if fonte is None:
                continue
            linha = self.conexao.execute(
                "SELECT ReferenceSourceGroup_idReferenceSourceGroup FROM ReferenceSource "
                "WHERE idReferenceSource = ?;", (fonte,)).fetchone()
            grupo = linha[0] if linha else None
            if grupo is None:
                continue
            dados = self._grupo("ReferenceSourceGroup", "idReferenceSourceGroup", grupo)
            if dados is None or dados[1]:
                continue
            ds.adiciona_item_ao_documento(doc_id, grupo, dados[0])

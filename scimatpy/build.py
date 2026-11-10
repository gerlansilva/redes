"""Constrói um projeto `.redes` a partir de documentos importados.

O arquivo gerado usa o mesmo esquema SQLite que o Bibliomapa lê, de modo que o
resto do fluxo (montagem dos conjuntos, redes, agrupamento, medidas) funciona
sem alteração — mas sem depender de o projeto ter sido criado pelo programa
Java.

A ordem de criação dos agrupamentos é a mesma do importador original, porque
ela define os identificadores dos itens e, com isso, o desempate dos
algoritmos de agrupamento.
"""

from __future__ import annotations

import sqlite3
from collections import OrderedDict
from pathlib import Path

from . import schema
from .dataset import Dataset
from .kb import ProjetoScimat
from .loaders.base import DocumentoFonte
from .references import converte_referencia, nome_do_grupo
from .text_utils import (abreviacao_de, chave, mesmo_plural, normaliza_palavra,
                         palavras_significativas, parece_abreviacao,
                         partes_abreviadas)


class Referencia:
    def __init__(self, ref_id: int, completa: str, bruta: str = "") -> None:
        self.id = ref_id
        self.completa = completa
        self.bruta = bruta or completa
        campos = completa.split(",")
        self.autor = campos[0].strip() if campos else ""
        self.ano = campos[1].strip() if len(campos) > 1 else ""
        self.fonte = campos[2].strip() if len(campos) > 2 else ""
        self.volume = campos[3].strip() if len(campos) > 3 else ""
        self.paginas = campos[4].strip() if len(campos) > 4 else ""


class Item:
    """Palavra, autor, referência ou fonte com sua contagem de documentos."""

    def __init__(self, item_id: int, nome: str) -> None:
        self.id = item_id
        self.nome = nome
        self.documentos: list[int] = []
        self.usos = 0

    @property
    def frequencia(self) -> int:
        return len(self.documentos)




def _converte_referencias(documentos: list[DocumentoFonte]) -> None:
    for documento in documentos:
        if documento.referencias_convertidas:
            continue
        convertidas = []
        for bruta in documento.referencias:
            item = converte_referencia(bruta)
            if item and item not in convertidas:
                convertidas.append(item)
        documento.referencias = convertidas
        documento.referencias_convertidas = True


class Construtor:
    """Recebe documentos e grava o projeto."""

    def __init__(self, documentos: list[DocumentoFonte]) -> None:
        self.documentos = documentos
        self.autores: "OrderedDict[str, Item]" = OrderedDict()
        self.palavras: "OrderedDict[str, Item]" = OrderedDict()
        self.referencias: "OrderedDict[str, Referencia]" = OrderedDict()
        self.autores_ref: "OrderedDict[str, Item]" = OrderedDict()
        self.fontes: "OrderedDict[str, Item]" = OrderedDict()
        self.paises: "OrderedDict[str, int]" = OrderedDict()
        self.afiliacoes: "OrderedDict[str, int]" = OrderedDict()
        self.nomes_completos: dict[str, str] = {}
        self.jornais: "OrderedDict[str, int]" = OrderedDict()
        self.datas: "OrderedDict[tuple[str, str], int]" = OrderedDict()

        self.vinculos_autor: dict[int, list[tuple[int, int]]] = {}
        self.vinculos_pais: dict[int, list[int]] = {}
        self.vinculos_afiliacao: dict[int, list[int]] = {}
        self.vinculos_palavra: dict[tuple[int, int], list[int]] = {}
        self.vinculos_referencia: dict[int, list[int]] = {}
        self.refs_por_autor_ref: dict[int, list[int]] = {}
        self.refs_por_fonte: dict[int, list[int]] = {}

    # ------------------------------------------------------------- importação

    def importa(self) -> None:
        _converte_referencias(self.documentos)

        for indice, documento in enumerate(self.documentos, start=1):
            self._documento(indice, documento)

    def _documento(self, doc_id: int, documento: DocumentoFonte) -> None:
        self.jornais.setdefault(documento.periodico, len(self.jornais) + 1)
        chave_data = (documento.ano, "")
        self.datas.setdefault(chave_data, len(self.datas) + 1)

        self.vinculos_autor[doc_id] = []
        vistos = set()
        for posicao, nome in enumerate(documento.autores, start=1):
            nome = (nome or "").strip()
            if not nome:
                continue
            item = self.autores.get(nome)
            if item is None:
                item = Item(len(self.autores) + 1, nome)
                self.autores[nome] = item
            if doc_id not in item.documentos:
                item.documentos.append(doc_id)
            if item.id in vistos:
                continue
            vistos.add(item.id)
            self.vinculos_autor[doc_id].append((item.id, posicao))

        for posicao, nome in enumerate(documento.autores):
            nome = (nome or "").strip()
            if not nome or nome in self.nomes_completos:
                continue
            completo = (documento.autores_completos[posicao]
                        if posicao < len(documento.autores_completos) else "")
            self.nomes_completos[nome] = (completo or "").strip() or nome

        self.vinculos_afiliacao[doc_id] = []
        for nome in documento.afiliacoes:
            nome = (nome or "").strip()
            if not nome:
                continue
            afiliacao_id = self.afiliacoes.get(nome)
            if afiliacao_id is None:
                afiliacao_id = len(self.afiliacoes) + 1
                self.afiliacoes[nome] = afiliacao_id
            if afiliacao_id not in self.vinculos_afiliacao[doc_id]:
                self.vinculos_afiliacao[doc_id].append(afiliacao_id)

        self.vinculos_pais[doc_id] = []
        for nome in documento.paises:
            nome = (nome or "").strip()
            if not nome:
                continue
            pais_id = self.paises.get(nome)
            if pais_id is None:
                pais_id = len(self.paises) + 1
                self.paises[nome] = pais_id
            if pais_id not in self.vinculos_pais[doc_id]:
                self.vinculos_pais[doc_id].append(pais_id)

        self.vinculos_referencia[doc_id] = []
        for posicao, completa in enumerate(documento.referencias):
            bruta = (documento.referencias_brutas[posicao]
                     if posicao < len(documento.referencias_brutas) else "")
            referencia = self.referencias.get(completa)
            if referencia is None:
                referencia = Referencia(len(self.referencias) + 1, completa,
                                        bruta.strip())
                self.referencias[completa] = referencia

                autor = self.autores_ref.get(referencia.autor)
                if autor is None:
                    autor = Item(len(self.autores_ref) + 1, referencia.autor)
                    self.autores_ref[referencia.autor] = autor
                autor.usos += 1
                self.refs_por_autor_ref.setdefault(autor.id, []).append(referencia.id)

                fonte = self.fontes.get(referencia.fonte)
                if fonte is None:
                    fonte = Item(len(self.fontes) + 1, referencia.fonte)
                    self.fontes[referencia.fonte] = fonte
                fonte.usos += 1
                self.refs_por_fonte.setdefault(fonte.id, []).append(referencia.id)

            if referencia.id not in self.vinculos_referencia[doc_id]:
                self.vinculos_referencia[doc_id].append(referencia.id)

        for tipo, termos in (("autor", documento.palavras_autor),
                             ("fonte", documento.palavras_fonte)):
            for termo in termos:
                nome = normaliza_palavra(termo)
                if not nome:
                    continue
                item = self.palavras.get(nome)
                if item is None:
                    item = Item(len(self.palavras) + 1, nome)
                    self.palavras[nome] = item
                if doc_id not in item.documentos:
                    item.documentos.append(doc_id)
                sinalizadores = self.vinculos_palavra.setdefault((doc_id, item.id), [0, 0, 0])
                sinalizadores[0 if tipo == "autor" else 1] = 1

    # ------------------------------------------------------------- agrupamento

    def agrupa_palavras(self) -> list[tuple[int, str, list[int]]]:
        """Pares (id do grupo, nome, ids das palavras), na ordem do original."""
        restantes = sorted(self.palavras.values(), key=lambda item: item.nome)
        grupos = []

        while restantes:
            base = restantes.pop(0)
            membros = [base]
            i = 0
            while i < len(restantes):
                if mesmo_plural(base.nome, restantes[i].nome):
                    membros.append(restantes.pop(i))
                else:
                    i += 1

            nome = base.nome
            maximo = base.frequencia
            for membro in membros:
                if membro.frequencia > maximo:
                    maximo = membro.frequencia
                    nome = membro.nome
            grupos.append((len(grupos) + 1, nome, [m.id for m in membros]))

        return grupos

    def agrupa_autores(self) -> list[tuple[int, str, list[int]]]:
        por_chave: "OrderedDict[str, list[Item]]" = OrderedDict()
        for autor in self.autores.values():
            por_chave.setdefault(chave(autor.nome), []).append(autor)

        grupos = []
        for membros in por_chave.values():
            representante = membros[0]
            for membro in membros:
                if membro.frequencia > representante.frequencia:
                    representante = membro
            grupos.append((len(grupos) + 1, representante.nome, [m.id for m in membros]))
        return grupos

    def agrupa_referencias(self) -> list[tuple[int, str, int]]:
        usados: set[str] = set()
        grupos = []
        for referencia in self.referencias.values():
            nome = nome_do_grupo(referencia.completa, usados)
            usados.add(nome)
            grupos.append((len(grupos) + 1, nome, referencia.id))
        return grupos

    def agrupa_autores_de_referencia(self) -> list[tuple[int, str, bool, list[int]]]:
        por_chave: "OrderedDict[str, list[Item]]" = OrderedDict()
        for autor in self.autores_ref.values():
            por_chave.setdefault(chave(autor.nome), []).append(autor)

        grupos = []
        for membros in por_chave.values():
            representante = membros[0]
            for membro in membros:
                if (membro.usos > representante.usos
                        or (membro.usos == representante.usos
                            and len(membro.nome) < len(representante.nome))):
                    representante = membro
            grupos.append((len(grupos) + 1, representante.nome,
                           representante.nome.lower() == "sem autor",
                           [m.id for m in membros]))
        return grupos

    def agrupa_fontes(self) -> list[tuple[int, str, bool, list[int]]]:
        por_chave: "OrderedDict[str, list[Item]]" = OrderedDict()
        for fonte in self.fontes.values():
            por_chave.setdefault(chave(fonte.nome), []).append(fonte)

        nome_por_chave = {k: self._representante_fonte(v).nome for k, v in por_chave.items()}
        alvo = self._abreviacoes_sem_ambiguidade(list(por_chave), nome_por_chave)

        grupos: "OrderedDict[str, list[Item]]" = OrderedDict()
        for k, membros in por_chave.items():
            destino = alvo.get(k, k)
            grupos.setdefault(destino, []).extend(membros)

        resultado = []
        for membros in grupos.values():
            representante = self._representante_fonte(membros)
            resultado.append((len(resultado) + 1, representante.nome,
                              representante.nome.lower() == "sem fonte",
                              [m.id for m in membros]))
        return resultado

    @staticmethod
    def _representante_fonte(membros: list[Item]) -> Item:
        escolhido = membros[0]
        for membro in membros:
            abreviado_escolhido = parece_abreviacao(escolhido.nome)
            abreviado_membro = parece_abreviacao(membro.nome)
            if (membro.usos > escolhido.usos
                    or (membro.usos == escolhido.usos and abreviado_escolhido
                        and not abreviado_membro)
                    or (membro.usos == escolhido.usos
                        and abreviado_escolhido == abreviado_membro
                        and len(membro.nome) < len(escolhido.nome))):
                escolhido = membro
        return escolhido

    @staticmethod
    def _abreviacoes_sem_ambiguidade(chaves, nome_por_chave) -> dict[str, str]:
        completas = []
        palavras = {}
        for k in chaves:
            nome = nome_por_chave[k]
            if not parece_abreviacao(nome) and nome.lower() != "sem fonte":
                completas.append(k)
                palavras[k] = palavras_significativas(nome)

        alvo = {}
        for k in chaves:
            partes = partes_abreviadas(nome_por_chave[k])
            if not partes:
                continue
            candidatas = [c for c in completas if abreviacao_de(partes, palavras[c])]
            if len(candidatas) == 1:
                alvo[k] = candidatas[0]
        return alvo

    # ------------------------------------------------------------- gravação

    def grava(self, destino: str | Path, periodos: list[tuple[str, int, int]]) -> None:
        caminho = Path(destino)
        if caminho.exists():
            caminho.unlink()
        caminho.parent.mkdir(parents=True, exist_ok=True)

        conexao = sqlite3.connect(str(caminho))
        schema.cria(conexao)

        grupos_palavra = self.agrupa_palavras()
        grupos_autor = self.agrupa_autores()
        grupos_referencia = self.agrupa_referencias()
        grupos_autor_ref = self.agrupa_autores_de_referencia()
        grupos_fonte = self.agrupa_fontes()

        self._grava_nucleo(conexao)
        self._grava_grupos(conexao, "WordGroup", "idWordGroup", "Word",
                           "idWord", "WordGroup_idWordGroup", grupos_palavra)
        self._grava_grupos(conexao, "AuthorGroup", "idAuthorGroup", "Author",
                           "idAuthor", "AuthorGroup_idAuthorGroup", grupos_autor)
        self._grava_referencias(conexao, grupos_referencia,
                               grupos_autor_ref, grupos_fonte)
        self._grava_periodos(conexao, periodos)
        schema.marca_versao(conexao)

        conexao.commit()
        conexao.close()

    def _grava_nucleo(self, conexao: sqlite3.Connection) -> None:
        for (ano, data), data_id in self.datas.items():
            conexao.execute(
                "INSERT INTO PublishDate(idPublishDate, year, date) VALUES (?, ?, ?)",
                (data_id, ano, data))

        for fonte, fonte_id in self.jornais.items():
            conexao.execute(
                "INSERT INTO Journal(idJournal, source) VALUES (?, ?)",
                (fonte_id, fonte))

        # O documento entra sem data nem periódico: os gatilhos de atualização do
        # esquema só então calculam os contadores e copiam o ano.
        for indice, documento in enumerate(self.documentos, start=1):
            conexao.execute(
                "INSERT INTO Document(idDocument, title, type, docAbstract, doi, "
                "citationsCount, authors, PublishDate_idPublishDate, Journal_idJournal) "
                "VALUES (?,?,?,?,?,?,?,NULL,NULL)",
                (indice, documento.titulo, documento.tipo, documento.resumo,
                 documento.doi, documento.citacoes, ", ".join(documento.autores)))
            conexao.execute(
                "UPDATE Document SET PublishDate_idPublishDate = ?, Journal_idJournal = ? "
                "WHERE idDocument = ?",
                (self.datas[(documento.ano, "")], self.jornais[documento.periodico],
                 indice))

        for nome, autor in self.autores.items():
            conexao.execute(
                "INSERT INTO Author(idAuthor, authorName, fullAuthorName, "
                "AuthorGroup_idAuthorGroup) VALUES (?, ?, ?, NULL)",
                (autor.id, nome, self.nomes_completos.get(nome, nome)))
        for doc_id, vinculos in self.vinculos_autor.items():
            conexao.executemany(
                "INSERT INTO Document_Author(Author_idAuthor, Document_idDocument, position) "
                "VALUES (?, ?, ?)",
                [(autor_id, doc_id, posicao) for autor_id, posicao in vinculos])

        for nome, afiliacao_id in self.afiliacoes.items():
            conexao.execute(
                "INSERT INTO Affiliation(idAffiliation, fullAffiliation, "
                "affiliation_documentsCount, affiliation_authorsCount) "
                "VALUES (?, ?, 0, 0)", (afiliacao_id, nome))
        conexao.executemany(
            "INSERT INTO Document_Affiliation(Affiliation_idAffiliation, "
            "Document_idDocument) VALUES (?, ?)",
            [(afiliacao_id, doc_id)
             for doc_id, afiliacoes in self.vinculos_afiliacao.items()
             for afiliacao_id in afiliacoes])

        for nome, pais_id in self.paises.items():
            conexao.execute(
                "INSERT INTO CountryGroup(idCountryGroup, groupName, stopGroup) "
                "VALUES (?, ?, 0)", (pais_id, nome))
            conexao.execute(
                "INSERT INTO Country(idCountry, countryName, "
                "CountryGroup_idCountryGroup) VALUES (?, ?, ?)",
                (pais_id, nome, pais_id))
        conexao.executemany(
            "INSERT INTO Document_Country(Country_idCountry, Document_idDocument) "
            "VALUES (?, ?)",
            [(pais_id, doc_id)
             for doc_id, paises in self.vinculos_pais.items()
             for pais_id in paises])

        for nome, palavra in self.palavras.items():
            conexao.execute(
                "INSERT INTO Word(idWord, wordName, WordGroup_idWordGroup) "
                "VALUES (?, ?, NULL)", (palavra.id, nome))
        conexao.executemany(
            "INSERT INTO Document_Word(Document_idDocument, Word_idWord, "
             "isAuthorWord, isSourceWord, isAddedWord) VALUES (?, ?, ?, ?, ?)",
            [(doc_id, palavra_id, a, f, 0)
             for (doc_id, palavra_id), (a, f, _) in self.vinculos_palavra.items()])

        for referencia in self.referencias.values():
            conexao.execute(
                "INSERT INTO Reference(idReference, fullReference, volume, page, "
                "year, doi, ReferenceGroup_idReferenceGroup, "
                "ReferenceSource_idReferenceSource) VALUES (?,?,?,?,?,?,NULL,NULL)",
                (referencia.id, referencia.completa, referencia.volume,
                 referencia.paginas, referencia.ano, ""))
        conexao.executemany(
            "INSERT INTO ReferenceRaw(Reference_idReference, rawReference) "
            "VALUES (?, ?)",
            [(referencia.id, referencia.bruta) for referencia in self.referencias.values()])

        for doc_id, refs in self.vinculos_referencia.items():
            conexao.executemany(
                "INSERT INTO Document_Reference(Document_idDocument, "
                "Reference_idReference) VALUES (?, ?)",
                [(doc_id, ref_id) for ref_id in refs])

        conexao.executemany(
            "INSERT INTO DocumentMetadata(Document_idDocument, metaKey, metaValue) "
            "VALUES (?, ?, ?)",
            [(indice, chave, valor)
             for indice, documento in enumerate(self.documentos, start=1)
             for chave, valor in documento.metadados.items()])

        for nome, autor in self.autores_ref.items():
            conexao.execute(
                "INSERT INTO AuthorReference(idAuthorReference, authorName, "
                "AuthorReferenceGroup_idAuthorReferenceGroup) VALUES (?, ?, NULL)",
                (autor.id, nome))
        for autor_id, refs in self.refs_por_autor_ref.items():
            conexao.executemany(
                "INSERT INTO AuthorReference_Reference(AuthorReference_idAuthorReference, "
             "Reference_idReference, position) VALUES (?, ?, ?)",
                [(autor_id, ref_id, 1) for ref_id in refs])

        for nome, fonte in self.fontes.items():
            conexao.execute(
                "INSERT INTO ReferenceSource(idReferenceSource, source, "
                "ReferenceSourceGroup_idReferenceSourceGroup) VALUES (?, ?, NULL)",
                (fonte.id, nome))
        for fonte_id, refs in self.refs_por_fonte.items():
            conexao.executemany(
                "UPDATE Reference SET ReferenceSource_idReferenceSource = ? "
                "WHERE idReference = ?", [(fonte_id, ref_id) for ref_id in refs])

    @staticmethod
    def _grava_grupos(conexao, tabela_grupo, coluna_grupo, tabela_item,
                      coluna_item, coluna_fk, grupos) -> None:
        for grupo_id, nome, membros in grupos:
            conexao.execute(
                f"INSERT INTO {tabela_grupo}({coluna_grupo}, groupName, stopGroup) "
                f"VALUES (?, ?, 0)", (grupo_id, nome))
            conexao.executemany(
                f"UPDATE {tabela_item} SET {coluna_fk} = ? WHERE {coluna_item} = ?",
                [(grupo_id, item_id) for item_id in membros])

    @staticmethod
    def _grava_referencias(conexao, grupos_referencia, grupos_autor_ref,
                           grupos_fonte) -> None:
        for grupo_id, nome, referencia_id in grupos_referencia:
            conexao.execute(
                "INSERT INTO ReferenceGroup(idReferenceGroup, groupName, stopGroup) "
                "VALUES (?, ?, 0)", (grupo_id, nome))
            conexao.execute(
                "UPDATE Reference SET ReferenceGroup_idReferenceGroup = ? "
                "WHERE idReference = ?", (grupo_id, referencia_id))

        for grupo_id, nome, parada, membros in grupos_autor_ref:
            conexao.execute(
                "INSERT INTO AuthorReferenceGroup(idAuthorReferenceGroup, groupName, "
                "stopGroup) VALUES (?, ?, ?)", (grupo_id, nome, int(parada)))
            conexao.executemany(
                "UPDATE AuthorReference SET AuthorReferenceGroup_idAuthorReferenceGroup = ? "
                "WHERE idAuthorReference = ?", [(grupo_id, m) for m in membros])

        for grupo_id, nome, parada, membros in grupos_fonte:
            conexao.execute(
                "INSERT INTO ReferenceSourceGroup(idReferenceSourceGroup, groupName, "
                "stopGroup) VALUES (?, ?, ?)", (grupo_id, nome, int(parada)))
            conexao.executemany(
                "UPDATE ReferenceSource SET ReferenceSourceGroup_idReferenceSourceGroup = ? "
                "WHERE idReferenceSource = ?", [(grupo_id, m) for m in membros])

    def _grava_periodos(self, conexao, periodos) -> None:
        datas = list(self.datas.items())
        for posicao, (nome, inicio, fim) in enumerate(periodos, start=1):
            conexao.execute("INSERT INTO Period(idPeriod, name, position) VALUES (?, ?, ?)",
                            (posicao, nome, posicao))
            for (ano, _), data_id in datas:
                try:
                    valor = int(str(ano).strip()[:4])
                except ValueError:
                    continue
                if inicio <= valor <= fim:
                    conexao.execute("INSERT INTO PublishDate_Period(PublishDate_idPublishDate, "
                                     "Period_idPeriod) VALUES (?, ?)",
                                    (data_id, posicao))


def constroi(documentos: list[DocumentoFonte], destino: str | Path,
             periodos: list[tuple[str, int, int]] | tuple[int, int] | None = None) -> dict:
    """Importa os documentos e grava o projeto; devolve um resumo."""
    if periodos is None:
        periodos = []
    if isinstance(periodos, tuple):
        periodos = [(f"{periodos[0]}\u2013{periodos[1]}", periodos[0], periodos[1])]
    if not periodos:
        # Sem faixas informadas: usa o intervalo real de anos do corpus.
        anos = [int(documento.ano) for documento in documentos
                if (documento.ano or "").isdigit()]
        if anos:
            periodos = [(f"{min(anos)}\u2013{max(anos)}", min(anos), max(anos))]
        else:
            periodos = [("0\u20139999", 0, 9999)]

    construtor = Construtor(documentos)
    construtor.importa()
    construtor.grava(destino, periodos)

    with ProjetoScimat(destino) as projeto:
        resumo = {
            "documentos": len(documentos),
            "palavras": len(construtor.palavras),
            "grupos_palavra": conectar_contagem(destino, "WordGroup", "idWordGroup"),
            "autores": len(construtor.autores),
            "grupos_autor": conectar_contagem(destino, "AuthorGroup", "idAuthorGroup"),
            "referencias": len(construtor.referencias),
            "grupos_referencia": conectar_contagem(destino, "ReferenceGroup", "idReferenceGroup"),
            "autores_referencia": len(construtor.autores_ref),
            "grupos_autor_referencia": conectar_contagem(
                destino, "AuthorReferenceGroup", "idAuthorReferenceGroup"),
            "fontes": len(construtor.fontes),
            "grupos_fonte": conectar_contagem(
                destino, "ReferenceSourceGroup", "idReferenceSourceGroup"),
            "paises": len(construtor.paises),
            "afiliacoes": len(construtor.afiliacoes),
            "periodos": [p.nome for p in projeto.periodos()],
            "unidades": {},
        }

        for unidade in ("Words", "Authors", "References", "AuthorsReference",
                        "ReferenceSources", "Countries"):
            periodo = projeto.periodos()[0]
            conjunto = projeto.dataset(unidade, periodo.id)
            resumo["unidades"][unidade] = {
                "itens": conjunto.quantidade_itens(),
                "documentos": conjunto.quantidade_documentos(),
            }
    return resumo


def conectar_contagem(caminho, tabela: str, coluna: str) -> int:
    conexao = sqlite3.connect(str(caminho))
    try:
        return conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
    finally:
        conexao.close()

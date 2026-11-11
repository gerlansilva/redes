"""Redes não orientadas do SciMAT.

`Rede` espelha `UndirectNetworkMatrix`: matriz simétrica em árvore ordenada,
pares lidos em ordem crescente (linha, coluna) e remoção de aresta nos dois
sentidos. Essa ordem é o critério de desempate de `CentersSimples`.
"""

from __future__ import annotations

import itertools

from .dataset import Dataset


class Rede:
    """Matriz de similaridade simétrica com nós ordenados por identificador."""

    def __init__(self, nos) -> None:
        self.nos: list[int] = sorted(nos)
        self._conjunto = set(self.nos)
        self.adjacencia: dict[int, dict[int, float]] = {no: {} for no in self.nos}

    # ------------------------------------------------------------------ arestas

    def adiciona_aresta(self, a: int, b: int, valor: float) -> bool:
        if a not in self._conjunto or b not in self._conjunto:
            return False
        self.adjacencia[a][b] = valor
        self.adjacencia[b][a] = valor
        return True

    def remove_aresta(self, a: int, b: int) -> bool:
        if a not in self._conjunto or b not in self._conjunto:
            return False
        self.adjacencia[a].pop(b, None)
        self.adjacencia[b].pop(a, None)
        return True

    def valor(self, a: int, b: int) -> float:
        return self.adjacencia.get(a, {}).get(b, 0.0)

    def contem_aresta(self, a: int, b: int) -> bool:
        return b in self.adjacencia.get(a, {})

    def vizinhos(self, no: int) -> list[int]:
        return sorted(self.adjacencia.get(no, {}))

    def grau(self, no: int) -> int:
        return len(self.adjacencia.get(no, {}))

    # ------------------------------------------------------------------ listas

    def arestas(self) -> list[tuple[int, int, float]]:
        """Pares do triângulo superior em ordem de linha e coluna (a < b)."""
        pares = []
        for a in self.nos:
            for b in sorted(self.adjacencia[a]):
                if b > a:
                    pares.append((a, b, self.adjacencia[a][b]))
        return pares

    def quantidade_nos(self) -> int:
        return len(self.nos)

    def quantidade_arestas(self) -> int:
        return sum(len(v) for v in self.adjacencia.values()) // 2

    # -------------------------------------------------------------- subconjuntos

    def pares_internos(self, nos) -> list[tuple[int, int, float]]:
        """Arestas com as duas pontas no conjunto dado."""
        conjunto = set(nos)
        pares = []
        for a in sorted(conjunto):
            for b in sorted(self.adjacencia.get(a, {})):
                if b > a and b in conjunto:
                    pares.append((a, b, self.adjacencia[a][b]))
        return pares

    def pares_externos(self, nos) -> list[tuple[int, int, float]]:
        """Arestas com uma ponta no conjunto e outra fora dele."""
        conjunto = set(nos)
        pares = []
        for a in sorted(conjunto):
            for b in sorted(self.adjacencia.get(a, {})):
                if b not in conjunto:
                    pares.append((a, b, self.adjacencia[a][b]))
        return pares

    def pares_entre(self, origem, destino) -> list[tuple[int, int, float]]:
        pares = []
        for a in origem:
            for b in destino:
                if a != b and self.contem_aresta(a, b):
                    pares.append((a, b, self.adjacencia[a][b]))
        return pares

    def para_networkx(self):
        """Converte para `networkx.Graph`, útil para layouts e diagnósticos."""
        import networkx as nx

        grafo = nx.Graph()
        grafo.add_nodes_from(self.nos)
        for a, b, valor in self.arestas():
            grafo.add_edge(a, b, weight=valor)
        return grafo

    def subgrafo(self, nos):
        """Subgrafo induzido, também em `networkx.Graph`."""
        import networkx as nx

        conjunto = set(nos)
        grafo = nx.Graph()
        grafo.add_nodes_from(conjunto)
        for a, b, valor in self.pares_internos(conjunto):
            grafo.add_edge(a, b, weight=valor)
        return grafo

    def componentes(self) -> list[list[int]]:
        """Componentes conexos (nó isolado conta como componente de um nó)."""
        visto: set[int] = set()
        saida: list[list[int]] = []
        for inicio in self.nos:
            if inicio in visto:
                continue
            visto.add(inicio)
            pilha, membros = [inicio], []
            while pilha:
                no = pilha.pop()
                membros.append(no)
                for vizinho in self.adjacencia[no]:
                    if vizinho not in visto:
                        visto.add(vizinho)
                        pilha.append(vizinho)
            saida.append(sorted(membros))
        return saida

    def filtra_por_valor(self, minimo: float) -> None:
        for a, b, valor in self.arestas():
            if valor < minimo:
                self.remove_aresta(a, b)


# --------------------------------------------------------------------- construtores


def rede_coocorrencia(dataset: Dataset) -> Rede:
    """Co-ocorrência de itens por documento."""
    rede = Rede(dataset.lista_itens())

    for doc_id in dataset.lista_documentos():
        itens = dataset.itens_do_documento(doc_id)
        for a, b in itertools.combinations(itens, 2):
            rede.adiciona_aresta(a, b, rede.valor(a, b) + 1)

    return rede


def rede_acoplamento(dataset: Dataset) -> Rede:
    """Acoplamento bibliográfico: nós são documentos, peso = itens em comum."""
    documentos = dataset.lista_documentos()
    rede = Rede(documentos)

    for i, doc_a in enumerate(documentos):
        itens_a = set(dataset.itens_do_documento(doc_a))
        for doc_b in documentos[i + 1:]:
            comuns = itens_a & set(dataset.itens_do_documento(doc_b))
            rede.adiciona_aresta(doc_a, doc_b, float(len(comuns)))

    return rede


def rede_acoplamento_agregado(agregado, dataset: Dataset) -> Rede:
    """Acoplamento agregado: peso = itens de baixo nível em comum.

    O original não compara documentos compartilhados: reúne todos os itens de
    baixo nível dos documentos de cada item de alto nível e conta a interseção.
    Por isso, num conjunto de autores, quase todo par tem peso positivo — o
    autor mais frequente aparece nos documentos de todos os demais.
    """
    altos = agregado.lista_alto_nivel()
    rede = Rede(altos)

    itens_por_alto = {}
    for alto in altos:
        conjunto = set()
        for doc_id in agregado.documentos_do_alto_nivel(alto):
            conjunto |= set(dataset.itens_do_documento(doc_id))
        itens_por_alto[alto] = conjunto

    for i, a in enumerate(altos):
        for b in altos[i + 1:]:
            comuns = itens_por_alto[a] & itens_por_alto[b]
            rede.adiciona_aresta(a, b, float(len(comuns)))

    return rede

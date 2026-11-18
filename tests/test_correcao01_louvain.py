from redes.clustering import _junta_grupos_pequenos


def _grafo(arestas, n):
    g = {i: {} for i in range(n)}
    for a, b, p in arestas:
        g[a][b] = p
        g[b][a] = p
    return g


def test_junta_grupos_pequenos_nao_estoura_indice():
    # grupo unitário no início: o índice do vizinho muda após a remoção
    grafo = _grafo([(0, 3, 1.0), (1, 3, 1.0), (2, 3, 1.0), (3, 4, 1.0), (4, 5, 1.0)], 6)
    grupos = [[0], [1], [2], [3, 4, 5]]
    out = _junta_grupos_pequenos(grupos, grafo, 3)
    assert sorted(n for g in out for n in g) == [0, 1, 2, 3, 4, 5]
    assert all(g for g in out)


def test_listas_vazias():
    assert _junta_grupos_pequenos([], {}, 3) == []
    assert _junta_grupos_pequenos([[], []], {}, 3) == []
    assert _junta_grupos_pequenos([[0]], {0: {}}, 3) == [[0]]
